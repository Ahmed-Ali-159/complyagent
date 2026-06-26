"""Diagnostic: verify the fixed Tier 1 regex (heading-only match) correctly
resolves the rows we found to be wrong with the original eval_ground_truth.py
(children's-consent rows incorrectly resolving to Article 6 instead of 8;
third-country-transfer rows incorrectly resolving to Article 45 instead of 49).

Run from repo root:
    uv run python scripts/check_ground_truth_fix.py
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from datasets import load_dataset

from complyagent.retrieval.eval_ground_truth import build_known_titles_map

ARTICLE_HEADING_PATTERN = re.compile(r"^#{1,4}\s*Article\s+(\d{1,3})\s*$", re.MULTILINE)


def resolve_v2(relevant_chunk, gt_answer, known_titles):
    m = ARTICLE_HEADING_PATTERN.search(relevant_chunk[:200])
    if m:
        return int(m.group(1)), "tier1_heading_only"
    first_line = relevant_chunk.split("\n")[0].strip("# ").strip("*").strip()
    if first_line in known_titles:
        return known_titles[first_line], "tier2_title_lookup"
    m2 = re.search(r"Article (\d{1,3})", gt_answer)
    if m2:
        return int(m2.group(1)), "tier3_from_gt_answer"
    return None, "UNRESOLVED"


def main():
    chunks = json.loads((REPO_ROOT / "data" / "processed" / "chunks.json").read_text(encoding="utf-8"))
    known_titles = build_known_titles_map(chunks)

    ds = load_dataset("SNTSVV/ClaimRAG-LAW", "gdpr-rag")

    check_ids = [9, 10, 12, 22, 25, 28]
    print("Spot-checking previously-wrong rows:")
    for row in ds["train"]:
        if row["query_id"] in check_ids:
            result, tier = resolve_v2(row["relevant_chunk"], row["gt_answer"], known_titles)
            print(f"  query_id={row['query_id']}: resolved={result} (tier={tier})")

    print()
    print("Full re-check across all 149 rows:")
    tier_counts = {}
    unresolved = []
    for row in ds["train"]:
        result, tier = resolve_v2(row["relevant_chunk"], row["gt_answer"], known_titles)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if result is None:
            unresolved.append(row["query_id"])

    print("  Tier counts:", tier_counts)
    print("  Unresolved:", unresolved)


if __name__ == "__main__":
    main()