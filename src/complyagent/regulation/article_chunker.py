"""Stage 3 chunker - state machine that walks the Articles text and produces chunk dicts.

Rules implemented (all confirmed against real GDPR PDF text):
  - Chapter/Section headings are tracked as context, not chunks themselves.
  - The line immediately after 'Article N' is always the article's title.
  - Article 4 numbers its top-level items as '(N)' instead of 'N.' - both are
    treated as the same conceptual "paragraph" level.
  - A paragraph with NO lettered sub-points -> one chunk for the whole paragraph.
  - A paragraph WITH lettered sub-points -> one chunk per sub-point, with the
    paragraph's lead-in text prepended to each sub-point's text.
  - An article with no paragraph numbering at all (prose-only) -> one chunk for
    the entire article body.
"""
from __future__ import annotations

from complyagent.regulation.line_classifier import classify_line

def chunk_articles_text(articles_text: str) -> list[dict]:
    lines = articles_text.split("\n")

    chunks: list[dict] = []

    current_chapter: str | None = None
    current_article_number: int | None = None
    current_article_title: str | None = None
    expecting_title = False

    current_paragraph_number: int | None = None
    current_paragraph_leadin_lines: list[str] = []
    current_paragraph_has_subpoints = False

    current_subpoint_letter: str | None = None
    current_subpoint_lines: list[str] = []

    article_has_seen_any_paragraph_marker = False
    prose_lines: list[str] = []

    def leadin_text() -> str:
        return " ".join(current_paragraph_leadin_lines).strip()

    def flush_subpoint():
        nonlocal current_subpoint_letter, current_subpoint_lines
        if current_subpoint_letter is None:
            return
        body = " ".join(current_subpoint_lines).strip()
        full_text = f"{leadin_text()} {body}".strip()
        chunks.append({
            "chunk_id": f"GDPR-Art-{current_article_number}-{current_paragraph_number}-{current_subpoint_letter}",
            "article_number": current_article_number,
            "article_title": current_article_title,
            "chapter": current_chapter,
            "paragraph": current_paragraph_number,
            "point": current_subpoint_letter,
            "text": full_text,
        })
        current_subpoint_letter = None
        current_subpoint_lines = []

    def flush_paragraph():
        nonlocal current_paragraph_number, current_paragraph_leadin_lines, current_paragraph_has_subpoints
        flush_subpoint()
        if current_paragraph_number is None:
            return
        if not current_paragraph_has_subpoints:
            full_text = leadin_text()
            chunks.append({
                "chunk_id": f"GDPR-Art-{current_article_number}-{current_paragraph_number}",
                "article_number": current_article_number,
                "article_title": current_article_title,
                "chapter": current_chapter,
                "paragraph": current_paragraph_number,
                "point": None,
                "text": full_text,
            })
        current_paragraph_number = None
        current_paragraph_leadin_lines = []
        current_paragraph_has_subpoints = False

    def flush_prose_article():
        nonlocal prose_lines
        if current_article_number is None or article_has_seen_any_paragraph_marker:
            prose_lines = []
            return
        body = " ".join(prose_lines).strip()
        if body:
            chunks.append({
                "chunk_id": f"GDPR-Art-{current_article_number}",
                "article_number": current_article_number,
                "article_title": current_article_title,
                "chapter": current_chapter,
                "paragraph": None,
                "point": None,
                "text": body,
            })
        prose_lines = []

    def flush_article():
        flush_paragraph()
        flush_prose_article()

    for raw_line in lines:
        if not raw_line.strip():
            continue

        if expecting_title:
            current_article_title = raw_line.strip()
            expecting_title = False
            continue

        kind, data = classify_line(raw_line)

        if kind == "chapter":
            current_chapter = data["text"]
            continue

        if kind == "section":
            continue  # tracked but not currently used on chunks

        if kind == "article":
            flush_article()
            current_article_number = data["number"]
            current_article_title = None
            expecting_title = True
            article_has_seen_any_paragraph_marker = False
            prose_lines = []
            continue

        if kind in ("paragraph_dot", "paragraph_paren"):
            flush_paragraph()
            article_has_seen_any_paragraph_marker = True
            current_paragraph_number = data["number"]
            current_paragraph_leadin_lines = [data["text"]]
            current_paragraph_has_subpoints = False
            continue

        if kind == "subpoint":
            flush_subpoint()
            current_paragraph_has_subpoints = True
            current_subpoint_letter = data["letter"]
            current_subpoint_lines = [data["text"]]
            continue

        # continuation line
        if current_subpoint_letter is not None:
            current_subpoint_lines.append(data["text"])
        elif current_paragraph_number is not None:
            # No sub-point open yet - this line extends the LEAD-IN, not a
            # separate "whole paragraph" buffer. If a sub-point never shows up,
            # the lead-in IS the whole paragraph's text - so this is correct
            # either way, fixing exactly the bug we found.
            current_paragraph_leadin_lines.append(data["text"])
        elif current_article_number is not None:
            prose_lines.append(data["text"])

    flush_article()

    return chunks