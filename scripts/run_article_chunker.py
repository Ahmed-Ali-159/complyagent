"""Run the Stage 3 article chunker against the real raw_articles_text.txt and
report summary statistics, before we build the full Pydantic-object pipeline.

Run from repo root:
    uv run python scripts/run_article_chunker.py
"""
from pathlib import Path

from complyagent.regulation.article_chunker import chunk_articles_text

text = Path("data/processed/raw_articles_text.txt").read_text(encoding="utf-8")
chunks = chunk_articles_text(text)

print(f"Total chunks produced: {len(chunks)}")

# Articles actually represented
article_numbers = sorted(set(c["article_number"] for c in chunks))
print(f"Distinct article numbers covered: {len(article_numbers)}")
missing_articles = sorted(set(range(1, 100)) - set(article_numbers))
print(f"Articles with ZERO chunks (missing entirely): {missing_articles}")

# Spot-check specific articles we hand-verified
for n in [1, 2, 4, 5, 10, 13]:
    matching = [c for c in chunks if c["article_number"] == n]
    print(f"\nArticle {n}: {len(matching)} chunks")
    for c in matching:
        print(f"  {c['chunk_id']:20} | {c['text'][:80]}")