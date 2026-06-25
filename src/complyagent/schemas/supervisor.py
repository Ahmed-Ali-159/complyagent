"""LangGraph supervisor state and routing decisions."""
from __future__ import annotations

from datetime import datetime, UTC

from pydantic import BaseModel, Field

from complyagent.schemas.enums import WorkerName
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk
from complyagent.schemas.report import AuditReport


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


class SupervisorState(BaseModel):
    """The mutable state object that flows through the LangGraph."""

    # Audit metadata - The original inputs. Never modified after the audit starts
    audit_id: str = Field(..., description="Unique ID for this audit run.")
    policy_source: str = Field(..., description="Name or URL of the policy being audited.")
    raw_policy_text: str = Field(..., description="Full text of the policy under audit.")

    # Outputs accumulated by workers
    statements: list[PolicyStatement] = Field(default_factory=list)     # filled by Policy Parser
    retrieved_chunks: dict[str, list[RegulationChunk]] = Field(         # filled by Researcher
        default_factory=dict,
        description="Mapping of statement_id (or query key) → retrieved chunks.",
    )
    findings: list[Finding] = Field(default_factory=list)               # filled by Analyst
    gaps: list[Gap] = Field(default_factory=list)                       # filled by Gap Hunter
    remediations: list[Remediation] = Field(default_factory=list)       # filled by Remediation Drafter
    report: AuditReport | None = Field(None, description="Set once the Report Writer runs.")    # filled by Report Writer (last)

    # Supervisor bookkeeping
    iteration: int = Field(0, ge=0, description="Current supervisor turn number.")  # current turn number -> checked against graph.max_iterations (15) as a hard ceiling.
    decisions: list[SupervisorDecision] = Field(    # the reasoning log -> he audit trail; grows by one per supervisor turn.
        default_factory=list,
        description="Full routing log — what makes this audit explainable.",
    )
    reretrieval_counts: dict[str, int] = Field(     # per-statement retry counter
        default_factory=dict,
        description="Per-statement re-retrieval counter, capped by config.max_reretrieval.",
    )
    # Note about: reretrieval_counts
    # reretrieval_counts — maps statement_id → number of times the supervisor 
    # has re-dispatched the Researcher for that statement. 
    # Checked against graph.max_reretrieval (2) before triggering 
    # another retry on low-confidence findings.