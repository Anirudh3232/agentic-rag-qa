"""AWS Secrets Manager integration with environment-variable fallback.

Call :func:`load_secrets` at application startup.  If the AWS SDK
(boto3) is installed and a secret ARN/name is configured, secrets are
fetched and injected into ``os.environ``.  Otherwise the function
silently returns, letting the caller rely on plain environment variables.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_SECRET_KEY_TO_ENV: dict[str, str] = {
    "OPENAI_API_KEY": "OPENAI_API_KEY",
}


def load_secrets(
    secret_name: str | None = None,
    region: str | None = None,
) -> None:
    """Fetch secrets from AWS Secrets Manager and export to env vars.

    *secret_name* falls back to ``AWS_SECRET_NAME`` env var.  The secret
    value is expected to be a JSON object whose keys map to environment
    variable names (see ``_SECRET_KEY_TO_ENV``).

    If neither is set, or boto3 is missing, this is a no-op.
    """
    name = secret_name or os.environ.get("AWS_SECRET_NAME")
    if not name:
        logger.debug("No secret name configured; using environment variables")
        return

    try:
        import boto3  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("boto3 not installed; skipping Secrets Manager")
        return

    aws_region = region or os.environ.get("AWS_REGION", "us-east-1")

    try:
        client = boto3.client("secretsmanager", region_name=aws_region)
        response = client.get_secret_value(SecretId=name)
        secret_dict = json.loads(response["SecretString"])
    except Exception:
        logger.warning("Failed to fetch secret %s from Secrets Manager", name, exc_info=True)
        return

    for secret_key, env_var in _SECRET_KEY_TO_ENV.items():
        if os.environ.get(env_var):
            logger.debug("%s already set; skipping Secrets Manager lookup", env_var)
            continue
        value = secret_dict.get(secret_key)
        if value:
            os.environ[env_var] = value
            logger.info("Loaded %s from Secrets Manager", env_var)
