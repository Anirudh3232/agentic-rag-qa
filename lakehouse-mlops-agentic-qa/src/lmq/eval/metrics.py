"""Deterministic scoring functions for regression tests.

All checks operate on the full answer string (case-insensitive) so they
remain stable in offline stub mode where the answer is just concatenated
retrieved chunks.
"""

from __future__ import annotations


def keyword_recall(answer: str, expected: list[str]) -> tuple[bool, float, list[str]]:
    """Check what fraction of *expected* keywords appear in *answer*.

    Returns (passed, recall, missing_keywords).
    A case passes when recall == 1.0 (all keywords found).
    """
    lower = answer.lower()
    missing = [kw for kw in expected if kw.lower() not in lower]
    total = len(expected) if expected else 1
    recall = (total - len(missing)) / total
    return len(missing) == 0, recall, missing


def substring_present(answer: str, expected: list[str]) -> tuple[bool, list[str]]:
    """Check that every expected substring appears verbatim (case-insensitive).

    Returns (all_present, missing_substrings).
    """
    lower = answer.lower()
    missing = [s for s in expected if s.lower() not in lower]
    return len(missing) == 0, missing
