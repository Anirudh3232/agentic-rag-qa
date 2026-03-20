from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LayerManifest(BaseModel):
    path: str
    row_count: int


class RunManifest(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    config_path: str
    raw_dir: str
    bronze: LayerManifest | None = None
    silver: LayerManifest | None = None
    gold: LayerManifest | None = None
    duckdb_smoke: dict[str, Any] = Field(default_factory=dict)
    gate_results: dict[str, Any] = Field(default_factory=dict)
    status: str = "running"

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
