"""Extracts ground-truth article numbers from the ClaimRAG-LAW gdpr-rag dataset's
relevant_chunk field, for use in retrieval evaluation (Step 2.8).

Three-tier resolution strategy, applied in order until one succeeds:
  1. Explicit "Article N" pattern found directly in relevant_chunk (covers most
     rows - the dataset often includes this as a markdown heading).
  2. The chunk's first heading/bold line matches one of our own corpus's known
     article titles exactly (covers rows where only the title is given, no
     explicit number - e.g. "**Subject-matter and objectives**" -> Article 1).
  3. Explicit "Article N" pattern found in gt_answer instead (fallback for rows
     where relevant_chunk only has an internal GDPR sub-heading, like "Processor"
     or "Derogations for specific situations", which are not the article's
     official title and won't match tier 2).

Verified against the real dataset: all 149 rows resolve via tiers 1-2 alone;
tier 3 was never needed but is kept as a defensive fallback.
"""
from __future__ import annotations

import re

ARTICLE_PATTERN = re.compile(r"Article (\d{1,3})")


def extract_title_line(relevant_chunk: str) -> str:
    first_line = relevant_chunk.split("\n")[0]
    return first_line.strip("# ").strip("*").strip()


def resolve_article_number(
    relevant_chunk: str,
    gt_answer: str,
    known_titles: dict[str, int],
) -> tuple[int | None, str]:
    """Returns (article_number, resolution_tier). article_number is None only if
    all three tiers fail (not observed on the real dataset, but handled safely)."""
    chunk_head = relevant_chunk[:200]
    m = ARTICLE_PATTERN.search(chunk_head)
    if m:
        return int(m.group(1)), "tier1_explicit_in_chunk"

    title = extract_title_line(relevant_chunk)
    if title in known_titles:
        return known_titles[title], "tier2_title_lookup"

    m2 = ARTICLE_PATTERN.search(gt_answer)
    if m2:
        return int(m2.group(1)), "tier3_from_gt_answer"

    return None, "UNRESOLVED"


def build_known_titles_map(chunks: list[dict]) -> dict[str, int]:
    """Build {article_title: article_number} from our own chunks.json."""
    return {c["article_title"]: c["article_number"] for c in chunks if c.get("article_title")}