from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Rate limiting with headers enabled for production-like rate limit information
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.UPLOAD_RATE_LIMIT_STORAGE_URI,
    headers_enabled=True  # Enable X-RateLimit-* headers in responses
)