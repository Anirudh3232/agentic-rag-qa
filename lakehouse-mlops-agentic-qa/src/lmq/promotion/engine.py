"""Rules-based promotion engine.

Reads the latest run manifest, regression report, and evidently summary,
then applies YAML-configured thresholds to produce a reject / canary /
production decision.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from lmq.config import PromotionRules

Decision = Literal["reject", "canary", "production"]


class PromotionInput(BaseModel):
    manifest_status: str
    all_gates_passed: bool
    regression_pass_rate: float | None = None
    drifted_columns: int | None = None


class PromotionResult(BaseModel):
    decision: Decision
    reasons: list[str]
    thresholds: dict[str, Any]
    inputs: PromotionInput
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ── artifact discovery ──────────────────────────────────────────────


def _latest_file(directory: Path, glob: str) -> Path | None:
    files = sorted(directory.glob(glob), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def discover_inputs(artifacts_dir: Path) -> PromotionInput:
    """Read the latest artifacts and build a PromotionInput."""
    manifest_path = _latest_file(artifacts_dir / "runs", "*_run_manifest.json")
    if manifest_path is None:
        return PromotionInput(
            manifest_status="missing",
            all_gates_passed=False,
        )

    manifest = _load_json(manifest_path)
    status = manifest.get("status", "unknown")

    gates = manifest.get("gate_results", {})
    all_gates = all(layer.get("passed", False) for layer in gates.values()) if gates else False

    regression_path = _latest_file(artifacts_dir / "regression", "*_regression.json")
    pass_rate: float | None = None
    if regression_path is not None:
        reg = _load_json(regression_path)
        pass_rate = reg.get("pass_rate")

    evidently_path = artifacts_dir / "evidently" / "evidently_summary.json"
    drifted: int | None = None
    if evidently_path.is_file():
        ev = _load_json(evidently_path)
        for m in ev.get("metrics", []):
            if "drifted_columns_count" in m:
                drifted = int(m["drifted_columns_count"])
                break

    return PromotionInput(
        manifest_status=status,
        all_gates_passed=all_gates,
        regression_pass_rate=pass_rate,
        drifted_columns=drifted,
    )


# ── decision rules ──────────────────────────────────────────────────


def evaluate(inputs: PromotionInput, rules: PromotionRules) -> PromotionResult:
    reasons: list[str] = []
    thresholds = rules.model_dump()

    if inputs.manifest_status != "success":
        reasons.append(f"pipeline status is '{inputs.manifest_status}', expected 'success'")

    if not inputs.all_gates_passed:
        reasons.append("one or more quality gates failed")

    if inputs.regression_pass_rate is None:
        reasons.append("no regression report found")
    elif inputs.regression_pass_rate < rules.canary_min_pass_rate:
        reasons.append(
            f"regression pass rate {inputs.regression_pass_rate:.1%} "
            f"< canary minimum {rules.canary_min_pass_rate:.1%}"
        )

    if inputs.drifted_columns is not None and inputs.drifted_columns > rules.max_drifted_columns:
        reasons.append(
            f"drifted columns {inputs.drifted_columns} "
            f"> max allowed {rules.max_drifted_columns}"
        )

    if reasons:
        return PromotionResult(
            decision="reject", reasons=reasons, thresholds=thresholds, inputs=inputs
        )

    if (
        inputs.regression_pass_rate is not None
        and inputs.regression_pass_rate < rules.prod_min_pass_rate
    ):
        reasons.append(
            f"regression pass rate {inputs.regression_pass_rate:.1%} "
            f"< production minimum {rules.prod_min_pass_rate:.1%} "
            f"(>= canary minimum {rules.canary_min_pass_rate:.1%})"
        )
        return PromotionResult(
            decision="canary", reasons=reasons, thresholds=thresholds, inputs=inputs
        )

    reasons.append("all checks passed")
    return PromotionResult(
        decision="production", reasons=reasons, thresholds=thresholds, inputs=inputs
    )


def write_result(result: PromotionResult, artifacts_dir: Path) -> Path:
    out_dir = artifacts_dir / "promotion"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = result.created_at.strftime("%Y%m%dT%H%M%S")
    path = out_dir / f"{ts}_promotion.json"
    path.write_text(json.dumps(result.to_json_dict(), indent=2), encoding="utf-8")
    return path
