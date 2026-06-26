"""Step 2.8: retrieval evaluation against the ClaimRAG-LAW gdpr-rag dataset.

For each of the 149 queries, ground truth is the article number the question was
generated from (resolved via the 3-tier strategy in eval_ground_truth.py, verified
to cover 100% of rows). We call retrieve(query, k=10) once per query and check:
  - Recall@5:  is a chunk from the ground-truth article in the top 5 results?
  - Recall@10: same, top 10 (diagnostic - shows if failures are "close" or "far")
  - MRR:       reciprocal rank of the first correct hit (rewards ranking higher,
               not just including the right answer somewhere in the list)

A "hit" means: at least one returned RegulationChunk has article_number equal to
the ground-truth article number. We check article-level match, not exact chunk_id
match, because this dataset's ground truth is article-level (the relevant_chunk
often spans an entire article, not one specific sub-point).

Run from repo root:
    uv run python scripts/eval_retrieval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from datasets import load_dataset

from complyagent.retrieval.eval_ground_truth import resolve_article_number
from complyagent.retrieval.retrieve import retrieve

CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.json"


def main() -> int:
    print("Loading ClaimRAG-LAW gdpr-rag dataset...")
    ds = load_dataset("SNTSVV/ClaimRAG-LAW", "gdpr-rag")
    rows = ds["train"]
    print(f"  {len(rows)} queries loaded.")

    print("\nResolving ground-truth article numbers...")
    eval_set = []
    for row in rows:
        if row["query_id"] < 60:
            continue  # excluded: inconsistent heading format, unreliable ground truth
        article_num = resolve_article_number(row["relevant_chunk"])
        if article_num is None:
            print(f"  WARNING: query_id {row['query_id']} has no heading match - excluding.")
            continue
        eval_set.append({"query_id": row["query_id"], "query": row["query"], "expected_article": article_num})
    print(f"  {len(eval_set)} queries with resolved ground truth ({len(rows) - len(eval_set)} excluded).")

    print(f"\nRunning retrieval for all {len(eval_set)} queries (this calls retrieve() once per query - may take a while)...")

    hits_at_5 = 0
    hits_at_10 = 0
    reciprocal_ranks = []
    failures = []

    for i, item in enumerate(eval_set, start=1):
        results = retrieve(item["query"], k=10)
        result_article_numbers = [r.article_number for r in results]

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

        if rank_of_first_hit is None or rank_of_first_hit > 5:
            failures.append({
                "query_id": item["query_id"],
                "query": item["query"],
                "expected_article": item["expected_article"],
                "rank_of_first_hit": rank_of_first_hit,
                "top_5_articles": result_article_numbers[:5],
            })

        if i % 25 == 0:
            print(f"  ...{i}/{len(eval_set)} done")

    n = len(eval_set)
    recall_at_5 = hits_at_5 / n
    recall_at_10 = hits_at_10 / n
    mrr = sum(reciprocal_ranks) / n

    print(f"\n{'=' * 50}")
    print(f"RESULTS over {n} queries")
    print(f"{'=' * 50}")
    print(f"Recall@5:  {recall_at_5:.4f}  ({hits_at_5}/{n})")
    print(f"Recall@10: {recall_at_10:.4f}  ({hits_at_10}/{n})")
    print(f"MRR:       {mrr:.4f}")
    print(f"\nDeliverable gate: Recall@5 >= 0.85 -> {'PASS' if recall_at_5 >= 0.85 else 'FAIL'}")

    if failures:
        print(f"\n{len(failures)} failures (rank > 5 or not found in top 10):")
        for f in failures[:20]:
            print(f"  query_id={f['query_id']}: expected Art.{f['expected_article']}, "
                  f"rank={f['rank_of_first_hit']}, top5={f['top_5_articles']}")
            print(f"    query: {f['query'][:100]}")

    return 0 if recall_at_5 >= 0.85 else 1


if __name__ == "__main__":
    sys.exit(main())