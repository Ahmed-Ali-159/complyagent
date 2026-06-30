"""Public entry points for running ComplyAgent audits.

run_audit:    blocking — returns the final AuditReport when done.
stream_audit: streaming — yields AuditEvent objects per node, then a final
              AuditCompleteEvent carrying the report. Use this for UIs.
"""

from typing import Iterator, Literal
from uuid import uuid4

from complyagent.schemas.report import AuditReport
from complyagent.schemas.supervisor import SupervisorState
from complyagent.supervisor.events import AuditCompleteEvent, AuditEvent
from complyagent.supervisor.graph import build_graph


_compiled_graph = build_graph()


def run_audit(
    raw_policy_text: str,
    audit_mode: Literal["single_clause", "full_policy"],
    policy_source: str = "(unspecified)",
    audit_id: str | None = None,
) -> AuditReport:
    """Run an end-to-end GDPR compliance audit.

    Args:
        raw_policy_text: The full text of the privacy policy to audit.
        audit_mode: 'single_clause' for one clause, 'full_policy' for full document.
        policy_source: Identifier for the policy (filename, URL, etc.).
        audit_id: Stable ID for this audit run. Auto-generated if None.

    Returns:
        AuditReport with all worker outputs, executive summary, and markdown.

    Raises:
        ValueError: if the graph terminates without producing a report (should
            not happen in normal operation — the Report Writer is the terminal
            node and always produces an AuditReport).
    """
    if audit_id is None:
        audit_id = f"audit-{uuid4().hex[:8]}"

    initial_state = SupervisorState(
        audit_id=audit_id,
        policy_source=policy_source,
        raw_policy_text=raw_policy_text,
        audit_mode=audit_mode,
    )

    final_state = _compiled_graph.invoke(initial_state)

    # final_state is a dict (LangGraph's merged-state return shape).
    report = final_state.get("report")
    if report is None:
        raise ValueError(
            f"run_audit: graph terminated without producing an AuditReport. "
            f"Final iteration={final_state.get('iteration')}, "
            f"decisions={len(final_state.get('decisions', []))}."
        )
    return report

def stream_audit(
    raw_policy_text: str,
    audit_mode: Literal["single_clause", "full_policy"],
    policy_source: str = "(unspecified)",
    audit_id: str | None = None,
) -> Iterator[AuditEvent | AuditCompleteEvent]:
    """Run an audit, yielding progress events per node completion.

    Yields one AuditEvent per LangGraph node finish, then one AuditCompleteEvent
    carrying the final AuditReport. Use this for UIs that need live progress;
    use run_audit() instead for callers that only need the final result.
    """
    if audit_id is None:
        audit_id = f"audit-{uuid4().hex[:8]}"

    initial_state = SupervisorState(
        audit_id=audit_id,
        policy_source=policy_source,
        raw_policy_text=raw_policy_text,
        audit_mode=audit_mode,
    )

    # LangGraph's stream() with mode="updates" yields {node_name: state_update}
    # per node completion. We track running totals across events ourselves.
    running_stats = {
        "statements": 0,
        "findings": 0,
        "gaps": 0,
        "remediations": 0,
    }
    emitted_keys: set[tuple[str, int]] = set()
    final_report: AuditReport | None = None

    for chunk in _compiled_graph.stream(initial_state, stream_mode="updates"):
        # chunk is {node_name: partial_state_update} for the just-completed node.
        # In fan-out cases (Send), multiple branches finish in one tick and
        # produce one chunk per branch.
        for node_name, update in chunk.items():
            if not isinstance(update, dict):
                continue

            # Update running stats from any list fields the node wrote.
            if "statements" in update:
                running_stats["statements"] = max(
                    running_stats["statements"], len(update["statements"])
                )
            if "findings" in update:
                running_stats["findings"] = max(
                    running_stats["findings"], running_stats["findings"] + len(update["findings"])
                )
            if "gaps" in update:
                running_stats["gaps"] = len(update["gaps"])
            if "remediations" in update:
                running_stats["remediations"] = len(update["remediations"])

            # Extract the latest decision (if any) appended by this node.
            new_decisions = update.get("decisions", [])
            latest_decision = new_decisions[-1] if new_decisions else None

            # Capture the final report from the terminal node.
            if node_name == "report_writer" and "report" in update:
                final_report = update["report"]

            # Only emit events for node names in our enum; LangGraph internal
            # nodes (like the dummy "route" passthrough) we still emit so the
            # UI sees the case-routing decision logged there.
            if node_name in {
                "parser",
                "process_statement",
                "check_confidence",
                "route",
                "gap_hunter",
                "remediation",
                "report_writer",
            }:
                # Dedupe by (phase, decision_iteration). LangGraph can emit
                # the same node update multiple times during a single tick;
                # we only yield each (phase, iteration) pair once.
                # Events without a decision (e.g. fan-out branches that don't
                # log) get a synthetic key based on stats so they pass through.
                if latest_decision is not None:
                    key = (node_name, latest_decision.iteration)
                else:
                    # Use a stats fingerprint as the "iteration" for None cases.
                    # Two consecutive None events with same stats = duplicate.
                    key = (node_name, hash(tuple(sorted(running_stats.items()))))

                if key in emitted_keys:
                    continue
                emitted_keys.add(key)

                yield AuditEvent(
                    phase=node_name,
                    decision=latest_decision,
                    stats=dict(running_stats),
                )

    if final_report is None:
        raise ValueError(
            "stream_audit: graph terminated without producing an AuditReport."
        )
    yield AuditCompleteEvent(report=final_report)