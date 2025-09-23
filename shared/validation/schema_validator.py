"""
Schema validation for Avro health records.

Provides validation against Avro schemas and basic structural checks.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path

from .validation_results import ValidationResult, ValidationError, ValidationSeverity


class SchemaValidator:
    """Validates health records against their Avro schemas."""

    def __init__(self, schema_directory: Optional[str] = None):
        """Initialize with schema directory path."""
        if schema_directory is None:
            # Default to shared schemas directory
            current_dir = Path(__file__).parent
            self.schema_directory = current_dir.parent / "schemas"
        else:
            self.schema_directory = Path(schema_directory)

        self.loaded_schemas = {}

    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load and cache an Avro schema."""
        if schema_name in self.loaded_schemas:
            return self.loaded_schemas[schema_name]

        schema_path = self.schema_directory / f"{schema_name}.avsc"

        try:
            with open(schema_path, 'r') as f:
                schema = json.load(f)
                self.loaded_schemas[schema_name] = schema
                return schema
        except FileNotFoundError:
            raise ValueError(f"Schema file not found: {schema_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema file {schema_path}: {e}")

    def validate_record_structure(self, record_data: Dict[str, Any], record_type: str) -> ValidationResult:
        """Validate record structure against schema."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": record_type, "validation_type": "schema"}
        )

        try:
            # Map record types to schema files
            schema_map = {
                "blood_glucose": "health_records/blood_glucose",
                "heart_rate": "health_records/heart_rate",
                "sleep_session": "health_records/sleep_session",
                "steps": "health_records/steps",
                "active_calories": "health_records/active_calories",
                "heart_rate_variability": "health_records/heart_rate_variability",
            }

            if record_type not in schema_map:
                result.add_error(ValidationError(
                    field_name="record_type",
                    error_message=f"Unknown record type: {record_type}",
                    severity=ValidationSeverity.ERROR,
                    error_code="UNKNOWN_RECORD_TYPE"
                ))
                return result

            schema = self.load_schema(schema_map[record_type])

            # Validate against schema
            validation_errors = self._validate_against_schema(record_data, schema)

            for error in validation_errors:
                result.add_error(error)

        except Exception as e:
            result.add_error(ValidationError(
                field_name="schema_validation",
                error_message=f"Schema validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                error_code="SCHEMA_VALIDATION_ERROR"
            ))

        return result

    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> list[ValidationError]:
        """Validate data against Avro schema definition."""
        errors = []

        if schema.get("type") != "record":
            errors.append(ValidationError(
                field_name="schema",
                error_message="Schema must be of type 'record'",
                severity=ValidationSeverity.ERROR,
                error_code="INVALID_SCHEMA_TYPE"
            ))
            return errors

        # Validate required fields
        required_fields = []
        optional_fields = []

        for field in schema.get("fields", []):
            field_name = field["name"]
            field_type = field["type"]

            # Check if field is optional (union with null or has default)
            is_optional = (
                isinstance(field_type, list) and "null" in field_type or
                "default" in field
            )

            if is_optional:
                optional_fields.append(field_name)
            else:
                required_fields.append(field_name)

        # Check for missing required fields
        for field_name in required_fields:
            if field_name not in data:
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message=f"Required field '{field_name}' is missing",
                    severity=ValidationSeverity.ERROR,
                    error_code="MISSING_REQUIRED_FIELD"
                ))

        # Validate field types
        for field in schema.get("fields", []):
            field_name = field["name"]
            field_type = field["type"]

            if field_name in data:
                field_errors = self._validate_field_type(
                    field_name, data[field_name], field_type
                )
                errors.extend(field_errors)

        # Check for unexpected fields
        schema_fields = {field["name"] for field in schema.get("fields", [])}
        data_fields = set(data.keys())
        unexpected_fields = data_fields - schema_fields

        for field_name in unexpected_fields:
            errors.append(ValidationError(
                field_name=field_name,
                error_message=f"Unexpected field '{field_name}' not in schema",
                severity=ValidationSeverity.WARNING,
                error_code="UNEXPECTED_FIELD"
            ))

        return errors

    def _validate_field_type(self, field_name: str, value: Any, field_type: Any) -> list[ValidationError]:
        """Validate a field's value against its type definition."""
        errors = []

        # Handle union types (e.g., ["null", "string"])
        if isinstance(field_type, list):
            # For union types, value must match at least one type
            union_valid = False
            for union_type in field_type:
                try:
                    union_errors = self._validate_field_type(field_name, value, union_type)
                    if not union_errors:
                        union_valid = True
                        break
                except:
                    continue

            if not union_valid and value is not None:
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message=f"Value does not match any type in union {field_type}",
                    severity=ValidationSeverity.ERROR,
                    error_code="UNION_TYPE_MISMATCH",
                    current_value=type(value).__name__
                ))

            return errors

        # Handle record types
        if isinstance(field_type, dict):
            type_name = field_type.get("type")

            if type_name == "record":
                if not isinstance(value, dict):
                    errors.append(ValidationError(
                        field_name=field_name,
                        error_message=f"Expected record (dict), got {type(value).__name__}",
                        severity=ValidationSeverity.ERROR,
                        error_code="TYPE_MISMATCH",
                        current_value=type(value).__name__,
                        expected_value="dict"
                    ))
                else:
                    # Recursively validate nested record
                    nested_errors = self._validate_against_schema(value, field_type)
                    for error in nested_errors:
                        error.field_name = f"{field_name}.{error.field_name}"
                        errors.append(error)

            elif type_name == "enum":
                if not isinstance(value, str):
                    errors.append(ValidationError(
                        field_name=field_name,
                        error_message=f"Expected string for enum, got {type(value).__name__}",
                        severity=ValidationSeverity.ERROR,
                        error_code="TYPE_MISMATCH",
                        current_value=type(value).__name__,
                        expected_value="string"
                    ))
                elif value not in field_type.get("symbols", []):
                    errors.append(ValidationError(
                        field_name=field_name,
                        error_message=f"Invalid enum value '{value}'",
                        severity=ValidationSeverity.ERROR,
                        error_code="INVALID_ENUM_VALUE",
                        current_value=value,
                        expected_value=field_type.get("symbols", [])
                    ))

            elif type_name == "array":
                if not isinstance(value, list):
                    errors.append(ValidationError(
                        field_name=field_name,
                        error_message=f"Expected array (list), got {type(value).__name__}",
                        severity=ValidationSeverity.ERROR,
                        error_code="TYPE_MISMATCH",
                        current_value=type(value).__name__,
                        expected_value="list"
                    ))
                else:
                    # Validate array items
                    item_type = field_type.get("items")
                    for i, item in enumerate(value):
                        item_errors = self._validate_field_type(f"{field_name}[{i}]", item, item_type)
                        errors.extend(item_errors)

            elif type_name == "map":
                if not isinstance(value, dict):
                    errors.append(ValidationError(
                        field_name=field_name,
                        error_message=f"Expected map (dict), got {type(value).__name__}",
                        severity=ValidationSeverity.ERROR,
                        error_code="TYPE_MISMATCH",
                        current_value=type(value).__name__,
                        expected_value="dict"
                    ))
                else:
                    # Validate map values
                    value_type = field_type.get("values")
                    for key, map_value in value.items():
                        value_errors = self._validate_field_type(f"{field_name}[{key}]", map_value, value_type)
                        errors.extend(value_errors)

        # Handle primitive types
        elif isinstance(field_type, str):
            if field_type == "null" and value is not None:
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message="Expected null value",
                    severity=ValidationSeverity.ERROR,
                    error_code="TYPE_MISMATCH",
                    current_value=type(value).__name__,
                    expected_value="null"
                ))
            elif field_type == "string" and not isinstance(value, str):
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message=f"Expected string, got {type(value).__name__}",
                    severity=ValidationSeverity.ERROR,
                    error_code="TYPE_MISMATCH",
                    current_value=type(value).__name__,
                    expected_value="string"
                ))
            elif field_type == "long" and not isinstance(value, int):
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message=f"Expected long (int), got {type(value).__name__}",
                    severity=ValidationSeverity.ERROR,
                    error_code="TYPE_MISMATCH",
                    current_value=type(value).__name__,
                    expected_value="int"
                ))
            elif field_type == "double" and not isinstance(value, (int, float)):
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message=f"Expected double (float), got {type(value).__name__}",
                    severity=ValidationSeverity.ERROR,
                    error_code="TYPE_MISMATCH",
                    current_value=type(value).__name__,
                    expected_value="float"
                ))
            elif field_type == "boolean" and not isinstance(value, bool):
                errors.append(ValidationError(
                    field_name=field_name,
                    error_message=f"Expected boolean, got {type(value).__name__}",
                    severity=ValidationSeverity.ERROR,
                    error_code="TYPE_MISMATCH",
                    current_value=type(value).__name__,
                    expected_value="bool"
                ))

        return errors

    def validate_message_schema(self, message_data: Dict[str, Any], message_type: str) -> ValidationResult:
        """Validate processing message against schema."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"message_type": message_type, "validation_type": "message_schema"}
        )

        try:
            # Map message types to schema files
            schema_map = {
                "health_data_processing": "processing/health_data_message",
                "etl_result": "processing/etl_result",
                "error": "processing/error_message",
            }

            if message_type not in schema_map:
                result.add_error(ValidationError(
                    field_name="message_type",
                    error_message=f"Unknown message type: {message_type}",
                    severity=ValidationSeverity.ERROR,
                    error_code="UNKNOWN_MESSAGE_TYPE"
                ))
                return result

            schema = self.load_schema(schema_map[message_type])

            # Validate against schema
            validation_errors = self._validate_against_schema(message_data, schema)

            for error in validation_errors:
                result.add_error(error)

        except Exception as e:
            result.add_error(ValidationError(
                field_name="schema_validation",
                error_message=f"Message schema validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                error_code="MESSAGE_SCHEMA_VALIDATION_ERROR"
            ))

        return result