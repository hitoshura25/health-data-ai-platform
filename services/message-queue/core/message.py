from dataclasses import dataclass, asdict
from dataclasses_json import dataclass_json
from typing import Dict, Any, Optional
import json
import hashlib
from datetime import datetime

# This import will fail until the config file is created.
# from config.settings import settings

@dataclass_json
@dataclass
class HealthDataMessage:
    """Intelligent health data message format"""

    # Core message data
    bucket: str
    key: str
    user_id: str
    upload_timestamp_utc: str
    record_type: str

    # Message identification
    correlation_id: str
    message_id: str

    # Deduplication
    content_hash: str  # SHA256 of file content
    idempotency_key: str

    # File metadata
    file_size_bytes: int

    # Processing metadata
    retry_count: int = 0
    max_retries: int = 3
    processing_priority: str = "normal"  # low, normal, high

    # File metadata
    record_count: Optional[int] = None

    # Optional health data metadata
    health_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Generate idempotency key if not provided"""
        if not self.idempotency_key:
            key_input = f"{self.user_id}:{self.content_hash}:{self.upload_timestamp_utc}"
            self.idempotency_key = hashlib.sha256(key_input.encode()).hexdigest()[:16]

    def to_json(self) -> str:
        """Convert to JSON for publishing"""
        return json.dumps(asdict(self), default=str, separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> 'HealthDataMessage':
        """Create from JSON"""
        data = json.loads(json_str)
        return cls(**data)

    def get_routing_key(self) -> str:
        """Generate routing key for topic exchange"""
        return f"health.processing.{self.record_type.lower()}.{self.processing_priority}"

    def get_retry_routing_key(self) -> str:
        """Generate routing key for retry scenarios"""
        return f"health.retry.{self.record_type.lower()}.attempt_{self.retry_count}"

    def increment_retry(self) -> 'HealthDataMessage':
        """Create new message with incremented retry count"""
        self.retry_count += 1
        return self

    def calculate_retry_delay(self) -> int:
        """Calculate delay for current retry attempt"""
        # This will be properly implemented once settings are available.
        # For now, using a hardcoded list.
        delays = [30, 300, 900]
        return delays[min(self.retry_count - 1, len(delays) - 1)]
