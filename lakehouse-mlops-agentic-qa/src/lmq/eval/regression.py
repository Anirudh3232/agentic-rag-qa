"""Regression test runner: load golden set, run QA, score, write artifact."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from lmq.agent.run import ask
from lmq.eval.metrics import keyword_recall, substring_present


class GoldenCase(BaseModel):
    question: str
    expected_keywords: list[str] = Field(default_factory=list)
    expected_substrings: list[str] = Field(default_factory=list)


class CaseResult(BaseModel):
    question: str
    passed: bool
    keyword_recall: float
    missing_keywords: list[str]
    missing_substrings: list[str]
    answer_preview: str
    mode: str


class RegressionReport(BaseModel):
    run_id: str
    created_at: datetime
    total: int
    passed: int
    failed: int
    pass_rate: float
    cases: list[CaseResult]

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def load_golden_set(path: Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        cases.append(GoldenCase.model_validate_json(line))
    return cases


def run_regression(
    golden_path: Path,
    index_dir: Path,
    top_k: int = 3,
) -> RegressionReport:
    cases = load_golden_set(golden_path)
    results: list[CaseResult] = []
    for gc in cases:
        answer = ask(gc.question, index_dir=index_dir, top_k=top_k)
        text = answer.answer

        kw_passed, kw_recall, kw_missing = keyword_recall(text, gc.expected_keywords)
        sub_passed, sub_missing = substring_present(text, gc.expected_substrings)
        passed = kw_passed and sub_passed

        preview = text[:200] + ("..." if len(text) > 200 else "")
        results.append(
            CaseResult(
                question=gc.question,
                passed=passed,
                keyword_recall=kw_recall,
                missing_keywords=kw_missing,
                missing_substrings=sub_missing,
                answer_preview=preview,
                mode=answer.mode,
            )
        )

    total = len(results)
    n_passed = sum(1 for r in results if r.passed)
    return RegressionReport(
        run_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        total=total,
        passed=n_passed,
        failed=total - n_passed,
        pass_rate=n_passed / total if total else 0.0,
        cases=results,
    )


def write_report(report: RegressionReport, artifacts_dir: Path) -> Path:
    out_dir = artifacts_dir / "regression"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.run_id}_regression.json"
    path.write_text(json.dumps(report.to_json_dict(), indent=2), encoding="utf-8")
    return path
