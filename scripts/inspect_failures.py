"""Diagnostic: inspect actual retrieved chunks (not just article_number) for a
sample of failing queries, to determine whether 'None' results are substantively
relevant recitals (eval methodology gap) or genuinely irrelevant (real retrieval
failure).

Run from repo root:
    uv run python scripts/inspect_failures.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from complyagent.retrieval.retrieve import retrieve

queries_to_check = [
    (60, "If an employer processes an employee's medical records to assess their fitness for a specific role, can the employer justify this processing solely on the basis of its legitimate business interests?"),
    (66, "An e-commerce company obtains customer consent to process their email addresses solely for the purpose of sending transactional updates like order confirmations. Can the company later use these same email addresses to send promotional marketing newsletters by justifying it as a legitimate business interest?"),
]

for qid, query in queries_to_check:
    print(f"=== query_id={qid} ===")
    print(f"Query: {query}")
    results = retrieve(query, k=5)
    for r in results:
        print(f"  {r.chunk_id} ({r.citation_label}): {r.text[:120]}")
    print()