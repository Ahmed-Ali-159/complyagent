"""Parse the official GDPR PDF (Regulation (EU) 2016/679) into Recitals and Articles text.

Pipeline:
  Stage 0 - extract text page by page (pdfplumber)
  Stage 1 - strip header line from each page (odd/even page header variants)
  Stage 1c - join all cleaned pages into one continuous string
  Stage 2 - split the joined string into raw_recitals_text / raw_articles_text
  Stage 2b - remove footnotes from each section using sequence-based rules

Run from repo root:
    uv run python scripts/parse_gdpr_pdf.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

PDF_PATH = REPO_ROOT / "data" / "raw" / "gdpr_official_2016_679.pdf"
OUT_DIR = REPO_ROOT / "data" / "processed"

# --- header patterns -------------------------------------------------
# Odd pages:  "4.5.2016 EN Official Journal of the European Union L 119/1"
# Even pages: "L 119/35 EN Official Journal of the European Union 4.5.2016"
HEADER_PATTERN = re.compile(
    r"^(?:"
    r"\d{1,2}\.\d{1,2}\.\d{4}\s+EN\s+Official Journal of the European Union\s+L\s*119/\d+"
    r"|"
    r"L\s*119/\d+\s+EN\s+Official Journal of the European Union\s+\d{1,2}\.\d{1,2}\.\d{4}"
    r")\s*\n?",
    re.MULTILINE,
)

# --- macro-section anchors -------------------------------------------
RECITALS_START_MARKER = "Whereas:"
ARTICLES_START_MARKER = "HAVE ADOPTED THIS REGULATION:"
DOCUMENT_END_MARKER = "This Regulation shall be binding in its entirety"


# Stage 0 - extract pages
def extract_pages(pdf_path: Path) -> list[str]:
    """Extract plain text for every page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


# the page-1 special case
def strip_page1_footnote_4(page1_text: str) -> str:
    """Page 1's footnote (4) numerically collides with recital (4) (both are '(4)'),
    so the general sequence rule would wrongly accept it as the next recital.
    Footnotes (1)-(3) are already correctly rejected by the sequence rule since
    their numbers don't match last_recital+1. We only need to remove (4) here.
    """
    lines = page1_text.split("\n")
    cleaned = [line for line in lines if not line.strip().startswith("(4) Directive 95/46/EC")]
    return "\n".join(cleaned)


# Stage 1 - strip headers
def strip_header(page_text: str) -> str:
    """Remove the repeating Official Journal header line from one page's text."""
    return HEADER_PATTERN.sub("", page_text, count=1).strip()


# Stage 1c - join pages
def join_pages(cleaned_pages: list[str]) -> str:
    """Join cleaned per-page text into one continuous string."""
    return "\n".join(p for p in cleaned_pages if p)


# Stage 2 — split_into_sections 
def split_into_sections(full_text: str) -> tuple[str, str]:
    """Split the joined document text into (raw_recitals_text, raw_articles_text)."""
    recitals_start = full_text.find(RECITALS_START_MARKER)
    articles_start = full_text.find(ARTICLES_START_MARKER)
    document_end = full_text.find(DOCUMENT_END_MARKER)

    if recitals_start == -1:
        raise RuntimeError(f"Could not find recitals start marker: {RECITALS_START_MARKER!r}")
    if articles_start == -1:
        raise RuntimeError(f"Could not find articles start marker: {ARTICLES_START_MARKER!r}")
    if document_end == -1:
        raise RuntimeError(f"Could not find document end marker: {DOCUMENT_END_MARKER!r}")

    raw_recitals_text = full_text[recitals_start + len(RECITALS_START_MARKER):articles_start]
    raw_articles_text = full_text[articles_start + len(ARTICLES_START_MARKER):document_end]
    return raw_recitals_text.strip(), raw_articles_text.strip()


# Stage 2b — remove footnotes from Recitals
def remove_recital_footnotes(recitals_text: str) -> str:
    """Drop footnote lines from the Recitals section using sequence-monotonicity.

    Walk line by line. A line starting with '(N)' is a real recital boundary only if
    N == last_accepted_recital + 1. Otherwise it's a footnote line (footnotes number
    independently and don't follow the recital sequence) - drop it. Lines with no
    leading '(N)' marker are always kept (continuation text of the current recital).
    """
    lines = recitals_text.split("\n")
    cleaned_lines = []
    last_recital_number = 0

    for line in lines:
        stripped = line.strip()
        match = re.match(r"^\((\d{1,3})\)", stripped)

        if match:
            n = int(match.group(1))
            if n == last_recital_number + 1:
                last_recital_number = n
                cleaned_lines.append(line)
            else:
                continue  # footnote line - drop
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# Stage 2c — remove footnotes from Articles
def remove_article_footnotes(articles_text: str) -> str:
    """Drop footnote lines from the Articles section.

    Real Article structure never starts a line with '(<digits>)' EXCEPT Article 4
    ('Definitions'), which numbers its 26 definitions as (1), (2), (3)... instead of
    the '1.', '2.', '3.' format every other article uses. We must not strip those.

    Strategy: cut the text into three pieces - everything before Article 4, Article 4
    itself, and everything from Article 5 onward. Only the first and third pieces get
    the bare-digit-paren footnote rule applied; Article 4's text passes through as-is.
    """
    article_4_match = re.search(r"^Article 4\s*$", articles_text, re.MULTILINE)
    article_5_match = re.search(r"^Article 5\s*$", articles_text, re.MULTILINE)

    if article_4_match is None or article_5_match is None:
        # Structure not found - fall back to applying the rule to everything.
        return _strip_bare_digit_parens(articles_text)

    before_article_4 = articles_text[:article_4_match.start()]
    article_4_text = articles_text[article_4_match.start():article_5_match.start()]
    from_article_5_onward = articles_text[article_5_match.start():]

    cleaned_before = _strip_bare_digit_parens(before_article_4)
    cleaned_after = _strip_bare_digit_parens(from_article_5_onward)

    return cleaned_before + article_4_text + cleaned_after


def _strip_bare_digit_parens(text: str) -> str:
    """Drop any line starting with '(<digits>)' - the footnote pattern."""
    lines = text.split("\n")
    return "\n".join(
        line for line in lines
        if not re.match(r"^\(\d{1,3}\)", line.strip())
    )


def main() -> int:
    print(f"Opening {PDF_PATH} ...")
    raw_pages = extract_pages(PDF_PATH)
    print(f"Extracted {len(raw_pages)} pages.")

    print("Stripping page-1-specific footnote block ...")
    raw_pages[0] = strip_page1_footnote_4(raw_pages[0])

    print("Stripping headers from each page ...")
    cleaned_pages = [strip_header(p) for p in raw_pages]

    print("Joining pages into one continuous text stream ...")
    full_text = join_pages(cleaned_pages)
    print(f"Joined text length: {len(full_text):,} characters")

    print("Splitting into Recitals / Articles ...")
    raw_recitals_text, raw_articles_text = split_into_sections(full_text)
    print(f"Recitals text length (before footnote removal): {len(raw_recitals_text):,} characters")
    print(f"Articles text length (before footnote removal): {len(raw_articles_text):,} characters")

    print("Removing footnotes ...")
    raw_recitals_text = remove_recital_footnotes(raw_recitals_text)
    raw_articles_text = remove_article_footnotes(raw_articles_text)
    print(f"Recitals text length (after footnote removal): {len(raw_recitals_text):,} characters")
    print(f"Articles text length (after footnote removal): {len(raw_articles_text):,} characters")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "raw_recitals_text.txt").write_text(raw_recitals_text, encoding="utf-8")
    (OUT_DIR / "raw_articles_text.txt").write_text(raw_articles_text, encoding="utf-8")
    print(f"\nWrote raw_recitals_text.txt and raw_articles_text.txt to {OUT_DIR}")

    print("\n--- First 300 chars of raw_recitals_text ---")
    print(raw_recitals_text[:300])
    print("\n--- First 300 chars of raw_articles_text ---")
    print(raw_articles_text[:300])
    print("\n--- Last 300 chars of raw_articles_text ---")
    print(raw_articles_text[-300:])

    return 0


if __name__ == "__main__":
    sys.exit(main())