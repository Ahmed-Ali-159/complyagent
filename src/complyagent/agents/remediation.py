"""Remediation Drafter worker — (Finding | Gap, PolicyStatement | None) -> Remediation.

Branches internally on input type:
  - Finding -> rewrite-style remediation using FINDING_PROMPT.
  - Gap     -> additive remediation using GAP_PROMPT.

LLM produces recommendation + suggested_policy_text + related_citations.
Python sets remediation_id, target_id, target_kind.
"""

from pydantic import BaseModel, Field

from complyagent.agents.llm_client import get_chat_model
from complyagent.prompts.remediation import FINDING_PROMPT, GAP_PROMPT
from complyagent.retrieval.retrieve import get_chunk_by_id
from complyagent.schemas.findings import Finding, Remediation
from complyagent.schemas.findings import Gap
from complyagent.schemas.policy import PolicyStatement
from complyagent.agents._retry import with_llm_retry


# LLM-facing schema: only the fields the LLM actually produces.
class _RemediationDraft(BaseModel):
    recommendation: str = Field(..., min_length=10)
    suggested_policy_text: str = Field(..., min_length=10)
    related_citations: list[str] = Field(default_factory=list)


def _format_provisions(chunk_ids: list[str]) -> str:
    """Resolve chunk_ids to readable GDPR provision text. Falls back to ID
    alone if a chunk_id is unknown (shouldn't happen in practice — gaps and
    findings carry IDs that came from retrieval, so they're in the store)."""
    lines = []
    for cid in chunk_ids:
        chunk = get_chunk_by_id(cid)
        if chunk is None:
            lines.append(f"  - {cid}: (text unavailable)")
        else:
            lines.append(f"  - {cid}: {chunk.text}")
    return "\n".join(lines) if lines else "  (no provisions provided)"


def _draft_for_finding(
    finding: Finding,
    original_statement: PolicyStatement,
    remediation_id: str,
) -> Remediation:
    """Internal: build a remediation for a non-compliant Finding."""
    model = get_chat_model()
    structured = model.with_structured_output(_RemediationDraft)
    chain = with_llm_retry(FINDING_PROMPT | structured)

    result: _RemediationDraft = chain.invoke({
        "original_statement": original_statement.text,
        "verdict": finding.verdict.value,
        "rationale": finding.rationale,
        "cited_provisions": _format_provisions(finding.citations),
    })

    # Filter related_citations to those the LLM was given in this Finding.
    valid_ids = set(finding.citations)
    filtered = [cid for cid in result.related_citations if cid in valid_ids]

    return Remediation(
        remediation_id=remediation_id,
        target_id=finding.statement_id,
        target_kind="finding",
        recommendation=result.recommendation,
        suggested_policy_text=result.suggested_policy_text,
        related_citations=filtered,
    )


def _draft_for_gap(gap: Gap, remediation_id: str) -> Remediation:
    """Internal: build a remediation for a coverage Gap."""
    model = get_chat_model()
    structured = model.with_structured_output(_RemediationDraft)
    chain = with_llm_retry(GAP_PROMPT | structured)

    result: _RemediationDraft = chain.invoke({
        "requirement": gap.requirement,
        "gap_rationale": gap.rationale,
        "provisions": _format_provisions(gap.gdpr_basis),
    })

    # Filter related_citations to those in the Gap's gdpr_basis.
    valid_ids = set(gap.gdpr_basis)
    filtered = [cid for cid in result.related_citations if cid in valid_ids]

    return Remediation(
        remediation_id=remediation_id,
        target_id=gap.gap_id,
        target_kind="gap",
        recommendation=result.recommendation,
        suggested_policy_text=result.suggested_policy_text,
        related_citations=filtered,
    )


def draft_remediation(
    target: Finding | Gap,
    original_statement: PolicyStatement | None = None,
    remediation_id: str = "rem-001",
) -> Remediation:
    """Draft a remediation for either a non-compliant Finding or a coverage Gap.

    Args:
        target: A Finding (verdict ∈ {violation, partial}) or a Gap.
        original_statement: REQUIRED if target is a Finding (the Finding alone
            doesn't carry the policy sentence text). MUST be None if target is
            a Gap (gaps describe missing content — no original sentence exists).
        remediation_id: Stable ID for this remediation. Supervisor assigns
            these in batch; default 'rem-001' is for single-call use.

    Returns:
        Remediation with LLM-produced recommendation + suggested_policy_text
        + related_citations (filtered to valid IDs), and Python-set target
        fields.

    Raises:
        ValueError: if target is a Finding but original_statement is None,
            or if target is a Gap but original_statement is not None.
    """
    if isinstance(target, Finding):
        if original_statement is None:
            raise ValueError(
                "draft_remediation: Finding inputs require original_statement"
            )
        if original_statement.statement_id != target.statement_id:
            raise ValueError(
                f"draft_remediation: original_statement.statement_id "
                f"({original_statement.statement_id!r}) does not match "
                f"finding.statement_id ({target.statement_id!r})"
            )
        return _draft_for_finding(target, original_statement, remediation_id)

    if isinstance(target, Gap):
        if original_statement is not None:
            raise ValueError(
                "draft_remediation: Gap inputs must not pass original_statement"
            )
        return _draft_for_gap(target, remediation_id)

    raise TypeError(
        f"draft_remediation: target must be Finding or Gap, got {type(target).__name__}"
    )