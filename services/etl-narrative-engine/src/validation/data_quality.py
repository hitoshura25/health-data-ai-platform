"""
Data Quality Validation Framework

This module implements comprehensive data validation and quality assessment
for health data files.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from .config import ValidationConfig

logger = structlog.get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of data quality validation"""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Add an error message"""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)


class DataQualityValidator:
    """
    Data quality validator for health records.

    This validator performs comprehensive validation including:
    - Schema validation
    - Data completeness checking
    - Physiological range validation
    - Temporal consistency checking
    - Quality score calculation
    """

    def __init__(
        self,
        config: ValidationConfig | None = None,
        s3_client: Any | None = None,
        bucket_name: str = "health-data"
    ):
        """
        Initialize validator.

        Args:
            config: Validation configuration (uses defaults if None)
            s3_client: S3 client for quarantine operations (optional)
            bucket_name: S3 bucket name for quarantine
        """
        self.config = config or ValidationConfig()
        self.config.validate_weights()
        self.s3_client = s3_client
        self.bucket_name = bucket_name

    async def validate(
        self,
        records: list[dict],
        record_type: str,
        file_size_bytes: int
    ) -> ValidationResult:
        """
        Validate health data records.

        Args:
            records: List of parsed Avro records
            record_type: Type of health data (e.g., "BloodGlucoseRecord")
            file_size_bytes: Size of original file

        Returns:
            ValidationResult with quality assessment
        """
        result = ValidationResult(is_valid=True)

        # Basic file checks
        if not records:
            result.add_error("No records found in file")
            return result

        if len(records) > self.config.max_records_per_file:
            result.add_warning(
                f"File contains {len(records)} records, exceeds limit of "
                f"{self.config.max_records_per_file}"
            )

        max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
        if file_size_bytes > max_size_bytes:
            result.add_warning(
                f"File size {file_size_bytes} bytes exceeds limit of "
                f"{max_size_bytes} bytes"
            )

        # Perform validation checks
        schema_valid = await self._validate_schema(records, record_type)
        completeness_score = await self._check_completeness(records, record_type)
        physiological_score = await self._check_physiological_ranges(
            records, record_type
        )
        temporal_score = await self._check_temporal_consistency(records)

        # Store individual scores in metadata
        result.metadata['schema_valid'] = schema_valid
        result.metadata['completeness_score'] = completeness_score
        result.metadata['physiological_score'] = physiological_score
        result.metadata['temporal_score'] = temporal_score
        result.metadata['record_count'] = len(records)
        result.metadata['record_type'] = record_type

        # Calculate quality score
        schema_score = 1.0 if schema_valid else 0.0
        quality_score = (
            self.config.schema_weight * schema_score +
            self.config.completeness_weight * completeness_score +
            self.config.physiological_weight * physiological_score +
            self.config.temporal_weight * temporal_score
        )
        result.quality_score = quality_score

        # Add errors/warnings based on scores
        if not schema_valid:
            result.add_error(f"Schema validation failed for {record_type}")

        if completeness_score < 0.5:
            result.add_error(
                f"Data completeness too low: {completeness_score:.2f}"
            )
        elif completeness_score < 0.8:
            result.add_warning(
                f"Data completeness below optimal: {completeness_score:.2f}"
            )

        if physiological_score < 0.8:
            result.add_warning(
                f"Some values outside physiological ranges: {physiological_score:.2f}"
            )

        if temporal_score < 1.0:
            result.add_warning("Timestamps not in chronological order")

        # Final validation decision
        if quality_score < self.config.quality_threshold:
            result.is_valid = False
            result.add_error(
                f"Quality score {quality_score:.2f} below threshold "
                f"{self.config.quality_threshold:.2f}"
            )

        logger.info(
            "validation_completed",
            record_type=record_type,
            record_count=len(records),
            quality_score=quality_score,
            is_valid=result.is_valid,
            errors=len(result.errors),
            warnings=len(result.warnings)
        )

        return result

    async def _validate_schema(
        self,
        records: list[dict],
        record_type: str
    ) -> bool:
        """
        Validate Avro schema compliance.

        Args:
            records: List of records to validate
            record_type: Type of health record

        Returns:
            True if schema is valid, False otherwise
        """
        if not records:
            return False

        # All Android Health Connect records should have metadata field
        first_record = records[0]

        # Basic validation: record should not be empty and should have some fields
        if not first_record or len(first_record) == 0:
            logger.warning(
                "empty_record",
                record_type=record_type
            )
            return False

        # Check for Android Health Connect metadata field (all records should have this)
        if 'metadata' not in first_record:
            logger.debug(
                "no_metadata_field",
                record_type=record_type,
                available_fields=list(first_record.keys())[:10]
            )

        # For now, accept any non-empty record with fields
        # TODO: Update with exact schema validation once Avro structure is confirmed
        logger.debug(
            "schema_validation_passed",
            record_type=record_type,
            field_count=len(first_record),
            sample_fields=list(first_record.keys())[:5]
        )

        return True

    async def _check_completeness(
        self,
        records: list[dict],
        record_type: str
    ) -> float:
        """
        Check data completeness (0.0 to 1.0).

        Args:
            records: List of records to check
            record_type: Type of health record

        Returns:
            Completeness score from 0.0 to 1.0
        """
        if not records:
            return 0.0

        required_fields = self._get_required_fields(record_type)
        if not required_fields:
            return 1.0

        complete_count = 0.0
        for record in records:
            fields_present = sum(
                1 for field_name in required_fields
                if field_name in record and record[field_name] is not None
            )
            complete_count += fields_present / len(required_fields)

        return complete_count / len(records)

    async def _check_physiological_ranges(
        self,
        records: list[dict],
        record_type: str
    ) -> float:
        """
        Check values are within physiological ranges (0.0 to 1.0).

        Args:
            records: List of records to check
            record_type: Type of health record

        Returns:
            Physiological validity score from 0.0 to 1.0
        """
        # TODO: Update field paths once actual Avro schema is confirmed
        # For now, skip physiological validation and return neutral score
        logger.debug(
            "physiological_validation_skipped",
            record_type=record_type,
            reason="avro_schema_structure_needs_confirmation"
        )

        # Return 1.0 (neutral/passing) since we can't validate without knowing schema
        return 1.0

    async def _check_temporal_consistency(
        self,
        records: list[dict]
    ) -> float:
        """
        Check timestamps are in chronological order (0.0 to 1.0).

        Args:
            records: List of records to check

        Returns:
            1.0 if chronological, 0.7 if not, 0.0 if no timestamps
        """
        if len(records) < 2:
            return 1.0

        # Extract timestamps
        timestamps = []
        for record in records:
            timestamp = self._extract_timestamp(record)
            if timestamp is not None:
                timestamps.append(timestamp)

        if len(timestamps) < 2:
            return 1.0

        # Check if sorted
        is_sorted = all(
            timestamps[i] <= timestamps[i+1]
            for i in range(len(timestamps)-1)
        )

        return 1.0 if is_sorted else 0.7

    async def quarantine_file(
        self,
        s3_key: str,
        validation_result: ValidationResult,
        file_content: bytes
    ) -> None:
        """
        Move file to quarantine with metadata.

        Args:
            s3_key: Original S3 key of the file
            validation_result: Validation result with errors/warnings
            file_content: Raw file content to quarantine

        Raises:
            ValueError: If S3 client is not configured
        """
        if not self.s3_client:
            raise ValueError("S3 client not configured for quarantine operations")

        if not self.config.enable_quarantine:
            logger.info(
                "quarantine_disabled",
                s3_key=s3_key,
                message="Quarantine is disabled in configuration"
            )
            return

        # Generate quarantine key
        quarantine_key = s3_key.replace('raw/', self.config.quarantine_prefix)

        # Upload quarantined file
        await self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=quarantine_key,
            Body=file_content,
            ContentType='application/avro'
        )

        logger.info(
            "file_quarantined",
            original_key=s3_key,
            quarantine_key=quarantine_key,
            quality_score=validation_result.quality_score
        )

        # Create metadata file if enabled
        if self.config.include_quarantine_metadata:
            metadata = {
                'original_key': s3_key,
                'quarantine_reason': validation_result.errors,
                'quality_score': validation_result.quality_score,
                'warnings': validation_result.warnings,
                'quarantined_at': datetime.now(UTC).isoformat(),
                'validation_metadata': validation_result.metadata
            }

            await self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{quarantine_key}.metadata.json",
                Body=json.dumps(metadata, indent=2).encode('utf-8'),
                ContentType='application/json'
            )

            logger.debug(
                "quarantine_metadata_created",
                metadata_key=f"{quarantine_key}.metadata.json"
            )

    # Helper methods

    def _get_required_fields(self, record_type: str) -> list[str]:
        """
        Get required fields for a record type.

        NOTE: Returns empty list for now since actual Avro schema structure
        needs to be confirmed from real sample files.
        """
        # TODO: Update with actual Android Health Connect Avro schema fields
        # once we can inspect the real sample files
        return []

    def _get_nested_field(self, record: dict, field_path: str) -> float | None:
        """
        Extract value from nested field path.

        Args:
            record: Record dictionary
            field_path: Dot-separated or array-indexed path (e.g., "level.inMilligramsPerDeciliter")

        Returns:
            Field value or None if not found
        """
        try:
            value = record
            parts = field_path.replace('[', '.').replace(']', '').split('.')

            for part in parts:
                if not part:
                    continue

                # Array index or dictionary key
                value = value[int(part)] if part.isdigit() else value[part]

            return float(value) if value is not None else None
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def _calculate_sleep_duration(self, record: dict) -> float | None:
        """
        Calculate sleep duration in hours from startTime and endTime.

        Args:
            record: Sleep session record

        Returns:
            Duration in hours or None if cannot calculate
        """
        try:
            start_time = self._get_nested_field(record, 'startTime.epochMillis')
            end_time = self._get_nested_field(record, 'endTime.epochMillis')

            if start_time is not None and end_time is not None:
                duration_ms = end_time - start_time
                duration_hours = duration_ms / (1000 * 60 * 60)
                return duration_hours

            return None
        except (KeyError, TypeError):
            return None

    def _extract_timestamp(self, record: dict) -> int | None:
        """
        Extract timestamp from record in various formats.

        Args:
            record: Health record

        Returns:
            Timestamp in milliseconds or None
        """
        # Try different timestamp field locations
        timestamp_fields = [
            'time.epochMillis',
            'startTime.epochMillis',
            'time',
            'startTime'
        ]

        for field_path in timestamp_fields:
            timestamp = self._get_nested_field(record, field_path)
            if timestamp is not None:
                return int(timestamp)

        return None
