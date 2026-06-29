"""Manual spot-check for the Report Writer against the real Groq API.

Builds a realistic full-policy SupervisorState (multiple statements, mixed
verdicts, gaps, remediations) and asks the worker to produce the final report.

Run from repo root:
    uv run python scripts/spot_check_report_writer.py
"""

from complyagent.agents.report_writer import write_report
from complyagent.schemas.enums import (
    GapSeverity,
    StatementCategory,
    VerdictType,
)
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.supervisor import SupervisorState


def _build_realistic_state() -> SupervisorState:
    """Build a SupervisorState with a mixed-verdict full-policy audit shape."""
    statements = [
        PolicyStatement(
            statement_id="stmt-001",
            text="The company processes user data based on the user's explicit consent.",
            category=StatementCategory.LEGAL_BASIS,
            source_span="We process your data with your consent.",
        ),
        PolicyStatement(
            statement_id="stmt-002",
            text="The company retains user data indefinitely for any future business purpose.",
            category=StatementCategory.RETENTION,
            source_span="We keep your data forever.",
        ),
        PolicyStatement(
            statement_id="stmt-003",
            text="The company shares user data with advertising partners.",
            category=StatementCategory.DATA_SHARING,
            source_span="We share your data with advertisers.",
        ),
    ]

    findings = [
        Finding(
            statement_id="stmt-001",
            verdict=VerdictType.COMPLIANT,
            rationale="Article 6(1)(a) lists consent as a lawful basis. The statement satisfies this.",
            citations=["GDPR-Art-6-1-a"],
            confidence=0.95,
        ),
        Finding(
            statement_id="stmt-002",
            verdict=VerdictType.VIOLATION,
            rationale="Article 5(1)(e) requires retention limited to what is necessary. "
                      "Indefinite retention for unspecified purposes violates storage limitation.",
            citations=["GDPR-Art-5-1-e"],
            confidence=0.95,
        ),
        Finding(
            statement_id="stmt-003",
            verdict=VerdictType.UNCLEAR,
            rationale="The retrieved chunks do not establish whether the data sharing has a "
                      "lawful basis or appropriate safeguards. Manual review required.",
            citations=[],
            confidence=0.4,
        ),
    ]

    gaps = [
        Gap(
            gap_id="gap-001",
            requirement="Identity and contact details of the data controller.",
            gdpr_basis=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
            severity=GapSeverity.CRITICAL,
            rationale="No statement in the policy identifies the data controller.",
        ),
        Gap(
            gap_id="gap-002",
            requirement="Data subject rights: access, rectification, erasure, restriction, objection, portability.",
            gdpr_basis=["GDPR-Art-13-2-b", "GDPR-Art-14-2-c"],
            severity=GapSeverity.CRITICAL,
            rationale="No statement informs users of their GDPR rights.",
        ),
    ]

    remediations = [
        Remediation(
            remediation_id="rem-001",
            target_id="stmt-002",
            target_kind="finding",
            recommendation="Define category-specific retention periods and document them.",
            suggested_policy_text="We retain user data for [X months] after account closure.",
            related_citations=["GDPR-Art-5-1-e"],
        ),
        Remediation(
            remediation_id="rem-002",
            target_id="gap-001",
            target_kind="gap",
            recommendation="Add a clause identifying the controller and contact details.",
            suggested_policy_text="The data controller is [Company Name], reachable at [email].",
            related_citations=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
        ),
        Remediation(
            remediation_id="rem-003",
            target_id="gap-002",
            target_kind="gap",
            recommendation="Add a dedicated section on GDPR rights with contact details.",
            suggested_policy_text="You have the following GDPR rights: ...",
            related_citations=["GDPR-Art-13-2-b"],
        ),
    ]

    return SupervisorState(
        audit_id="audit-spotcheck-001",
        policy_source="synthetic-test-policy.txt",
        raw_policy_text="(full policy text omitted for spot-check)",
        audit_mode="full_policy",
        statements=statements,
        findings=findings,
        gaps=gaps,
        remediations=remediations,
    )


def main():
    print("Building realistic SupervisorState...")
    state = _build_realistic_state()

    print("Calling Report Writer...\n")
    report = write_report(state)

    print("=" * 70)
    print(f"AUDIT REPORT (audit_id={report.audit_id})")
    print(f"created_at: {report.created_at}")
    print("=" * 70)
    print()

    print("--- EXECUTIVE SUMMARY ---")
    print(report.executive_summary)
    print()

    print("--- MARKDOWN REPORT ---")
    print(report.markdown_report)
    print()

    print("=" * 70)
    print("Passthrough verification:")
    print(f"  statements:   {len(report.statements)} (expected 3)")
    print(f"  findings:     {len(report.findings)} (expected 3)")
    print(f"  gaps:         {len(report.gaps)} (expected 2)")
    print(f"  remediations: {len(report.remediations)} (expected 3)")


if __name__ == "__main__":
    main()