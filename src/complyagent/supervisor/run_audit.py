"""Public entry point for running a full ComplyAgent audit.

Builds the initial SupervisorState, invokes the compiled graph, and returns
the final AuditReport. This is what integration tests and the eventual
Streamlit UI call.
"""

from typing import Literal
from uuid import uuid4

from complyagent.schemas.report import AuditReport
from complyagent.schemas.supervisor import SupervisorState
from complyagent.supervisor.graph import build_graph

# Compile the graph once at module import. LangGraph compilation is
# non-trivial (validates topology, resolves edges); doing it once and
# reusing the compiled object across audits avoids per-call overhead.
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