"""Schema for one chunk of GDPR regulation text."""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Format: GDPR-Art-{article}[-{paragraph}|-p{prose_index}][-{point}]
CHUNK_ID_PATTERN = re.compile(
    r"^GDPR-Art-(?P<article>\d{1,3})"
    r"(?:-(?:(?P<paragraph>\d+)|p(?P<prose>\d+)))?"
    r"(?:-(?P<point>[a-z]))?$"
)


class RegulationChunk(BaseModel):
    """One atomic piece of GDPR text with full traceability metadata."""
    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(..., description="Hierarchical ID, e.g. 'GDPR-Art-5-1-e'.")
    article_number: int = Field(0, ge=0, le=99, description="Auto-derived from chunk_id.")
    article_title: str = Field(..., description="Official title of the article.")
    paragraph: int | None = Field(None, description="Top-level paragraph number within the article, Auto-derived from chunk_id.")
    point: str | None = Field(None, description="Auto-derived from chunk_id, Sub-point letter within a paragraph (e.g. 'e' for Art. 5(1)(e)).")
    text: str = Field(..., min_length=1, description="The regulation text in this chunk.")
    chapter: str | None = Field(None, description="GDPR chapter, e.g. 'Chapter II — Principles'..")
    source_url: str = Field(..., description="Source URL on gdpr-info.eu.")

    @model_validator(mode="before")
    @classmethod
    def _derive_from_chunk_id(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        chunk_id = data.get("chunk_id")
        if not isinstance(chunk_id, str):
            return data
        match = CHUNK_ID_PATTERN.match(chunk_id)
        if not match:
            raise ValueError(f"Invalid chunk_id format: {chunk_id!r}")
        data["article_number"] = int(match.group("article"))
        data["paragraph"] = int(match.group("paragraph")) if match.group("paragraph") else None
        data["point"] = match.group("point")
        return data

    @property
    def citation_label(self) -> str:
        """Human-readable citation, e.g. 'Article 5(1)(e) GDPR'."""
        parts = [f"Article {self.article_number}"]
        if self.paragraph is not None:
            parts.append(f"({self.paragraph})")
        if self.point is not None:
            parts.append(f"({self.point})")
        return "".join(parts) + " GDPR"