"""Schema for one chunk of GDPR regulation text (articles and recitals)."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Two valid top-level forms:
#   GDPR-Art-{article}[-{paragraph}][-{point}]   e.g. GDPR-Art-5-1-e
#   GDPR-Rec-{number}                             e.g. GDPR-Rec-26
CHUNK_ID_PATTERN = re.compile(
    r"^GDPR-(?:"
    r"Art-(?P<article>\d{1,3})(?:-(?P<paragraph>\d+))?(?:-(?P<point>[a-z]))?"
    r"|"
    r"Rec-(?P<recital>\d{1,3})"
    r")$"
)


class RegulationChunk(BaseModel):
    """One atomic piece of GDPR text - either an Article provision or a Recital."""
    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(..., description="Hierarchical ID, e.g. 'GDPR-Art-5-1-e' or 'GDPR-Rec-26'.")
    source_type: Literal["article", "recital"] = Field(
        ..., description="Whether this chunk is binding legal text (article) or interpretive context (recital). Auto-derived from chunk_id."
    )
    article_number: int | None = Field(None, ge=1, le=99, description="Auto-derived from chunk_id; None for recitals.")
    recital_number: int | None = Field(None, ge=1, le=173, description="Auto-derived from chunk_id; None for articles.")
    article_title: str | None = Field(None, description="Official title of the article; None for recitals.")
    paragraph: int | None = Field(None, description="Top-level paragraph number within the article. Auto-derived from chunk_id.")
    point: str | None = Field(None, description="Sub-point letter within a paragraph (e.g. 'e' for Art. 5(1)(e)). Auto-derived from chunk_id.")
    text: str = Field(..., min_length=1, description="The regulation text in this chunk.")
    chapter: str | None = Field(None, description="GDPR chapter, e.g. 'Chapter II — Principles'. None for recitals.")

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

        if match.group("recital"):
            data["source_type"] = "recital"
            data["recital_number"] = int(match.group("recital"))
            data["article_number"] = None
            data["paragraph"] = None
            data["point"] = None
        else:
            data["source_type"] = "article"
            data["article_number"] = int(match.group("article"))
            data["paragraph"] = int(match.group("paragraph")) if match.group("paragraph") else None
            data["point"] = match.group("point")
            data["recital_number"] = None

        return data

    @property
    def citation_label(self) -> str:
        """Human-readable citation, e.g. 'Article 5(1)(e) GDPR' or 'Recital 26 GDPR'."""
        if self.source_type == "recital":
            return f"Recital {self.recital_number} GDPR"
        parts = [f"Article {self.article_number}"]
        if self.paragraph is not None:
            parts.append(f"({self.paragraph})")
        if self.point is not None:
            parts.append(f"({self.point})")
        return "".join(parts) + " GDPR"