"""Tests for the Compliance Analyst worker. Mocked LLM — tests behavior, not LLM quality."""

from unittest.mock import patch
from langchain_core.runnables import RunnableLambda

from complyagent.agents.analyst import analyze_statement, _AnalystOutput
from complyagent.schemas.enums import StatementCategory, VerdictType
from complyagent.schemas.findings import Finding
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.regulation import RegulationChunk


# Helpers ---------------------------------------------------------------------

def _make_statement(stmt_id: str = "stmt-001") -> PolicyStatement:
    return PolicyStatement(
        statement_id=stmt_id,
        text="The company processes user data based on consent.",
        category=StatementCategory.LEGAL_BASIS,
        source_span=None,
    )


def _make_chunk(chunk_id: str, text: str = "Some GDPR text.") -> RegulationChunk:
    # NOTE: This constructor call assumes RegulationChunk's required fields are
    # chunk_id and text. If Phase 1 made article/recital variants required, the
    # test fixture may need adjustment — the analyst itself only reads .chunk_id
    # and .text, so the worker code is unaffected.
    return RegulationChunk(chunk_id=chunk_id, text=text)


def _patch_chain_returning(output: _AnalystOutput):
    fake_structured = RunnableLambda(lambda _input: output)

    from unittest.mock import MagicMock
    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = fake_structured

    return patch("complyagent.agents.analyst.get_chat_model", return_value=mock_model)


# Short-circuit ---------------------------------------------------------------

def test_empty_chunks_returns_unclear_finding_without_llm():
    with patch("complyagent.agents.analyst.get_chat_model") as mock_get:
        result = analyze_statement(_make_statement(), retrieved_chunks=[])

    assert isinstance(result, Finding)
    assert result.statement_id == "stmt-001"
    assert result.verdict == VerdictType.UNCLEAR
    assert result.confidence == 0.0
    assert result.citations == []
    assert "No relevant GDPR provisions" in result.rationale
    mock_get.assert_not_called()


# Citation filtering ----------------------------------------------------------

def test_invented_citations_are_filtered_out():
    chunks = [_make_chunk("GDPR-Art-6-1-a"), _make_chunk("GDPR-Art-7-1")]
    llm_output = _AnalystOutput(
        verdict=VerdictType.COMPLIANT,
        rationale="The statement aligns with the consent provisions.",
        citations=["GDPR-Art-6-1-a", "GDPR-Art-99-FAKE", "GDPR-Art-7-1"],
        confidence=0.9,
    )
    with _patch_chain_returning(llm_output):
        result = analyze_statement(_make_statement(), chunks)

    assert result.citations == ["GDPR-Art-6-1-a", "GDPR-Art-7-1"]


def test_all_invented_citations_yields_empty_list_not_error():
    chunks = [_make_chunk("GDPR-Art-6-1-a")]
    llm_output = _AnalystOutput(
        verdict=VerdictType.UNCLEAR,
        rationale="Cannot find supporting provisions in retrieved chunks.",
        citations=["GDPR-Art-FAKE-1", "GDPR-Art-FAKE-2"],
        confidence=0.4,
    )
    with _patch_chain_returning(llm_output):
        result = analyze_statement(_make_statement(), chunks)

    assert result.citations == []
    assert result.verdict == VerdictType.UNCLEAR  # Verdict preserved despite filter.


def test_valid_citations_preserved_intact():
    chunks = [_make_chunk("GDPR-Art-6-1-a"), _make_chunk("GDPR-Art-7-1")]
    llm_output = _AnalystOutput(
        verdict=VerdictType.COMPLIANT,
        rationale="Both provisions cleanly support the statement.",
        citations=["GDPR-Art-6-1-a", "GDPR-Art-7-1"],
        confidence=0.95,
    )
    with _patch_chain_returning(llm_output):
        result = analyze_statement(_make_statement(), chunks)

    assert result.citations == ["GDPR-Art-6-1-a", "GDPR-Art-7-1"]


# Field passthrough -----------------------------------------------------------

def test_statement_id_comes_from_input_not_llm():
    chunks = [_make_chunk("GDPR-Art-5-1-e")]
    llm_output = _AnalystOutput(
        verdict=VerdictType.VIOLATION,
        rationale="Indefinite retention contradicts storage limitation.",
        citations=["GDPR-Art-5-1-e"],
        confidence=0.9,
    )
    with _patch_chain_returning(llm_output):
        result = analyze_statement(_make_statement("stmt-042"), chunks)

    assert result.statement_id == "stmt-042"


def test_all_verdict_types_pass_through():
    chunks = [_make_chunk("GDPR-Art-6-1-a")]
    for verdict in VerdictType:
        llm_output = _AnalystOutput(
            verdict=verdict,
            rationale="Test rationale that is long enough.",
            citations=["GDPR-Art-6-1-a"],
            confidence=0.7,
        )
        with _patch_chain_returning(llm_output):
            result = analyze_statement(_make_statement(), chunks)
        assert result.verdict == verdict


def test_confidence_passes_through_at_boundaries():
    chunks = [_make_chunk("GDPR-Art-6-1-a")]
    for conf in [0.0, 0.5, 1.0]:
        llm_output = _AnalystOutput(
            verdict=VerdictType.UNCLEAR,
            rationale="Rationale long enough to pass min_length.",
            citations=[],
            confidence=conf,
        )
        with _patch_chain_returning(llm_output):
            result = analyze_statement(_make_statement(), chunks)
        assert result.confidence == conf