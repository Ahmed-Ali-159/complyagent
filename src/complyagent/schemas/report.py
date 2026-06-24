"""Top-level audit report schema."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement


class AuditReport(BaseModel):
    """The final deliverable assembled by the Report Writer."""

    audit_id: str = Field(..., description="Unique ID for this audit run.")
    policy_source: str = Field(..., description="Name or URL of the audited policy.")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    statements: list[PolicyStatement] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    remediations: list[Remediation] = Field(default_factory=list)

    executive_summary: str = Field(
        ...,
        min_length=20,
        description="Plain-English overview of the audit outcome.",
    )
    markdown_report: str = Field(
        ...,
        min_length=50,
        description="Full markdown report with embedded citations.",
    )