
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', env_file=".env")

    SECRET_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    S3_ENDPOINT_URL: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str = "health-data"
    RABBITMQ_URL: str
    RABBITMQ_MAIN_EXCHANGE: str
    UPLOAD_RATE_LIMIT: str = "10/minute"
    UPLOAD_RATE_LIMIT_STORAGE_URI: str
    MAX_FILE_SIZE_MB: int = 50

    # Jaeger Distributed Tracing (points to webauthn-stack Jaeger)
    JAEGER_OTLP_ENDPOINT: str = "http://host.docker.internal:4319"
    JAEGER_SERVICE_NAME: str = "health-api-service"

    # WebAuthn Integration (for token exchange)
    # Uses JWKS endpoint (RFC 7517) for automatic key fetching and rotation support
    WEBAUTHN_JWKS_URL: str = "http://host.docker.internal:8000/.well-known/jwks.json"
    WEBAUTHN_JWKS_CACHE_LIFESPAN: int = 300  # JWKS cache duration in seconds (default: 5 minutes for production)
    WEBAUTHN_ISSUER: str = "mpo-webauthn"

    # SSO User Email Domain (for WebAuthn users without email addresses)
    # Use a real domain you control, or example.com for testing (RFC 2606)
    # Note: .local domains fail email validation, use a valid TLD
    SSO_USER_EMAIL_DOMAIN: str = "sso.example.com"

settings = Settings()


def parse_rate_limit(rate_string: str) -> tuple[int, int]:
    """
    Parse rate limit string and return (times, seconds).

    Args:
        rate_string: Rate limit in format "number/period" (e.g., "10/minute")

    Returns:
        Tuple of (times, seconds) for RateLimiter

    Example:
        >>> parse_rate_limit("10/minute")
        (10, 60)
        >>> parse_rate_limit("100/hour")
        (100, 3600)
    """
    rate_parts = rate_string.split("/")
    rate_times = int(rate_parts[0])
    rate_period = rate_parts[1] if len(rate_parts) > 1 else "minute"

    # Convert period to seconds
    period_seconds = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400
    }.get(rate_period, 60)

    return rate_times, period_seconds
