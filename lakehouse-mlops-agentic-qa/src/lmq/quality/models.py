from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

LayerName = Literal["bronze", "silver", "gold"]


class GateCheckResult(BaseModel):
    name: str
    passed: bool
    detail: str | None = None


class GateReport(BaseModel):
    layer: LayerName
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    passed: bool
    checks: list[GateCheckResult]

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
