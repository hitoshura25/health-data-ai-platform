"""
Avro file parsing utilities for health data records.

Handles parsing of Apache Avro files downloaded from the data lake and
extracts health records into Python dictionaries for processing.
"""

import io
from typing import Any

import fastavro
import structlog

from ..consumer.error_recovery import SchemaError

logger = structlog.get_logger()


class AvroParser:
    """
    Parser for Apache Avro files containing health data records.

    Uses fastavro for efficient parsing of Avro files without
    requiring schema files (schema is embedded in Avro container).
    """

    def __init__(self):
        """Initialize Avro parser"""
        self.logger = structlog.get_logger()

    def parse_records(
        self,
        avro_data: bytes,
        expected_record_type: str = None
    ) -> list[dict[str, Any]]:
        """
        Parse Avro file and extract records.

        Args:
            avro_data: Raw Avro file contents as bytes
            expected_record_type: Expected record type for validation (optional)

        Returns:
            List of record dictionaries

        Raises:
            SchemaError: If Avro schema is invalid or parsing fails
        """
        self.logger.info(
            "parsing_avro_file",
            data_size=len(avro_data),
            expected_type=expected_record_type
        )

        try:
            # Create bytes IO stream
            avro_stream = io.BytesIO(avro_data)

            # Parse Avro file using fastavro
            records = []
            reader = fastavro.reader(avro_stream)

            # Extract all records
            for record in reader:
                records.append(record)

            if not records:
                self.logger.warning("no_records_found_in_avro_file")
                return []

            self.logger.info(
                "avro_records_parsed",
                record_count=len(records),
                sample_keys=list(records[0].keys()) if records else []
            )

            # Validate record type if specified
            if expected_record_type and records:
                self._validate_record_type(records, expected_record_type)

            return records

        except fastavro.errors.AvroException as e:
            self.logger.error(
                "avro_parsing_error",
                exception=str(e),
                exception_type=type(e).__name__
            )
            raise SchemaError(f"Invalid Avro schema: {str(e)}") from e

        except Exception as e:
            self.logger.error(
                "unexpected_parsing_error",
                exception=str(e),
                exception_type=type(e).__name__
            )
            raise SchemaError(f"Avro parsing failed: {str(e)}") from e

    def _validate_record_type(
        self,
        records: list[dict[str, Any]],
        expected_type: str
    ) -> None:
        """
        Validate that records match expected type.

        Args:
            records: Parsed records
            expected_type: Expected record type name

        Raises:
            SchemaError: If record type doesn't match
        """
        if not records:
            return

        # Check first record for type information
        # Note: Record type validation depends on Avro schema structure
        # For now, we log and accept any valid Avro file
        # Module 2 (validation) will perform detailed type checking

        self.logger.debug(
            "record_type_validation_skipped",
            reason="detailed_validation_in_module_2",
            expected_type=expected_type
        )

    def get_record_statistics(
        self,
        records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Get basic statistics about parsed records.

        Args:
            records: Parsed records

        Returns:
            Dictionary with statistics
        """
        if not records:
            return {
                "count": 0,
                "fields": [],
                "has_data": False
            }

        first_record = records[0]

        stats = {
            "count": len(records),
            "fields": list(first_record.keys()),
            "has_data": True,
            "sample_record_keys": list(first_record.keys())[:10]  # First 10 fields
        }

        return stats
