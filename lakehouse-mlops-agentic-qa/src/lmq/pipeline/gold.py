from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class GoldOutput:
    path: Path
    row_count: int


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        msg = "max_chars must be >= 1"
        raise ValueError(msg)
    if not text:
        return []
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def build_gold(silver_parquet: Path, gold_parquet: Path, chunk_max_chars: int) -> GoldOutput:
    silver = pl.read_parquet(silver_parquet)
    rows: list[dict[str, object]] = []
    for row in silver.iter_rows(named=True):
        doc_id = str(row["doc_id"])
        source_path = str(row["source_path"])
        clean = str(row["clean_text"])
        ingested_at = row["ingested_at"]
        chunks = _chunk_text(clean, chunk_max_chars)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}#{idx}"
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": idx,
                    "text": chunk,
                    "source_path": source_path,
                    "ingested_at": ingested_at,
                }
            )
    df = pl.DataFrame(rows)
    gold_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(gold_parquet)
    return GoldOutput(path=gold_parquet, row_count=len(df))
