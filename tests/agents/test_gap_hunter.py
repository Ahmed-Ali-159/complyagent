"""Tests for the Gap Hunter worker. Mocked LLM — tests behavior, not LLM quality."""

from unittest.mock import patch, MagicMock
from langchain_core.runnables import RunnableLambda

from complyagent.agents.gap_checklist import ChecklistItem
from complyagent.agents.gap_hunter import hunt_gaps, _GapDraft, _GapList
from complyagent.schemas.enums import GapSeverity, StatementCategory
from complyagent.schemas.findings import Gap
from complyagent.schemas.policy import PolicyStatement


# Helpers ---------------------------------------------------------------------

def _make_statement(stmt_id: str = "stmt-001") -> PolicyStatement:
    return PolicyStatement(
        statement_id=stmt_id,
        text="The company collects user email addresses.",
        category=StatementCategory.DATA_COLLECTION,
        source_span=None,
    )


def _make_checklist() -> list[ChecklistItem]:
    return [
        ChecklistItem(
            chunk_ids=["GDPR-Art-13-1-a"],
            requirement="Identity of the controller.",
            severity="critical",
        ),
        ChecklistItem(
            chunk_ids=["GDPR-Art-13-1-c"],
            requirement="Legal basis for processing.",
            severity="critical",
        ),
    ]


def _patch_chain_returning(gaps: list[_GapDraft]):
    fake_structured = RunnableLambda(lambda _input: _GapList(gaps=gaps))
    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = fake_structured
    return patch("complyagent.agents.gap_hunter.get_chat_model", return_value=mock_model)


# Short-circuit ---------------------------------------------------------------

def test_empty_statements_returns_empty_without_llm():
    with patch("complyagent.agents.gap_hunter.get_chat_model") as mock_get:
        result = hunt_gaps(statements=[], checklist=_make_checklist())

    assert result == []
    mock_get.assert_not_called()


# ID assignment ---------------------------------------------------------------

def test_gap_ids_assigned_in_order():
    drafts = [
        _GapDraft(
            requirement="Identity of the controller.",
            gdpr_basis=["GDPR-Art-13-1-a"],
            severity=GapSeverity.CRITICAL,
            rationale="No statement identifies the data controller.",
        ),
        _GapDraft(
            requirement="Legal basis for processing.",
            gdpr_basis=["GDPR-Art-13-1-c"],
            severity=GapSeverity.CRITICAL,
            rationale="No statement specifies the legal basis for processing.",
        ),
    ]
    with _patch_chain_returning(drafts):
        result = hunt_gaps([_make_statement()], _make_checklist())

    assert [g.gap_id for g in result] == ["gap-001", "gap-002"]


# Validation against checklist ------------------------------------------------

def test_fabricated_gap_with_unknown_chunk_id_is_dropped():
    """LLM invents a gdpr_basis that doesn't match any checklist item — drop it."""
    drafts = [
        _GapDraft(
            requirement="Identity of the controller.",
            gdpr_basis=["GDPR-Art-13-1-a"],  # Valid.
            severity=GapSeverity.CRITICAL,
            rationale="No statement identifies the controller.",
        ),
        _GapDraft(
            requirement="Made-up requirement not on the checklist.",
            gdpr_basis=["GDPR-Art-99-99"],  # Not in any checklist item.
            severity=GapSeverity.HIGH,
            rationale="The LLM hallucinated this entirely.",
        ),
    ]
    with _patch_chain_returning(drafts):
        result = hunt_gaps([_make_statement()], _make_checklist())

    assert len(result) == 1
    assert result[0].requirement == "Identity of the controller."


def test_ids_renumber_after_filtering():
    """When the first draft gets filtered, surviving gaps get sequential IDs starting at 001."""
    drafts = [
        _GapDraft(
            requirement="Fabricated.",
            gdpr_basis=["GDPR-Art-99-99"],
            severity=GapSeverity.MEDIUM,
            rationale="LLM made this up.",
        ),
        _GapDraft(
            requirement="Identity of the controller.",
            gdpr_basis=["GDPR-Art-13-1-a"],
            severity=GapSeverity.CRITICAL,
            rationale="No statement identifies the controller.",
        ),
    ]
    with _patch_chain_returning(drafts):
        result = hunt_gaps([_make_statement()], _make_checklist())

    assert len(result) == 1
    assert result[0].gap_id == "gap-001"


def test_gdpr_basis_chunk_ids_match_regardless_of_order():
    """Checklist item has [A, B]; LLM returns [B, A] — should still validate."""
    checklist = [
        ChecklistItem(
            chunk_ids=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
            requirement="Identity of the controller (Art 13 and 14).",
            severity="critical",
        ),
    ]
    drafts = [
        _GapDraft(
            requirement="Identity of the controller (Art 13 and 14).",
            gdpr_basis=["GDPR-Art-14-1-a", "GDPR-Art-13-1-a"],  # Reordered.
            severity=GapSeverity.CRITICAL,
            rationale="No statement identifies the controller.",
        ),
    ]
    with _patch_chain_returning(drafts):
        result = hunt_gaps([_make_statement()], checklist)

    assert len(result) == 1


# Defaults --------------------------------------------------------------------

def test_default_checklist_used_when_none_provided():
    """No checklist arg -> falls back to GDPR_DISCLOSURE_CHECKLIST."""
    drafts: list[_GapDraft] = []
    with _patch_chain_returning(drafts):
        # Just verify it runs and returns [] without raising on the default.
        result = hunt_gaps([_make_statement()])

    assert result == []


# Output structure ------------------------------------------------------------

def test_returns_proper_gap_objects():
    drafts = [
        _GapDraft(
            requirement="Identity of the controller.",
            gdpr_basis=["GDPR-Art-13-1-a"],
            severity=GapSeverity.CRITICAL,
            rationale="No statement identifies the controller in the policy.",
        ),
    ]
    with _patch_chain_returning(drafts):
        result = hunt_gaps([_make_statement()], _make_checklist())

    assert len(result) == 1
    gap = result[0]
    assert isinstance(gap, Gap)
    assert gap.severity == GapSeverity.CRITICAL
    assert gap.gdpr_basis == ["GDPR-Art-13-1-a"]
    assert gap.requirement == "Identity of the controller."


def test_empty_gap_list_from_llm_means_full_coverage():
    """If the LLM finds no gaps, return []."""
    with _patch_chain_returning([]):
        result = hunt_gaps([_make_statement()], _make_checklist())

    assert result == []