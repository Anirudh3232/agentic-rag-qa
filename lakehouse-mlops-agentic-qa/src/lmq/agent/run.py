"""Minimal RAG agent: retrieve relevant chunks then generate an answer."""

from __future__ import annotations

from pathlib import Path

from lmq.rag.generate import QAAnswer, generate
from lmq.rag.retrieve import retrieve


def ask(question: str, index_dir: Path, top_k: int = 3) -> QAAnswer:
    chunks = retrieve(question, persist_dir=index_dir, top_k=top_k)
    return generate(question, chunks)
