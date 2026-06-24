"""One-off diagnostic: confirm pdfplumber extracts the GDPR PDF cleanly.

Run from repo root:
    uv run python scripts/inspect_pdf.py
"""
import pdfplumber

PDF_PATH = "data/raw/gdpr_official_2016_679.pdf"


def main() -> None:
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"Total pages: {len(pdf.pages)}")

        # Page 1 (0-indexed: 0) — start of Recitals
        print("\n--- Page 1 (index 0) sample ---")
        print(pdf.pages[0].extract_text()[:500])

        # Page 32 (0-indexed: 31) — should be near start of Articles
        print("\n--- Page 32 (index 31) sample ---")
        print(pdf.pages[31].extract_text()[:500])

        # Page 88 (0-indexed: 87) — final page, signature block
        print("\n--- Page 88 (index 87) sample ---")
        print(pdf.pages[87].extract_text()[:500])

        # Find the exact page where "Article 1" first appears
        print("\n--- Searching for 'Article 1' boundary ---")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "CHAPTER I" in text or "Article 1" in text:
                print(f"Page index {i} (page {i + 1}) contains 'CHAPTER I' or 'Article 1':")
                print(text[:600])
                print("...")
                break


if __name__ == "__main__":
    main()