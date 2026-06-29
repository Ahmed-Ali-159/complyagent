"""Hardcoded v1 checklist of mandatory GDPR disclosures (Articles 13 and 14).

Each item is a coverage requirement: a privacy policy MUST address it, or it
counts as a gap. The Gap Hunter checks whether any policy statement addresses
each requirement; it does NOT judge the quality of how it's addressed
(that's the Analyst's job, separately).

v1 scope: the most universally-applicable mandatory disclosures from Art 13/14.
Not exhaustive — deeper coverage is post-v1 scope per project plan.
"""

from pydantic import BaseModel


class ChecklistItem(BaseModel):
    """One mandatory GDPR disclosure requirement."""
    chunk_ids: list[str]  # GDPR provisions establishing this requirement.
    requirement: str       # One-line plain-English summary for the LLM.
    severity: str          # GapSeverity value if this item is missing.


# Severity rationale:
#   CRITICAL — disclosure is structurally mandatory and absence undermines
#              the policy's legal validity (e.g. legal basis, identity).
#   HIGH     — required by GDPR but ambiguous absences may be inferable
#              from context (e.g. retention, recipients).
#   MEDIUM   — required but lower direct user impact (e.g. complaint right
#              recital language).
GDPR_DISCLOSURE_CHECKLIST: list[ChecklistItem] = [
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
        requirement="Identity and contact details of the data controller.",
        severity="critical",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-1-b", "GDPR-Art-14-1-b"],
        requirement="Contact details of the data protection officer, where applicable.",
        severity="medium",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-1-c", "GDPR-Art-14-1-c"],
        requirement="Purposes of the processing for which personal data are intended.",
        severity="critical",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-1-c", "GDPR-Art-14-1-c"],
        requirement="Legal basis for the processing.",
        severity="critical",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-1-e", "GDPR-Art-14-1-e"],
        requirement="Recipients or categories of recipients of the personal data.",
        severity="high",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-1-f", "GDPR-Art-14-1-f"],
        requirement="Whether personal data are transferred to a third country, and the safeguards used.",
        severity="high",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-2-a", "GDPR-Art-14-2-a"],
        requirement="Period for which personal data will be stored, or criteria used to determine that period.",
        severity="high",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-2-b", "GDPR-Art-14-2-c"],
        requirement="Data subject rights: access, rectification, erasure, restriction, objection, portability.",
        severity="critical",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-2-c"],
        requirement="Where processing is based on consent, the right to withdraw consent at any time.",
        severity="high",
    ),
    ChecklistItem(
        chunk_ids=["GDPR-Art-13-2-d", "GDPR-Art-14-2-e"],
        requirement="The right to lodge a complaint with a supervisory authority.",
        severity="medium",
    ),
]