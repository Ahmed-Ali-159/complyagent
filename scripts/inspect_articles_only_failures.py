"""Diagnostic: show actual articles-only retrieval results for failing queries,
to understand the genuine retrieval-quality gap (separate from the recital
effect we've now quantified and set aside).

Run from repo root:
    uv run python scripts/inspect_articles_only_failures.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from datasets import load_dataset

from complyagent.retrieval.eval_ground_truth import resolve_article_number
from complyagent.retrieval.retrieve import retrieve


def main():
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

    failures = []
    for item in eval_set:
        results = retrieve(item["query"], k=20)
        article_only = [r for r in results if r.source_type == "article"]
        article_numbers = [r.article_number for r in article_only]
        rank = None
        for i, num in enumerate(article_numbers[:5], start=1):
            if num == item["expected_article"]:
                rank = i
                break
        if rank is None:
            failures.append((item, article_only[:5]))

    print(f"Total articles-only failures (rank > 5): {len(failures)}")
    print()
    for item, top5 in failures[:10]:
        print(f"query_id={item['query_id']}, expected Art.{item['expected_article']}")
        print(f"  query: {item['query'][:150]}")
        print(f"  top5 articles returned: {[(r.chunk_id, r.article_number) for r in top5]}")
        print()


if __name__ == "__main__":
    main()