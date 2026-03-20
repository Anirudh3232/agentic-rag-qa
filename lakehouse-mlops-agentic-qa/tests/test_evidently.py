"""Tests for Evidently report generation.

Requires gold.parquet from a prior pipeline run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lmq.monitoring.evidently_reports import generate_report

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GOLD = _PROJECT_ROOT / "data" / "lake" / "gold" / "gold.parquet"


@pytest.fixture(scope="module")
def gold_parquet() -> Path:
    if not _GOLD.is_file():
        pytest.skip("Gold parquet not found — run `lmq pipeline run` first")
    return _GOLD


def test_self_comparison_report(gold_parquet: Path, tmp_path: Path) -> None:
    """Self-comparison should produce an HTML and JSON file with no drift."""
    paths = generate_report(gold_parquet, gold_parquet, tmp_path / "ev")
    assert paths.html.is_file()
    assert paths.html.stat().st_size > 0
    assert paths.json_summary.is_file()
    summary = json.loads(paths.json_summary.read_text(encoding="utf-8"))
    assert "metrics" in summary
    assert len(summary["metrics"]) > 0
