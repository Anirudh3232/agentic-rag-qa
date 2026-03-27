"""Amazon S3 storage helpers.

Provides ``storage_options`` for Polars S3 Parquet I/O and path
utilities.  Returns ``None`` when ``AWS_S3_BUCKET`` is not set, which
causes Polars to use the local filesystem transparently.
"""

from __future__ import annotations

import os
from typing import Any


def get_storage_options() -> dict[str, Any] | None:
    """Build s3fs-compatible storage_options from environment.

    Returns ``None`` when ``AWS_S3_BUCKET`` is not set, keeping all
    Polars I/O local.  When set, uses the default boto3 credential
    chain (env vars, IAM role, SSO profile, etc.).
    """
    bucket = os.environ.get("AWS_S3_BUCKET")
    if not bucket:
        return None
    region = os.environ.get("AWS_REGION", "us-east-1")
    return {"region": region}


def s3_uri(bucket: str, key: str) -> str:
    """Build an ``s3://`` URI.

    >>> s3_uri("lmq-data", "lake/gold/gold.parquet")
    's3://lmq-data/lake/gold/gold.parquet'
    """
    return f"s3://{bucket}/{key}"


def is_cloud_path(path: str) -> bool:
    """Return ``True`` if *path* is an S3 URI."""
    return path.startswith("s3://")
