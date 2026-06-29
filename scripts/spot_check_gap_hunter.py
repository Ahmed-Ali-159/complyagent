"""Manual spot-check for the Gap Hunter against the real Groq API.

Run from repo root:
    uv run python scripts/spot_check_gap_hunter.py
"""

from complyagent.agents.gap_hunter import hunt_gaps
from complyagent.schemas.enums import StatementCategory
from complyagent.schemas.policy import PolicyStatement


# A policy with deliberate gaps: it discloses purpose and retention but never
# identifies the controller, never states the legal basis, and never mentions
# data subject rights. Gap Hunter should flag at least those three.
INCOMPLETE_POLICY = [
    PolicyStatement(
        statement_id="stmt-001",
        text="The company collects user email addresses to provide newsletter services.",
        category=StatementCategory.DATA_COLLECTION,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-002",
        text="The company retains user data for 24 months.",
        category=StatementCategory.RETENTION,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-003",
        text="The company uses cookies to track user activity.",
        category=StatementCategory.COOKIES,
        source_span=None,
    ),
]

# A policy that addresses every checklist item, even if briefly. Gap Hunter
# should return [] or near-empty.
COMPLETE_POLICY = [
    PolicyStatement(
        statement_id="stmt-001",
        text="The data controller is Example Inc., reachable at privacy@example.com.",
        category=StatementCategory.CONTACT,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-002",
        text="Example Inc.'s data protection officer can be reached at dpo@example.com.",
        category=StatementCategory.CONTACT,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-003",
        text="The company processes user data to provide its services.",
        category=StatementCategory.DATA_USE,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-004",
        text="Processing is based on the user's consent.",
        category=StatementCategory.LEGAL_BASIS,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-005",
        text="The company shares data with analytics providers and payment processors.",
        category=StatementCategory.DATA_SHARING,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-006",
        text="Data may be transferred to processors in the United States under Standard Contractual Clauses.",
        category=StatementCategory.INTERNATIONAL_TRANSFER,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-007",
        text="The company retains user data for 24 months after account closure.",
        category=StatementCategory.RETENTION,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-008",
        text="Users may exercise their rights to access, rectify, erase, restrict, port, or object to processing of their data.",
        category=StatementCategory.USER_RIGHTS,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-009",
        text="Users may withdraw their consent at any time by contacting support.",
        category=StatementCategory.USER_RIGHTS,
        source_span=None,
    ),
    PolicyStatement(
        statement_id="stmt-010",
        text="Users may lodge a complaint with their local data protection authority.",
        category=StatementCategory.USER_RIGHTS,
        source_span=None,
    ),
]


def _print_gaps(label: str, gaps) -> None:
    print(f"--- {label} ---")
    print(f"  {len(gaps)} gap(s) found:")
    for g in gaps:
        print(f"    [{g.gap_id}] ({g.severity.value}) {g.requirement}")
        print(f"      basis: {g.gdpr_basis}")
        print(f"      rationale: {g.rationale}")
        print()


def main():
    print("Case 1: deliberately incomplete policy")
    print("Expected: multiple gaps including controller identity, legal basis, user rights.\n")
    _print_gaps("Incomplete policy", hunt_gaps(INCOMPLETE_POLICY))

    print("Case 2: full coverage policy")
    print("Expected: zero or near-zero gaps.\n")
    _print_gaps("Complete policy", hunt_gaps(COMPLETE_POLICY))

    print("Case 3: empty input short-circuit")
    _print_gaps("Empty policy", hunt_gaps([]))


if __name__ == "__main__":
    main()