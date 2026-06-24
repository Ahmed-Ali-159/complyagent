"""Schema for atomic claims extracted from a privacy policy."""
from __future__ import annotations

from pydantic import BaseModel, Field

from complyagent.schemas.enums import StatementCategory


class PolicyStatement(BaseModel):
    """One atomic factual claim extracted from a privacy policy."""

    statement_id: str = Field(
        ...,
        description="Stable ID within an audit, e.g. 'stmt-001'.",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="The claim itself, as a self-contained sentence in the policy's own words.",
    )
    category: StatementCategory = Field(
        ...,
        description="The high-level topic this statement addresses.",
    )
    source_span: str | None = Field(
        None,
        description="Original sentence(s) from the policy this was distilled from, for traceability.",
    )