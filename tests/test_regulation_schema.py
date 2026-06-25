"""Tests for RegulationChunk - chunk_id parsing, validation, citation labels."""
import pytest
from pydantic import ValidationError

from complyagent.schemas import RegulationChunk


def test_article_chunk_with_paragraph_and_point():
    c = RegulationChunk(chunk_id="GDPR-Art-5-1-e", text="some text")
    assert c.source_type == "article"
    assert c.article_number == 5
    assert c.paragraph == 1
    assert c.point == "e"
    assert c.recital_number is None
    assert c.citation_label == "Article 5(1)(e) GDPR"


def test_article_chunk_paragraph_only_no_point():
    c = RegulationChunk(chunk_id="GDPR-Art-1-2", text="some text")
    assert c.article_number == 1
    assert c.paragraph == 2
    assert c.point is None
    assert c.citation_label == "Article 1(2) GDPR"


def test_article_chunk_whole_article_no_paragraph_no_point():
    c = RegulationChunk(chunk_id="GDPR-Art-10", text="some text")
    assert c.article_number == 10
    assert c.paragraph is None
    assert c.point is None
    assert c.citation_label == "Article 10 GDPR"


def test_article_chunk_point_without_paragraph():
    """Article 50 case: sub-points directly under the article, no paragraph level."""
    c = RegulationChunk(chunk_id="GDPR-Art-50-a", text="some text")
    assert c.article_number == 50
    assert c.paragraph is None
    assert c.point == "a"
    assert c.citation_label == "Article 50(a) GDPR"


def test_recital_chunk():
    c = RegulationChunk(chunk_id="GDPR-Rec-26", text="some text")
    assert c.source_type == "recital"
    assert c.recital_number == 26
    assert c.article_number is None
    assert c.citation_label == "Recital 26 GDPR"


def test_invalid_chunk_id_format_raises():
    with pytest.raises(ValidationError, match="Invalid chunk_id format"):
        RegulationChunk(chunk_id="bad-id", text="some text")


def test_invalid_chunk_id_uppercase_point_raises():
    with pytest.raises(ValidationError):
        RegulationChunk(chunk_id="GDPR-Art-5-1-E", text="some text")


def test_empty_text_raises():
    with pytest.raises(ValidationError):
        RegulationChunk(chunk_id="GDPR-Art-5-1-e", text="")


def test_chunk_is_frozen():
    c = RegulationChunk(chunk_id="GDPR-Art-5-1-e", text="some text")
    with pytest.raises(ValidationError):
        c.text = "different text"


def test_article_number_out_of_range_raises():
    """Article numbers must be 1-99; chunk_id regex itself caps at 3 digits, but
    the field-level ge/le constraint should still reject something like 999 if it
    ever got past the regex (defense in depth)."""
    with pytest.raises(ValidationError):
        RegulationChunk(chunk_id="GDPR-Art-999-1", text="some text")