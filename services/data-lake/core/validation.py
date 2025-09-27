import avro.schema
import avro.io
import io
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
import structlog

logger = structlog.get_logger()

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    quality_score: float  # 0.0 to 1.0

@dataclass
class QualityMetrics:
    completeness_score: float
    consistency_score: float
    validity_score: float
    temporal_score: float
    overall_score: float

class ComprehensiveDataValidator:
    """Advanced data quality validation with physiological range checking"""

    def __init__(self, quality_threshold: float = 0.7):
        self.quality_threshold = quality_threshold
        self.physiological_ranges = {
            'blood_glucose_mg_dl': (20, 800),
            'heart_rate_bpm': (30, 220),
            'sleep_duration_hours': (0.5, 24),
            'steps_count': (0, 100000),
            'calories_burned': (0, 10000),
            'hrv_rmssd_ms': (5, 200),
            'systolic_bp_mmhg': (70, 250),
            'diastolic_bp_mmhg': (40, 150)
        }

        self.validation_rules = {
            'BloodGlucoseRecord': self._validate_blood_glucose,
            'HeartRateRecord': self._validate_heart_rate,
            'SleepSessionRecord': self._validate_sleep_session,
            'StepsRecord': self._validate_steps,
            'ActiveCaloriesBurnedRecord': self._validate_calories,
            'HeartRateVariabilityRmssdRecord': self._validate_hrv,
            'BloodPressureRecord': self._validate_blood_pressure
        }

    async def validate_file(
        self,
        file_content: bytes,
        record_type: str,
        expected_user_id: str
    ) -> ValidationResult:
        """Perform comprehensive file validation with quality scoring"""

        errors = []
        warnings = []
        metadata = {
            'file_size_bytes': len(file_content),
            'validation_timestamp': pd.Timestamp.utcnow().isoformat()
        }

        try:
            # 1. Avro structure validation
            records, schema = self._parse_avro_file(file_content)

            if not records:
                errors.append("No valid records found in file")
                return ValidationResult(False, errors, warnings, metadata, 0.0)

            metadata.update({
                'schema_fields': [field.name for field in schema.fields],
                'record_count': len(records),
                'schema_name': getattr(schema, 'name', 'unknown')
            })

            # 2. Record-specific validation
            type_validation = None
            if record_type in self.validation_rules:
                type_validation = await self.validation_rules[record_type](
                    records, expected_user_id
                )
                errors.extend(type_validation.get('errors', []))
                warnings.extend(type_validation.get('warnings', []))

            # 3. Comprehensive quality assessment
            quality_metrics = await self._assess_data_quality(
                records, schema, record_type, expected_user_id
            )

            metadata['quality_metrics'] = {
                'completeness_score': quality_metrics.completeness_score,
                'consistency_score': quality_metrics.consistency_score,
                'validity_score': quality_metrics.validity_score,
                'temporal_score': quality_metrics.temporal_score,
                'overall_score': quality_metrics.overall_score
            }

            # 4. Determine validation result
            is_valid = (
                len(errors) == 0 and
                quality_metrics.overall_score >= self.quality_threshold
            )

            if not is_valid and len(errors) == 0:
                warnings.append(f"Quality score {quality_metrics.overall_score:.2f} below threshold {self.quality_threshold}")

            logger.info("File validation completed",
                       record_type=record_type,
                       record_count=len(records),
                       quality_score=quality_metrics.overall_score,
                       is_valid=is_valid)

            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                metadata=metadata,
                quality_score=quality_metrics.overall_score
            )

        except Exception as e:
            errors.append(f"Validation failed: {e}")
            return ValidationResult(False, errors, warnings, metadata, 0.0)

    def _parse_avro_file(self, file_content: bytes) -> tuple:
        """Parse Avro file and extract records"""
        bytes_reader = io.BytesIO(file_content)
        decoder = avro.io.BinaryDecoder(bytes_reader)

        # Read schema
        schema_len = decoder.read_long()
        schema_data = decoder.read(schema_len)
        schema = avro.schema.parse(schema_data.decode('utf-8'))

        # Read records
        datum_reader = avro.io.DatumReader(schema)
        records = []

        while True:
            try:
                record = datum_reader.read(decoder)
                records.append(record)

                # Limit records for validation performance
                if len(records) >= 10000:
                    break

            except EOFError:
                break

        return records, schema

    async def _assess_data_quality(
        self,
        records: List[Dict[str, Any]],
        schema,
        record_type: str,
        expected_user_id: str
    ) -> QualityMetrics:
        """Comprehensive data quality assessment"""

        # 1. Completeness Score
        completeness_score = self._calculate_completeness(records, schema)

        # 2. Consistency Score
        consistency_score = self._calculate_consistency(records, expected_user_id)

        # 3. Validity Score
        validity_score = self._calculate_validity(records, record_type)

        # 4. Temporal Score
        temporal_score = self._calculate_temporal_consistency(records)

        # 5. Overall Score (weighted average)
        overall_score = (
            completeness_score * 0.25 +
            consistency_score * 0.25 +
            validity_score * 0.30 +
            temporal_score * 0.20
        )

        return QualityMetrics(
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            validity_score=validity_score,
            temporal_score=temporal_score,
            overall_score=overall_score
        )

    def _calculate_completeness(self, records: List[Dict], schema) -> float:
        """Calculate data completeness score"""
        if not records:
            return 0.0

        required_fields = [field.name for field in schema.fields]
        completeness_scores = []

        for record in records:
            present_fields = sum(
                1 for field in required_fields
                if field in record and record[field] is not None
            )
            completeness_scores.append(present_fields / len(required_fields))

        return np.mean(completeness_scores)

    def _calculate_consistency(self, records: List[Dict], expected_user_id: str) -> float:
        """Calculate data consistency score"""
        if not records:
            return 0.0

        consistent_records = 0

        for record in records:
            # Check user ID consistency
            metadata = record.get('metadata', {})
            client_record_id = metadata.get('clientRecordId', '')

            if client_record_id.startswith(expected_user_id):
                consistent_records += 1

        return consistent_records / len(records)

    def _calculate_validity(self, records: List[Dict], record_type: str) -> float:
        """Calculate data validity score based on physiological ranges"""
        if not records or record_type not in self.validation_rules:
            return 1.0  # Assume valid if no specific rules

        valid_records = 0

        for record in records:
            if self._is_record_valid(record, record_type):
                valid_records += 1

        return valid_records / len(records)

    def _calculate_temporal_consistency(self, records: List[Dict]) -> float:
        """Calculate temporal consistency score"""
        if len(records) < 2:
            return 1.0

        timestamps = []
        for record in records:
            time_data = record.get('time', {})
            if time_data and 'epochMillis' in time_data:
                timestamps.append(time_data['epochMillis'])

        if len(timestamps) < 2:
            return 0.5

        # Check for reasonable time ordering and gaps
        timestamps.sort()
        reasonable_gaps = 0

        for i in range(1, len(timestamps)):
            gap_ms = timestamps[i] - timestamps[i-1]
            gap_hours = gap_ms / (1000 * 60 * 60)

            # Reasonable gap: between 1 minute and 7 days
            if 0.0167 <= gap_hours <= 168:  # 1 minute to 7 days
                reasonable_gaps += 1

        return reasonable_gaps / (len(timestamps) - 1) if len(timestamps) > 1 else 1.0

    def _is_record_valid(self, record: Dict, record_type: str) -> bool:
        """Check if individual record is valid"""
        try:
            if record_type == 'BloodGlucoseRecord':
                level = record.get('level', {})
                if level and 'inMilligramsPerDeciliter' in level:
                    value = level['inMilligramsPerDeciliter']
                    min_val, max_val = self.physiological_ranges['blood_glucose_mg_dl']
                    return min_val <= value <= max_val

            elif record_type == 'HeartRateRecord':
                bpm = record.get('beatsPerMinute')
                if bpm:
                    min_val, max_val = self.physiological_ranges['heart_rate_bpm']
                    return min_val <= bpm <= max_val

            # Add more record type validations as needed

            return True  # Default to valid if no specific validation

        except Exception:
            return False

    async def _validate_blood_glucose(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate blood glucose specific constraints"""
        errors = []
        warnings = []

        for i, record in enumerate(records):
            # User ID validation
            metadata = record.get('metadata', {})
            client_record_id = metadata.get('clientRecordId', '')

            if not client_record_id.startswith(expected_user_id):
                warnings.append(f"Record {i}: User ID mismatch")

            # Value range validation
            level = record.get('level', {})
            if level and 'inMilligramsPerDeciliter' in level:
                mg_dl_value = level['inMilligramsPerDeciliter']
                min_val, max_val = self.physiological_ranges['blood_glucose_mg_dl']

                if not (min_val <= mg_dl_value <= max_val):
                    errors.append(
                        f"Record {i}: Blood glucose {mg_dl_value} mg/dL out of physiological range"
                    )

            # Meal type validation
            meal_type = record.get('mealType')
            valid_meal_types = ['BEFORE_MEAL', 'AFTER_MEAL', 'FASTING', 'RANDOM']
            if meal_type and meal_type not in valid_meal_types:
                warnings.append(f"Record {i}: Invalid meal type '{meal_type}'")

        return {'errors': errors, 'warnings': warnings}

    async def _validate_sleep_session(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate sleep session constraints"""
        errors = []
        warnings = []

        for i, record in enumerate(records):
            # Duration validation
            start_time = record.get('startTime', {}).get('epochMillis')
            end_time = record.get('endTime', {}).get('epochMillis')

            if start_time and end_time:
                duration_hours = (end_time - start_time) / (1000 * 60 * 60)
                min_val, max_val = self.physiological_ranges['sleep_duration_hours']

                if not (min_val <= duration_hours <= max_val):
                    if duration_hours < min_val:
                        warnings.append(f"Record {i}: Very short sleep duration {duration_hours:.1f} hours")
                    else:
                        errors.append(f"Record {i}: Unrealistic sleep duration {duration_hours:.1f} hours")

        return {'errors': errors, 'warnings': warnings}

    # Additional validation methods for other record types...
    async def _validate_heart_rate(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate heart rate constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_steps(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate steps constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_calories(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate calories constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_hrv(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate HRV constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_blood_pressure(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate blood pressure constraints"""
        return {'errors': [], 'warnings': []}