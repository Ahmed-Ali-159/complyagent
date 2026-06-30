"""Tests for stream_audit: events emitted per node, terminal event has report."""

from unittest.mock import patch

import pytest

from complyagent.schemas.enums import (
    GapSeverity,
    StatementCategory,
    VerdictType,
)
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk
from complyagent.schemas.report import AuditReport
from complyagent.supervisor.events import AuditCompleteEvent, AuditEvent
from complyagent.supervisor.run_audit import stream_audit


def _stmt(stmt_id: str = "stmt-001") -> PolicyStatement:
    return PolicyStatement(
        statement_id=stmt_id,
        text="Test statement.",
        category=StatementCategory.DATA_COLLECTION,
        source_span=None,
    )


def _chunk() -> RegulationChunk:
    return RegulationChunk(chunk_id="GDPR-Art-6-1-a", text="GDPR text.")


def _finding(stmt_id: str = "stmt-001") -> Finding:
    return Finding(
        statement_id=stmt_id,
        verdict=VerdictType.COMPLIANT,
        rationale="A rationale long enough to pass validation.",
        citations=["GDPR-Art-6-1-a"],
        confidence=0.9,
    )


def _gap() -> Gap:
    return Gap(
        gap_id="gap-001",
        requirement="Identity of the controller.",
        gdpr_basis=["GDPR-Art-13-1-a"],
        severity=GapSeverity.CRITICAL,
        rationale="No statement identifies the controller.",
    )


def _remediation() -> Remediation:
    return Remediation(
        remediation_id="rem-001",
        target_id="gap-001",
        target_kind="gap",
        recommendation="Add a clause identifying the controller.",
        suggested_policy_text="The data controller is [Company Name].",
        related_citations=["GDPR-Art-13-1-a"],
    )


def _report() -> AuditReport:
    return AuditReport(
        audit_id="audit-test-001",
        policy_source="test.txt",
        executive_summary="Executive summary long enough to pass validation.",
        markdown_report="# GDPR Compliance Audit Report\n\nMarkdown body long enough to pass min_length validation.",
    )


def _patch_all_workers(statements, chunks, findings, gaps, remediations, report):
    chunks_by_id = {s.statement_id: chunks for s in statements}
    return [
        patch("complyagent.supervisor.graph.parse_policy", return_value=statements),
        patch("complyagent.supervisor.graph.research_statement",
              side_effect=lambda stmt: chunks_by_id.get(stmt.statement_id, [])),
        patch("complyagent.supervisor.graph.analyze_statement",
              side_effect=lambda stmt, c: next(f for f in findings if f.statement_id == stmt.statement_id)),
        patch("complyagent.supervisor.graph.hunt_gaps", return_value=gaps),
        patch("complyagent.supervisor.graph.draft_remediation",
              side_effect=lambda target, original_statement, remediation_id: remediations[
                  int(remediation_id.split("-")[1]) - 1
              ]),
        patch("complyagent.supervisor.graph.write_report", return_value=report),
    ]


def test_stream_audit_yields_events_per_node():
    statements = [_stmt()]
    findings = [_finding()]
    patches = _patch_all_workers(statements, [_chunk()], findings, [_gap()], [_remediation()], _report())
    for p in patches:
        p.start()
    try:
        events = list(stream_audit(
            raw_policy_text="Some policy text.",
            audit_mode="full_policy",
            policy_source="test.txt",
        ))
    finally:
        for p in patches:
            p.stop()

    # We expect at least one AuditEvent per node + a terminal AuditCompleteEvent.
    progress_events = [e for e in events if isinstance(e, AuditEvent)]
    complete_events = [e for e in events if isinstance(e, AuditCompleteEvent)]

    assert len(progress_events) >= 5  # parser, process_statement, check_confidence, route, gap_hunter, remediation, report_writer = at least 5+ depending on filtering
    assert len(complete_events) == 1


def test_stream_audit_terminal_event_carries_report():
    statements = [_stmt()]
    findings = [_finding()]
    patches = _patch_all_workers(statements, [_chunk()], findings, [_gap()], [_remediation()], _report())
    for p in patches:
        p.start()
    try:
        events = list(stream_audit(
            raw_policy_text="Some policy text.",
            audit_mode="full_policy",
            policy_source="test.txt",
        ))
    finally:
        for p in patches:
            p.stop()

    complete = events[-1]
    assert isinstance(complete, AuditCompleteEvent)
    assert complete.report.audit_id == "audit-test-001"
    assert complete.report.executive_summary.startswith("Executive summary")


def test_stream_audit_events_carry_running_stats():
    statements = [_stmt("stmt-001"), _stmt("stmt-002")]
    findings = [_finding("stmt-001"), _finding("stmt-002")]
    patches = _patch_all_workers(statements, [_chunk()], findings, [_gap()], [_remediation()], _report())
    for p in patches:
        p.start()
    try:
        events = list(stream_audit(
            raw_policy_text="Some policy text.",
            audit_mode="full_policy",
            policy_source="test.txt",
        ))
    finally:
        for p in patches:
            p.stop()

    # Find the final progress event before completion — should have full stats.
    progress_events = [e for e in events if isinstance(e, AuditEvent)]
    last_progress = progress_events[-1]
    assert last_progress.stats["statements"] >= 2
    assert last_progress.stats["gaps"] == 1
    assert last_progress.stats["remediations"] == 1


def test_stream_audit_progress_events_carry_decisions():
    statements = [_stmt()]
    findings = [_finding()]
    patches = _patch_all_workers(statements, [_chunk()], findings, [_gap()], [_remediation()], _report())
    for p in patches:
        p.start()
    try:
        events = list(stream_audit(
            raw_policy_text="Some policy text.",
            audit_mode="full_policy",
            policy_source="test.txt",
        ))
    finally:
        for p in patches:
            p.stop()

    progress_events = [e for e in events if isinstance(e, AuditEvent)]
    # At least some events should carry a decision (parser does for sure).
    events_with_decisions = [e for e in progress_events if e.decision is not None]
    assert len(events_with_decisions) >= 1
    # And every decision's reasoning should be non-trivial.
    for e in events_with_decisions:
        assert len(e.decision.reasoning) >= 5