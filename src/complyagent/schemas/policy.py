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

# What is the difference between text and source_span fields in the PolicyStatement class?
# Here is an example to illustrate the difference:
# Example:
    # Let's say we have a privacy policy that contains the following sentence:
        # "We collect your email address and phone number to provide you with personalized services."
    # In this case, the text field in the PolicyStatement class would contain the distilled claim:
    # "We collect your email address and phone number."
    # The source_span field would contain the original sentence from the policy