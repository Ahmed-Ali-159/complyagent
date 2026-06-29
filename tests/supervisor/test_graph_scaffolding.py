"""Sub-phase 4.1: verify the graph scaffolding wires correctly.

These tests mock all six worker functions and check that the graph invokes
them in the right order with the right inputs. They do NOT test worker
behavior (that's Phase 3) or LangGraph internals (that's LangChain).
"""

from unittest.mock import patch, MagicMock

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
from complyagent.schemas.supervisor import SupervisorState
from complyagent.supervisor.graph import build_graph


# Helpers ---------------------------------------------------------------------

def _make_state(raw_text: str = "Some policy text.") -> SupervisorState:
    return SupervisorState(
        audit_id="audit-test-001",
        policy_source="test.txt",
        raw_policy_text=raw_text,
        audit_mode="full_policy",
    )


def _stmt(stmt_id: str, text: str = "Test statement.") -> PolicyStatement:
    return PolicyStatement(
        statement_id=stmt_id,
        text=text,
        category=StatementCategory.DATA_COLLECTION,
        source_span=None,
    )


def _chunk(chunk_id: str = "GDPR-Art-6-1-a") -> RegulationChunk:
    return RegulationChunk(chunk_id=chunk_id, text="GDPR text.")


def _finding(stmt_id: str, verdict=VerdictType.COMPLIANT) -> Finding:
    return Finding(
        statement_id=stmt_id,
        verdict=verdict,
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


def _remediation(rem_id: str = "rem-001") -> Remediation:
    return Remediation(
        remediation_id=rem_id,
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
        executive_summary="Executive summary that is long enough to pass validation.",
        markdown_report="# Report\n\nMarkdown body that is also long enough to pass min length.",
    )


# Patch context for all six workers -------------------------------------------

def _patch_all_workers(
    statements: list[PolicyStatement],
    chunks_per_statement: dict[str, list[RegulationChunk]],
    findings: list[Finding],
    gaps: list[Gap],
    remediations: list[Remediation],
    report: AuditReport,
):
    """Returns a list of patch context managers to enter together."""
    return [
        patch("complyagent.supervisor.graph.parse_policy", return_value=statements),
        patch(
            "complyagent.supervisor.graph.research_statement",
            side_effect=lambda stmt: chunks_per_statement.get(stmt.statement_id, []),
        ),
        patch(
            "complyagent.supervisor.graph.analyze_statement",
            side_effect=lambda stmt, chunks: next(
                f for f in findings if f.statement_id == stmt.statement_id
            ),
        ),
        patch("complyagent.supervisor.graph.hunt_gaps", return_value=gaps),
        patch(
            "complyagent.supervisor.graph.draft_remediation",
            side_effect=lambda target, original_statement, remediation_id: remediations[
                int(remediation_id.split("-")[1]) - 1
            ],
        ),
        patch("complyagent.supervisor.graph.write_report", return_value=report),
    ]


# Tests -----------------------------------------------------------------------

def test_graph_runs_full_case2_path_end_to_end():
    """Happy path: 2 statements, both compliant + 1 gap + 1 remediation for the gap."""
    statements = [_stmt("stmt-001"), _stmt("stmt-002")]
    chunks_by_id = {
        "stmt-001": [_chunk("GDPR-Art-6-1-a")],
        "stmt-002": [_chunk("GDPR-Art-6-1-b")],
    }
    findings = [_finding("stmt-001"), _finding("stmt-002")]
    gaps = [_gap()]
    remediations = [_remediation("rem-001")]
    report = _report()

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    # final_state is a dict (LangGraph returns the merged state as a dict).
    assert len(final_state["statements"]) == 2
    assert len(final_state["findings"]) == 2
    assert len(final_state["gaps"]) == 1
    assert len(final_state["remediations"]) == 1
    assert final_state["report"] is not None
    assert final_state["report"].audit_id == "audit-test-001"


def test_remediation_node_skips_compliant_findings():
    """A compliant finding should not produce a remediation."""
    statements = [_stmt("stmt-001"), _stmt("stmt-002")]
    chunks_by_id = {
        "stmt-001": [_chunk()],
        "stmt-002": [_chunk()],
    }
    findings = [
        _finding("stmt-001", verdict=VerdictType.COMPLIANT),
        _finding("stmt-002", verdict=VerdictType.VIOLATION),
    ]
    gaps: list[Gap] = []
    remediations = [_remediation("rem-001")]  # Only one — for the violation.
    report = _report()

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    # Only the violation gets a remediation; compliant is skipped.
    assert len(final_state["remediations"]) == 1


def test_remediation_node_skips_unclear_findings():
    """Unclear verdicts should also not produce remediations."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001", verdict=VerdictType.UNCLEAR)]
    gaps: list[Gap] = []
    remediations: list[Remediation] = []
    report = _report()

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    assert len(final_state["remediations"]) == 0


def test_remediation_node_processes_all_gaps():
    """Every Gap gets a remediation, regardless of finding verdicts."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001", verdict=VerdictType.COMPLIANT)]
    gaps = [_gap(), _gap()]
    remediations = [_remediation("rem-001"), _remediation("rem-002")]
    report = _report()

    # Mutate gap IDs so they're distinct (helper builds identical ones).
    gaps[1] = Gap(
        gap_id="gap-002",
        requirement="Different requirement.",
        gdpr_basis=["GDPR-Art-13-1-b"],
        severity=GapSeverity.HIGH,
        rationale="A different gap rationale.",
    )

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    assert len(final_state["remediations"]) == 2


def test_case1_skips_gap_hunter():
    """Case 1 (single_clause) routes from process_statement straight to remediation."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001", verdict=VerdictType.VIOLATION)]
    gaps: list[Gap] = []
    remediations = [_remediation("rem-001")]
    report = _report()

    # State with audit_mode="single_clause".
    state = SupervisorState(
        audit_id="audit-test-001",
        policy_source="test.txt",
        raw_policy_text="Some policy text.",
        audit_mode="single_clause",
    )

    # Spy on hunt_gaps to confirm it's never called.
    hunt_gaps_spy = MagicMock(return_value=[])

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    # Replace the hunt_gaps patch with our spy.
    patches = [p for p in patches if "hunt_gaps" not in str(p)]
    hunt_patch = patch("complyagent.supervisor.graph.hunt_gaps", hunt_gaps_spy)
    patches.append(hunt_patch)

    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(state)
    finally:
        for p in patches:
            p.stop()

    # Gap Hunter must not have been called.
    hunt_gaps_spy.assert_not_called()
    # Remediation still produces output for the violation finding.
    assert len(final_state["remediations"]) == 1
    assert final_state["report"] is not None


def test_case2_runs_gap_hunter():
    """Case 2 (full_policy) routes through gap_hunter normally."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001", verdict=VerdictType.COMPLIANT)]
    gaps = [_gap()]
    remediations = [_remediation("rem-001")]
    report = _report()

    hunt_gaps_spy = MagicMock(return_value=gaps)

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    patches = [p for p in patches if "hunt_gaps" not in str(p)]
    hunt_patch = patch("complyagent.supervisor.graph.hunt_gaps", hunt_gaps_spy)
    patches.append(hunt_patch)

    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())  # default audit_mode="full_policy"
    finally:
        for p in patches:
            p.stop()

    hunt_gaps_spy.assert_called_once()
    assert len(final_state["gaps"]) == 1


def test_low_confidence_finding_triggers_retry():
    """A finding with confidence < 0.6 should cause process_statement to re-run."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}

    call_count = {"n": 0}
    def analyze_side_effect(stmt, chunks):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return Finding(
                statement_id=stmt.statement_id,
                verdict=VerdictType.UNCLEAR,
                rationale="First pass had insufficient retrieval.",
                citations=[],
                confidence=0.3,
            )
        return Finding(
            statement_id=stmt.statement_id,
            verdict=VerdictType.COMPLIANT,
            rationale="Second pass succeeded with new chunks.",
            citations=["GDPR-Art-6-1-a"],
            confidence=0.9,
        )

    report = _report()
    patches = [
        patch("complyagent.supervisor.graph.parse_policy", return_value=statements),
        patch("complyagent.supervisor.graph.research_statement",
              side_effect=lambda stmt: chunks_by_id[stmt.statement_id]),
        patch("complyagent.supervisor.graph.analyze_statement",
              side_effect=analyze_side_effect),
        patch("complyagent.supervisor.graph.hunt_gaps", return_value=[]),
        patch("complyagent.supervisor.graph.write_report", return_value=report),
    ]

    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    assert call_count["n"] == 2
    assert len(final_state["findings"]) == 1
    assert final_state["findings"][0].confidence == 0.9


def test_retry_cap_enforced():
    """If retries always return low confidence, retries stop at MAX_RERETRIEVAL."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    call_count = {"n": 0}

    def analyze_side_effect(stmt, chunks):
        call_count["n"] += 1
        return Finding(
            statement_id=stmt.statement_id,
            verdict=VerdictType.UNCLEAR,
            rationale="Persistent low confidence — bad query rewriting.",
            citations=[],
            confidence=0.3,
        )

    report = _report()
    patches = [
        patch("complyagent.supervisor.graph.parse_policy", return_value=statements),
        patch("complyagent.supervisor.graph.research_statement",
              side_effect=lambda stmt: chunks_by_id[stmt.statement_id]),
        patch("complyagent.supervisor.graph.analyze_statement",
              side_effect=analyze_side_effect),
        patch("complyagent.supervisor.graph.hunt_gaps", return_value=[]),
        patch("complyagent.supervisor.graph.write_report", return_value=report),
    ]

    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    assert call_count["n"] == 3
    assert final_state["reretrieval_counts"]["stmt-001"] == 2
    assert len(final_state["findings"]) == 1
    assert final_state["findings"][0].confidence == 0.3


def test_high_confidence_skips_retry():
    """A high-confidence first finding should mean zero retries."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001")]
    report = _report()

    patches = _patch_all_workers(statements, chunks_by_id, findings, [], [], report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    assert final_state["reretrieval_counts"] == {}
    assert len(final_state["findings"]) == 1


def test_decision_log_is_populated_through_full_audit():
    """Every node should append exactly one SupervisorDecision to state.decisions."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001")]
    gaps = [_gap()]
    remediations = [_remediation("rem-001")]
    report = _report()

    patches = _patch_all_workers(statements, chunks_by_id, findings, gaps, remediations, report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    decisions = final_state["decisions"]
    # Full Case 2 happy path: parser, check_confidence, route, gap_hunter,
    # remediation, report_writer = 6 decisions.
    assert len(decisions) == 6
    # Iteration counter equals decision count.
    assert final_state["iteration"] == 6
    # Last decision is the terminal one.
    assert decisions[-1].is_terminal is True
    assert decisions[-1].next_worker is None
    # Each decision has a non-trivial reasoning string.
    for d in decisions:
        assert len(d.reasoning) >= 5


def test_decision_log_records_case1_routing():
    """Case 1 should record the 'skipping Gap Hunter' decision."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}
    findings = [_finding("stmt-001", verdict=VerdictType.VIOLATION)]
    remediations = [_remediation("rem-001")]
    report = _report()

    state = SupervisorState(
        audit_id="audit-test-001",
        policy_source="test.txt",
        raw_policy_text="Some policy text.",
        audit_mode="single_clause",
    )

    patches = _patch_all_workers(statements, chunks_by_id, findings, [], remediations, report)
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(state)
    finally:
        for p in patches:
            p.stop()

    decisions = final_state["decisions"]
    # Case 1: parser, check_confidence, route, remediation, report_writer = 5 decisions.
    assert len(decisions) == 5
    # The route decision should mention Case 1.
    route_decisions = [d for d in decisions if "Case 1" in d.reasoning]
    assert len(route_decisions) == 1


def test_decision_log_records_retry():
    """A retry should produce check_confidence decisions on both turns."""
    statements = [_stmt("stmt-001")]
    chunks_by_id = {"stmt-001": [_chunk()]}

    call_count = {"n": 0}
    def analyze_side_effect(stmt, chunks):
        call_count["n"] += 1
        confidence = 0.3 if call_count["n"] == 1 else 0.9
        verdict = VerdictType.UNCLEAR if call_count["n"] == 1 else VerdictType.COMPLIANT
        return Finding(
            statement_id=stmt.statement_id,
            verdict=verdict,
            rationale="Decision test rationale.",
            citations=["GDPR-Art-6-1-a"] if call_count["n"] == 2 else [],
            confidence=confidence,
        )

    report = _report()
    patches = [
        patch("complyagent.supervisor.graph.parse_policy", return_value=statements),
        patch("complyagent.supervisor.graph.research_statement",
              side_effect=lambda stmt: chunks_by_id[stmt.statement_id]),
        patch("complyagent.supervisor.graph.analyze_statement",
              side_effect=analyze_side_effect),
        patch("complyagent.supervisor.graph.hunt_gaps", return_value=[]),
        patch("complyagent.supervisor.graph.write_report", return_value=report),
    ]
    for p in patches:
        p.start()
    try:
        graph = build_graph()
        final_state = graph.invoke(_make_state())
    finally:
        for p in patches:
            p.stop()

    decisions = final_state["decisions"]
    # Retry decisions: one says "retrying", the next (after retry succeeds) says "above threshold".
    retry_mentions = [d for d in decisions if "retry" in d.reasoning.lower()]
    threshold_mentions = [d for d in decisions if "above confidence threshold" in d.reasoning.lower()]
    assert len(retry_mentions) >= 1
    assert len(threshold_mentions) >= 1