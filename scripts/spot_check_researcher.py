"""Manual spot-check for the Regulation Researcher against the real Groq API + retrieval.

This is the first spot-check that exercises real retrieval (BM25 + Chroma + reranker),
so the first run will be slower as initialization happens.

Run from repo root:
    uv run python scripts/spot_check_researcher.py
"""

from complyagent.agents.researcher import research_statement
from complyagent.schemas.enums import StatementCategory
from complyagent.schemas.policy import PolicyStatement


def _print_result(label: str, chunks) -> None:
    print(f"--- {label} ---")
    print(f"  retrieved {len(chunks)} chunks:")
    for c in chunks:
        preview = c.text[:120].replace("\n", " ") + ("..." if len(c.text) > 120 else "")
        print(f"    [{c.chunk_id}] {preview}")
    print()


def main():
    statements = [
        PolicyStatement(
            statement_id="stmt-001",
            text="The company processes user data based on the user's explicit consent.",
            category=StatementCategory.LEGAL_BASIS,
            source_span=None,
        ),
        PolicyStatement(
            statement_id="stmt-002",
            text="The company retains user data for 24 months after account closure.",
            category=StatementCategory.RETENTION,
            source_span=None,
        ),
        PolicyStatement(
            statement_id="stmt-003",
            text="Users may request deletion of their account by contacting support.",
            category=StatementCategory.USER_RIGHTS,
            source_span=None,
        ),
    ]

    for stmt in statements:
        print(f"INPUT: ({stmt.category.value}) {stmt.text}")
        chunks = research_statement(stmt)
        _print_result(f"Result for {stmt.statement_id}", chunks)


if __name__ == "__main__":
    main()