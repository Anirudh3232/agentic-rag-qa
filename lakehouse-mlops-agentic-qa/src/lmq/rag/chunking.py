"""Load gold-layer chunks into typed records for indexing and retrieval."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from pydantic import BaseModel


class GoldChunk(BaseModel):
    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    source_path: str


def load_gold_chunks(gold_parquet: Path) -> list[GoldChunk]:
    df = pl.read_parquet(gold_parquet)
    return [
        GoldChunk(
            chunk_id=str(row["chunk_id"]),
            doc_id=str(row["doc_id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
            source_path=str(row["source_path"]),
        )
        for row in df.iter_rows(named=True)
    ]
