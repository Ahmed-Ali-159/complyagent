"""Inspect specific chunks by ID for manual review.

Run from repo root:
    uv run python scripts/inspect_chunks.py
"""
from pathlib import Path

from complyagent.regulation.article_chunker import chunk_articles_text

text = Path("data/processed/raw_articles_text.txt").read_text(encoding="utf-8")
chunks = chunk_articles_text(text)

target_ids = [
    "GDPR-Art-4-22-a",
    "GDPR-Art-4-22-b",
    "GDPR-Art-4-22-c",
    "GDPR-Art-4-23-a",
    "GDPR-Art-4-23-b",
    "GDPR-Art-2-4",
]

for cid in target_ids:
    match = next((x for x in chunks if x["chunk_id"] == cid), None)
    if match is None:
        print(f"{cid}: NOT FOUND")
        continue
    print(f"{cid}:")
    print(f"  {match['text']}")
    print()