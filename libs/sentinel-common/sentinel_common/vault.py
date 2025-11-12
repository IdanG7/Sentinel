"""HashiCorp Vault client for secrets management."""

import logging
from typing import Any, Optional

import hvac
from hvac.exceptions import VaultError

logger = logging.getLogger(__name__)


class VaultClient:
    """
    HashiCorp Vault client for secrets management.

    Supports:
    - Kubernetes auth
    - Token auth
    - Dynamic secret rotation
    - KV v2 secrets engine
    """

    def __init__(
        self,
        url: str,
        auth_method: str = "kubernetes",
        role: Optional[str] = None,
        token: Optional[str] = None,
        namespace: Optional[str] = None,
    ):
        """
        Initialize Vault client.

        Args:
            url: Vault server URL (e.g., https://vault.example.com:8200)
            auth_method: Authentication method (kubernetes, token)
            role: Kubernetes role or AppRole role
            token: Vault token (for token auth)
            namespace: Vault namespace (for Vault Enterprise)
        """
        self.url = url
        self.auth_method = auth_method
        self.role = role
        self.namespace = namespace

        self.client = hvac.Client(url=url, namespace=namespace)

        if auth_method == "token" and token:
            self.client.token = token
            logger.info("Vault client initialized with token auth")
        elif auth_method == "kubernetes":
            self._authenticate_kubernetes()
        else:
            raise ValueError(f"Unsupported auth method: {auth_method}")

    def _authenticate_kubernetes(self) -> None:
        """Authenticate to Vault using Kubernetes service account."""
        try:
            # Read Kubernetes service account token
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token", "r") as f:
                jwt = f.read()

            # Authenticate with Vault
            self.client.auth.kubernetes.login(
                role=self.role,
                jwt=jwt,
            )

            logger.info(f"✓ Authenticated to Vault using Kubernetes auth (role={self.role})")

        except FileNotFoundError:
            logger.warning(
                "Kubernetes service account token not found. "
                "Are you running in a Kubernetes cluster?"
            )
            raise
        except VaultError as e:
            logger.error(f"Failed to authenticate to Vault: {e}")
            raise

    def get_secret(self, path: str, key: Optional[str] = None) -> Any:
        """
        Get a secret from Vault KV v2.

        Args:
            path: Secret path (e.g., "database/sentinel/password")
            key: Optional key within the secret (returns entire secret if None)

        Returns:
            Secret value or dict of all keys

        Example:
            >>> vault.get_secret("database/sentinel", "password")
            "super-secret-password"

            >>> vault.get_secret("database/sentinel")
            {"username": "sentinel", "password": "super-secret-password"}
        """
        try:
            # KV v2 secrets are under /data/ path
            response = self.client.secrets.kv.v2.read_secret_version(path=path)

            secret_data = response["data"]["data"]

            if key:
                return secret_data.get(key)
            return secret_data

        except VaultError as e:
            logger.error(f"Failed to read secret {path}: {e}")
            raise

    def get_secret_or_default(
        self,
        path: str,
        key: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """
        Get a secret from Vault with fallback to default.

        Args:
            path: Secret path
            key: Optional key within the secret
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        try:
            return self.get_secret(path, key)
        except VaultError:
            logger.warning(f"Secret {path}/{key} not found, using default")
            return default

    def set_secret(self, path: str, secrets: dict[str, Any]) -> None:
        """
        Create or update a secret in Vault KV v2.

        Args:
            path: Secret path
            secrets: Dictionary of key-value pairs

        Example:
            >>> vault.set_secret("database/sentinel", {
            ...     "username": "sentinel",
            ...     "password": "new-password"
            ... })
        """
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=secrets,
            )
            logger.info(f"✓ Secret {path} updated successfully")

        except VaultError as e:
            logger.error(f"Failed to write secret {path}: {e}")
            raise

    def delete_secret(self, path: str) -> None:
        """
        Delete a secret from Vault KV v2.

        Args:
            path: Secret path
        """
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=path)
            logger.info(f"✓ Secret {path} deleted successfully")

        except VaultError as e:
            logger.error(f"Failed to delete secret {path}: {e}")
            raise

    def get_database_credentials(
        self,
        database_role: str,
        mount_point: str = "database",
    ) -> dict[str, str]:
        """
        Get dynamic database credentials from Vault.

        Credentials are automatically rotated by Vault.

        Args:
            database_role: Vault database role
            mount_point: Database secrets engine mount point

        Returns:
            {"username": "v-kubernetes-sentinel-...", "password": "..."}
        """
        try:
            response = self.client.secrets.database.generate_credentials(
                name=database_role,
                mount_point=mount_point,
            )

            creds = response["data"]
            logger.info(
                f"✓ Generated dynamic database credentials "
                f"(username={creds['username']}, ttl={creds['lease_duration']}s)"
            )

            return {
                "username": creds["username"],
                "password": creds["password"],
            }

        except VaultError as e:
            logger.error(f"Failed to generate database credentials: {e}")
            raise

    def renew_token(self, increment: Optional[int] = None) -> None:
        """
        Renew the Vault token.

        Args:
            increment: TTL increment in seconds (None for default)
        """
        try:
            self.client.auth.token.renew_self(increment=increment)
            logger.info("✓ Vault token renewed successfully")

        except VaultError as e:
            logger.error(f"Failed to renew Vault token: {e}")
            raise

    @property
    def is_authenticated(self) -> bool:
        """Check if the client is authenticated to Vault."""
        try:
            return self.client.is_authenticated()
        except VaultError:
            return False


def get_vault_client_from_env() -> Optional[VaultClient]:
    """
    Create Vault client from environment variables.

    Environment variables:
        VAULT_ENABLED: Whether Vault is enabled (default: false)
        VAULT_ADDR: Vault server URL
        VAULT_AUTH_METHOD: Auth method (kubernetes, token)
        VAULT_ROLE: Kubernetes role
        VAULT_TOKEN: Vault token (for token auth)
        VAULT_NAMESPACE: Vault namespace (optional)

    Returns:
        VaultClient if enabled, None otherwise
    """
    import os

    if not os.getenv("VAULT_ENABLED", "false").lower() in ("true", "1", "yes"):
        logger.info("Vault disabled")
        return None

    vault_addr = os.getenv("VAULT_ADDR")
    if not vault_addr:
        raise ValueError("VAULT_ADDR required when Vault is enabled")

    auth_method = os.getenv("VAULT_AUTH_METHOD", "kubernetes")
    role = os.getenv("VAULT_ROLE")
    token = os.getenv("VAULT_TOKEN")
    namespace = os.getenv("VAULT_NAMESPACE")

    if auth_method == "kubernetes" and not role:
        raise ValueError("VAULT_ROLE required for Kubernetes auth")

    if auth_method == "token" and not token:
        raise ValueError("VAULT_TOKEN required for token auth")

    return VaultClient(
        url=vault_addr,
        auth_method=auth_method,
        role=role,
        token=token,
        namespace=namespace,
    )
