"""Extracts ground-truth article numbers from the ClaimRAG-LAW gdpr-rag dataset's
relevant_chunk field, for use in retrieval evaluation (Step 2.8).

Ground truth is determined ONLY from relevant_chunk's own heading - never from
gt_answer or title-matching. gt_answer can legitimately reference multiple
related articles for context (verified on rows 102, 107, 138), which makes it
unreliable as a ground-truth signal; the only honest source of truth for "which
article is this chunk" is the chunk's own explicit heading.

This restricts the usable eval set to query_id >= 60 (90 of 149 rows), where the
dataset consistently uses an explicit "# Article N" heading. Rows 1-59 use
inconsistent formatting (sometimes title-only, sometimes leading with a
cross-referenced article number in body text) and were found to produce wrong
ground truth via every fallback strategy tried - excluded rather than patched.
"""
from __future__ import annotations

import re

ARTICLE_HEADING_PATTERN = re.compile(r"^#{1,4}\s*Article\s+(\d{1,3})\s*$", re.MULTILINE)


def resolve_article_number(relevant_chunk: str) -> int | None:
    """Returns the article number from relevant_chunk's own heading, or None if
    no unambiguous heading is present (caller should exclude the row)."""
    match = ARTICLE_HEADING_PATTERN.search(relevant_chunk[:200])
    return int(match.group(1)) if match else None