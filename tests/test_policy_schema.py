"""Tests for PolicyStatement."""
import pytest
from pydantic import ValidationError

from complyagent.schemas import PolicyStatement, StatementCategory


def test_valid_statement():
    s = PolicyStatement(
        statement_id="stmt-001",
        text="We retain user data for 5 years.",
        category=StatementCategory.RETENTION,
    )
    assert s.statement_id == "stmt-001"
    assert s.category == StatementCategory.RETENTION
    assert s.source_span is None


def test_source_span_optional_but_settable():
    s = PolicyStatement(
        statement_id="stmt-002",
        text="We share data with partners.",
        category=StatementCategory.DATA_SHARING,
        source_span="We may share certain data with our trusted partners.",
    )
    assert s.source_span == "We may share certain data with our trusted partners."


def test_empty_text_raises():
    with pytest.raises(ValidationError):
        PolicyStatement(statement_id="stmt-003", text="", category=StatementCategory.OTHER)


def test_invalid_category_raises():
    with pytest.raises(ValidationError):
        PolicyStatement(statement_id="stmt-004", text="Some text.", category="not_a_real_category")


def test_missing_required_field_raises():
    with pytest.raises(ValidationError):
        PolicyStatement(text="Some text.", category=StatementCategory.OTHER)