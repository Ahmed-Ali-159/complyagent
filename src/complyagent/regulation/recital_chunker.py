"""Stage 3 chunker - Recitals.

Recitals are flat: each one is '(N) <text...>' continuing until the next '(N+1)'
marker appears. No paragraphs, no sub-points, no lead-in concept needed.
"""
from __future__ import annotations

import re

RECITAL_MARKER_PATTERN = re.compile(r"^\((\d{1,3})\)\s+(.*)$")


def chunk_recitals_text(recitals_text: str) -> list[dict]:
    lines = recitals_text.split("\n")

    chunks: list[dict] = []
    current_number: int | None = None
    current_lines: list[str] = []

    def flush():
        if current_number is None:
            return
        body = " ".join(current_lines).strip()
        if body:
            chunks.append({
                "chunk_id": f"GDPR-Rec-{current_number}",
                "recital_number": current_number,
                "text": body,
            })

    for raw_line in lines:
        if not raw_line.strip():
            continue
        stripped = raw_line.strip()
        match = RECITAL_MARKER_PATTERN.match(stripped)

        if match:
            flush()
            current_number = int(match.group(1))
            current_lines = [match.group(2)]
        else:
            if current_number is not None:
                current_lines.append(stripped)

    flush()
    return chunks