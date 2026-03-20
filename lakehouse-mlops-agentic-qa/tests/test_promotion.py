"""Unit tests for the promotion engine (no artifacts or index required)."""

from __future__ import annotations

from lmq.config import PromotionRules
from lmq.promotion.engine import PromotionInput, evaluate


def _rules(**overrides: object) -> PromotionRules:
    defaults = {
        "prod_min_pass_rate": 1.0,
        "canary_min_pass_rate": 0.75,
        "max_drifted_columns": 0,
    }
    defaults.update(overrides)
    return PromotionRules.model_validate(defaults)


def test_production_when_all_green() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=True,
        regression_pass_rate=1.0,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "production"


def test_reject_when_pipeline_failed() -> None:
    inp = PromotionInput(
        manifest_status="failed",
        all_gates_passed=True,
        regression_pass_rate=1.0,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "reject"
    assert any("pipeline status" in r for r in result.reasons)


def test_reject_when_gate_failed() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=False,
        regression_pass_rate=1.0,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "reject"
    assert any("gates failed" in r for r in result.reasons)


def test_reject_when_regression_too_low() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=True,
        regression_pass_rate=0.5,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "reject"
    assert any("canary minimum" in r for r in result.reasons)


def test_canary_when_pass_rate_between_thresholds() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=True,
        regression_pass_rate=0.9,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "canary"
    assert any("production minimum" in r for r in result.reasons)


def test_reject_when_drift_exceeds_max() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=True,
        regression_pass_rate=1.0,
        drifted_columns=2,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "reject"
    assert any("drifted columns" in r for r in result.reasons)


def test_reject_when_no_regression_report() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=True,
        regression_pass_rate=None,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules())
    assert result.decision == "reject"
    assert any("no regression report" in r for r in result.reasons)


def test_thresholds_included_in_result() -> None:
    inp = PromotionInput(
        manifest_status="success",
        all_gates_passed=True,
        regression_pass_rate=1.0,
        drifted_columns=0,
    )
    result = evaluate(inp, _rules(prod_min_pass_rate=0.95))
    assert result.thresholds["prod_min_pass_rate"] == 0.95
    assert result.decision == "production"
