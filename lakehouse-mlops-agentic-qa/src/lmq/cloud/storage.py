"""Azure Data Lake Storage Gen2 helpers.

Provides ``storage_options`` for Polars ADLS Parquet I/O and path
utilities.  Returns ``None`` when ``AZURE_STORAGE_ACCOUNT`` is not set,
which causes Polars to use the local filesystem transparently.
"""

from __future__ import annotations

import os
from typing import Any


def get_storage_options() -> dict[str, Any] | None:
    """Build adlfs-compatible storage_options from environment.

    Returns ``None`` when ``AZURE_STORAGE_ACCOUNT`` is not set, keeping
    all Polars I/O local.  When set, uses ``DefaultAzureCredential``
    via adlfs (``anon=False``).
    """
    account = os.environ.get("AZURE_STORAGE_ACCOUNT")
    if not account:
        return None
    return {"account_name": account, "anon": False}


def adls_uri(container: str, path: str, account: str | None = None) -> str:
    """Build an ``abfss://`` URI for ADLS Gen2.

    >>> adls_uri("lake", "gold/gold.parquet", account="myacct")
    'abfss://lake@myacct.dfs.core.windows.net/gold/gold.parquet'
    """
    acct = account or os.environ.get("AZURE_STORAGE_ACCOUNT", "")
    return f"abfss://{container}@{acct}.dfs.core.windows.net/{path}"


def is_cloud_path(path: str) -> bool:
    """Return ``True`` if *path* is an ADLS Gen2 URI."""
    return path.startswith(("abfss://", "az://"))
