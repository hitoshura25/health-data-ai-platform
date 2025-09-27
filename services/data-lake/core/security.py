import hashlib
import hmac
from typing import Optional


def generate_hmac_signature(secret_key: str, message: str) -> str:
    """Generate HMAC-SHA256 signature."""
    return hmac.new(
        secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_hmac_signature(secret_key: str, message: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected_signature = generate_hmac_signature(secret_key, message)
    return hmac.compare_digest(expected_signature, signature)
