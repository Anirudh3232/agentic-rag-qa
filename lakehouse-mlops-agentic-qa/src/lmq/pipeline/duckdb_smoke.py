from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def smoke_query_parquet(parquet_path: Path) -> dict[str, Any]:
    """Run lightweight DuckDB checks against a Parquet file."""
    path = parquet_path.resolve()
    if not path.is_file():
        msg = f"Parquet file not found: {path}"
        raise FileNotFoundError(msg)

    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(
            "SELECT COUNT(*)::BIGINT AS n FROM read_parquet(?)",
            [str(path)],
        ).fetchone()
        if row is None:
            msg = "DuckDB returned no rows for COUNT"
            raise RuntimeError(msg)
        row_count = row[0]
        sample_cols = con.execute(
            "SELECT * FROM read_parquet(?) LIMIT 0",
            [str(path)],
        ).description
        columns = [c[0] for c in sample_cols] if sample_cols else []
        return {
            "parquet_path": str(path),
            "row_count": int(row_count),
            "columns": columns,
        }
    finally:
        con.close()


def smoke_all_layers(
    bronze: Path,
    silver: Path,
    gold: Path,
) -> dict[str, Any]:
    return {
        "bronze": smoke_query_parquet(bronze),
        "silver": smoke_query_parquet(silver),
        "gold": smoke_query_parquet(gold),
    }
