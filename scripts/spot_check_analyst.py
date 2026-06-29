"""Manual spot-check for the Compliance Analyst against the real Groq API.

Run from repo root:
    uv run python scripts/spot_check_analyst.py
"""

from complyagent.agents.analyst import analyze_statement
from complyagent.schemas.enums import StatementCategory
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk


def _print_finding(label: str, finding) -> None:
    print(f"--- {label} ---")
    print(f"  statement_id: {finding.statement_id}")
    print(f"  verdict:      {finding.verdict.value}")
    print(f"  confidence:   {finding.confidence}")
    print(f"  citations:    {finding.citations}")
    print(f"  rationale:    {finding.rationale}")
    print()


def main():
    # Case 1: should be COMPLIANT with high confidence.
    stmt_compliant = PolicyStatement(
        statement_id="stmt-001",
        text="The company processes user data based on the user's explicit consent.",
        category=StatementCategory.LEGAL_BASIS,
        source_span=None,
    )
    chunks_compliant = [
        RegulationChunk(
            chunk_id="GDPR-Art-6-1-a",
            text="Processing shall be lawful only if the data subject has given "
                 "consent to the processing of his or her personal data for one "
                 "or more specific purposes.",
        ),
    ]
    _print_finding("Case 1: clear compliance", analyze_statement(stmt_compliant, chunks_compliant))

    # Case 2: should be VIOLATION.
    stmt_violation = PolicyStatement(
        statement_id="stmt-002",
        text="The company retains user data indefinitely for any future business purpose.",
        category=StatementCategory.RETENTION,
        source_span=None,
    )
    chunks_violation = [
        RegulationChunk(
            chunk_id="GDPR-Art-5-1-e",
            text="Personal data shall be kept in a form which permits identification "
                 "of data subjects for no longer than is necessary for the purposes "
                 "for which the personal data are processed.",
        ),
    ]
    _print_finding("Case 2: clear violation", analyze_statement(stmt_violation, chunks_violation))

    # Case 3: should be UNCLEAR — off-topic chunks.
    stmt_unclear = PolicyStatement(
        statement_id="stmt-003",
        text="The company shares user data with third-party advertising partners.",
        category=StatementCategory.DATA_SHARING,
        source_span=None,
    )
    chunks_unclear = [
        RegulationChunk(
            chunk_id="GDPR-Art-12-1",
            text="The controller shall take appropriate measures to provide any "
                 "information... in a concise, transparent, intelligible and "
                 "easily accessible form.",
        ),
    ]
    _print_finding("Case 3: off-topic retrieval (expect unclear)", analyze_statement(stmt_unclear, chunks_unclear))

    # Case 4: short-circuit on empty chunks.
    _print_finding(
        "Case 4: empty chunks short-circuit",
        analyze_statement(stmt_compliant, retrieved_chunks=[]),
    )


if __name__ == "__main__":
    main()