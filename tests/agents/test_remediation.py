"""Tests for the Remediation Drafter worker. Mocked LLM."""

from unittest.mock import patch, MagicMock
import pytest
from langchain_core.runnables import RunnableLambda

from complyagent.agents.remediation import (
    draft_remediation,
    _RemediationDraft,
)
from complyagent.schemas.enums import (
    GapSeverity,
    StatementCategory,
    VerdictType,
)
from complyagent.schemas.findings import Finding, Remediation
from complyagent.schemas.findings import Gap
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk


# Helpers ---------------------------------------------------------------------

def _make_statement(stmt_id: str = "stmt-001") -> PolicyStatement:
    return PolicyStatement(
        statement_id=stmt_id,
        text="The company retains user data indefinitely.",
        category=StatementCategory.RETENTION,
        source_span=None,
    )


def _make_finding(stmt_id: str = "stmt-001") -> Finding:
    return Finding(
        statement_id=stmt_id,
        verdict=VerdictType.VIOLATION,
        rationale="Indefinite retention contradicts the storage limitation principle.",
        citations=["GDPR-Art-5-1-e"],
        confidence=0.9,
    )


def _make_gap() -> Gap:
    return Gap(
        gap_id="gap-001",
        requirement="Identity and contact details of the data controller.",
        gdpr_basis=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
        severity=GapSeverity.CRITICAL,
        rationale="No statement identifies the data controller.",
    )


def _patch_chain_returning(draft: _RemediationDraft):
    """Patch get_chat_model so chain.invoke returns our draft."""
    fake_structured = RunnableLambda(lambda _input: draft)
    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = fake_structured
    return patch("complyagent.agents.remediation.get_chat_model", return_value=mock_model)


def _patch_chunk_lookup():
    """Patch get_chunk_by_id so prompt rendering doesn't hit the real chunk store."""
    return patch(
        "complyagent.agents.remediation.get_chunk_by_id",
        return_value=RegulationChunk(
            chunk_id="GDPR-Art-5-1-e",
            text="Personal data shall be kept in a form which permits identification "
                 "of data subjects for no longer than is necessary.",
        ),
    )


# Dispatch & input validation -------------------------------------------------

def test_finding_without_original_statement_raises():
    with pytest.raises(ValueError, match="require original_statement"):
        draft_remediation(target=_make_finding(), original_statement=None)


def test_gap_with_original_statement_raises():
    with pytest.raises(ValueError, match="must not pass original_statement"):
        draft_remediation(target=_make_gap(), original_statement=_make_statement())


def test_mismatched_statement_id_raises():
    finding = _make_finding(stmt_id="stmt-001")
    wrong_statement = _make_statement(stmt_id="stmt-042")
    with pytest.raises(ValueError, match="does not match"):
        draft_remediation(target=finding, original_statement=wrong_statement)


def test_unknown_target_type_raises():
    with pytest.raises(TypeError, match="target must be Finding or Gap"):
        draft_remediation(target="not a valid target", original_statement=None)


# Finding case ----------------------------------------------------------------

def test_finding_case_sets_target_fields_correctly():
    draft = _RemediationDraft(
        recommendation="Define a clear retention period of no more than 24 months.",
        suggested_policy_text="We retain user data for [X months] after account closure.",
        related_citations=["GDPR-Art-5-1-e"],
    )
    with _patch_chain_returning(draft), _patch_chunk_lookup():
        result = draft_remediation(
            target=_make_finding(),
            original_statement=_make_statement(),
            remediation_id="rem-007",
        )

    assert isinstance(result, Remediation)
    assert result.remediation_id == "rem-007"
    assert result.target_id == "stmt-001"
    assert result.target_kind == "finding"
    assert result.recommendation.startswith("Define a clear")
    assert "[X months]" in result.suggested_policy_text


def test_finding_case_filters_invented_citations():
    draft = _RemediationDraft(
        recommendation="Define a clear retention period.",
        suggested_policy_text="We retain data for [X months].",
        related_citations=["GDPR-Art-5-1-e", "GDPR-Art-99-9"],  # second is invented.
    )
    with _patch_chain_returning(draft), _patch_chunk_lookup():
        result = draft_remediation(
            target=_make_finding(),
            original_statement=_make_statement(),
        )

    assert result.related_citations == ["GDPR-Art-5-1-e"]


# Gap case --------------------------------------------------------------------

def test_gap_case_sets_target_fields_correctly():
    draft = _RemediationDraft(
        recommendation="Add a clause identifying the data controller and contact details.",
        suggested_policy_text="The data controller is [Company Name], reachable at [email@example.com].",
        related_citations=["GDPR-Art-13-1-a", "GDPR-Art-14-1-a"],
    )
    with _patch_chain_returning(draft), _patch_chunk_lookup():
        result = draft_remediation(
            target=_make_gap(),
            remediation_id="rem-003",
        )

    assert isinstance(result, Remediation)
    assert result.remediation_id == "rem-003"
    assert result.target_id == "gap-001"
    assert result.target_kind == "gap"


def test_gap_case_filters_invented_citations():
    draft = _RemediationDraft(
        recommendation="Identify the controller.",
        suggested_policy_text="The data controller is [Company Name].",
        related_citations=["GDPR-Art-13-1-a", "GDPR-Art-77-1"],  # second not in gdpr_basis.
    )
    with _patch_chain_returning(draft), _patch_chunk_lookup():
        result = draft_remediation(target=_make_gap())

    assert result.related_citations == ["GDPR-Art-13-1-a"]


# Default remediation_id ------------------------------------------------------

def test_default_remediation_id_is_rem_001():
    draft = _RemediationDraft(
        recommendation="Test recommendation that is long enough.",
        suggested_policy_text="Test policy text that is long enough.",
        related_citations=[],
    )
    with _patch_chain_returning(draft), _patch_chunk_lookup():
        result = draft_remediation(target=_make_gap())

    assert result.remediation_id == "rem-001"