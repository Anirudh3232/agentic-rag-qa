from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

TEXT_EXTENSIONS = {".md", ".txt"}


@dataclass(frozen=True)
class BronzeOutput:
    path: Path
    row_count: int


def _utc_now_naive() -> datetime:
    """UTC wall time as naive datetime (avoids tzdata issues on some Windows setups)."""
    return datetime.now(UTC).replace(tzinfo=None)


def ingest_bronze(raw_dir: Path, bronze_parquet: Path) -> BronzeOutput:
    """Read text files from raw_dir and write a single bronze Parquet table."""
    raw_dir = raw_dir.resolve()
    rows: list[dict[str, object]] = []
    if not raw_dir.is_dir():
        msg = f"raw_dir is not a directory: {raw_dir}"
        raise FileNotFoundError(msg)

    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel = path.relative_to(raw_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        rows.append(
            {
                "doc_id": rel,
                "source_path": str(path.resolve()),
                "raw_text": text,
                "ingested_at": _utc_now_naive(),
            }
        )

    bronze_parquet.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(rows, schema_overrides={"ingested_at": pl.Datetime(time_unit="us")})
    df.write_parquet(bronze_parquet)
    return BronzeOutput(path=bronze_parquet, row_count=len(df))
