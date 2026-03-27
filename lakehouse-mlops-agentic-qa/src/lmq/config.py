from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class GateThresholds(BaseModel):
    bronze_min_rows: int = Field(ge=0)
    silver_min_rows: int = Field(ge=0)
    gold_min_rows: int = Field(ge=0)
    min_text_length: int = Field(ge=0)


class RAGConfig(BaseModel):
    index_dir: Path = Path("artifacts/chroma")
    top_k: int = Field(default=3, ge=1, le=50)


class PromotionRules(BaseModel):
    prod_min_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    canary_min_pass_rate: float = Field(default=0.75, ge=0.0, le=1.0)
    max_drifted_columns: int = Field(default=0, ge=0)


class CloudConfig(BaseModel):
    """Optional AWS cloud settings. Ignored when absent."""

    s3_bucket: str | None = None
    aws_region: str | None = None
    secret_name: str | None = None
    mlflow_tracking_uri: str | None = None


class PipelineConfig(BaseModel):
    raw_dir: Path
    lake_root: Path
    artifacts_dir: Path
    gold_chunk_max_chars: int = Field(ge=1, le=100_000)
    rag: RAGConfig = RAGConfig()
    promotion: PromotionRules = PromotionRules()
    gates: GateThresholds
    cloud: CloudConfig | None = None

    @classmethod
    def load(cls, path: Path) -> PipelineConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg = f"Config must be a mapping: {path}"
            raise ValueError(msg)
        return cls.model_validate(raw)
