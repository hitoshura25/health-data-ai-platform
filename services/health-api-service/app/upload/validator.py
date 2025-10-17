import avro.schema
import avro.io
import avro.datafile
import io
import hashlib
from fastapi import UploadFile
from dataclasses import dataclass
from typing import List, Optional
import structlog
from app.supported_record_types import SUPPORTED_RECORD_TYPES

logger = structlog.get_logger()

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    record_type: Optional[str] = None
    record_count: int = 0  # For streaming validation, this will be 0 (counted during upload)
    file_hash: Optional[str] = None  # For streaming validation, this will be None (calculated during upload)

class HealthDataValidator:
    def __init__(self, max_file_size_bytes: int):
        self.max_file_size_bytes = max_file_size_bytes

    async def validate_upload_streaming(self, file: UploadFile) -> ValidationResult:
        """
        Lightweight streaming validation - only reads Avro header and samples records.
        Memory efficient: Only reads header + first few records (~few KB).
        File hash and record count will be calculated during upload.
        """
        errors = []
        warnings = []

        # Check file extension
        if not file.filename.endswith('.avro'):
            raise ValueError("Only .avro files are supported")

        # Access the underlying SpooledTemporaryFile
        file_obj = file.file
        initial_position = file_obj.tell()

        # Check file size by seeking to end
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Seek back to start

        if file_size > self.max_file_size_bytes:
            raise ValueError(f"File size {file_size} exceeds maximum {self.max_file_size_bytes}")

        reader = None
        try:
            # Read Avro header and validate schema (minimal read)
            datum_reader = avro.io.DatumReader()
            reader = avro.datafile.DataFileReader(file_obj, datum_reader)

            # Get record type from schema
            record_type = reader.meta.get('avro.schema')
            schema = avro.schema.parse(record_type)
            record_type = schema.name
            logger.info("Avro schema parsed", schema_name=record_type)

            # Validate record type is supported
            if record_type not in SUPPORTED_RECORD_TYPES:
                raise ValueError(f"Unsupported record type: {record_type}")

            # Sample first few records to validate format (streaming)
            sample_count = 0
            for record in reader:
                sample_count += 1
                if sample_count >= 10:  # Just validate first 10 records
                    break

            if sample_count == 0:
                raise ValueError("No valid records found in Avro file")

            logger.info("Streaming validation completed",
                       filename=file.filename,
                       record_type=record_type,
                       sample_records=sample_count)

            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                record_type=record_type,
                record_count=0,  # Will be counted during upload
                file_hash=None   # Will be calculated during upload
            )

        except ValueError as e:
            raise e
        except Exception as e:
            logger.error("Avro validation failed", error=str(e))
            raise ValueError(f"Avro validation failed: {e}")
        finally:
            # IMPORTANT: Do NOT close DataFileReader here - it will close the underlying file!
            # The processor will handle file cleanup
            # Just seek back to start for upload
            file_obj.seek(0)

    async def validate_upload(self, file: UploadFile) -> ValidationResult:
        """Comprehensive file validation"""
        errors = []
        warnings = []

        if not file.filename.endswith('.avro'):
            raise ValueError("Only .avro files are supported")

        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Check file size from content (file.size may be None across Starlette versions)
        if len(content) > self.max_file_size_bytes:
            raise ValueError(f"File size {len(content)} exceeds maximum {self.max_file_size_bytes}")

        # Generate file hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Avro validation
        reader = None
        try:
            bytes_reader = io.BytesIO(content)
            datum_reader = avro.io.DatumReader()
            reader = avro.datafile.DataFileReader(bytes_reader, datum_reader)

            record_type = reader.meta.get('avro.schema')
            schema = avro.schema.parse(record_type)
            record_type = schema.name
            logger.info("Avro schema parsed", schema_name=record_type)

            if record_type not in SUPPORTED_RECORD_TYPES:
                raise ValueError(f"Unsupported record type: {record_type}")

            record_count = 0
            for record in reader:
                record_count += 1

            if record_count == 0:
                raise ValueError("No valid records found in Avro file")

            logger.info("File validation completed",
                       filename=file.filename,
                       record_type=record_type,
                       record_count=record_count,
                       file_hash=file_hash[:8])

            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                record_type=record_type,
                record_count=record_count,
                file_hash=file_hash
            )

        except ValueError as e:
            raise e
        except Exception as e:
            logger.error("Avro validation failed", error=str(e))
            errors.append(f"Avro validation failed: {e}")
            return ValidationResult(False, errors, warnings, file_hash=file_hash)
        finally:
            # Close DataFileReader to free resources
            if reader is not None:
                reader.close()
