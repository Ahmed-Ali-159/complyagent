"""Tests for SupervisorState, SupervisorDecision."""
import pytest
from pydantic import ValidationError

from complyagent.schemas import SupervisorDecision, SupervisorState, WorkerName


def test_supervisor_state_minimal_valid():
    state = SupervisorState(
        audit_id="audit-001",
        policy_source="https://example.com/privacy",
        raw_policy_text="We collect your email address.",
    )
    assert state.statements == []
    assert state.findings == []
    assert state.report is None
    assert state.iteration == 0


def test_supervisor_state_collections_are_independent_across_instances():
    s1 = SupervisorState(audit_id="a1", policy_source="x", raw_policy_text="x")
    s2 = SupervisorState(audit_id="a2", policy_source="y", raw_policy_text="y")
    s1.decisions.append(
        SupervisorDecision(iteration=0, next_worker=WorkerName.POLICY_PARSER, reasoning="start here")
    )
    assert s2.decisions == []


def test_supervisor_decision_terminal_has_no_next_worker():
    d = SupervisorDecision(iteration=5, next_worker=None, reasoning="all done", is_terminal=True)
    assert d.next_worker is None
    assert d.is_terminal is True


def test_supervisor_decision_negative_iteration_raises():
    with pytest.raises(ValidationError):
        SupervisorDecision(iteration=-1, reasoning="bad iteration")


def test_supervisor_decision_short_reasoning_raises():
    with pytest.raises(ValidationError):
        SupervisorDecision(iteration=0, reasoning="hi")


def test_reretrieval_counts_default_empty_dict():
    state = SupervisorState(audit_id="a1", policy_source="x", raw_policy_text="x")
    assert state.reretrieval_counts == {}
    state.reretrieval_counts["stmt-001"] = 1
    state2 = SupervisorState(audit_id="a2", policy_source="y", raw_policy_text="y")
    assert state2.reretrieval_counts == {}  # must not share the mutated dict