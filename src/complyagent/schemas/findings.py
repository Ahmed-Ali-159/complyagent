"""Schemas for compliance findings, gaps, and remediations."""
from __future__ import annotations

from pydantic import BaseModel, Field

from complyagent.schemas.enums import GapSeverity, VerdictType


class Finding(BaseModel):
    """The Compliance Analyst's verdict on one PolicyStatement."""

    statement_id: str = Field(..., description="ID of the PolicyStatement this verdicts.")
    verdict: VerdictType = Field(..., description="Compliance verdict.")
    rationale: str = Field(
        ...,
        min_length=10,
        description="Concise legal reasoning linking the statement to the cited GDPR provisions.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="chunk_ids of the GDPR chunks supporting this verdict (e.g. ['GDPR-Art-6-1-a']).",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Analyst's self-reported confidence; <0.6 may trigger re-retrieval.",
    )


class Gap(BaseModel):
    """A mandatory GDPR requirement the policy fails to address."""

    gap_id: str = Field(..., description="Stable ID within the audit, e.g. 'gap-001'.")
    requirement: str = Field(
        ...,
        description="Plain-English description of the missing requirement.",
    )
    gdpr_basis: list[str] = Field(
        ...,
        min_length=1,
        description="chunk_ids that establish this requirement.",
    )
    severity: GapSeverity = Field(..., description="How serious this gap is.")
    rationale: str = Field(
        ...,
        min_length=10,
        description="Why this is a gap given the full set of policy statements.",
    )


class Remediation(BaseModel):
    """A proposed fix for a Finding (verdict ≠ compliant) or a Gap."""

    remediation_id: str = Field(..., description="Stable ID, e.g. 'rem-001'.")
    target_id: str = Field(
        ...,
        description="The statement_id or gap_id this remediation addresses.",
    )
    target_kind: str = Field(
        ...,
        pattern="^(finding|gap)$",
        description="Whether target_id refers to a Finding's statement_id or a Gap's gap_id.",
    )
    recommendation: str = Field(
        ...,
        min_length=10,
        description="What the company should do (process / control / disclosure).",
    )
    suggested_policy_text: str = Field(
        ...,
        min_length=10,
        description="Drop-in language to add or replace in the policy.",
    )
    related_citations: list[str] = Field(
        default_factory=list,
        description="GDPR chunk_ids that motivate this remediation.",
    )