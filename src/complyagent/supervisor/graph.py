"""LangGraph definition for the ComplyAgent supervisor.

Sub-phase 4.1: static linear Case-2-only topology. No routing decisions yet,
no retries, no Case 1 branch. Each worker node reads inputs from
SupervisorState and returns a partial-state update; LangGraph merges via
the reducers we annotated on the schema.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from complyagent.config import settings

from complyagent.agents.analyst import analyze_statement
from complyagent.agents.gap_hunter import hunt_gaps
from complyagent.agents.parser import parse_policy
from complyagent.agents.remediation import draft_remediation
from complyagent.agents.report_writer import write_report
from complyagent.agents.researcher import research_statement
from complyagent.schemas.enums import VerdictType
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.supervisor import SupervisorState
from complyagent.schemas.regulation import RegulationChunk
from complyagent.schemas.enums import WorkerName
from complyagent.schemas.report import SupervisorDecision
from complyagent.schemas.supervisor import SupervisorState

# Sub-phase 4.4 thresholds. Sourced from settings to keep tunable via config.
CONFIDENCE_THRESHOLD = settings.graph.confidence_threshold  # default 0.6
MAX_RERETRIEVAL = settings.graph.max_reretrieval            # default 2

MAX_ITERATIONS = settings.graph.max_iterations  # 15


def _make_decision(
    state: SupervisorState,
    reasoning: str,
    next_worker: WorkerName | None = None,
    is_terminal: bool = False,
) -> SupervisorDecision:
    """Build a SupervisorDecision with iteration = current_count + 1.

    Iteration is bumped once per decision, so len(state.decisions) after
    this call equals state.iteration. Callers append to decisions via the
    state-return dict; the iteration field is updated via this helper's
    output.
    """
    return SupervisorDecision(
        iteration=state.iteration + 1,
        next_worker=next_worker,
        reasoning=reasoning,
        is_terminal=is_terminal,
    )


# --- Node functions ----------------------------------------------------------
# Each node takes the full state and returns a partial-state dict. LangGraph
# merges the returned dict into the global state using the reducers we
# annotated on SupervisorState fields.

def parser_node(state: SupervisorState) -> dict:
    statements = parse_policy(state.raw_policy_text)
    decision = _make_decision(
        state,
        reasoning=(
            f"Parser extracted {len(statements)} statement(s) from policy "
            f"{state.policy_source!r}. Audit mode = {state.audit_mode}."
        ),
        next_worker=WorkerName.REGULATION_RESEARCHER,
    )
    return {
        "statements": statements,
        "decisions": [decision],
        "iteration": decision.iteration,
    }


def process_statement_node(state: dict) -> dict:
    """Process ONE statement: research then analyze.

    Fanned out via Send from after the Parser. Combining Researcher + Analyst
    into one node avoids fan-out-of-fan-out duplication and reflects the real
    per-statement coupling (you never research statement A and analyze B).
    """
    stmt: PolicyStatement = state["statement"]
    chunks = research_statement(stmt)
    finding = analyze_statement(stmt, chunks)
    return {
        "retrieved_chunks": {stmt.statement_id: chunks},
        "findings": [finding],
    }

def check_confidence_node(state: SupervisorState) -> dict:
    """Identify statements eligible for retry and log the decision."""
    new_counts: dict[str, int] = dict(state.reretrieval_counts)
    to_retry: list[str] = []

    for finding in state.findings:
        if finding.confidence >= CONFIDENCE_THRESHOLD:
            continue
        current = new_counts.get(finding.statement_id, 0)
        if current < MAX_RERETRIEVAL:
            new_counts[finding.statement_id] = current + 1
            to_retry.append(finding.statement_id)

    # Build reasoning string describing what we decided and why.
    if to_retry:
        reasoning = (
            f"Found {len(to_retry)} low-confidence finding(s) eligible for "
            f"retry: {to_retry}. Re-dispatching process_statement."
        )
        next_worker = WorkerName.REGULATION_RESEARCHER
    else:
        low_conf_capped = [
            f.statement_id for f in state.findings
            if f.confidence < CONFIDENCE_THRESHOLD
        ]
        if low_conf_capped:
            reasoning = (
                f"{len(low_conf_capped)} finding(s) remain below confidence "
                f"threshold ({low_conf_capped}) but retry cap of "
                f"{MAX_RERETRIEVAL} reached. Accepting current findings."
            )
        else:
            reasoning = (
                f"All {len(state.findings)} finding(s) above confidence "
                f"threshold {CONFIDENCE_THRESHOLD}. Proceeding."
            )
        next_worker = None  # the case router picks the actual next worker.

    decision = _make_decision(state, reasoning=reasoning, next_worker=next_worker)

    return {
        "reretrieval_counts": new_counts,
        "pending_retry_ids": to_retry,
        "decisions": [decision],
        "iteration": decision.iteration,
    }


def route_after_confidence_check(state: SupervisorState) -> str | list[Send]:
    """Fan out retries, OR proceed forward, OR force-stop if iteration cap hit."""
    # Hard ceiling: if we've already burned MAX_ITERATIONS supervisor decisions,
    # force the audit forward even if retries remain. Guards against runaway loops.
    if state.iteration >= MAX_ITERATIONS:
        return "route"

    if not state.pending_retry_ids:
        return "route"

    statements_by_id = {s.statement_id: s for s in state.statements}
    return [
        Send("process_statement", {"statement": statements_by_id[sid]})
        for sid in state.pending_retry_ids
        if sid in statements_by_id
    ]


def gap_hunter_node(state: SupervisorState) -> dict:
    gaps = hunt_gaps(state.statements)
    decision = _make_decision(
        state,
        reasoning=(
            f"Gap Hunter identified {len(gaps)} coverage gap(s) against "
            f"the GDPR disclosure checklist."
        ),
        next_worker=WorkerName.REMEDIATION_DRAFTER,
    )
    return {
        "gaps": gaps,
        "decisions": [decision],
        "iteration": decision.iteration,
    }


def remediation_node(state: SupervisorState) -> dict:
    """Filter Findings to violation/partial only; remediate those + all Gaps.
    Log which findings were skipped and why.
    """
    statements_by_id = {s.statement_id: s for s in state.statements}

    qualifying_findings: list[Finding] = []
    skipped_compliant: list[str] = []
    skipped_unclear: list[str] = []
    for f in state.findings:
        if f.verdict in {VerdictType.VIOLATION, VerdictType.PARTIAL}:
            qualifying_findings.append(f)
        elif f.verdict == VerdictType.COMPLIANT:
            skipped_compliant.append(f.statement_id)
        elif f.verdict == VerdictType.UNCLEAR:
            skipped_unclear.append(f.statement_id)

    remediations: list[Remediation] = []
    rem_counter = 1

    for finding in qualifying_findings:
        original = statements_by_id.get(finding.statement_id)
        if original is None:
            raise ValueError(
                f"remediation_node: Finding {finding.statement_id!r} "
                f"has no matching statement in state."
            )
        remediations.append(draft_remediation(
            target=finding,
            original_statement=original,
            remediation_id=f"rem-{rem_counter:03d}",
        ))
        rem_counter += 1

    for gap in state.gaps:
        remediations.append(draft_remediation(
            target=gap,
            original_statement=None,
            remediation_id=f"rem-{rem_counter:03d}",
        ))
        rem_counter += 1

    reasoning_parts = [
        f"Drafted {len(remediations)} remediation(s): "
        f"{len(qualifying_findings)} for non-compliant findings, "
        f"{len(state.gaps)} for gaps."
    ]
    if skipped_compliant:
        reasoning_parts.append(
            f"Skipped {len(skipped_compliant)} compliant finding(s): {skipped_compliant}."
        )
    if skipped_unclear:
        reasoning_parts.append(
            f"Skipped {len(skipped_unclear)} unclear finding(s) "
            f"(routed to manual review): {skipped_unclear}."
        )

    decision = _make_decision(
        state,
        reasoning=" ".join(reasoning_parts),
        next_worker=WorkerName.REPORT_WRITER,
    )
    return {
        "remediations": remediations,
        "decisions": [decision],
        "iteration": decision.iteration,
    }


def report_writer_node(state: SupervisorState) -> dict:
    report = write_report(state)
    decision = _make_decision(
        state,
        reasoning=(
            f"Report Writer assembled final AuditReport. Audit complete: "
            f"{len(state.statements)} statements, {len(state.findings)} findings, "
            f"{len(state.gaps)} gaps, {len(state.remediations)} remediations."
        ),
        next_worker=None,
        is_terminal=True,
    )
    return {
        "report": report,
        "decisions": [decision],
        "iteration": decision.iteration,
    }


# --- Fan-out dispatchers -----------------------------------------------------
# Send creates per-statement invocations of researcher_node/analyst_node.
# Each Send payload becomes the "state" the per-item node sees.

def fan_out_per_statement(state: SupervisorState) -> list[Send]:
    """Fan out one process_statement invocation per statement."""
    return [Send("process_statement", {"statement": stmt}) for stmt in state.statements]

def route_after_processing(state: SupervisorState) -> str:
    """Decide whether to run Gap Hunter or skip straight to Remediation.

    Case 1 (single_clause): skip Gap Hunter — coverage analysis against a
    mandatory-disclosure checklist doesn't make sense for one clause.
    Case 2 (full_policy): run Gap Hunter normally.
    """
    if state.audit_mode == "single_clause":
        return "remediation"
    return "gap_hunter"

def route_node(state: SupervisorState) -> dict:
    """Passthrough between check_confidence and case routing. Logs the
    Case 1 vs Case 2 decision so the audit trail shows it explicitly.
    """
    if state.audit_mode == "single_clause":
        reasoning = (
            "Case 1 (single_clause): skipping Gap Hunter — coverage analysis "
            "doesn't apply to single-clause review. Routing to Remediation."
        )
        next_worker = WorkerName.REMEDIATION_DRAFTER
    else:
        reasoning = (
            "Case 2 (full_policy): proceeding to Gap Hunter for "
            "coverage analysis against the mandatory disclosure checklist."
        )
        next_worker = WorkerName.GAP_HUNTER

    decision = _make_decision(state, reasoning=reasoning, next_worker=next_worker)
    return {"decisions": [decision], "iteration": decision.iteration}

# --- Graph construction ------------------------------------------------------

def build_graph():
    """Construct the Phase-4 LangGraph through Sub-phase 4.4."""
    graph = StateGraph(SupervisorState)

    graph.add_node("parser", parser_node)
    graph.add_node("process_statement", process_statement_node)
    graph.add_node("check_confidence", check_confidence_node)
    graph.add_node("route", route_node)
    graph.add_node("gap_hunter", gap_hunter_node)
    graph.add_node("remediation", remediation_node)
    graph.add_node("report_writer", report_writer_node)

    graph.add_edge(START, "parser")
    graph.add_conditional_edges("parser", fan_out_per_statement, ["process_statement"])
    graph.add_edge("process_statement", "check_confidence")
    graph.add_conditional_edges(
        "check_confidence",
        route_after_confidence_check,
        ["process_statement", "route"],
    )
    graph.add_conditional_edges(
        "route",
        route_after_processing,
        ["gap_hunter", "remediation"],
    )
    graph.add_edge("gap_hunter", "remediation")
    graph.add_edge("remediation", "report_writer")
    graph.add_edge("report_writer", END)

    return graph.compile()