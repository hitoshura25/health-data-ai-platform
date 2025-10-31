# Rate limiting configuration for fastapi-limiter
# This module provides the rate limit string used by routes
from app.config import settings

# Rate limit string (parsed by fastapi-limiter)
# Format: "number/period" where period can be: second, minute, hour, day
UPLOAD_RATE_LIMIT = settings.UPLOAD_RATE_LIMIT  # e.g., "10/minute"