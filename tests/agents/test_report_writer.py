"""Tests for the Report Writer worker. Mocked LLM."""

from datetime import datetime, UTC
from unittest.mock import patch, MagicMock
from langchain_core.runnables import RunnableLambda

from complyagent.agents.report_writer import write_report, _ReportDraft
from complyagent.schemas.enums import (
    GapSeverity,
    StatementCategory,
    VerdictType,
)
from complyagent.schemas.findings import Finding, Gap, Remediation
from complyagent.schemas.policy import PolicyStatement
from complyagent.schemas.report import AuditReport
from complyagent.schemas.supervisor import SupervisorState


# Helpers ---------------------------------------------------------------------

def _make_statement(stmt_id: str = "stmt-001") -> PolicyStatement:
    return PolicyStatement(
        statement_id=stmt_id,
        text="The company collects user emails.",
        category=StatementCategory.DATA_COLLECTION,
        source_span=None,
    )


def _make_finding(stmt_id: str = "stmt-001") -> Finding:
    return Finding(
        statement_id=stmt_id,
        verdict=VerdictType.COMPLIANT,
        rationale="The statement satisfies the cited GDPR provision.",
        citations=["GDPR-Art-6-1-a"],
        confidence=0.9,
    )


def _make_gap() -> Gap:
    return Gap(
        gap_id="gap-001",
        requirement="Identity of the data controller.",
        gdpr_basis=["GDPR-Art-13-1-a"],
        severity=GapSeverity.CRITICAL,
        rationale="No statement identifies the controller.",
    )


def _make_remediation() -> Remediation:
    return Remediation(
        remediation_id="rem-001",
        target_id="gap-001",
        target_kind="gap",
        recommendation="Add a controller identity clause.",
        suggested_policy_text="The data controller is [Company Name].",
        related_citations=["GDPR-Art-13-1-a"],
    )


def _make_state(
    statements=None,
    findings=None,
    gaps=None,
    remediations=None,
) -> SupervisorState:
    return SupervisorState(
        audit_id="audit-test-001",
        policy_source="test-policy.txt",
        raw_policy_text="Some policy text.",
        audit_mode="full_policy",  # new required field
        statements=statements or [],
        findings=findings or [],
        gaps=gaps or [],
        remediations=remediations or [],
    )


def _patch_chain_returning(draft: _ReportDraft):
    fake_structured = RunnableLambda(lambda _input: draft)
    mock_model = MagicMock()
    # .bind() returns a new model; both the original and bound versions need
    # to expose with_structured_output for the chain to build.
    mock_model.bind.return_value = mock_model
    mock_model.with_structured_output.return_value = fake_structured
    return patch("complyagent.agents.report_writer.get_chat_model", return_value=mock_model)


# Passthrough behavior --------------------------------------------------------

def test_audit_id_and_policy_source_pass_through_from_state():
    draft = _ReportDraft(
        executive_summary="Test summary that is long enough to pass min_length.",
        markdown_report="# Test\n\nMarkdown body that is also long enough to pass the minimum length check.",
    )
    state = _make_state(statements=[_make_statement()])
    with _patch_chain_returning(draft):
        report = write_report(state)

    assert isinstance(report, AuditReport)
    assert report.audit_id == "audit-test-001"
    assert report.policy_source == "test-policy.txt"


def test_all_lists_pass_through_unchanged():
    statements = [_make_statement("stmt-001"), _make_statement("stmt-002")]
    findings = [_make_finding("stmt-001")]
    gaps = [_make_gap()]
    remediations = [_make_remediation()]

    draft = _ReportDraft(
        executive_summary="Test summary that is long enough to pass min_length.",
        markdown_report="# Test\n\nMarkdown body that is also long enough to pass the minimum length check.",
    )
    state = _make_state(
        statements=statements,
        findings=findings,
        gaps=gaps,
        remediations=remediations,
    )
    with _patch_chain_returning(draft):
        report = write_report(state)

    assert report.statements == statements
    assert report.findings == findings
    assert report.gaps == gaps
    assert report.remediations == remediations


def test_llm_outputs_populate_report_fields():
    draft = _ReportDraft(
        executive_summary="Five statements audited, all compliant. No gaps found.",
        markdown_report="# GDPR Compliance Audit Report\n\n## Executive Summary\n\nFive statements audited, all compliant.",
    )
    state = _make_state(statements=[_make_statement()], findings=[_make_finding()])
    with _patch_chain_returning(draft):
        report = write_report(state)

    assert report.executive_summary == draft.executive_summary
    assert report.markdown_report == draft.markdown_report


# Empty list handling ---------------------------------------------------------

def test_empty_gaps_and_remediations_still_produces_valid_report():
    """Case 1 shape: 1 statement, 1 finding, 0 gaps, 0 remediations."""
    draft = _ReportDraft(
        executive_summary="Single-clause audit completed.",
        markdown_report="# GDPR Compliance Audit Report\n\nSingle-clause review of one statement.",
    )
    state = _make_state(
        statements=[_make_statement()],
        findings=[_make_finding()],
        gaps=[],
        remediations=[],
    )
    with _patch_chain_returning(draft):
        report = write_report(state)

    assert report.gaps == []
    assert report.remediations == []
    assert isinstance(report, AuditReport)


def test_completely_empty_state_still_produces_valid_report():
    """Edge case: state with no statements at all."""
    draft = _ReportDraft(
        executive_summary="No statements were extracted from the input.",
        markdown_report="# GDPR Compliance Audit Report\n\nNo content available to audit.",
    )
    state = _make_state()
    with _patch_chain_returning(draft):
        report = write_report(state)

    assert report.statements == []
    assert isinstance(report, AuditReport)


# max_tokens override -------------------------------------------------------

def test_max_tokens_override_applied():
    """Verify .bind(max_tokens=8192) is actually called on the model."""
    draft = _ReportDraft(
        executive_summary="Test summary that is long enough to pass min_length.",
        markdown_report="# Test\n\nMarkdown body that is also long enough to pass the minimum length check.",
    )
    state = _make_state(statements=[_make_statement()])

    mock_model = MagicMock()
    mock_model.bind.return_value = mock_model
    mock_model.with_structured_output.return_value = RunnableLambda(lambda _: draft)

    with patch("complyagent.agents.report_writer.get_chat_model", return_value=mock_model):
        write_report(state)

    mock_model.bind.assert_called_once_with(max_tokens=8192)