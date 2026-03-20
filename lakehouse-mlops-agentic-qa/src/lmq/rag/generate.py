"""Answer generation: offline stub by default, optional LLM when configured."""

from __future__ import annotations

import os

from pydantic import BaseModel

from lmq.rag.retrieve import RetrievedChunk

_STUB_PREAMBLE = (
    "**[stub mode — no LLM configured]**\n"
    "The following answer is assembled from the top retrieved chunks:\n\n"
)


class QAAnswer(BaseModel):
    question: str
    answer: str
    mode: str  # "stub" or "llm"
    sources: list[RetrievedChunk]


def _build_context(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] (doc={c.doc_id}, chunk={c.chunk_index})\n{c.text}")
    return "\n\n".join(parts)


def generate_stub(question: str, chunks: list[RetrievedChunk]) -> QAAnswer:
    if not chunks:
        answer = "No relevant chunks found."
    else:
        answer = _STUB_PREAMBLE + _build_context(chunks)
    return QAAnswer(question=question, answer=answer, mode="stub", sources=chunks)


def generate_llm(question: str, chunks: list[RetrievedChunk]) -> QAAnswer:
    """Call an OpenAI-compatible API. Requires OPENAI_API_KEY in env."""
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError as exc:
        msg = "openai package is not installed — run `pip install openai`"
        raise RuntimeError(msg) from exc

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("LMQ_LLM_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key, base_url=base_url)
    context = _build_context(chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a concise QA assistant. Answer the user's question "
                "using ONLY the provided context. If the context does not contain "
                "the answer, say so."
            ),
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0)
    text = resp.choices[0].message.content or ""
    return QAAnswer(question=question, answer=text.strip(), mode="llm", sources=chunks)


def generate(question: str, chunks: list[RetrievedChunk]) -> QAAnswer:
    if os.environ.get("OPENAI_API_KEY"):
        return generate_llm(question, chunks)
    return generate_stub(question, chunks)
