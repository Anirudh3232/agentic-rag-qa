# Databricks notebook source
# MAGIC %md
# MAGIC # LMQ Medallion Pipeline — Databricks Job
# MAGIC
# MAGIC Runs the bronze → silver → gold pipeline against ADLS Gen2 storage
# MAGIC via Unity Catalog volumes, then logs results to Azure ML (MLflow).
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - The `lmq` wheel installed as a cluster library
# MAGIC - Unity Catalog volume `/Volumes/lmq_catalog/default/raw` with source documents
# MAGIC - ADLS Gen2 access via Unity Catalog external locations

# COMMAND ----------

# MAGIC %pip install /Workspace/packages/lmq-0.1.0-py3-none-any.whl --quiet
# dbutils.library.restartPython()  # uncomment if needed after install

# COMMAND ----------

import json
from pathlib import Path

from lmq.config import PipelineConfig
from lmq.pipeline.run import run_pipeline

cfg = PipelineConfig.load(Path("/Workspace/configs/pipeline.azure.yaml"))
manifest_path = run_pipeline(cfg, Path("/Workspace/configs/pipeline.azure.yaml"), raw_dir_override=None)

print(f"Pipeline complete. Manifest: {manifest_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log results to Azure ML (MLflow)

# COMMAND ----------

import mlflow

mlflow.set_tracking_uri(dbutils.secrets.get("lmq-scope", "mlflow-tracking-uri"))  # noqa: F821
mlflow.set_experiment("/lmq/pipeline-runs")

manifest = json.loads(Path(manifest_path).read_text())

with mlflow.start_run(run_name=f"pipeline-{manifest['run_id'][:8]}"):
    mlflow.log_param("run_id", manifest["run_id"])
    mlflow.log_param("status", manifest["status"])

    for layer in ("bronze", "silver", "gold"):
        info = manifest.get(layer)
        if info:
            mlflow.log_metric(f"{layer}_row_count", info["row_count"])

    for layer, result in manifest.get("gate_results", {}).items():
        mlflow.log_metric(f"{layer}_gate_passed", int(result.get("passed", False)))

    mlflow.log_artifact(str(manifest_path))

print("Results logged to MLflow")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build vector index (optional)
# MAGIC
# MAGIC Only needed when the gold layer changes.

# COMMAND ----------

from lmq.rag.chunking import load_gold_chunks
from lmq.rag.index import build_index

gold_parquet = Path(cfg.lake_root) / "gold" / "gold.parquet"
chunks = load_gold_chunks(gold_parquet)
count = build_index(chunks, cfg.rag.index_dir)
print(f"Index built: {count} chunks")
