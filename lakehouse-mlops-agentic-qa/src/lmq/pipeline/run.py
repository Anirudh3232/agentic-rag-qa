from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from lmq.config import PipelineConfig
from lmq.pipeline.bronze import ingest_bronze
from lmq.pipeline.duckdb_smoke import smoke_query_parquet
from lmq.pipeline.gold import build_gold
from lmq.pipeline.manifest import LayerManifest, RunManifest
from lmq.pipeline.silver import transform_silver
from lmq.quality.gates import run_layer_gates
from lmq.quality.models import GateReport, LayerName


class PipelineGateError(RuntimeError):
    """Raised when a layer gate fails (fail-fast)."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _write_gate_artifact(report: GateReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_json_dict()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_gate_and_persist(
    layer: LayerName,
    run_id: str,
    df: pl.DataFrame,
    cfg: PipelineConfig,
    gates_dir: Path,
) -> GateReport:
    report = run_layer_gates(
        layer=layer,
        run_id=run_id,
        df=df,
        thresholds=cfg.gates,
    )
    _write_gate_artifact(report, gates_dir / f"{layer}_{run_id}.json")
    return report


def run_pipeline(cfg: PipelineConfig, config_path: Path, raw_dir_override: Path | None) -> Path:
    run_id = str(uuid.uuid4())
    started = _utc_now()
    raw_dir = (raw_dir_override or cfg.raw_dir).resolve()
    lake = cfg.lake_root.resolve()
    artifacts = cfg.artifacts_dir.resolve()

    bronze_path = lake / "bronze" / "bronze.parquet"
    silver_path = lake / "silver" / "silver.parquet"
    gold_path = lake / "gold" / "gold.parquet"
    gates_dir = artifacts / "gates"
    manifest_path = artifacts / "runs" / f"{run_id}_run_manifest.json"

    manifest = RunManifest(
        run_id=run_id,
        started_at=started,
        config_path=str(config_path.resolve()),
        raw_dir=str(raw_dir),
    )

    def fail_fast(report: GateReport, layer: LayerName) -> None:
        manifest.gate_results[layer] = report.to_json_dict()
        manifest.status = "failed"
        manifest.finished_at = _utc_now()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_json_dict(), indent=2),
            encoding="utf-8",
        )
        msg = f"Gate failed for layer={layer}: {report.checks}"
        raise PipelineGateError(msg)

    try:
        bo = ingest_bronze(raw_dir, bronze_path)
        bronze_df = pl.read_parquet(bo.path)
        br = _run_gate_and_persist("bronze", run_id, bronze_df, cfg, gates_dir)
        manifest.gate_results["bronze"] = br.to_json_dict()
        if not br.passed:
            fail_fast(br, "bronze")

        so = transform_silver(bo.path, silver_path)
        silver_df = pl.read_parquet(so.path)
        sr = _run_gate_and_persist("silver", run_id, silver_df, cfg, gates_dir)
        manifest.gate_results["silver"] = sr.to_json_dict()
        if not sr.passed:
            fail_fast(sr, "silver")

        go = build_gold(so.path, gold_path, cfg.gold_chunk_max_chars)
        gold_df = pl.read_parquet(go.path)
        gr = _run_gate_and_persist("gold", run_id, gold_df, cfg, gates_dir)
        manifest.gate_results["gold"] = gr.to_json_dict()
        if not gr.passed:
            fail_fast(gr, "gold")

        manifest.bronze = LayerManifest(path=str(bo.path.resolve()), row_count=bo.row_count)
        manifest.silver = LayerManifest(path=str(so.path.resolve()), row_count=so.row_count)
        manifest.gold = LayerManifest(path=str(go.path.resolve()), row_count=go.row_count)

        manifest.duckdb_smoke = {
            "bronze": smoke_query_parquet(bo.path),
            "silver": smoke_query_parquet(so.path),
            "gold": smoke_query_parquet(go.path),
        }
        manifest.status = "success"
        manifest.finished_at = _utc_now()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_json_dict(), indent=2),
            encoding="utf-8",
        )

        try:
            from lmq.cloud.mlflow_log import log_pipeline_run

            log_pipeline_run(
                run_id=run_id,
                status="success",
                gate_results=manifest.gate_results,
                layer_counts={
                    "bronze": bo.row_count,
                    "silver": so.row_count,
                    "gold": go.row_count,
                },
                tracking_uri=(
                    cfg.cloud.mlflow_tracking_uri if cfg.cloud else None
                ),
            )
        except Exception:
            pass

        return manifest_path
    except PipelineGateError:
        raise
    except Exception as exc:
        manifest.status = "failed"
        manifest.finished_at = _utc_now()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_json_dict(), indent=2),
            encoding="utf-8",
        )
        msg = f"Pipeline failed: {exc}"
        raise RuntimeError(msg) from exc
