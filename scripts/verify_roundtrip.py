"""Round-trip validation (Defense #3): word-coverage check between raw article text
and the chunks produced from it.

Run from repo root:
    uv run python scripts/verify_roundtrip.py

This does NOT check exact reconstruction (impossible by design - lead-in text is
intentionally duplicated across sub-point chunks). It checks that every word
appearing in each article's raw text appears at least as many times across that
article's chunks - catching genuine content loss without false-flagging the
intentional duplication.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTICLES_TEXT_PATH = REPO_ROOT / "data" / "processed" / "raw_articles_text.txt"
CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.json"

ARTICLE_HEADING_PATTERN = re.compile(r"^Article (\d{1,3})\s*$", re.MULTILINE)
CHAPTER_LINE_PATTERN = re.compile(r"^CHAPTER\s+[IVXLCDM]+\s*$", re.MULTILINE)
SECTION_LINE_PATTERN = re.compile(r"^Section\s+\d+\s*$", re.MULTILINE)


def strip_structural_lines(article_span: str) -> str:
    """Remove lines that are structural markers, not actual regulation content:
    the 'Article N' heading line itself, the article's title line (the line right
    after the heading), and any Chapter/Section heading lines that fell inside this
    span. Paragraph/sub-point markers ('1.', '(a)') are left as-is since they're
    stripped naturally by normalize_words (which only keeps alphanumeric tokens,
    so '1.' contributes '1' - we accept this minor noise rather than trying to
    perfectly distinguish marker digits from content digits).
    """
    lines = article_span.split("\n")
    if len(lines) >= 2 and ARTICLE_HEADING_PATTERN.match(lines[0].strip() + "\n"):
        lines = lines[2:]
    cleaned = "\n".join(lines)
    cleaned = CHAPTER_LINE_PATTERN.sub("", cleaned)
    cleaned = SECTION_LINE_PATTERN.sub("", cleaned)
    return cleaned


def normalize_words(text: str) -> Counter:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return Counter(words)


def split_articles_text_by_number(full_text: str) -> dict[int, str]:
    """Split the full Articles text into per-article spans, keyed by article number."""
    matches = list(ARTICLE_HEADING_PATTERN.finditer(full_text))
    spans: dict[int, str] = {}
    for i, m in enumerate(matches):
        article_num = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        spans[article_num] = full_text[start:end]
    return spans


def main() -> int:
    full_text = ARTICLES_TEXT_PATH.read_text(encoding="utf-8")
    article_spans = split_articles_text_by_number(full_text)

    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    article_chunks = [c for c in chunks if c["source_type"] == "article"]

    chunks_by_article: dict[int, list[str]] = defaultdict(list)
    for c in article_chunks:
        chunks_by_article[c["article_number"]].append(c["text"])

    problems = []
    for article_num, raw_span in sorted(article_spans.items()):
        cleaned_span = strip_structural_lines(raw_span)
        raw_counts = normalize_words(cleaned_span)
        chunk_counts = Counter()
        for t in chunks_by_article.get(article_num, []):
            chunk_counts.update(normalize_words(t))

        missing = Counter()
        for word, raw_count in raw_counts.items():
            chunk_count = chunk_counts.get(word, 0)
            if chunk_count < raw_count:
                missing[word] = raw_count - chunk_count

        # Filter out single-occurrence misses of very short/common words - these
        # are usually structural artifacts (e.g. the word "Article" itself appearing
        # in a heading we don't carry into chunk text) rather than real content loss.
        # We keep anything missing 2+ times, OR any missing word 4+ letters long,
        # as a genuine signal worth a human look.
        significant_missing = {
            w: n for w, n in missing.items() if n >= 2 or len(w) >= 4
        }

        if significant_missing:
            problems.append((article_num, significant_missing))

    print(f"Checked {len(article_spans)} articles.")
    if not problems:
        print("✅ No significant word-coverage gaps found - no evidence of dropped content.")
    else:
        print(f"⚠️  {len(problems)} article(s) with possible dropped content:")
        for article_num, missing in problems:
            print(f"  Article {article_num}: missing {missing}")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())