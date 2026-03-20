"""Pytest wrapper around the regression runner.

Requires a built index (lmq pipeline run + lmq qa build-index).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lmq.config import PipelineConfig
from lmq.eval.regression import load_golden_set, run_regression

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "configs" / "pipeline.yaml"
_GOLDEN_PATH = _PROJECT_ROOT / "tests" / "golden" / "qa_pairs.jsonl"


@pytest.fixture(scope="module")
def config() -> PipelineConfig:
    if not _CONFIG_PATH.is_file():
        pytest.skip(f"Config not found: {_CONFIG_PATH}")
    return PipelineConfig.load(_CONFIG_PATH)


@pytest.fixture(scope="module")
def index_dir(config: PipelineConfig) -> Path:
    d = config.rag.index_dir
    if not d.is_dir():
        pytest.skip("Chroma index not built — run `lmq qa build-index` first")
    return d


def test_golden_set_loads() -> None:
    cases = load_golden_set(_GOLDEN_PATH)
    assert len(cases) > 0, "Golden set is empty"
    for c in cases:
        assert c.question, "Question must not be empty"
        assert c.expected_keywords or c.expected_substrings, (
            f"Case '{c.question}' has no expectations"
        )


def test_regression_all_pass(config: PipelineConfig, index_dir: Path) -> None:
    report = run_regression(
        golden_path=_GOLDEN_PATH,
        index_dir=index_dir,
        top_k=config.rag.top_k,
    )
    failures = [c for c in report.cases if not c.passed]
    details = "\n".join(
        f"  FAIL: {c.question} | missing_kw={c.missing_keywords}"
        for c in failures
    )
    assert report.pass_rate == 1.0, (
        f"Regression pass rate {report.pass_rate:.1%} < 100%\n{details}"
    )
