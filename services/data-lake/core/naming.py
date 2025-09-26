import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
import re
import structlog

logger = structlog.get_logger()

@dataclass
class ObjectKeyComponents:
    """Components of an intelligent object key"""
    layer: str  # raw, processed, quarantine, training
    record_type: str
    user_id: str
    timestamp: datetime
    file_hash: str
    source_device: Optional[str] = None
    processing_version: Optional[str] = None
    reason: Optional[str] = None  # For quarantine

class IntelligentObjectKeyGenerator:
    """Generate intelligent object keys with embedded metadata"""

    def __init__(self, hash_length: int = 8):
        self.hash_length = hash_length

    def generate_raw_key(
        self,
        record_type: str,
        user_id: str,
        timestamp: datetime,
        file_hash: str,
        source_device: str = "unknown"
    ) -> str:
        """
        Generate structured key for raw health data
        Format: raw/{record_type}/{year}/{month}/{day}/{user_id}_{timestamp}_{device}_{hash}.avro
        """
        # Validate inputs
        self._validate_inputs(record_type, user_id, file_hash)

        # Build date hierarchy
        date_path = timestamp.strftime("%Y/%m/%d")
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Sanitize and truncate components
        clean_record_type = self._sanitize_component(record_type)
        clean_user_id = self._sanitize_component(user_id)
        clean_device = self._sanitize_component(source_device)
        short_hash = file_hash[:self.hash_length]

        # Build filename
        filename = f"{clean_user_id}_{timestamp_str}_{clean_device}_{short_hash}.avro"

        # Build full key
        object_key = f"raw/{clean_record_type}/{date_path}/{filename}"

        logger.debug("Generated raw object key",
                    record_type=record_type,
                    user_id=user_id,
                    object_key=object_key)

        return object_key

    def generate_processed_key(
        self,
        record_type: str,
        user_id: str,
        processing_date: datetime,
        processing_version: str = "v1",
        file_format: str = "jsonl"
    ) -> str:
        """Generate key for processed/aggregated data"""
        self._validate_inputs(record_type, user_id)

        date_path = processing_date.strftime("%Y/%m")
        timestamp_str = processing_date.strftime("%Y%m%d_%H%M%S")

        clean_record_type = self._sanitize_component(record_type)
        clean_user_id = self._sanitize_component(user_id)
        clean_version = self._sanitize_component(processing_version)

        filename = f"{clean_user_id}_{timestamp_str}_{clean_version}.{file_format}"
        object_key = f"processed/{clean_record_type}/{date_path}/{filename}"

        return object_key

    def generate_quarantine_key(
        self,
        original_key: str,
        reason: str,
        quarantine_timestamp: Optional[datetime] = None
    ) -> str:
        """Move failed files to quarantine with reason"""
        if quarantine_timestamp is None:
            quarantine_timestamp = datetime.utcnow()

        timestamp_str = quarantine_timestamp.strftime("%Y%m%d_%H%M%S")
        clean_reason = self._sanitize_component(reason)

        # Extract filename from original key
        filename = original_key.split("/")[-1]
        base_name = filename.split(".")[0]

        object_key = f"quarantine/{clean_reason}/{timestamp_str}_{base_name}.avro"

        logger.info("Generated quarantine key",
                   original_key=original_key,
                   quarantine_key=object_key,
                   reason=reason)

        return object_key

    def generate_training_key(
        self,
        data_type: str,
        training_date: datetime,
        version: str = "v1",
        file_format: str = "jsonl"
    ) -> str:
        """Generate key for training datasets"""
        date_path = training_date.strftime("%Y/%m")
        timestamp_str = training_date.strftime("%Y%m%d")

        clean_data_type = self._sanitize_component(data_type)
        clean_version = self._sanitize_component(version)

        filename = f"health_journal_{timestamp_str}_{clean_version}.{file_format}"
        object_key = f"training/{clean_data_type}/{date_path}/{filename}"

        return object_key

    def parse_object_key(self, object_key: str) -> Optional[ObjectKeyComponents]:
        """Parse object key to extract metadata components"""
        try:
            parts = object_key.split("/")

            if len(parts) < 4:
                return None

            layer = parts[0]

            if layer == "raw" and len(parts) >= 6:
                record_type = parts[1]
                year, month, day = parts[2], parts[3], parts[4]
                filename = parts[5]

                # Parse filename: {user_id}_{timestamp}_{device}_{hash}.avro
                name_parts = filename.replace(".avro", "").split("_")
                if len(name_parts) >= 4:
                    user_id = name_parts[0]
                    timestamp_str = f"{name_parts[1]}_{name_parts[2]}"
                    device = name_parts[3] if len(name_parts) > 4 else name_parts[3]
                    file_hash = name_parts[-1]

                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    return ObjectKeyComponents(
                        layer=layer,
                        record_type=record_type,
                        user_id=user_id,
                        timestamp=timestamp,
                        file_hash=file_hash,
                        source_device=device
                    )

            elif layer == "quarantine" and len(parts) >= 3:
                reason = parts[1]
                filename = parts[2]

                return ObjectKeyComponents(
                    layer=layer,
                    record_type="unknown",
                    user_id="unknown",
                    timestamp=datetime.utcnow(),
                    file_hash="unknown",
                    reason=reason
                )

            return None

        except Exception as e:
            logger.error("Failed to parse object key", object_key=object_key, error=str(e))
            return None

    def _validate_inputs(self, record_type: str, user_id: str, file_hash: str = None):
        """Validate input parameters"""
        if not record_type or not record_type.strip():
            raise ValueError("record_type cannot be empty")

        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")

        if file_hash and len(file_hash) < self.hash_length:
            raise ValueError(f"file_hash must be at least {self.hash_length} characters")

    def _sanitize_component(self, component: str) -> str:
        """Sanitize component for use in object keys"""
        if not component:
            return "unknown"

        # Replace invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '_', component)

        # Limit length
        max_length = 50
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.lower()

    def generate_analytics_key(self, analytics_type: str, date: datetime) -> str:
        """Generate key for analytics data"""
        date_str = date.strftime("%Y%m%d")
        return f"analytics/{analytics_type}/{date_str}.json"