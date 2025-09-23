"""
Clinical validation rules for different health record types.

These validators implement medical knowledge and clinical best practices
for validating health data ranges and patterns.
"""

from typing import List, Optional
import math
from datetime import datetime, timedelta

from ..types.health_records import (
    AvroBloodGlucoseRecord,
    AvroHeartRateRecord,
    AvroSleepSessionRecord,
    AvroStepsRecord,
    AvroActiveCaloriesBurnedRecord,
    AvroHeartRateVariabilityRmssdRecord,
    AvroBloodGlucoseSpecimenSource,
    AvroBloodGlucoseRelationToMeal,
)
from .validation_results import ValidationResult, ValidationError, ValidationSeverity


class BloodGlucoseValidator:
    """Clinical validator for blood glucose measurements."""

    # Clinical ranges in mg/dL
    ABSOLUTE_MIN = 20.0  # Below this is life-threatening
    ABSOLUTE_MAX = 600.0  # Above this is dangerous
    NORMAL_MIN = 70.0
    NORMAL_MAX = 140.0
    HYPOGLYCEMIC_THRESHOLD = 70.0
    HYPERGLYCEMIC_THRESHOLD = 180.0

    def validate(self, record: AvroBloodGlucoseRecord) -> ValidationResult:
        """Validate blood glucose record with clinical rules."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": "blood_glucose"}
        )

        # Validate glucose level range
        glucose_level = record.level_in_milligrams_per_deciliter

        if glucose_level < self.ABSOLUTE_MIN:
            result.add_error(ValidationError(
                field_name="level_in_milligrams_per_deciliter",
                error_message=f"Glucose level {glucose_level} mg/dL is dangerously low (life-threatening)",
                severity=ValidationSeverity.CRITICAL,
                error_code="GLUCOSE_CRITICALLY_LOW",
                current_value=glucose_level,
                expected_value=f">= {self.ABSOLUTE_MIN}",
                clinical_context="Severe hypoglycemia requiring immediate medical attention"
            ))
        elif glucose_level > self.ABSOLUTE_MAX:
            result.add_error(ValidationError(
                field_name="level_in_milligrams_per_deciliter",
                error_message=f"Glucose level {glucose_level} mg/dL is dangerously high",
                severity=ValidationSeverity.CRITICAL,
                error_code="GLUCOSE_CRITICALLY_HIGH",
                current_value=glucose_level,
                expected_value=f"<= {self.ABSOLUTE_MAX}",
                clinical_context="Severe hyperglycemia requiring immediate medical attention"
            ))
        elif glucose_level < self.HYPOGLYCEMIC_THRESHOLD:
            result.add_error(ValidationError(
                field_name="level_in_milligrams_per_deciliter",
                error_message=f"Glucose level {glucose_level} mg/dL indicates hypoglycemia",
                severity=ValidationSeverity.WARNING,
                error_code="GLUCOSE_HYPOGLYCEMIC",
                current_value=glucose_level,
                expected_value=f">= {self.HYPOGLYCEMIC_THRESHOLD}",
                clinical_context="Low blood sugar - monitor closely and consider treatment"
            ))
        elif glucose_level > self.HYPERGLYCEMIC_THRESHOLD:
            result.add_error(ValidationError(
                field_name="level_in_milligrams_per_deciliter",
                error_message=f"Glucose level {glucose_level} mg/dL indicates hyperglycemia",
                severity=ValidationSeverity.WARNING,
                error_code="GLUCOSE_HYPERGLYCEMIC",
                current_value=glucose_level,
                expected_value=f"<= {self.HYPERGLYCEMIC_THRESHOLD}",
                clinical_context="High blood sugar - consider dietary and medication management"
            ))

        # Validate meal context consistency
        if (record.relation_to_meal == AvroBloodGlucoseRelationToMeal.FASTING and
            glucose_level > 126.0):
            result.add_error(ValidationError(
                field_name="level_in_milligrams_per_deciliter",
                error_message=f"Fasting glucose {glucose_level} mg/dL is elevated (>126 mg/dL)",
                severity=ValidationSeverity.WARNING,
                error_code="FASTING_GLUCOSE_ELEVATED",
                current_value=glucose_level,
                expected_value="< 126.0 for normal fasting glucose",
                clinical_context="Elevated fasting glucose may indicate diabetes or prediabetes"
            ))

        # Validate specimen source appropriateness
        if record.specimen_source == AvroBloodGlucoseSpecimenSource.INTERSTITIAL_FLUID:
            if glucose_level < 40.0 or glucose_level > 400.0:
                result.add_error(ValidationError(
                    field_name="specimen_source",
                    error_message="CGM reading outside typical sensor range",
                    severity=ValidationSeverity.INFO,
                    error_code="CGM_RANGE_WARNING",
                    clinical_context="Continuous glucose monitor may be less accurate at extreme values"
                ))

        # Quality score based on clinical appropriateness
        if self.NORMAL_MIN <= glucose_level <= self.NORMAL_MAX:
            quality_bonus = 0.0
        elif self.HYPOGLYCEMIC_THRESHOLD <= glucose_level < self.NORMAL_MIN:
            quality_bonus = -0.1  # Slightly lower quality for borderline low
        elif self.NORMAL_MAX < glucose_level <= self.HYPERGLYCEMIC_THRESHOLD:
            quality_bonus = -0.1  # Slightly lower quality for borderline high
        else:
            quality_bonus = -0.3  # Significantly lower quality for abnormal values

        result.quality_score = max(0.0, 1.0 + quality_bonus)
        return result


class HeartRateValidator:
    """Clinical validator for heart rate measurements."""

    # Clinical ranges in beats per minute
    ABSOLUTE_MIN = 30  # Below this is dangerous bradycardia
    ABSOLUTE_MAX = 220  # Above this is dangerous tachycardia
    NORMAL_RESTING_MIN = 60
    NORMAL_RESTING_MAX = 100
    BRADYCARDIA_THRESHOLD = 60
    TACHYCARDIA_THRESHOLD = 100

    def validate(self, record: AvroHeartRateRecord) -> ValidationResult:
        """Validate heart rate record with clinical rules."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": "heart_rate", "sample_count": len(record.samples)}
        )

        if not record.samples:
            result.add_error(ValidationError(
                field_name="samples",
                error_message="Heart rate record contains no samples",
                severity=ValidationSeverity.ERROR,
                error_code="NO_SAMPLES"
            ))
            return result

        # Validate each sample
        for i, sample in enumerate(record.samples):
            hr = sample.beats_per_minute

            if hr < self.ABSOLUTE_MIN:
                result.add_error(ValidationError(
                    field_name=f"samples[{i}].beats_per_minute",
                    error_message=f"Heart rate {hr} bpm is dangerously low (severe bradycardia)",
                    severity=ValidationSeverity.CRITICAL,
                    error_code="HR_CRITICALLY_LOW",
                    current_value=hr,
                    expected_value=f">= {self.ABSOLUTE_MIN}",
                    clinical_context="Severe bradycardia requiring immediate medical evaluation"
                ))
            elif hr > self.ABSOLUTE_MAX:
                result.add_error(ValidationError(
                    field_name=f"samples[{i}].beats_per_minute",
                    error_message=f"Heart rate {hr} bpm is dangerously high",
                    severity=ValidationSeverity.CRITICAL,
                    error_code="HR_CRITICALLY_HIGH",
                    current_value=hr,
                    expected_value=f"<= {self.ABSOLUTE_MAX}",
                    clinical_context="Extreme tachycardia requiring immediate medical evaluation"
                ))

        # Calculate statistics
        heart_rates = [sample.beats_per_minute for sample in record.samples]
        avg_hr = sum(heart_rates) / len(heart_rates)
        min_hr = min(heart_rates)
        max_hr = max(heart_rates)

        # Validate average heart rate
        if avg_hr < self.BRADYCARDIA_THRESHOLD:
            result.add_error(ValidationError(
                field_name="average_heart_rate",
                error_message=f"Average heart rate {avg_hr:.1f} bpm indicates bradycardia",
                severity=ValidationSeverity.WARNING,
                error_code="HR_BRADYCARDIA",
                current_value=avg_hr,
                expected_value=f">= {self.BRADYCARDIA_THRESHOLD}",
                clinical_context="Slow heart rate - may be normal for athletes or require evaluation"
            ))
        elif avg_hr > self.TACHYCARDIA_THRESHOLD:
            result.add_error(ValidationError(
                field_name="average_heart_rate",
                error_message=f"Average heart rate {avg_hr:.1f} bpm indicates tachycardia",
                severity=ValidationSeverity.WARNING,
                error_code="HR_TACHYCARDIA",
                current_value=avg_hr,
                expected_value=f"<= {self.TACHYCARDIA_THRESHOLD}",
                clinical_context="Elevated heart rate - may indicate stress, exercise, or medical condition"
            ))

        # Validate heart rate variability within session
        hr_range = max_hr - min_hr
        if hr_range > 50:
            result.add_error(ValidationError(
                field_name="heart_rate_variability",
                error_message=f"Large heart rate variation ({hr_range} bpm) within measurement period",
                severity=ValidationSeverity.INFO,
                error_code="HR_HIGH_VARIABILITY",
                current_value=hr_range,
                clinical_context="High variability may indicate measurement artifacts or arrhythmia"
            ))

        # Quality score based on measurement consistency and clinical normalcy
        quality_score = 1.0
        if hr_range > 30:
            quality_score -= 0.1  # High variability reduces quality
        if not (self.NORMAL_RESTING_MIN <= avg_hr <= self.NORMAL_RESTING_MAX):
            quality_score -= 0.1  # Abnormal average reduces quality

        result.quality_score = max(0.0, quality_score)
        return result


class SleepValidator:
    """Clinical validator for sleep session data."""

    # Clinical sleep parameters
    MIN_SLEEP_DURATION_HOURS = 1.0  # Minimum for a valid sleep session
    MAX_SLEEP_DURATION_HOURS = 16.0  # Maximum reasonable sleep duration
    NORMAL_SLEEP_DURATION_MIN = 6.0
    NORMAL_SLEEP_DURATION_MAX = 9.0
    MIN_SLEEP_EFFICIENCY = 0.5  # 50% minimum
    GOOD_SLEEP_EFFICIENCY = 0.85  # 85% is considered good

    def validate(self, record: AvroSleepSessionRecord) -> ValidationResult:
        """Validate sleep session record with clinical rules."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": "sleep_session", "stage_count": len(record.stages)}
        )

        # Calculate sleep duration
        total_duration_hours = (record.end_time_epoch_millis - record.start_time_epoch_millis) / (1000 * 60 * 60)

        if total_duration_hours < self.MIN_SLEEP_DURATION_HOURS:
            result.add_error(ValidationError(
                field_name="duration",
                error_message=f"Sleep session duration {total_duration_hours:.1f} hours is too short",
                severity=ValidationSeverity.WARNING,
                error_code="SLEEP_TOO_SHORT",
                current_value=total_duration_hours,
                expected_value=f">= {self.MIN_SLEEP_DURATION_HOURS}",
                clinical_context="Very short sleep sessions may not provide restorative benefits"
            ))
        elif total_duration_hours > self.MAX_SLEEP_DURATION_HOURS:
            result.add_error(ValidationError(
                field_name="duration",
                error_message=f"Sleep session duration {total_duration_hours:.1f} hours is unusually long",
                severity=ValidationSeverity.INFO,
                error_code="SLEEP_TOO_LONG",
                current_value=total_duration_hours,
                expected_value=f"<= {self.MAX_SLEEP_DURATION_HOURS}",
                clinical_context="Unusually long sleep may indicate health issues or measurement errors"
            ))

        if record.stages:
            # Calculate sleep efficiency
            sleep_efficiency = record.get_sleep_efficiency()

            if sleep_efficiency < self.MIN_SLEEP_EFFICIENCY:
                result.add_error(ValidationError(
                    field_name="sleep_efficiency",
                    error_message=f"Sleep efficiency {sleep_efficiency:.1%} is very low",
                    severity=ValidationSeverity.WARNING,
                    error_code="POOR_SLEEP_EFFICIENCY",
                    current_value=sleep_efficiency,
                    expected_value=f">= {self.MIN_SLEEP_EFFICIENCY:.1%}",
                    clinical_context="Poor sleep efficiency may indicate sleep disorders or environmental issues"
                ))

            # Validate stage transitions
            self._validate_stage_transitions(record, result)

            # Quality score based on sleep metrics
            quality_score = 1.0
            if not (self.NORMAL_SLEEP_DURATION_MIN <= total_duration_hours <= self.NORMAL_SLEEP_DURATION_MAX):
                quality_score -= 0.1
            if sleep_efficiency < self.GOOD_SLEEP_EFFICIENCY:
                quality_score -= 0.1

            result.quality_score = max(0.0, quality_score)

        return result

    def _validate_stage_transitions(self, record: AvroSleepSessionRecord, result: ValidationResult):
        """Validate logical sleep stage transitions."""
        if len(record.stages) < 2:
            return

        for i in range(len(record.stages) - 1):
            current_stage = record.stages[i]
            next_stage = record.stages[i + 1]

            # Check for time gaps or overlaps
            if current_stage.end_time_epoch_millis > next_stage.start_time_epoch_millis:
                result.add_error(ValidationError(
                    field_name=f"stages[{i}]",
                    error_message="Sleep stages overlap in time",
                    severity=ValidationSeverity.ERROR,
                    error_code="STAGE_TIME_OVERLAP",
                    clinical_context="Sleep stage timing should be sequential"
                ))


class StepsValidator:
    """Clinical validator for step count data."""

    # Reasonable step count ranges
    MAX_STEPS_PER_HOUR = 10000  # Maximum reasonable steps per hour
    MAX_DAILY_STEPS = 50000  # Maximum reasonable daily steps

    def validate(self, record: AvroStepsRecord) -> ValidationResult:
        """Validate steps record with activity patterns."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": "steps"}
        )

        # Calculate steps per hour
        duration_hours = (record.end_time_epoch_millis - record.start_time_epoch_millis) / (1000 * 60 * 60)

        if duration_hours > 0:
            steps_per_hour = record.count / duration_hours

            if steps_per_hour > self.MAX_STEPS_PER_HOUR:
                result.add_error(ValidationError(
                    field_name="count",
                    error_message=f"Steps per hour ({steps_per_hour:.0f}) exceeds reasonable maximum",
                    severity=ValidationSeverity.WARNING,
                    error_code="STEPS_RATE_HIGH",
                    current_value=steps_per_hour,
                    expected_value=f"<= {self.MAX_STEPS_PER_HOUR}",
                    clinical_context="Extremely high step rate may indicate measurement error"
                ))

        if record.count > self.MAX_DAILY_STEPS:
            result.add_error(ValidationError(
                field_name="count",
                error_message=f"Step count ({record.count}) exceeds reasonable daily maximum",
                severity=ValidationSeverity.WARNING,
                error_code="STEPS_COUNT_HIGH",
                current_value=record.count,
                expected_value=f"<= {self.MAX_DAILY_STEPS}",
                clinical_context="Unusually high step count may indicate measurement error"
            ))

        return result


class CaloriesValidator:
    """Clinical validator for calories burned data."""

    # Reasonable calorie burn ranges
    MAX_CALORIES_PER_HOUR = 1200  # Maximum for intense exercise
    MAX_DAILY_CALORIES = 5000  # Maximum reasonable daily active calories

    def validate(self, record: AvroActiveCaloriesBurnedRecord) -> ValidationResult:
        """Validate calories burned record."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": "active_calories"}
        )

        # Calculate calories per hour
        duration_hours = (record.end_time_epoch_millis - record.start_time_epoch_millis) / (1000 * 60 * 60)

        if duration_hours > 0:
            calories_per_hour = record.energy_in_kilocalories / duration_hours

            if calories_per_hour > self.MAX_CALORIES_PER_HOUR:
                result.add_error(ValidationError(
                    field_name="energy_in_kilocalories",
                    error_message=f"Calorie burn rate ({calories_per_hour:.0f} cal/hr) is extremely high",
                    severity=ValidationSeverity.WARNING,
                    error_code="CALORIES_RATE_HIGH",
                    current_value=calories_per_hour,
                    expected_value=f"<= {self.MAX_CALORIES_PER_HOUR}",
                    clinical_context="Very high calorie burn rate may indicate measurement error"
                ))

        if record.energy_in_kilocalories > self.MAX_DAILY_CALORIES:
            result.add_error(ValidationError(
                field_name="energy_in_kilocalories",
                error_message=f"Daily active calories ({record.energy_in_kilocalories}) exceeds reasonable maximum",
                severity=ValidationSeverity.WARNING,
                error_code="CALORIES_COUNT_HIGH",
                current_value=record.energy_in_kilocalories,
                expected_value=f"<= {self.MAX_DAILY_CALORIES}",
                clinical_context="Unusually high calorie burn may indicate measurement error"
            ))

        return result


class HRVValidator:
    """Clinical validator for Heart Rate Variability data."""

    # Clinical HRV RMSSD ranges (milliseconds)
    ABSOLUTE_MIN = 1.0   # Below this is likely measurement error
    ABSOLUTE_MAX = 200.0  # Above this is likely measurement error
    NORMAL_MIN = 20.0    # Normal range for adults
    NORMAL_MAX = 50.0    # Normal range for adults
    ATHLETE_MAX = 100.0  # Athletes may have higher HRV

    def validate(self, record: AvroHeartRateVariabilityRmssdRecord) -> ValidationResult:
        """Validate HRV record with clinical rules."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={"record_type": "hrv"}
        )

        hrv_value = record.heart_rate_variability_rmssd

        if hrv_value < self.ABSOLUTE_MIN:
            result.add_error(ValidationError(
                field_name="heart_rate_variability_rmssd",
                error_message=f"HRV RMSSD {hrv_value} ms is below measurable range",
                severity=ValidationSeverity.ERROR,
                error_code="HRV_TOO_LOW",
                current_value=hrv_value,
                expected_value=f">= {self.ABSOLUTE_MIN}",
                clinical_context="HRV below 1ms likely indicates measurement error"
            ))
        elif hrv_value > self.ABSOLUTE_MAX:
            result.add_error(ValidationError(
                field_name="heart_rate_variability_rmssd",
                error_message=f"HRV RMSSD {hrv_value} ms is above reasonable range",
                severity=ValidationSeverity.ERROR,
                error_code="HRV_TOO_HIGH",
                current_value=hrv_value,
                expected_value=f"<= {self.ABSOLUTE_MAX}",
                clinical_context="HRV above 200ms likely indicates measurement error"
            ))
        elif hrv_value < self.NORMAL_MIN:
            result.add_error(ValidationError(
                field_name="heart_rate_variability_rmssd",
                error_message=f"HRV RMSSD {hrv_value} ms is below normal range",
                severity=ValidationSeverity.INFO,
                error_code="HRV_LOW_NORMAL",
                current_value=hrv_value,
                expected_value=f">= {self.NORMAL_MIN}",
                clinical_context="Low HRV may indicate stress, fatigue, or poor cardiovascular health"
            ))
        elif hrv_value > self.ATHLETE_MAX:
            result.add_error(ValidationError(
                field_name="heart_rate_variability_rmssd",
                error_message=f"HRV RMSSD {hrv_value} ms is unusually high",
                severity=ValidationSeverity.INFO,
                error_code="HRV_UNUSUALLY_HIGH",
                current_value=hrv_value,
                expected_value=f"<= {self.ATHLETE_MAX}",
                clinical_context="Very high HRV may indicate excellent fitness or measurement artifact"
            ))

        # Quality score based on clinical normalcy
        if self.NORMAL_MIN <= hrv_value <= self.NORMAL_MAX:
            quality_bonus = 0.0
        elif hrv_value < self.NORMAL_MIN or hrv_value > self.NORMAL_MAX:
            quality_bonus = -0.1
        else:
            quality_bonus = 0.0

        result.quality_score = max(0.0, 1.0 + quality_bonus)
        return result