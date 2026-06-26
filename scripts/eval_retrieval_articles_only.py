"""Diagnostic: run the same 90-query eval, but with retrieval restricted to
ARTICLES ONLY (recitals filtered out before BM25/dense retrieval ever see them).
This isolates whether recitals "stealing" top-5 slots is the real cause of our
Recall@5 gap, or whether retrieval quality itself needs work.

This is a TEMPORARY diagnostic configuration, not a permanent change - recitals
stay in the real, production retrieve() function regardless of this result,
since they provide genuinely valuable interpretive context (confirmed concretely
by the query 66 inspection - Recital 50 was the best available answer for a
purpose-limitation scenario question).

Run from repo root:
    uv run python scripts/eval_retrieval_articles_only.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from datasets import load_dataset

from complyagent.retrieval.eval_ground_truth import resolve_article_number
from complyagent.retrieval.retrieve import retrieve

def main() -> int:
    print("Loading ClaimRAG-LAW gdpr-rag dataset...")
    ds = load_dataset("SNTSVV/ClaimRAG-LAW", "gdpr-rag")
    rows = ds["train"]

    eval_set = []
    for row in rows:
        if row["query_id"] < 60:
            continue
        article_num = resolve_article_number(row["relevant_chunk"])
        if article_num is None:
            continue
        eval_set.append({"query_id": row["query_id"], "query": row["query"], "expected_article": article_num})
    print(f"  {len(eval_set)} queries with resolved ground truth.")

    print(f"\nRunning retrieval for all {len(eval_set)} queries, filtering recitals from results post-hoc...")

    hits_at_5 = 0
    hits_at_10 = 0
    reciprocal_ranks = []

    for i, item in enumerate(eval_set, start=1):
        # Fetch more than we need (k=20) so that after filtering out recitals,
        # we still have a meaningful top-10 of ARTICLE chunks to evaluate against.
        results = retrieve(item["query"], k=20)
        article_only_results = [r for r in results if r.source_type == "article"]
        result_article_numbers = [r.article_number for r in article_only_results]

        rank_of_first_hit = None
        for rank, article_num in enumerate(result_article_numbers, start=1):
            if article_num == item["expected_article"]:
                rank_of_first_hit = rank
                break

        if rank_of_first_hit is not None and rank_of_first_hit <= 5:
            hits_at_5 += 1
        if rank_of_first_hit is not None and rank_of_first_hit <= 10:
            hits_at_10 += 1
        reciprocal_ranks.append(1.0 / rank_of_first_hit if rank_of_first_hit else 0.0)

        if i % 25 == 0:
            print(f"  ...{i}/{len(eval_set)} done")

    n = len(eval_set)
    print(f"\n{'=' * 50}")
    print(f"RESULTS (ARTICLES-ONLY, post-hoc filtered) over {n} queries")
    print(f"{'=' * 50}")
    print(f"Recall@5:  {hits_at_5/n:.4f}  ({hits_at_5}/{n})")
    print(f"Recall@10: {hits_at_10/n:.4f}  ({hits_at_10}/{n})")
    print(f"MRR:       {sum(reciprocal_ranks)/n:.4f}")

    return 0

if __name__ == "__main__":
    sys.exit(main())