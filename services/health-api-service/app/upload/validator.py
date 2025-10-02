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
    record_count: int = 0
    file_hash: Optional[str] = None

class HealthDataValidator:
    def __init__(self, max_file_size_bytes: int):
        self.max_file_size_bytes = max_file_size_bytes

    async def validate_upload(self, file: UploadFile) -> ValidationResult:
        """Comprehensive file validation"""
        errors = []
        warnings = []

        # Basic file checks
        if file.size > self.max_file_size_bytes:
            raise ValueError(f"File size {file.size} exceeds maximum {self.max_file_size_bytes}")

        if not file.filename.endswith('.avro'):
            raise ValueError("Only .avro files are supported")

        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Generate file hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Avro validation
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
