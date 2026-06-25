"""Spot-check markdown generator (Defense #4): dump specific important articles'
full chunk breakdown into a readable markdown file for manual visual review.

Run from repo root:
    uv run python scripts/generate_spotcheck.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.json"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "spotcheck.md"

# Articles chosen for their structural variety and real-world relevance to privacy
# policy audits:
#   4  - definitions ((N) numbering, nested sub-points - our trickiest case)
#   5  - core principles (flagship example, lead-in repeated across sub-points)
#   6  - lawful basis (heavily cited in real audits)
#   13 - info to be provided (long, cross-page in the source PDF, many sub-points)
#   17 - right to erasure ("right to be forgotten" - famous provision)
#   32 - security of processing (commonly cited in breach-related findings)
#   50 - paragraph-less sub-points (the edge case we found and fixed)
TARGET_ARTICLES = [4, 5, 6, 13, 17, 32, 50]

# A handful of recitals worth a glance too - 26 is the anonymization/pseudonymisation
# one we discussed early on as a reason to include recitals at all.
TARGET_RECITALS = [1, 26, 173]

def article_chunk_sort_key(chunk: dict) -> tuple[int, str]:
    """Sort by (paragraph, point) numerically, not by chunk_id string (which sorts
    '4-10' before '4-2' lexicographically - wrong for display purposes)."""
    paragraph = chunk.get("paragraph")
    point = chunk.get("point")
    paragraph_key = paragraph if paragraph is not None else -1
    point_key = point if point is not None else ""
    return (paragraph_key, point_key)


def format_article_section(article_num: int, chunks: list[dict]) -> str:
    lines = [f"## Article {article_num}"]
    if chunks:
        title = chunks[0].get("article_title") or "(no title)"
        chapter = chunks[0].get("chapter") or "(no chapter)"
        lines.append(f"*Title: {title}*  ")
        lines.append(f"*Chapter: {chapter}*  ")
        lines.append(f"*Chunk count: {len(chunks)}*")
        lines.append("")
    else:
        lines.append("**NO CHUNKS FOUND FOR THIS ARTICLE**")
        lines.append("")

    for c in sorted(chunks, key=article_chunk_sort_key):
        lines.append(f"**`{c['chunk_id']}`**")
        lines.append("")
        lines.append(c["text"])
        lines.append("")

    return "\n".join(lines)


def format_recital_section(recital_num: int, chunk: dict | None) -> str:
    lines = [f"## Recital {recital_num}"]
    if chunk is None:
        lines.append("**NO CHUNK FOUND FOR THIS RECITAL**")
        lines.append("")
        return "\n".join(lines)
    lines.append(f"**`{chunk['chunk_id']}`**")
    lines.append("")
    lines.append(chunk["text"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))

    article_chunks_by_num: dict[int, list[dict]] = defaultdict(list)
    recital_chunks_by_num: dict[int, dict] = {}

    for c in chunks:
        if c["source_type"] == "article":
            article_chunks_by_num[c["article_number"]].append(c)
        else:
            recital_chunks_by_num[c["recital_number"]] = c

    sections = [
        "# ComplyAgent - Chunk Spot-Check",
        "",
        "Manual review file for a hand-picked set of articles and recitals, chosen for",
        "structural variety and real-world relevance to privacy policy audits.",
        "",
        "Read through each section below and confirm: complete sentences, no truncated",
        "lead-ins, no garbled sub-points, no leftover footnote text, no header/page artifacts.",
        "",
        "---",
        "",
        "# Articles",
        "",
    ]

    for article_num in TARGET_ARTICLES:
        sections.append(format_article_section(article_num, article_chunks_by_num.get(article_num, [])))
        sections.append("---")
        sections.append("")

    sections.append("# Recitals")
    sections.append("")
    for recital_num in TARGET_RECITALS:
        sections.append(format_recital_section(recital_num, recital_chunks_by_num.get(recital_num)))
        sections.append("---")
        sections.append("")

    output = "\n".join(sections)
    OUTPUT_PATH.write_text(output, encoding="utf-8")

    total_articles_found = sum(1 for n in TARGET_ARTICLES if article_chunks_by_num.get(n))
    total_recitals_found = sum(1 for n in TARGET_RECITALS if n in recital_chunks_by_num)
    print(f"Wrote spot-check file to {OUTPUT_PATH}")
    print(f"Articles included: {total_articles_found}/{len(TARGET_ARTICLES)}")
    print(f"Recitals included: {total_recitals_found}/{len(TARGET_RECITALS)}")

    missing_articles = [n for n in TARGET_ARTICLES if not article_chunks_by_num.get(n)]
    missing_recitals = [n for n in TARGET_RECITALS if n not in recital_chunks_by_num]
    if missing_articles:
        print(f"WARNING: no chunks found for articles: {missing_articles}")
    if missing_recitals:
        print(f"WARNING: no chunks found for recitals: {missing_recitals}")

    return 1 if (missing_articles or missing_recitals) else 0


if __name__ == "__main__":
    sys.exit(main())