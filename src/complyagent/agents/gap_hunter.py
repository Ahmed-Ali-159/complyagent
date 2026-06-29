"""Gap Hunter worker — (list[PolicyStatement], list[ChecklistItem]) -> list[Gap].

Single batch LLM call. Identifies which mandatory GDPR disclosures from the
checklist the policy fails to address at all. Coverage-only, blind to quality.
"""

from pydantic import BaseModel, Field

from complyagent.agents.gap_checklist import GDPR_DISCLOSURE_CHECKLIST, ChecklistItem
from complyagent.agents.llm_client import get_chat_model
from complyagent.prompts.gap_hunter import GAP_HUNTER_PROMPT
from complyagent.schemas.enums import GapSeverity
from complyagent.schemas.findings import Gap
from complyagent.schemas.policy import PolicyStatement
from complyagent.agents._retry import with_llm_retry


# LLM-facing schema: no gap_id (Python assigns it).
class _GapDraft(BaseModel):
    requirement: str
    gdpr_basis: list[str] = Field(..., min_length=1)
    severity: GapSeverity
    rationale: str = Field(..., min_length=10)


class _GapList(BaseModel):
    """Wrapper schema since with_structured_output binds one schema, not a list."""
    gaps: list[_GapDraft]


def _format_statements(statements: list[PolicyStatement]) -> str:
    """Render statements as readable list for the prompt."""
    if not statements:
        return "  (no statements)"
    return "\n".join(
        f"  - [{s.statement_id}] ({s.category.value}) {s.text}"
        for s in statements
    )


def _format_checklist(checklist: list[ChecklistItem]) -> str:
    """Render checklist items so each can be referenced by the LLM."""
    return "\n".join(
        f"  - chunk_ids={item.chunk_ids}, severity={item.severity}\n"
        f"    requirement: {item.requirement}"
        for item in checklist
    )


def hunt_gaps(
    statements: list[PolicyStatement],
    checklist: list[ChecklistItem] | None = None,
) -> list[Gap]:
    """Find mandatory GDPR disclosure requirements the policy fails to address.

    Args:
        statements: All atomic policy statements from the Parser.
        checklist: Optional override; defaults to GDPR_DISCLOSURE_CHECKLIST.

    Returns:
        list[Gap] — one Gap per unaddressed requirement. Empty list if the
        policy addresses all checklist items.
    """
    # Short-circuit: no statements means everything is a gap, but also means
    # the input is degenerate. Don't waste an LLM call — return empty and let
    # the Supervisor/Report Writer handle the "empty policy" case explicitly.
    if not statements:
        return []

    active_checklist = checklist if checklist is not None else GDPR_DISCLOSURE_CHECKLIST

    model = get_chat_model()
    structured = model.with_structured_output(_GapList)
    chain = with_llm_retry(GAP_HUNTER_PROMPT | structured)

    result: _GapList = chain.invoke({
        "statements": _format_statements(statements),
        "checklist": _format_checklist(active_checklist),
    })

    # Validate gdpr_basis: each Gap's chunk_ids must match a checklist item.
    # This blocks the LLM from inventing requirements or mangling chunk_ids.
    valid_basis_sets = [frozenset(item.chunk_ids) for item in active_checklist]

    validated_gaps: list[Gap] = []
    for i, draft in enumerate(result.gaps, start=1):
        if frozenset(draft.gdpr_basis) not in valid_basis_sets:
            # LLM produced a Gap whose gdpr_basis doesn't match any checklist
            # item. Skip it rather than emit a fabricated requirement.
            continue
        validated_gaps.append(Gap(
            gap_id=f"gap-{i:03d}",
            requirement=draft.requirement,
            gdpr_basis=draft.gdpr_basis,
            severity=draft.severity,
            rationale=draft.rationale,
        ))

    # Re-number after filtering so IDs stay sequential.
    return [
        Gap(
            gap_id=f"gap-{i:03d}",
            requirement=g.requirement,
            gdpr_basis=g.gdpr_basis,
            severity=g.severity,
            rationale=g.rationale,
        )
        for i, g in enumerate(validated_gaps, start=1)
    ]