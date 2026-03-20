"""Generate Evidently data-drift and quality reports from gold Parquet snapshots.

Derives simple tabular features from the gold layer so Evidently can run
standard statistical tests without touching embeddings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import polars as pl
from evidently import Report  # type: ignore[import-untyped]
from evidently.presets import DataDriftPreset, DataSummaryPreset  # type: ignore[import-untyped]


def _extract_features(gold_parquet: Path) -> pd.DataFrame:
    """Read a gold Parquet and derive tabular features for Evidently."""
    df = pl.read_parquet(gold_parquet)
    features = df.select(
        pl.col("chunk_index"),
        pl.col("text").str.len_chars().alias("chunk_length"),
        pl.col("text").str.split(" ").list.len().alias("token_count"),
    )
    return features.to_pandas()


@dataclass(frozen=True)
class ReportPaths:
    html: Path
    json_summary: Path


def generate_report(
    baseline_parquet: Path,
    current_parquet: Path,
    output_dir: Path,
) -> ReportPaths:
    """Build an Evidently report (Data Drift + Data Summary).

    Returns paths to the HTML report and JSON summary.
    """
    ref = _extract_features(baseline_parquet)
    cur = _extract_features(current_parquet)

    report = Report([DataDriftPreset(), DataSummaryPreset()])
    snapshot = report.run(current_data=cur, reference_data=ref)

    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "evidently_report.html"
    snapshot.save_html(str(html_path))

    summary = _build_summary(snapshot)
    json_path = output_dir / "evidently_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    return ReportPaths(html=html_path, json_summary=json_path)


def _build_summary(snapshot: Any) -> dict[str, Any]:
    """Extract key numbers from the snapshot dict."""
    data: dict[str, Any] = snapshot.dict()
    summary: dict[str, Any] = {"metrics": []}
    for metric in data.get("metrics", []):
        entry: dict[str, Any] = {
            "metric": metric.get("metric_name", "unknown"),
        }
        value = metric.get("value")
        config = metric.get("config", {})
        if "drift_share" in config:
            entry["drifted_columns_count"] = (
                value.get("count") if isinstance(value, dict) else value
            )
        if "column" in config:
            entry["column"] = config["column"]
            entry["drift_score"] = value
        summary["metrics"].append(entry)
    return summary
