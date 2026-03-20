"""Tests for the FastAPI serving layer.

Requires a built index (lmq pipeline run + lmq qa build-index).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lmq.serving.api import create_app

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "configs" / "pipeline.yaml"


@pytest.fixture(scope="module")
def client() -> TestClient:
    if not _CONFIG_PATH.is_file():
        pytest.skip(f"Config not found: {_CONFIG_PATH}")
    app = create_app(_CONFIG_PATH)
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_qa_success(client: TestClient) -> None:
    resp = client.post("/v1/qa", json={"question": "What are quality gates?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == "What are quality gates?"
    assert isinstance(body["answer"], str)
    assert len(body["answer"]) > 0
    assert body["mode"] in ("stub", "llm")
    assert isinstance(body["top_k"], int)
    assert isinstance(body["sources"], list)
    assert len(body["sources"]) > 0
    src = body["sources"][0]
    assert "chunk_id" in src
    assert "doc_id" in src
    assert "distance" in src


def test_qa_custom_top_k(client: TestClient) -> None:
    resp = client.post("/v1/qa", json={"question": "What is RAG?", "top_k": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["top_k"] == 2
    assert len(body["sources"]) <= 2


def test_qa_empty_question_rejected(client: TestClient) -> None:
    resp = client.post("/v1/qa", json={"question": ""})
    assert resp.status_code == 422


def test_qa_missing_question_rejected(client: TestClient) -> None:
    resp = client.post("/v1/qa", json={})
    assert resp.status_code == 422
