"""Optional MLflow experiment tracking.

Every public function is best-effort: it silently returns when MLflow is
not installed or ``MLFLOW_TRACKING_URI`` is not set.  This lets the same
pipeline code run locally (no tracking) and in the cloud (full tracking
via SageMaker MLflow or any compatible server) without conditional
imports at the call site.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        return False
    try:
        import mlflow  # noqa: F401

        return True
    except ImportError:
        return False


def log_pipeline_run(
    run_id: str,
    status: str,
    gate_results: dict[str, Any],
    layer_counts: dict[str, int],
    tracking_uri: str | None = None,
) -> None:
    if tracking_uri:
        os.environ.setdefault("MLFLOW_TRACKING_URI", tracking_uri)
    if not is_configured():
        return
    import mlflow

    mlflow.set_experiment("lmq-pipeline")
    with mlflow.start_run(run_name=f"pipeline-{run_id[:8]}"):
        mlflow.log_param("pipeline_run_id", run_id)
        mlflow.log_param("status", status)
        for layer, count in layer_counts.items():
            mlflow.log_metric(f"{layer}_row_count", count)
        for layer, result in gate_results.items():
            passed = result.get("passed", False) if isinstance(result, dict) else False
            mlflow.log_metric(f"{layer}_gate_passed", int(passed))
    logger.info("Pipeline run %s logged to MLflow", run_id[:8])


def log_regression(
    run_id: str,
    total: int,
    passed: int,
    pass_rate: float,
) -> None:
    if not is_configured():
        return
    import mlflow

    mlflow.set_experiment("lmq-regression")
    with mlflow.start_run(run_name=f"regression-{run_id[:8]}"):
        mlflow.log_param("regression_run_id", run_id)
        mlflow.log_metric("total_cases", total)
        mlflow.log_metric("passed_cases", passed)
        mlflow.log_metric("pass_rate", pass_rate)
    logger.info("Regression run %s logged to MLflow", run_id[:8])


def log_promotion(
    decision: str,
    reasons: list[str],
    pass_rate: float | None,
    drifted_columns: int | None,
) -> None:
    if not is_configured():
        return
    import mlflow

    mlflow.set_experiment("lmq-promotion")
    with mlflow.start_run(run_name=f"promotion-{decision}"):
        mlflow.log_param("decision", decision)
        mlflow.log_param("reasons", "; ".join(reasons))
        if pass_rate is not None:
            mlflow.log_metric("regression_pass_rate", pass_rate)
        if drifted_columns is not None:
            mlflow.log_metric("drifted_columns", drifted_columns)
    logger.info("Promotion decision '%s' logged to MLflow", decision)
