"""Stage 3 chunker - line classification helpers.

These regexes classify each line of the cleaned Articles text into one of:
  CHAPTER, SECTION, ARTICLE, PARAGRAPH (dot-numbered), PARAGRAPH_PAREN (Art. 4 style),
  SUBPOINT (lettered), or CONTINUATION (none of the above - body text).
"""
import re

CHAPTER_PATTERN = re.compile(r"^CHAPTER\s+[IVXLCDM]+\s*$")
SECTION_PATTERN = re.compile(r"^Section\s+\d+\s*$")
ARTICLE_PATTERN = re.compile(r"^Article\s+(\d{1,3})\s*$")
PARAGRAPH_DOT_PATTERN = re.compile(r"^(\d{1,2})\.\s+(.*)$")
PARAGRAPH_PAREN_PATTERN = re.compile(r"^\((\d{1,2})\)\s+(.*)$")
SUBPOINT_PATTERN = re.compile(r"^\(([a-z])\)\s+(.*)$")


def classify_line(line: str) -> tuple[str, dict]:
    """Classify one line. Returns (kind, data) where kind is one of:
    'chapter', 'section', 'article', 'paragraph_dot', 'paragraph_paren',
    'subpoint', 'continuation'.
    """
    stripped = line.strip()

    if CHAPTER_PATTERN.match(stripped):
        return "chapter", {"text": stripped}

    if SECTION_PATTERN.match(stripped):
        return "section", {"text": stripped}

    m = ARTICLE_PATTERN.match(stripped)
    if m:
        return "article", {"number": int(m.group(1))}

    m = SUBPOINT_PATTERN.match(stripped)
    if m:
        return "subpoint", {"letter": m.group(1), "text": m.group(2)}

    m = PARAGRAPH_DOT_PATTERN.match(stripped)
    if m:
        return "paragraph_dot", {"number": int(m.group(1)), "text": m.group(2)}

    m = PARAGRAPH_PAREN_PATTERN.match(stripped)
    if m:
        return "paragraph_paren", {"number": int(m.group(1)), "text": m.group(2)}

    return "continuation", {"text": stripped}


if __name__ == "__main__":
    # Quick smoke test against representative real lines.
    test_lines = [
        "CHAPTER I",
        "Section 2",
        "Article 5",
        "1. Personal data shall be:",
        "(1) 'personal data' means any information relating to an identified or identifiable natural person ('data subject'); an",
        "(a) processed lawfully, fairly and in a transparent manner in relation to the data subject ('lawfulness, fairness and",
        "transparency');",
        "Principles relating to processing of personal data",  # article title line - should be continuation
    ]
    for line in test_lines:
        kind, data = classify_line(line)
        print(f"{kind:16} {data}")