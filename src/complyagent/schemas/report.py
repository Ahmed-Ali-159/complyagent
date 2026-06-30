"""Top-level audit report schema and the SupervisorDecision it carries.

SupervisorDecision lives here (rather than in supervisor.py) so that
AuditReport can directly carry a list of them without creating a circular
import — supervisor.py already imports AuditReport from this module.
"""
from __future__ import annotations

from datetime import datetime, UTC

from pydantic import BaseModel, Field

from complyagent.schemas.enums import WorkerName
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement


class SupervisorDecision(BaseModel):
    """One routing decision in the supervisor's reasoning log."""

    iteration: int = Field(..., ge=0, description="Supervisor turn number (0-indexed).")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    next_worker: WorkerName | None = Field(
        None,
        description="Worker to dispatch to, or None when ending the audit.",
    )
    reasoning: str = Field(
        ...,
        min_length=5,
        description="Why the supervisor chose this action given the current state.",
    )
    is_terminal: bool = Field(False, description="True if this decision ends the audit.")


class AuditReport(BaseModel):
    """The final deliverable assembled by the Report Writer."""

    audit_id: str = Field(..., description="Unique ID for this audit run.")
    policy_source: str = Field(..., description="Name or URL of the audited policy.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    statements: list[PolicyStatement] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    remediations: list[Remediation] = Field(default_factory=list)
    decisions: list[SupervisorDecision] = Field(
        default_factory=list,
        description="Full reasoning log from the supervisor — every routing decision made during this audit.",
    )

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