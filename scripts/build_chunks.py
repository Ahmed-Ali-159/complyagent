"""Stage 3 orchestrator: build RegulationChunk objects from the cleaned Articles and
Recitals text, validate them structurally, and write data/processed/chunks.json.

Run from repo root:
    uv run python scripts/build_chunks.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from complyagent.regulation.article_chunker import chunk_articles_text
from complyagent.regulation.recital_chunker import chunk_recitals_text
from complyagent.schemas import RegulationChunk

ARTICLES_TEXT_PATH = REPO_ROOT / "data" / "processed" / "raw_articles_text.txt"
RECITALS_TEXT_PATH = REPO_ROOT / "data" / "processed" / "raw_recitals_text.txt"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "chunks.json"

# Structural assertions - known-correct counts, confirmed by hand against the real
# GDPR text earlier in this project. If any of these fail, something in the upstream
# text or chunking logic has regressed.
EXPECTED_TOTAL_ARTICLES = 99
EXPECTED_TOTAL_RECITALS = 173
EXPECTED_ARTICLE_5_CHUNK_COUNT = 7   # 6 sub-points (a)-(f) + paragraph 2
EXPECTED_ARTICLE_1_CHUNK_COUNT = 3   # 3 plain paragraphs, no sub-points
EXPECTED_ARTICLE_10_CHUNK_COUNT = 1  # prose-only article


def build_article_chunks() -> list[RegulationChunk]:
    text = ARTICLES_TEXT_PATH.read_text(encoding="utf-8")
    raw_chunks = chunk_articles_text(text)
    return [RegulationChunk(**c) for c in raw_chunks]


def build_recital_chunks() -> list[RegulationChunk]:
    text = RECITALS_TEXT_PATH.read_text(encoding="utf-8")
    raw_chunks = chunk_recitals_text(text)
    return [RegulationChunk(**c) for c in raw_chunks]


def run_structural_assertions(article_chunks: list[RegulationChunk], recital_chunks: list[RegulationChunk]) -> list[str]:
    """Run known-correct structural checks. Returns a list of failure messages (empty if all pass)."""
    failures = []

    article_numbers = sorted(set(c.article_number for c in article_chunks))
    if len(article_numbers) != EXPECTED_TOTAL_ARTICLES:
        failures.append(
            f"Expected {EXPECTED_TOTAL_ARTICLES} distinct articles, found {len(article_numbers)}: "
            f"missing {sorted(set(range(1, 100)) - set(article_numbers))}"
        )

    recital_numbers = sorted(c.recital_number for c in recital_chunks)
    if len(recital_numbers) != EXPECTED_TOTAL_RECITALS:
        failures.append(
            f"Expected {EXPECTED_TOTAL_RECITALS} recitals, found {len(recital_numbers)}: "
            f"missing {sorted(set(range(1, 174)) - set(recital_numbers))}"
        )

    art5_count = len([c for c in article_chunks if c.article_number == 5])
    if art5_count != EXPECTED_ARTICLE_5_CHUNK_COUNT:
        failures.append(f"Article 5: expected {EXPECTED_ARTICLE_5_CHUNK_COUNT} chunks, found {art5_count}")

    art1_count = len([c for c in article_chunks if c.article_number == 1])
    if art1_count != EXPECTED_ARTICLE_1_CHUNK_COUNT:
        failures.append(f"Article 1: expected {EXPECTED_ARTICLE_1_CHUNK_COUNT} chunks, found {art1_count}")

    art10_count = len([c for c in article_chunks if c.article_number == 10])
    if art10_count != EXPECTED_ARTICLE_10_CHUNK_COUNT:
        failures.append(f"Article 10: expected {EXPECTED_ARTICLE_10_CHUNK_COUNT} chunks, found {art10_count}")

    # Uniqueness: no duplicate chunk_ids across the whole set.
    all_ids = [c.chunk_id for c in article_chunks + recital_chunks]
    duplicates = {cid for cid in all_ids if all_ids.count(cid) > 1}
    if duplicates:
        failures.append(f"Duplicate chunk_ids found: {duplicates}")

    return failures


def main() -> int:
    print("Building article chunks...")
    article_chunks = build_article_chunks()
    print(f"  {len(article_chunks)} article chunks built and validated by RegulationChunk schema.")

    print("Building recital chunks...")
    recital_chunks = build_recital_chunks()
    print(f"  {len(recital_chunks)} recital chunks built and validated by RegulationChunk schema.")

    all_chunks = article_chunks + recital_chunks
    print(f"\nTotal chunks: {len(all_chunks)}")

    print("\nRunning structural assertions...")
    failures = run_structural_assertions(article_chunks, recital_chunks)
    if failures:
        print("FAILURES FOUND:")
        for f in failures:
            print(f"  - {f}")
    else:
        print("  All structural assertions passed.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = [c.model_dump() for c in all_chunks]
    OUTPUT_PATH.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(all_chunks)} chunks to {OUTPUT_PATH}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())