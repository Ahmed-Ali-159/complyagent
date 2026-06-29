"""LangGraph supervisor state and routing decisions."""
from __future__ import annotations

from datetime import datetime, UTC

from pydantic import BaseModel, Field

from operator import add
from typing import Annotated, Literal

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


def _latest_finding_per_statement(
    existing: list[Finding], new: list[Finding]
) -> list[Finding]:
    """Reducer: keep the most recent Finding per statement_id.

    LangGraph calls this when merging worker output into state. Without this,
    a retry on a low-confidence finding would APPEND rather than REPLACE,
    leaving duplicate findings for the same statement_id in state.
    Order in the returned list preserves first-seen order of statement_ids
    so downstream consumers see a stable iteration order.
    """
    merged: dict[str, Finding] = {f.statement_id: f for f in existing}
    order = [f.statement_id for f in existing]
    for f in new:
        if f.statement_id not in merged:
            order.append(f.statement_id)
        merged[f.statement_id] = f  # last write wins
    return [merged[sid] for sid in order]


class SupervisorState(BaseModel):
    """The mutable state object that flows through the LangGraph."""

    # Audit metadata - The original inputs. Never modified after the audit starts
    audit_id: str = Field(..., description="Unique ID for this audit run.")
    policy_source: str = Field(..., description="Name or URL of the policy being audited.")
    raw_policy_text: str = Field(..., description="Full text of the policy under audit.")
    audit_mode: Literal["single_clause", "full_policy"] = Field(
        ...,
        description="Set at audit start; determines Case 1 vs Case 2 routing.",
    )

    # Outputs accumulated by workers — Annotated with reducers so LangGraph
    # appends/merges rather than overwriting when multiple nodes write to them.
    statements: Annotated[list[PolicyStatement], add] = Field(default_factory=list)
    retrieved_chunks: Annotated[
        dict[str, list[RegulationChunk]], lambda a, b: {**a, **b}
    ] = Field(
        default_factory=dict,
        description="Mapping of statement_id (or query key) → retrieved chunks.",
    )
    findings: Annotated[list[Finding], _latest_finding_per_statement] = Field(
        default_factory=list
    )
    gaps: Annotated[list[Gap], add] = Field(default_factory=list)
    remediations: Annotated[list[Remediation], add] = Field(default_factory=list)
    decisions: Annotated[list[SupervisorDecision], add] = Field(
        default_factory=list,
        description="Full routing log — what makes this audit explainable.",
    )
    report: AuditReport | None = Field(None, description="Set once the Report Writer runs.")    # filled by Report Writer (last)

    # Supervisor bookkeeping
    iteration: int = Field(0, ge=0, description="Current supervisor turn number.")  # current turn number -> checked against graph.max_iterations (15) as a hard ceiling.
    reretrieval_counts: dict[str, int] = Field(     # per-statement retry counter
        default_factory=dict,
        description="Per-statement re-retrieval counter, capped by config.max_reretrieval.",
    )
    # Note about: reretrieval_counts
    # reretrieval_counts — maps statement_id → number of times the supervisor 
    # has re-dispatched the Researcher for that statement. 
    # Checked against graph.max_reretrieval (2) before triggering 
    # another retry on low-confidence findings.
    pending_retry_ids: list[str] = Field(
        default_factory=list,
        description="Statement IDs scheduled for retry this iteration. "
                    "Set by check_confidence_node, consumed by the router.",
    )