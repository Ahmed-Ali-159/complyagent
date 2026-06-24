"""Verify recital numbering in data/processed/raw_recitals_text.txt is 1..173,
sequential, no gaps, no duplicates.

Run from repo root:
    uv run python scripts/verify_recitals.py
"""
import re
from pathlib import Path

text = Path("data/processed/raw_recitals_text.txt").read_text(encoding="utf-8")

# Find every line that starts with a recital marker.
numbers = [int(m.group(1)) for m in re.finditer(r"^\((\d{1,3})\)", text, re.MULTILINE)]

print(f"Total recital markers found: {len(numbers)}")
print(f"First 5: {numbers[:5]}")
print(f"Last 5: {numbers[-5:]}")

expected = list(range(1, 174))
missing = sorted(set(expected) - set(numbers))
extra = sorted(set(numbers) - set(expected))
duplicates = sorted({n for n in numbers if numbers.count(n) > 1})

# Check strict ordering (no out-of-sequence jumps).
out_of_order = []
for i in range(1, len(numbers)):
    if numbers[i] != numbers[i - 1] + 1:
        out_of_order.append((numbers[i - 1], numbers[i]))

print(f"\nMissing recitals: {missing}")
print(f"Unexpected/extra numbers: {extra}")
print(f"Duplicate numbers: {duplicates}")
print(f"Out-of-sequence jumps (prev -> next): {out_of_order}")

if not missing and not extra and not duplicates and not out_of_order:
    print("\n✅ All 173 recitals present, in order, no duplicates.")
else:
    print("\n❌ Problems found - see above.")