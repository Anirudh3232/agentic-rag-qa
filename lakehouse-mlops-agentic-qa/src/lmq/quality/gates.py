from __future__ import annotations

import polars as pl

from lmq.config import GateThresholds
from lmq.quality.models import GateCheckResult, GateReport, LayerName


def run_layer_gates(
    layer: LayerName,
    run_id: str,
    df: pl.DataFrame,
    thresholds: GateThresholds,
) -> GateReport:
    if layer == "bronze":
        return _gate_bronze(run_id, df, thresholds)
    if layer == "silver":
        return _gate_silver(run_id, df, thresholds)
    return _gate_gold(run_id, df, thresholds)


def _gate_bronze(run_id: str, df: pl.DataFrame, t: GateThresholds) -> GateReport:
    checks: list[GateCheckResult] = []
    n = len(df)
    checks.append(
        GateCheckResult(
            name="bronze_min_rows",
            passed=n >= t.bronze_min_rows,
            detail=f"rows={n}, min={t.bronze_min_rows}",
        )
    )
    if "raw_text" in df.columns:
        too_short = df.filter(pl.col("raw_text").str.len_chars() < t.min_text_length)
        checks.append(
            GateCheckResult(
                name="bronze_raw_text_min_length",
                passed=len(too_short) == 0,
                detail=f"violations={len(too_short)}",
            )
        )
    else:
        checks.append(
            GateCheckResult(
                name="bronze_has_raw_text_column",
                passed=False,
                detail="missing column raw_text",
            )
        )
    passed = all(c.passed for c in checks)
    return GateReport(layer="bronze", run_id=run_id, passed=passed, checks=checks)


def _gate_silver(run_id: str, df: pl.DataFrame, t: GateThresholds) -> GateReport:
    checks: list[GateCheckResult] = []
    n = len(df)
    checks.append(
        GateCheckResult(
            name="silver_min_rows",
            passed=n >= t.silver_min_rows,
            detail=f"rows={n}, min={t.silver_min_rows}",
        )
    )
    if "doc_id" in df.columns:
        dup = df.group_by("doc_id").len().filter(pl.col("len") > 1)
        checks.append(
            GateCheckResult(
                name="silver_doc_id_unique",
                passed=len(dup) == 0,
                detail=f"duplicate_doc_ids={len(dup)}",
            )
        )
    else:
        checks.append(
            GateCheckResult(
                name="silver_has_doc_id_column",
                passed=False,
                detail="missing column doc_id",
            )
        )
    if "clean_text" in df.columns:
        too_short = df.filter(pl.col("clean_text").str.len_chars() < t.min_text_length)
        checks.append(
            GateCheckResult(
                name="silver_clean_text_min_length",
                passed=len(too_short) == 0,
                detail=f"violations={len(too_short)}",
            )
        )
    else:
        checks.append(
            GateCheckResult(
                name="silver_has_clean_text_column",
                passed=False,
                detail="missing column clean_text",
            )
        )
    passed = all(c.passed for c in checks)
    return GateReport(layer="silver", run_id=run_id, passed=passed, checks=checks)


def _gate_gold(run_id: str, df: pl.DataFrame, t: GateThresholds) -> GateReport:
    checks: list[GateCheckResult] = []
    n = len(df)
    checks.append(
        GateCheckResult(
            name="gold_min_rows",
            passed=n >= t.gold_min_rows,
            detail=f"rows={n}, min={t.gold_min_rows}",
        )
    )
    if "text" in df.columns:
        empty = df.filter(pl.col("text").str.len_chars() < t.min_text_length)
        checks.append(
            GateCheckResult(
                name="gold_chunk_text_min_length",
                passed=len(empty) == 0,
                detail=f"violations={len(empty)}",
            )
        )
    else:
        checks.append(
            GateCheckResult(
                name="gold_has_text_column",
                passed=False,
                detail="missing column text",
            )
        )
    passed = all(c.passed for c in checks)
    return GateReport(layer="gold", run_id=run_id, passed=passed, checks=checks)
