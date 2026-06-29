"""Manual spot-check for the Remediation Drafter against real Groq + retrieval.

Run from repo root:
    uv run python scripts/spot_check_remediation.py
"""

from complyagent.agents.remediation import draft_remediation
from complyagent.schemas.enums import (
    GapSeverity,
    StatementCategory,
    VerdictType,
)
from complyagent.schemas.findings import Finding
from complyagent.schemas.findings import Gap
from complyagent.schemas.policy import PolicyStatement


def _print_remediation(label: str, rem) -> None:
    print(f"--- {label} ---")
    print(f"  remediation_id: {rem.remediation_id}")
    print(f"  target_kind:    {rem.target_kind}")
    print(f"  target_id:      {rem.target_id}")
    print(f"  related_citations: {rem.related_citations}")
    print(f"  recommendation:")
    print(f"    {rem.recommendation}")
    print(f"  suggested_policy_text:")
    print(f"    {rem.suggested_policy_text}")
    print()


def main():
    # Case 1: Finding remediation — fixing a clear violation.
    print("Case 1: Finding — indefinite retention (violation)\n")
    statement = PolicyStatement(
        statement_id="stmt-001",
        text="The company retains user data indefinitely for any future business purpose.",
        category=StatementCategory.RETENTION,
        source_span=None,
    )
    finding = Finding(
        statement_id="stmt-001",
        verdict=VerdictType.VIOLATION,
        rationale="Article 5(1)(e) requires retention limited to what is necessary. "
                  "Indefinite retention for unspecified purposes violates storage limitation.",
        citations=["GDPR-Art-5-1-e"],
        confidence=0.95,
    )
    _print_remediation("Finding remediation", draft_remediation(
        target=finding,
        original_statement=statement,
        remediation_id="rem-001",
    ))

    # Case 2: Gap remediation — missing controller identity.
    print("Case 2: Gap — missing controller identity\n")
    gap = Gap(
        gap_id="gap-001",
        requirement="Identity and contact details of the data controller.",
        gdpr_basis=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
        severity=GapSeverity.CRITICAL,
        rationale="No statement in the policy identifies the data controller or "
                  "provides their contact details.",
    )
    _print_remediation("Gap remediation", draft_remediation(
        target=gap,
        remediation_id="rem-002",
    ))

    # Case 3: Gap remediation — missing data subject rights.
    print("Case 3: Gap — missing data subject rights disclosure\n")
    gap2 = Gap(
        gap_id="gap-002",
        requirement="Data subject rights: access, rectification, erasure, restriction, objection, portability.",
        gdpr_basis=["GDPR-Art-13-2-b", "GDPR-Art-14-2-c"],
        severity=GapSeverity.CRITICAL,
        rationale="No statement informs users of their GDPR rights.",
    )
    _print_remediation("Gap remediation (rights)", draft_remediation(
        target=gap2,
        remediation_id="rem-003",
    ))


if __name__ == "__main__":
    main()