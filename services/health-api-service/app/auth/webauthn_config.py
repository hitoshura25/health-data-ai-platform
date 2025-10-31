"""
WebAuthn server integration configuration.

Uses PyJWKClient to automatically fetch and cache JWKS from WebAuthn server.
This follows RFC 7517 standard for JSON Web Key Sets.
"""

import structlog
from jwt import PyJWKClient
from app.config import settings

logger = structlog.get_logger()


class WebAuthnConfig:
    """
    WebAuthn server configuration using JWKS endpoint.

    Uses PyJWKClient for automatic key fetching and caching (5 minute TTL default).
    This is more robust than manual public key fetching as it:
    - Supports key rotation automatically
    - Handles key ID (kid) matching
    - Caches keys efficiently
    - Follows RFC 7517 standard
    """

    def __init__(self):
        self.jwks_url = settings.WEBAUTHN_JWKS_URL
        self.issuer = settings.WEBAUTHN_ISSUER

        # PyJWKClient automatically fetches and caches JWKS
        logger.info("Initializing JWKS client", jwks_url=self.jwks_url)
        self.jwks_client = PyJWKClient(self.jwks_url)
        logger.info("JWKS client initialized successfully")

    def get_signing_key_from_jwt(self, token: str):
        """
        Get the signing key for a JWT token.

        PyJWKClient fetches the JWKS, finds the key with matching kid,
        and returns the signing key.

        Args:
            token: JWT token string

        Returns:
            Signing key object with .key property for verification

        Raises:
            jwt.exceptions.PyJWKClientError: If key cannot be fetched or found
        """
        return self.jwks_client.get_signing_key_from_jwt(token)


# Global instance - initialized on startup
webauthn_config = WebAuthnConfig()
