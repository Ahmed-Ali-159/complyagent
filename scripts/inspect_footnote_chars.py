"""One-off diagnostic: inspect exact characters around footnote markers on page 1.

Run from repo root:
    uv run python scripts/inspect_footnote_chars.py
"""
import pdfplumber

PDF_PATH = "data/raw/gdpr_official_2016_679.pdf"

with pdfplumber.open(PDF_PATH) as pdf:
    page1_text = pdf.pages[0].extract_text()
    print(repr(page1_text))