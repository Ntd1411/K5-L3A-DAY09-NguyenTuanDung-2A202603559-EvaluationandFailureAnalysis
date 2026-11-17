"""Regression tests for docs/trace_case.md: seeded_regression failure modes.

Exercises first-wrong-step assertions and code grader verifications on:
- C-014@11: FM-05 (pre_deducted) leading to FM-08 (reply/ledger mismatch)
- C-002@11: FM-03 (ticket_trust / model_override overwriting DB delay_days)
"""

import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def graders():
    # The overlaid Lab 8 CI collects these tests with only Lab 8 dependencies.
    from lab9 import graders

    return graders


@pytest.fixture(scope="module")
def trace_case():
    from lab9 import trace_case

    return trace_case


def _make_ctx(case):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(
        name="trace_case",
        inputs={},
        metadata=None,
        expected_output=case["label"],
        output=case["trial"],
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


@pytest.fixture(scope="module")
def case_c014_regression(trace_case):
    return trace_case.investigate("seeded_regression", "C-014", 11)


@pytest.fixture(scope="module")
def case_c014_fixed(trace_case):
    return trace_case.investigate("fixed", "C-014", 11)


@pytest.fixture(scope="module")
def case_c002_regression(trace_case):
    return trace_case.investigate("seeded_regression", "C-002", 11)


@pytest.fixture(scope="module")
def case_c002_fixed(trace_case):
    return trace_case.investigate("fixed", "C-002", 11)


def test_trace_case_c014_first_wrong_step(case_c014_regression):
    events = case_c014_regression["trial"]["events"]
    kinds = [e.get("kind") for e in events]
    assert kinds[:5] == ["handoff", "investigator", "quote", "refund_history", "proposal"]
    # Step 3 quote is correct (150.000đ)
    assert events[2]["payload"]["amount_vnd"] == 150000
    # Step 4 history is correct (30.000đ)
    assert events[3]["payload"]["refunded_vnd"] == 30000
    # Step 5 is the FIRST wrong step: pre-deducts history before calling host
    assert events[4]["payload"]["amount_vnd"] == 120000


def test_trace_case_c014_graders_catch_error(case_c014_regression, graders):
    ctx = _make_ctx(case_c014_regression)
    # The host deducted 30.000 again from 120.000 -> 90.000 in ledger
    assert case_c014_regression["trial"]["snapshot"]["refund_vnd"] == 90000
    assert graders.ProposalAmountCorrect().evaluate(ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(ctx).value is False
    # Reply claimed 120.000đ but ledger committed 90.000đ
    assert graders.ReplyLedgerConsistent().evaluate(ctx).value is False


def test_trace_case_c014_fixed_passes(case_c014_fixed, graders):
    ctx = _make_ctx(case_c014_fixed)
    assert case_c014_fixed["trial"]["snapshot"]["refund_vnd"] == 120000
    assert "proposal" not in [e.get("kind") for e in case_c014_fixed["trial"]["events"]]
    assert graders.ProposalAmountCorrect().evaluate(ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(ctx).value is True
    assert graders.ReplyLedgerConsistent().evaluate(ctx).value is True
    assert graders.TrialPass().evaluate(ctx).value is True


def test_trace_case_c002_first_wrong_step(case_c002_regression):
    events = case_c002_regression["trial"]["events"]
    assert len(events) >= 3
    assert events[0]["kind"] == "handoff"
    assert events[1]["kind"] == "investigator"
    # Event 3 is the FIRST wrong step: overrides DB delay_days
    assert events[2]["kind"] == "model_override"
    assert events[2]["payload"].get("delay_days") == 5


def test_trace_case_c002_graders_catch_error(case_c002_regression, graders):
    ctx = _make_ctx(case_c002_regression)
    assert graders.DbFactKept().evaluate(ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(ctx).value is False
    assert graders.TrialPass().evaluate(ctx).value is False


def test_trace_case_c002_fixed_passes(case_c002_fixed, graders):
    ctx = _make_ctx(case_c002_fixed)
    assert "model_override" not in [e.get("kind") for e in case_c002_fixed["trial"]["events"]]
    assert case_c002_fixed["trial"]["snapshot"]["refund_vnd"] == 0
    assert graders.DbFactKept().evaluate(ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(ctx).value is True
    assert graders.TrialPass().evaluate(ctx).value is True
