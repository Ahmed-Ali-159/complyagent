"""One-off diagnostic: print full text of pages containing Article 5 and Article 13.

Run from repo root:
    uv run python scripts/inspect_pdf_articles.py
"""
import re

import pdfplumber

PDF_PATH = "data/raw/gdpr_official_2016_679.pdf"

# Anchored: "Article 5" must appear as its own heading line, not inside "Article 5X".
ARTICLE_5_PATTERN = re.compile(r"^Article 5\s*$", re.MULTILINE)
ARTICLE_13_PATTERN = re.compile(r"^Article 13\s*$", re.MULTILINE)


def main() -> None:
    with pdfplumber.open(PDF_PATH) as pdf:
        # Only scan pages from the Articles section onward (index 31+) to avoid
        # accidentally matching "Article 5" inside Recitals prose (e.g. "Article 5 TFEU").
        for i, page in enumerate(pdf.pages[31:], start=31):
            text = page.extract_text() or ""
            if ARTICLE_5_PATTERN.search(text):
                print(f"=== Article 5 found on page index {i} (page {i + 1}) ===")
                print(text)
                print("\n" + "=" * 80 + "\n")
                break

        for i, page in enumerate(pdf.pages[31:], start=31):
            text = page.extract_text() or ""
            if ARTICLE_13_PATTERN.search(text):
                print(f"=== Article 13 found on page index {i} (page {i + 1}) ===")
                print(text)
                print("\n" + "=" * 80 + "\n")
                break


if __name__ == "__main__":
    main()