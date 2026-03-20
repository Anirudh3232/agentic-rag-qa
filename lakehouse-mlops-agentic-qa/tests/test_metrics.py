"""Unit tests for eval metrics (no index required)."""

from __future__ import annotations

from lmq.eval.metrics import keyword_recall, substring_present


def test_keyword_recall_all_present() -> None:
    passed, recall, missing = keyword_recall(
        "Bronze, Silver, and Gold layers", ["bronze", "silver", "gold"]
    )
    assert passed
    assert recall == 1.0
    assert missing == []


def test_keyword_recall_partial() -> None:
    passed, recall, missing = keyword_recall("Only bronze here", ["bronze", "silver"])
    assert not passed
    assert recall == 0.5
    assert missing == ["silver"]


def test_keyword_recall_empty_expected() -> None:
    passed, recall, _ = keyword_recall("anything", [])
    assert passed
    assert recall == 1.0


def test_substring_present_all() -> None:
    ok, missing = substring_present("quality gates are automated", ["quality gates", "automated"])
    assert ok
    assert missing == []


def test_substring_present_missing() -> None:
    ok, missing = substring_present("quality gates", ["automated checks"])
    assert not ok
    assert missing == ["automated checks"]
