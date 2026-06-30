"""Event objects yielded by stream_audit() to drive progress UIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from complyagent.schemas.report import AuditReport
from complyagent.schemas.supervisor import SupervisorDecision


class AuditEvent(BaseModel):
    """One step of progress during a streaming audit.

    Emitted after each LangGraph node completes. UIs use the `phase` field to
    render appropriate progress messages; the `decision` field carries the
    Supervisor's reasoning at this step (the most recently appended decision);
    `stats` carries running counters for at-a-glance progress display.
    """

    phase: Literal[
        "parser",
        "process_statement",
        "check_confidence",
        "route",
        "gap_hunter",
        "remediation",
        "report_writer",
    ] = Field(..., description="Which node just finished.")

    decision: SupervisorDecision | None = Field(
        None,
        description="The most recently appended SupervisorDecision, if any.",
    )

    stats: dict[str, int] = Field(
        default_factory=dict,
        description="Running counters (statements, findings, gaps, remediations).",
    )


class AuditCompleteEvent(BaseModel):
    """Terminal event yielded when the audit finishes successfully."""

    report: AuditReport