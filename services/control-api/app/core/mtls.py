"""mTLS integration for Control API.

Provides HTTPS server with mutual TLS authentication.
"""

import logging
import os

from sentinel_common.mtls import create_ssl_context, mtls_config_from_env

logger = logging.getLogger(__name__)


class ControlAPIMTLS:
    """mTLS configuration for Control API server."""

    def __init__(
        self,
        enabled: bool = True,
        cert_path: str | None = None,
        key_path: str | None = None,
        ca_cert_path: str | None = None,
        verify_client: bool = False,  # Optional for API (can use JWT instead)
    ):
        """
        Initialize Control API mTLS.

        Args:
            enabled: Enable mTLS (disable for local development)
            cert_path: Path to server certificate
            key_path: Path to server private key
            ca_cert_path: Path to CA certificate
            verify_client: Require client certificates (optional, JWT can be used)
        """
        self.enabled = enabled

        if not enabled:
            logger.warning("mTLS is DISABLED - not recommended for production")
            self.config = None
            self.ssl_context = None
            return

        # Load mTLS configuration
        try:
            self.config = mtls_config_from_env(
                cert_path=cert_path,
                key_path=key_path,
                ca_cert_path=ca_cert_path,
                verify_client=verify_client,
                verify_server=False,  # Server doesn't verify itself
            )

            # Create SSL context for server
            self.ssl_context = create_ssl_context(self.config, server_side=True)

            logger.info("Control API mTLS enabled")

        except FileNotFoundError as e:
            logger.error(f"Failed to load mTLS certificates: {e}")
            logger.warning("Falling back to HTTP (insecure)")
            self.enabled = False
            self.config = None
            self.ssl_context = None

    def get_ssl_context(self):
        """
        Get SSL context for uvicorn/FastAPI.

        Returns:
            ssl.SSLContext or None if mTLS is disabled
        """
        return self.ssl_context if self.enabled else None

    def get_uvicorn_ssl_config(self) -> dict:
        """
        Get SSL configuration for uvicorn server.

        Returns:
            Dict with ssl_keyfile, ssl_certfile, ssl_ca_certs
        """
        if not self.enabled or not self.config:
            return {}

        return {
            "ssl_keyfile": str(self.config.key_path),
            "ssl_certfile": str(self.config.cert_path),
            "ssl_ca_certs": str(self.config.ca_cert_path),
            "ssl_cert_reqs": (
                2 if self.config.verify_client else 0
            ),  # CERT_REQUIRED or CERT_NONE
        }


# Global instance (initialized at startup)
_mtls_instance: ControlAPIMTLS | None = None


def init_mtls(
    enabled: bool | None = None,
    cert_path: str | None = None,
    key_path: str | None = None,
    ca_cert_path: str | None = None,
    verify_client: bool = False,
) -> ControlAPIMTLS:
    """
    Initialize global mTLS configuration.

    Args:
        enabled: Enable mTLS (reads from MTLS_ENABLED env var if None)
        cert_path: Path to server certificate
        key_path: Path to server private key
        ca_cert_path: Path to CA certificate
        verify_client: Require client certificates

    Returns:
        ControlAPIMTLS instance
    """
    global _mtls_instance

    if enabled is None:
        enabled = os.getenv("MTLS_ENABLED", "true").lower() == "true"

    _mtls_instance = ControlAPIMTLS(
        enabled=enabled,
        cert_path=cert_path,
        key_path=key_path,
        ca_cert_path=ca_cert_path,
        verify_client=verify_client,
    )

    return _mtls_instance


def get_mtls() -> ControlAPIMTLS:
    """
    Get global mTLS configuration.

    Returns:
        ControlAPIMTLS instance

    Raises:
        RuntimeError: If mTLS not initialized
    """
    if _mtls_instance is None:
        raise RuntimeError("mTLS not initialized. Call init_mtls() first.")
    return _mtls_instance
