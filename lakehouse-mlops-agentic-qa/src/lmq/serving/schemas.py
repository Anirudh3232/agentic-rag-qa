from __future__ import annotations

from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)


class SourceChunk(BaseModel):
    chunk_id: str
    doc_id: str
    source_path: str
    chunk_index: int
    text: str
    distance: float


class QAResponse(BaseModel):
    question: str
    answer: str
    mode: str
    top_k: int
    sources: list[SourceChunk]


class HealthResponse(BaseModel):
    status: str
    version: str
