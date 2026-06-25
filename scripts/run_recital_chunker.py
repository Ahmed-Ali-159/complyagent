"""Run the Stage 3 recital chunker against the real raw_recitals_text.txt.

Run from repo root:
    uv run python scripts/run_recital_chunker.py
"""
from pathlib import Path

from complyagent.regulation.recital_chunker import chunk_recitals_text

text = Path("data/processed/raw_recitals_text.txt").read_text(encoding="utf-8")
chunks = chunk_recitals_text(text)

print(f"Total recital chunks: {len(chunks)}")

numbers = sorted(c["recital_number"] for c in chunks)
expected = list(range(1, 174))
missing = sorted(set(expected) - set(numbers))
extra = sorted(set(numbers) - set(expected))
print(f"Missing: {missing}")
print(f"Unexpected extra: {extra}")

print("\nFirst 3 recitals:")
for c in chunks[:3]:
    print(f"  {c['chunk_id']}: {c['text'][:100]}")

print("\nRecital 26 (the anonymization one we discussed earlier):")
r26 = next(c for c in chunks if c["recital_number"] == 26)
print(f"  {r26['text']}")

print("\nLast 3 recitals:")
for c in chunks[-3:]:
    print(f"  {c['chunk_id']}: {c['text'][:100]}")