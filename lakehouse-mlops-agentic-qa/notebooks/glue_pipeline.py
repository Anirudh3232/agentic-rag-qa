"""AWS Glue Python Shell Job — LMQ Medallion Pipeline.

Runs the bronze -> silver -> gold pipeline against S3 storage, then
optionally logs results to a SageMaker MLflow tracking server.

Prerequisites:
  - The ``lmq`` wheel uploaded to S3 and referenced as an
    ``--extra-py-files`` argument in the Glue job definition.
  - An S3 bucket with source documents under the ``raw/`` prefix.
  - (Optional) A SageMaker MLflow tracking server for experiment logging.

Glue job parameters (passed via --additional-python-modules or
resolved from environment):
  --S3_BUCKET        Target S3 bucket name
  --AWS_REGION       AWS region (default: us-east-1)
  --SECRET_NAME      Secrets Manager secret name (optional)
  --MLFLOW_URI       MLflow tracking URI (optional)
"""

import json
import sys
from pathlib import Path

from awsglue.utils import getResolvedOptions  # type: ignore[import-untyped]

from lmq.config import PipelineConfig
from lmq.pipeline.run import run_pipeline

args = getResolvedOptions(sys.argv, ["S3_BUCKET", "AWS_REGION"])

bucket = args["S3_BUCKET"]
region = args.get("AWS_REGION", "us-east-1")

cfg_content = f"""\
raw_dir: s3://{bucket}/raw
lake_root: s3://{bucket}/lake
artifacts_dir: s3://{bucket}/artifacts
gold_chunk_max_chars: 500
rag:
  index_dir: /tmp/lmq/chroma
  top_k: 3
promotion:
  prod_min_pass_rate: 1.0
  canary_min_pass_rate: 0.75
  max_drifted_columns: 0
gates:
  bronze_min_rows: 1
  silver_min_rows: 1
  gold_min_rows: 1
  min_text_length: 1
cloud:
  s3_bucket: {bucket}
  aws_region: {region}
"""

cfg_path = Path("/tmp/pipeline_glue.yaml")
cfg_path.write_text(cfg_content, encoding="utf-8")

cfg = PipelineConfig.load(cfg_path)
manifest_path = run_pipeline(cfg, cfg_path, raw_dir_override=None)

print(f"Pipeline complete. Manifest: {manifest_path}")

manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
print(f"Status: {manifest['status']}")
for layer in ("bronze", "silver", "gold"):
    info = manifest.get(layer)
    if info:
        print(f"  {layer}: {info['row_count']} rows")
