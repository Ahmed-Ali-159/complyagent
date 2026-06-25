"""Tests for Finding, Gap, Remediation."""
import pytest
from pydantic import ValidationError

from complyagent.schemas import Finding, Gap, GapSeverity, Remediation, VerdictType


# --- Finding ---

def test_finding_minimal_valid():
    f = Finding(
        statement_id="stmt-001",
        verdict=VerdictType.COMPLIANT,
        rationale="This matches Article 6(1)(a) consent requirements.",
        confidence=0.9,
    )
    assert f.citations == []  # default_factory gives an empty list, not shared


def test_finding_citations_default_is_independent_per_instance():
    """Guards against the mutable-default-argument bug - each Finding's empty
    citations list must NOT be the same object shared across instances."""
    f1 = Finding(statement_id="s1", verdict=VerdictType.UNCLEAR, rationale="x" * 10, confidence=0.5)
    f2 = Finding(statement_id="s2", verdict=VerdictType.UNCLEAR, rationale="y" * 10, confidence=0.5)
    f1.citations.append("GDPR-Art-5-1-a")
    assert f2.citations == []  # f2 must be unaffected by f1's mutation


def test_finding_confidence_out_of_range_raises():
    with pytest.raises(ValidationError):
        Finding(statement_id="s1", verdict=VerdictType.VIOLATION, rationale="x" * 10, confidence=1.5)


def test_finding_rationale_too_short_raises():
    with pytest.raises(ValidationError):
        Finding(statement_id="s1", verdict=VerdictType.VIOLATION, rationale="short", confidence=0.5)


def test_finding_invalid_verdict_raises():
    with pytest.raises(ValidationError):
        Finding(statement_id="s1", verdict="maybe", rationale="x" * 10, confidence=0.5)


# --- Gap ---

def test_gap_requires_at_least_one_basis():
    with pytest.raises(ValidationError):
        Gap(
            gap_id="gap-001",
            requirement="Must disclose data portability rights.",
            gdpr_basis=[],  # empty - should fail min_length=1
            severity=GapSeverity.CRITICAL,
            rationale="No statement addresses this requirement at all.",
        )


def test_gap_valid_with_basis():
    g = Gap(
        gap_id="gap-001",
        requirement="Must disclose data portability rights.",
        gdpr_basis=["GDPR-Art-20"],
        severity=GapSeverity.CRITICAL,
        rationale="No statement addresses this requirement at all.",
    )
    assert g.severity == GapSeverity.CRITICAL


# --- Remediation ---

def test_remediation_valid_target_kind_finding():
    r = Remediation(
        remediation_id="rem-001",
        target_id="stmt-007",
        target_kind="finding",
        recommendation="Add a data retention disclosure.",
        suggested_policy_text="We retain your data for no longer than necessary.",
    )
    assert r.target_kind == "finding"


def test_remediation_valid_target_kind_gap():
    r = Remediation(
        remediation_id="rem-002",
        target_id="gap-003",
        target_kind="gap",
        recommendation="Implement data portability mechanism.",
        suggested_policy_text="You may request your data in a portable format.",
    )
    assert r.target_kind == "gap"


def test_remediation_invalid_target_kind_raises():
    with pytest.raises(ValidationError):
        Remediation(
            remediation_id="rem-003",
            target_id="stmt-007",
            target_kind="something_else",
            recommendation="x" * 15,
            suggested_policy_text="y" * 15,
        )