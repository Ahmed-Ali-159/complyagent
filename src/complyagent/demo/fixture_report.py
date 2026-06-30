"""Synthetic AuditReport fixture for UI development.

Used by app.py's demo mode to populate the UI with a realistic, deterministic
report without running a real audit. Mirrors what a Policy C audit would
actually produce.
"""

from datetime import datetime, UTC

from complyagent.schemas.enums import (
    GapSeverity,
    StatementCategory,
    VerdictType,
)
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.report import AuditReport
from complyagent.schemas.report import SupervisorDecision

def build_demo_report() -> AuditReport:
    """Build a realistic AuditReport for a Policy-C-shaped audit.

    Mixes all verdict types, several severity levels, and full remediation
    fields so the UI can exercise every render path without a real audit.
    """
    statements = [
        PolicyStatement(
            statement_id="stmt-001",
            text="The company collects users' name, email, phone number, home address, payment card details, browsing history, precise GPS location, contacts list, and photo library metadata.",
            category=StatementCategory.DATA_COLLECTION,
            source_span="We collect your name, email, phone number, home address, payment card details, browsing history within the app, precise GPS location at all times the app is installed (even when not in use), your device contacts list, and your photo library metadata.",
        ),
        PolicyStatement(
            statement_id="stmt-002",
            text="The company uses user data however it sees fit to grow its business.",
            category=StatementCategory.DATA_USE,
            source_span="We use your data however we see fit to grow our business.",
        ),
        PolicyStatement(
            statement_id="stmt-003",
            text="The company shares and sells user personal data, including location and contacts, to advertising partners and data brokers without permission.",
            category=StatementCategory.DATA_SHARING,
            source_span="We share and sell your personal data... to advertising partners, data brokers, and any other third party willing to pay for it. We do not ask for your permission before sharing this data.",
        ),
        PolicyStatement(
            statement_id="stmt-004",
            text="The company retains all data forever, including after account deletion.",
            category=StatementCategory.RETENTION,
            source_span="We keep all data forever, including after you delete your account, in case we need it for future business purposes.",
        ),
        PolicyStatement(
            statement_id="stmt-005",
            text="Users have no ability to access, correct, or delete their personal data.",
            category=StatementCategory.USER_RIGHTS,
            source_span="You have no ability to access, correct, or delete your personal data.",
        ),
        PolicyStatement(
            statement_id="stmt-006",
            text="By using this app, users waive any rights they may have under any data protection law, including the GDPR.",
            category=StatementCategory.USER_RIGHTS,
            source_span="By using this app, you waive any rights you may have under any data protection law, including the GDPR.",
        ),
        PolicyStatement(
            statement_id="stmt-007",
            text="The app collects data from children under 13 with no additional safeguards or parental consent.",
            category=StatementCategory.CHILDREN,
            source_span="This app is intended for all ages, including children under 13, and we collect the same data from child users as from adult users with no additional safeguards or parental consent.",
        ),
        PolicyStatement(
            statement_id="stmt-008",
            text="The company transfers data to advertising partners' servers worldwide, including in countries with no data protection laws, with no additional safeguards.",
            category=StatementCategory.INTERNATIONAL_TRANSFER,
            source_span="We transfer all data to our servers and to our advertising partners' servers worldwide, including in countries with no data protection laws, with no additional safeguards.",
        ),
        PolicyStatement(
            statement_id="stmt-009",
            text="The company does not encrypt stored data because encryption slows systems.",
            category=StatementCategory.SECURITY,
            source_span="We do not encrypt stored data, as encryption slows down our systems.",
        ),
        PolicyStatement(
            statement_id="stmt-010",
            text="The company does not provide a contact method for privacy inquiries.",
            category=StatementCategory.CONTACT,
            source_span="We do not provide a contact method for privacy inquiries.",
        ),
    ]

    findings = [
        Finding(
            statement_id="stmt-001",
            verdict=VerdictType.VIOLATION,
            rationale="Article 5(1)(c) requires data collection to be adequate, relevant, and limited to what is necessary. Collecting precise GPS at all times, full contacts, and photo metadata for a flash-sale shopping app is grossly excessive relative to stated purposes.",
            citations=["GDPR-Art-5-1-c"],
            confidence=0.95,
        ),
        Finding(
            statement_id="stmt-002",
            verdict=VerdictType.VIOLATION,
            rationale="Article 6(1) requires a valid legal basis for processing. 'However we see fit' articulates no lawful basis at all.",
            citations=["GDPR-Art-6-1"],
            confidence=0.95,
        ),
        Finding(
            statement_id="stmt-003",
            verdict=VerdictType.VIOLATION,
            rationale="Selling data without consent violates Article 6(1) (no valid legal basis) and Article 7 (consent must be freely given). The policy explicitly disclaims seeking permission.",
            citations=["GDPR-Art-6-1", "GDPR-Art-7-1"],
            confidence=0.93,
        ),
        Finding(
            statement_id="stmt-004",
            verdict=VerdictType.VIOLATION,
            rationale="Article 5(1)(e) prohibits retention beyond what is necessary for specified purposes. 'Forever, including after deletion' directly violates the storage limitation principle.",
            citations=["GDPR-Art-5-1-e"],
            confidence=0.97,
        ),
        Finding(
            statement_id="stmt-005",
            verdict=VerdictType.VIOLATION,
            rationale="Articles 15 and 17 grant the rights of access and erasure to data subjects. These rights cannot be denied; the policy explicitly does so.",
            citations=["GDPR-Art-15", "GDPR-Art-17"],
            confidence=0.95,
        ),
        Finding(
            statement_id="stmt-006",
            verdict=VerdictType.VIOLATION,
            rationale="GDPR rights are not contractually waivable. A clause purporting to waive them is void and itself a violation.",
            citations=["GDPR-Art-15", "GDPR-Art-17"],
            confidence=0.95,
        ),
        Finding(
            statement_id="stmt-007",
            verdict=VerdictType.VIOLATION,
            rationale="Article 8(1) requires parental consent for processing children's data in the context of information society services. Collecting from under-13s with zero safeguards is a direct violation.",
            citations=["GDPR-Art-8-1"],
            confidence=0.94,
        ),
        Finding(
            statement_id="stmt-008",
            verdict=VerdictType.VIOLATION,
            rationale="Articles 44 and 46 require an adequacy decision or appropriate safeguards for transfers outside the EEA. 'No data protection laws' and 'no additional safeguards' violate both.",
            citations=["GDPR-Art-44", "GDPR-Art-46"],
            confidence=0.96,
        ),
        Finding(
            statement_id="stmt-009",
            verdict=VerdictType.VIOLATION,
            rationale="Article 32(1) requires appropriate technical measures including encryption where appropriate, given the risk. Declining to encrypt payment card data violates this.",
            citations=["GDPR-Art-32-1"],
            confidence=0.94,
        ),
        Finding(
            statement_id="stmt-010",
            verdict=VerdictType.VIOLATION,
            rationale="Article 13(1)(a) requires identity and contact details of the controller to be provided. No contact method is given.",
            citations=["GDPR-Art-13-1-a"],
            confidence=0.90,
        ),
        Finding(
            statement_id="stmt-011",
            verdict=VerdictType.UNCLEAR,
            rationale="The statement about cookies is ambiguous; the retrieved chunks do not clearly establish whether the specific cookie practices described comply with ePrivacy directive requirements.",
            citations=[],
            confidence=0.4,
        ),
    ]

    gaps = [
        Gap(
            gap_id="gap-001",
            requirement="Contact details of the data protection officer, where applicable.",
            gdpr_basis=["GDPR-Art-13-1-b", "GDPR-Art-14-1-b"],
            severity=GapSeverity.MEDIUM,
            rationale="No statement provides DPO contact details or addresses DPO applicability.",
        ),
        Gap(
            gap_id="gap-002",
            requirement="Recipients or categories of recipients of the personal data.",
            gdpr_basis=["GDPR-Art-13-1-e", "GDPR-Art-14-1-e"],
            severity=GapSeverity.HIGH,
            rationale="The policy mentions sharing with 'advertising partners' but does not categorize or identify specific recipients.",
        ),
        Gap(
            gap_id="gap-003",
            requirement="Period for which personal data will be stored, or criteria used to determine that period.",
            gdpr_basis=["GDPR-Art-13-2-a", "GDPR-Art-14-2-a"],
            severity=GapSeverity.HIGH,
            rationale="The policy says data is kept 'forever' which is not a valid retention period or criterion.",
        ),
        Gap(
            gap_id="gap-004",
            requirement="Right to lodge a complaint with a supervisory authority.",
            gdpr_basis=["GDPR-Art-13-2-d", "GDPR-Art-14-2-e"],
            severity=GapSeverity.MEDIUM,
            rationale="No statement informs users of their right to lodge a complaint.",
        ),
    ]

    remediations = [
        Remediation(
            remediation_id="rem-001",
            target_id="stmt-001",
            target_kind="finding",
            recommendation="Apply data minimisation: collect only what is necessary for each stated purpose. Replace 'at all times GPS' with 'GPS only when actively using location features.' Remove contacts and photo metadata collection unless tied to a specific user-initiated feature.",
            suggested_policy_text="We collect personal information only when necessary to provide our services: account details (name, email, phone) to create and manage your account; payment information to process purchases; and location data only when you actively use location-based features. We do not collect access to your contacts or photo library without explicit, feature-specific consent.",
            related_citations=["GDPR-Art-5-1-c"],
        ),
        Remediation(
            remediation_id="rem-002",
            target_id="stmt-002",
            target_kind="finding",
            recommendation="Identify and disclose a specific legal basis for each processing purpose per Article 6(1). Most likely: consent for marketing, contractual necessity for service provision, legitimate interest for analytics.",
            suggested_policy_text="We process your personal data on the following legal bases: (a) the performance of our contract with you (for account management and service provision); (b) your consent (for marketing communications and optional features); (c) our legitimate interests (for service improvement and security), balanced against your privacy rights; and (d) legal obligations (for tax and compliance records).",
            related_citations=["GDPR-Art-6-1"],
        ),
        Remediation(
            remediation_id="rem-003",
            target_id="stmt-004",
            target_kind="finding",
            recommendation="Define category-specific retention periods. Document a retention schedule and publish it. Data must be deleted or anonymised when no longer necessary.",
            suggested_policy_text="We retain your data only as long as necessary for the purposes described: account data for the duration of your account plus 30 days for recovery; transaction records for 7 years to meet tax obligations; marketing data until you withdraw consent. After these periods, data is securely deleted or anonymised.",
            related_citations=["GDPR-Art-5-1-e"],
        ),
        Remediation(
            remediation_id="rem-004",
            target_id="gap-001",
            target_kind="gap",
            recommendation="Designate a Data Protection Officer if required by Article 37, or document the assessment that no DPO is required. Publish DPO contact details in the policy.",
            suggested_policy_text="Our Data Protection Officer can be reached at [dpo@example.com] or by mail at [Company Name, Attn: DPO, Address]. The DPO oversees our compliance with GDPR and is your primary contact for any data protection inquiries or to exercise your rights.",
            related_citations=["GDPR-Art-13-1-b"],
        ),
        Remediation(
            remediation_id="rem-005",
            target_id="gap-002",
            target_kind="gap",
            recommendation="Disclose the categories of third-party recipients (e.g. 'payment processors', 'analytics providers', 'advertising partners'). Where possible, name specific processors.",
            suggested_policy_text="We share your personal data with the following categories of recipients: (a) payment processors to handle transactions; (b) cloud hosting providers to store and process data; (c) analytics providers to understand product usage; (d) marketing partners (only with your consent). A current list of our specific processors is available at [URL].",
            related_citations=["GDPR-Art-13-1-e"],
        ),
    ]

    decisions = [
        SupervisorDecision(
            iteration=1,
            next_worker="regulation_researcher",
            reasoning="Parser extracted 11 statement(s) from policy 'demo-fixture'. Audit mode = full_policy.",
            is_terminal=False,
        ),
        SupervisorDecision(
            iteration=2,
            next_worker=None,
            reasoning="All 11 finding(s) above confidence threshold 0.6. Proceeding.",
            is_terminal=False,
        ),
        SupervisorDecision(
            iteration=3,
            next_worker="gap_hunter",
            reasoning="Case 2 (full_policy): proceeding to Gap Hunter for coverage analysis against the mandatory disclosure checklist.",
            is_terminal=False,
        ),
        SupervisorDecision(
            iteration=4,
            next_worker="remediation_drafter",
            reasoning="Gap Hunter identified 4 coverage gap(s) against the GDPR disclosure checklist.",
            is_terminal=False,
        ),
        SupervisorDecision(
            iteration=5,
            next_worker="report_writer",
            reasoning="Drafted 5 remediation(s): 1 for non-compliant findings, 4 for gaps. Skipped 0 compliant finding(s). Skipped 1 unclear finding(s) (routed to manual review).",
            is_terminal=False,
        ),
        SupervisorDecision(
            iteration=6,
            next_worker=None,
            reasoning="Report Writer assembled final AuditReport. Audit complete: 11 statements, 11 findings, 4 gaps, 5 remediations.",
            is_terminal=True,
        ),
    ]

    return AuditReport(
        audit_id="audit-demo-fixture",
        policy_source="demo-fixture (synthetic, no LLM)",
        created_at=datetime.now(UTC),
        statements=statements,
        findings=findings,
        gaps=gaps,
        remediations=remediations,
        decisions=decisions,
        executive_summary=(
            "This privacy policy contains 10 clear GDPR violations spanning data "
            "minimisation, lawful basis, retention, user rights, children's data, "
            "international transfers, security, and controller identification. "
            "One additional statement requires manual review. Four mandatory "
            "disclosure gaps were also identified. Immediate remediation is needed; "
            "the policy as written is not fit for use under GDPR."
        ),
        markdown_report=(
            "# GDPR Compliance Audit Report\n\n"
            "## Executive Summary\n\n"
            "This privacy policy contains 10 clear GDPR violations spanning data "
            "minimisation, lawful basis, retention, user rights, children's data, "
            "international transfers, security, and controller identification. "
            "One additional statement requires manual review. Four mandatory "
            "disclosure gaps were also identified. Immediate remediation is needed.\n\n"
            "## Statement-by-Statement Findings\n\n"
            "### Violations (10)\n\n"
            "All 10 violations are critical and need direct remediation. See the "
            "Remediations panel for suggested replacements.\n\n"
            "### Unclear (1)\n\n"
            "One statement requires manual review.\n\n"
            "## Coverage Gaps (4)\n\n"
            "Four mandatory GDPR disclosures are absent. See the Gaps panel for details.\n\n"
            "## Remediations (5)\n\n"
            "Five remediation drafts have been prepared.\n\n"
            "## Methodology Note\n\n"
            "This report was generated by an automated multi-agent audit system. "
            "Findings marked as 'unclear' require human assessment before a final "
            "determination. All citations reference specific GDPR provisions for "
            "traceability."
        ),
    )