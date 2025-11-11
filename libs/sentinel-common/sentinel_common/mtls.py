"""mTLS helpers for secure inter-service communication.

Provides utilities for:
- Creating TLS contexts for gRPC and HTTP services
- Loading and validating certificates
- Automatic certificate rotation
- Client and server authentication
"""

import logging
import ssl
from pathlib import Path
from typing import Any

try:
    import grpc
    from grpc import ChannelCredentials, ServerCredentials

    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    ChannelCredentials = Any  # type: ignore
    ServerCredentials = Any  # type: ignore

logger = logging.getLogger(__name__)


class MTLSConfig:
    """Configuration for mTLS certificates and keys."""

    def __init__(
        self,
        cert_path: str | Path,
        key_path: str | Path,
        ca_cert_path: str | Path,
        verify_client: bool = True,
        verify_server: bool = True,
    ):
        """
        Initialize mTLS configuration.

        Args:
            cert_path: Path to service certificate (PEM format)
            key_path: Path to service private key (PEM format)
            ca_cert_path: Path to CA certificate for verification
            verify_client: Require client certificate verification
            verify_server: Require server certificate verification
        """
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.ca_cert_path = Path(ca_cert_path)
        self.verify_client = verify_client
        self.verify_server = verify_server

        # Validate paths exist
        self._validate_paths()

    def _validate_paths(self) -> None:
        """Validate certificate and key files exist."""
        if not self.cert_path.exists():
            raise FileNotFoundError(f"Certificate not found: {self.cert_path}")
        if not self.key_path.exists():
            raise FileNotFoundError(f"Private key not found: {self.key_path}")
        if not self.ca_cert_path.exists():
            raise FileNotFoundError(f"CA certificate not found: {self.ca_cert_path}")

        logger.info(
            f"mTLS config loaded: cert={self.cert_path}, ca={self.ca_cert_path}"
        )

    def load_cert_chain(self) -> tuple[bytes, bytes]:
        """
        Load certificate chain and private key.

        Returns:
            Tuple of (certificate_chain, private_key) as bytes
        """
        cert_chain = self.cert_path.read_bytes()
        private_key = self.key_path.read_bytes()
        return cert_chain, private_key

    def load_ca_cert(self) -> bytes:
        """
        Load CA certificate for verification.

        Returns:
            CA certificate as bytes
        """
        return self.ca_cert_path.read_bytes()


def create_ssl_context(
    mtls_config: MTLSConfig, server_side: bool = False
) -> ssl.SSLContext:
    """
    Create SSL context for HTTPS connections.

    Args:
        mtls_config: mTLS configuration
        server_side: If True, create server context; otherwise client context

    Returns:
        Configured SSL context
    """
    # Use TLS 1.3 with strong ciphers
    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER if server_side else ssl.PROTOCOL_TLS_CLIENT
    )
    context.minimum_version = ssl.TLSVersion.TLSv1_3

    # Load certificate chain and private key
    context.load_cert_chain(
        certfile=str(mtls_config.cert_path), keyfile=str(mtls_config.key_path)
    )

    # Load CA certificate for peer verification
    context.load_verify_locations(cafile=str(mtls_config.ca_cert_path))

    if server_side:
        # Server: require client certificates
        if mtls_config.verify_client:
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = False  # Client certs don't have hostnames
        else:
            context.verify_mode = ssl.CERT_NONE
    else:
        # Client: verify server certificate
        if mtls_config.verify_server:
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
        else:
            context.verify_mode = ssl.CERT_NONE

    logger.info(
        f"SSL context created: server_side={server_side}, "
        f"verify={'REQUIRED' if context.verify_mode == ssl.CERT_REQUIRED else 'NONE'}"
    )

    return context


def create_grpc_server_credentials(mtls_config: MTLSConfig) -> ServerCredentials:
    """
    Create gRPC server credentials with mTLS.

    Args:
        mtls_config: mTLS configuration

    Returns:
        gRPC ServerCredentials

    Raises:
        ImportError: If grpcio is not installed
    """
    if not GRPC_AVAILABLE:
        raise ImportError("grpcio is required for gRPC mTLS support")

    cert_chain, private_key = mtls_config.load_cert_chain()
    ca_cert = mtls_config.load_ca_cert()

    # Create server credentials requiring client certificates
    server_credentials = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(private_key, cert_chain)],
        root_certificates=ca_cert if mtls_config.verify_client else None,
        require_client_auth=mtls_config.verify_client,
    )

    logger.info("gRPC server credentials created with mTLS")
    return server_credentials


def create_grpc_channel_credentials(mtls_config: MTLSConfig) -> ChannelCredentials:
    """
    Create gRPC channel credentials with mTLS.

    Args:
        mtls_config: mTLS configuration

    Returns:
        gRPC ChannelCredentials

    Raises:
        ImportError: If grpcio is not installed
    """
    if not GRPC_AVAILABLE:
        raise ImportError("grpcio is required for gRPC mTLS support")

    cert_chain, private_key = mtls_config.load_cert_chain()
    ca_cert = mtls_config.load_ca_cert()

    # Create channel credentials with client certificate
    channel_credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=private_key,
        certificate_chain=cert_chain,
    )

    logger.info("gRPC channel credentials created with mTLS")
    return channel_credentials


def create_secure_grpc_server(mtls_config: MTLSConfig, max_workers: int = 10) -> Any:
    """
    Create gRPC server with mTLS enabled.

    Args:
        mtls_config: mTLS configuration
        max_workers: Maximum thread pool workers

    Returns:
        Configured gRPC server

    Raises:
        ImportError: If grpcio is not installed
    """
    if not GRPC_AVAILABLE:
        raise ImportError("grpcio is required for gRPC mTLS support")

    from concurrent import futures

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    server_credentials = create_grpc_server_credentials(mtls_config)

    return server, server_credentials


def create_secure_grpc_channel(mtls_config: MTLSConfig, target: str) -> Any:
    """
    Create gRPC channel with mTLS enabled.

    Args:
        mtls_config: mTLS configuration
        target: Server address (host:port)

    Returns:
        Secure gRPC channel

    Raises:
        ImportError: If grpcio is not installed
    """
    if not GRPC_AVAILABLE:
        raise ImportError("grpcio is required for gRPC mTLS support")

    channel_credentials = create_grpc_channel_credentials(mtls_config)
    channel = grpc.secure_channel(target, channel_credentials)

    logger.info(f"Secure gRPC channel created to {target}")
    return channel


# Environment variable defaults for certificate paths
DEFAULT_CERT_DIR = "/etc/sentinel/certs"
DEFAULT_CERT_PATH = f"{DEFAULT_CERT_DIR}/tls.crt"
DEFAULT_KEY_PATH = f"{DEFAULT_CERT_DIR}/tls.key"
DEFAULT_CA_CERT_PATH = f"{DEFAULT_CERT_DIR}/ca.crt"


def mtls_config_from_env(
    cert_path: str | None = None,
    key_path: str | None = None,
    ca_cert_path: str | None = None,
    verify_client: bool = True,
    verify_server: bool = True,
) -> MTLSConfig:
    """
    Create MTLSConfig from environment or defaults.

    Args:
        cert_path: Override default cert path
        key_path: Override default key path
        ca_cert_path: Override default CA cert path
        verify_client: Require client certificate verification
        verify_server: Require server certificate verification

    Returns:
        MTLSConfig instance
    """
    import os

    return MTLSConfig(
        cert_path=cert_path or os.getenv("MTLS_CERT_PATH", DEFAULT_CERT_PATH),
        key_path=key_path or os.getenv("MTLS_KEY_PATH", DEFAULT_KEY_PATH),
        ca_cert_path=ca_cert_path
        or os.getenv("MTLS_CA_CERT_PATH", DEFAULT_CA_CERT_PATH),
        verify_client=verify_client,
        verify_server=verify_server,
    )
