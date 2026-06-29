"""Tests for the Policy Parser worker. Mocked LLM — tests behavior, not LLM quality."""

from unittest.mock import patch, MagicMock

import pytest

from complyagent.agents.parser import (
    parse_policy,
    _ParsedStatement,
    _PolicyStatementList,
)
from complyagent.schemas.enums import StatementCategory
from complyagent.schemas.policy import PolicyStatement


def _patch_chain_returning(statements: list[_ParsedStatement]):
    """Patch the LCEL chain so its .invoke() returns the given wrapped statements.

    We patch the `|` operator's result by replacing get_chat_model with a model
    whose with_structured_output() returns a Runnable mock that, when piped
    with PARSER_PROMPT, yields a chain whose .invoke returns our payload.

    Simpler approach: patch the entire chain construction by intercepting
    `with_structured_output` to return an object that, piped with a prompt,
    produces a chain whose invoke is fully controlled.
    """
    wrapped = _PolicyStatementList(statements=statements)

    # A real-enough Runnable: piping ChatPromptTemplate | this returns a
    # RunnableSequence whose final .invoke calls this mock's .invoke.
    # We use MagicMock with spec to behave like a Runnable.
    from langchain_core.runnables import RunnableLambda

    # RunnableLambda is a real Runnable that ignores input and returns wrapped.
    fake_structured = RunnableLambda(lambda _input: wrapped)

    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = fake_structured

    return patch("complyagent.agents.parser.get_chat_model", return_value=mock_model)


# --- Short-circuit behavior ---

def test_empty_string_returns_empty_list_without_calling_llm():
    with patch("complyagent.agents.parser.get_chat_model") as mock_get:
        result = parse_policy("")
        assert result == []
        mock_get.assert_not_called()


def test_whitespace_only_returns_empty_list_without_calling_llm():
    with patch("complyagent.agents.parser.get_chat_model") as mock_get:
        result = parse_policy("   \n\t  ")
        assert result == []
        mock_get.assert_not_called()


def test_below_threshold_returns_empty_list_without_calling_llm():
    with patch("complyagent.agents.parser.get_chat_model") as mock_get:
        result = parse_policy("hi")
        assert result == []
        mock_get.assert_not_called()


# --- ID assignment ---

def test_ids_assigned_in_document_order():
    statements = [
        _ParsedStatement(text="First claim.", category=StatementCategory.DATA_COLLECTION),
        _ParsedStatement(text="Second claim.", category=StatementCategory.DATA_SHARING),
        _ParsedStatement(text="Third claim.", category=StatementCategory.RETENTION),
    ]
    with _patch_chain_returning(statements):
        result = parse_policy("Some policy text long enough to pass the threshold.")

    assert [s.statement_id for s in result] == ["stmt-001", "stmt-002", "stmt-003"]


def test_ids_are_stable_across_runs():
    statements = [
        _ParsedStatement(text="A claim.", category=StatementCategory.SECURITY),
    ]
    with _patch_chain_returning(statements):
        run1 = parse_policy("Some policy text long enough to pass the threshold.")
        run2 = parse_policy("Some policy text long enough to pass the threshold.")

    assert run1[0].statement_id == run2[0].statement_id == "stmt-001"


# --- Output structure ---

def test_returns_policy_statement_instances():
    statements = [
        _ParsedStatement(
            text="The company collects user emails.",
            category=StatementCategory.DATA_COLLECTION,
            source_span="We collect your email.",
        ),
    ]
    with _patch_chain_returning(statements):
        result = parse_policy("Some policy text long enough to pass the threshold.")

    assert len(result) == 1
    assert isinstance(result[0], PolicyStatement)
    assert result[0].text == "The company collects user emails."
    assert result[0].category == StatementCategory.DATA_COLLECTION
    assert result[0].source_span == "We collect your email."


def test_source_span_can_be_none():
    statements = [
        _ParsedStatement(
            text="Some claim.",
            category=StatementCategory.OTHER,
            source_span=None,
        ),
    ]
    with _patch_chain_returning(statements):
        result = parse_policy("Some policy text long enough to pass the threshold.")

    assert result[0].source_span is None


def test_empty_statement_list_from_llm_returns_empty_list():
    with _patch_chain_returning([]):
        result = parse_policy("Some policy text long enough to pass the threshold.")

    assert result == []