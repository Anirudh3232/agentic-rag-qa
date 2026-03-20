"""Azure Key Vault integration with environment-variable fallback.

Call :func:`load_secrets` at application startup.  If a vault URL is
configured and the Azure SDK is installed, secrets are fetched and
injected into ``os.environ``.  Otherwise the function silently returns,
letting the caller rely on plain environment variables.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_VAULT_TO_ENV: dict[str, str] = {
    "OPENAI-API-KEY": "OPENAI_API_KEY",
}


def load_secrets(vault_url: str | None = None) -> None:
    """Fetch secrets from Key Vault and set them as environment variables.

    *vault_url* falls back to the ``AZURE_KEYVAULT_URL`` env var.  If
    neither is set, or the Azure SDK is missing, this is a no-op.
    """
    url = vault_url or os.environ.get("AZURE_KEYVAULT_URL")
    if not url:
        logger.debug("No Key Vault URL configured; using environment variables")
        return

    try:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("azure-identity/azure-keyvault-secrets not installed; skipping Key Vault")
        return

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=url, credential=credential)

    for secret_name, env_var in _VAULT_TO_ENV.items():
        if os.environ.get(env_var):
            logger.debug("%s already set; skipping Key Vault lookup", env_var)
            continue
        try:
            secret = client.get_secret(secret_name)
            if secret.value:
                os.environ[env_var] = secret.value
                logger.info("Loaded %s from Key Vault", env_var)
        except Exception:
            logger.warning("Failed to load %s from Key Vault", secret_name, exc_info=True)
