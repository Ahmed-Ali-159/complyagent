"""Inspect Article 50's chunks specifically - the no-paragraph-wrapper case.

Run from repo root:
    uv run python scripts/inspect_article_50.py
"""
from pathlib import Path

from complyagent.regulation.article_chunker import chunk_articles_text

text = Path("data/processed/raw_articles_text.txt").read_text(encoding="utf-8")
chunks = chunk_articles_text(text)

for c in chunks:
    if c["article_number"] == 50:
        print(f"{c['chunk_id']:20} | paragraph={c['paragraph']} | {c['text'][:100]}")