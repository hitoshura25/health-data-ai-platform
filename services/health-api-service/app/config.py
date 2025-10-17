
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

settings = Settings()
