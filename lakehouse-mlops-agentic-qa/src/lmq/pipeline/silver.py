from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class SilverOutput:
    path: Path
    row_count: int


def transform_silver(bronze_parquet: Path, silver_parquet: Path) -> SilverOutput:
    df = pl.read_parquet(bronze_parquet)
    with_title = df.with_columns(
        pl.col("raw_text")
        .str.split("\n")
        .list.get(0)
        .fill_null("")
        .str.strip_chars()
        .alias("title")
    )
    cleaned = with_title.with_columns(
        pl.col("raw_text")
        .str.replace_all(r"\r\n", "\n")
        .str.replace_all(r"\n+", " ")
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
        .alias("clean_text")
    )
    hashed = cleaned.with_columns(
        pl.col("clean_text").hash(seed=0).cast(pl.Utf8).alias("content_hash")
    )
    out = hashed.select(
        [
            "doc_id",
            "source_path",
            "title",
            "clean_text",
            "content_hash",
            "ingested_at",
        ]
    )
    silver_parquet.parent.mkdir(parents=True, exist_ok=True)
    out.write_parquet(silver_parquet)
    return SilverOutput(path=silver_parquet, row_count=len(out))
