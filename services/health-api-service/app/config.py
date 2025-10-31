
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
    WEBAUTHN_ISSUER: str = "mpo-webauthn"

settings = Settings()
