"""Report Writer worker — SupervisorState -> AuditReport.

The final worker. Reads accumulated audit state, asks the LLM to produce the
executive summary and full markdown narrative, and assembles the AuditReport
with all per-worker outputs passed through unchanged.
"""

from pydantic import BaseModel, Field

from complyagent.agents.llm_client import get_chat_model
from complyagent.prompts.report_writer import REPORT_PROMPT
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.report import AuditReport
from complyagent.schemas.supervisor import SupervisorState
from complyagent.agents._retry import with_llm_retry


# Reports can be long — single LLM default of 4096 is tight for full-policy
# audits. 8192 gives comfortable headroom for executive_summary + a full
# markdown report covering ~10 findings + gaps + remediations.
REPORT_MAX_TOKENS = 8192


# LLM-facing schema: only the two narrative fields. Everything else in
# AuditReport is passed through from SupervisorState by our code.
class _ReportDraft(BaseModel):
    executive_summary: str = Field(..., min_length=20)
    markdown_report: str = Field(..., min_length=50)


def _format_statements(statements: list[PolicyStatement]) -> str:
    if not statements:
        return "  (none)"
    return "\n".join(
        f"  - [{s.statement_id}] ({s.category.value}) {s.text}"
        for s in statements
    )


def _format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "  (none)"
    lines = []
    for f in findings:
        cites = ", ".join(f.citations) if f.citations else "no citations"
        lines.append(
            f"  - [{f.statement_id}] verdict={f.verdict.value}, "
            f"confidence={f.confidence:.2f}, citations=[{cites}]\n"
            f"    rationale: {f.rationale}"
        )
    return "\n".join(lines)


def _format_gaps(gaps: list[Gap]) -> str:
    if not gaps:
        return "  (none)"
    lines = []
    for g in gaps:
        basis = ", ".join(g.gdpr_basis)
        lines.append(
            f"  - [{g.gap_id}] severity={g.severity.value}, basis=[{basis}]\n"
            f"    requirement: {g.requirement}\n"
            f"    rationale: {g.rationale}"
        )
    return "\n".join(lines)


def _format_remediations(remediations: list[Remediation]) -> str:
    """Render remediations compactly for the report prompt.

    We deliberately omit suggested_policy_text from the LLM prompt because
    it's the longest field by far and inflates the report prompt past
    free-tier request limits on full-policy audits. The remediations remain
    in the final AuditReport unchanged (they're passthrough state), so the
    suggested text is preserved for downstream display — just not narrated
    inline by the LLM.
    """
    if not remediations:
        return "  (none)"
    lines = []
    for r in remediations:
        cites = ", ".join(r.related_citations) if r.related_citations else "none"
        lines.append(
            f"  - [{r.remediation_id}] targets {r.target_kind} {r.target_id}, "
            f"related_citations=[{cites}]\n"
            f"    recommendation: {r.recommendation}"
        )
    return "\n".join(lines)


def write_report(state: SupervisorState) -> AuditReport:
    """Produce the final AuditReport from accumulated audit state.

    Args:
        state: The SupervisorState carrying all worker outputs.

    Returns:
        AuditReport with LLM-produced executive_summary and markdown_report,
        and all per-worker outputs (statements, findings, gaps, remediations)
        passed through unchanged from state.
    """
    model = get_chat_model().bind(max_tokens=REPORT_MAX_TOKENS)
    structured = model.with_structured_output(_ReportDraft)
    chain = with_llm_retry(REPORT_PROMPT | structured)

    draft: _ReportDraft = chain.invoke({
        "audit_id": state.audit_id,
        "policy_source": state.policy_source,
        "statement_count": len(state.statements),
        "finding_count": len(state.findings),
        "gap_count": len(state.gaps),
        "remediation_count": len(state.remediations),
        "statements": _format_statements(state.statements),
        "findings": _format_findings(state.findings),
        "gaps": _format_gaps(state.gaps),
        "remediations": _format_remediations(state.remediations),
    })

    return AuditReport(
        audit_id=state.audit_id,
        policy_source=state.policy_source,
        # created_at uses AuditReport's default_factory — set to "now" automatically.
        statements=state.statements,
        findings=state.findings,
        gaps=state.gaps,
        remediations=state.remediations,
        decisions=state.decisions,
        executive_summary=draft.executive_summary,
        markdown_report=draft.markdown_report,
    )