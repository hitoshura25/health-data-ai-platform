"""
Data quality scoring framework for health records.

Provides comprehensive quality assessment including:
- Completeness scoring
- Accuracy assessment
- Consistency checks
- Clinical relevance scoring
"""

from typing import Dict, Any, List, Optional
import math
from datetime import datetime, timedelta

from ..types.health_records import (
    AvroBloodGlucoseRecord,
    AvroHeartRateRecord,
    AvroSleepSessionRecord,
    AvroStepsRecord,
    AvroActiveCaloriesBurnedRecord,
    AvroHeartRateVariabilityRmssdRecord,
)
from ..types.common import AvroMetadata
from .validation_results import ValidationResult, ValidationError, ValidationSeverity


class DataQualityScorer:
    """Comprehensive data quality assessment for health records."""

    def __init__(self):
        self.quality_weights = {
            "completeness": 0.3,
            "accuracy": 0.3,
            "consistency": 0.2,
            "timeliness": 0.1,
            "clinical_relevance": 0.1
        }

    def assess_quality(self, record: Any, record_type: str) -> ValidationResult:
        """Assess overall data quality for a health record."""
        result = ValidationResult(
            is_valid=True,
            quality_score=1.0,
            errors=[],
            metadata={
                "record_type": record_type,
                "quality_dimensions": {}
            }
        )

        # Assess each quality dimension
        completeness_score = self._assess_completeness(record, record_type)
        accuracy_score = self._assess_accuracy(record, record_type)
        consistency_score = self._assess_consistency(record, record_type)
        timeliness_score = self._assess_timeliness(record)
        clinical_relevance_score = self._assess_clinical_relevance(record, record_type)

        # Store dimension scores
        result.metadata["quality_dimensions"] = {
            "completeness": completeness_score,
            "accuracy": accuracy_score,
            "consistency": consistency_score,
            "timeliness": timeliness_score,
            "clinical_relevance": clinical_relevance_score
        }

        # Calculate weighted overall score
        overall_score = (
            completeness_score * self.quality_weights["completeness"] +
            accuracy_score * self.quality_weights["accuracy"] +
            consistency_score * self.quality_weights["consistency"] +
            timeliness_score * self.quality_weights["timeliness"] +
            clinical_relevance_score * self.quality_weights["clinical_relevance"]
        )

        result.quality_score = max(0.0, min(1.0, overall_score))

        # Add quality warnings based on dimension scores
        self._add_quality_warnings(result, result.metadata["quality_dimensions"])

        return result

    def _assess_completeness(self, record: Any, record_type: str) -> float:
        """Assess data completeness (0.0 - 1.0)."""
        if record_type == "blood_glucose":
            return self._assess_blood_glucose_completeness(record)
        elif record_type == "heart_rate":
            return self._assess_heart_rate_completeness(record)
        elif record_type == "sleep_session":
            return self._assess_sleep_completeness(record)
        elif record_type == "steps":
            return self._assess_steps_completeness(record)
        elif record_type == "active_calories":
            return self._assess_calories_completeness(record)
        elif record_type == "hrv":
            return self._assess_hrv_completeness(record)
        else:
            return 1.0

    def _assess_blood_glucose_completeness(self, record: AvroBloodGlucoseRecord) -> float:
        """Assess completeness of blood glucose record."""
        score = 1.0

        # Required fields are implicitly complete (dataclass enforces)
        # Check optional but valuable fields
        if record.zone_offset_id is None:
            score -= 0.1  # Timezone info missing

        # Check metadata completeness
        if record.metadata.device is None:
            score -= 0.2  # Device info missing
        elif (record.metadata.device.manufacturer is None and
              record.metadata.device.model is None):
            score -= 0.1  # Device details incomplete

        return max(0.0, score)

    def _assess_heart_rate_completeness(self, record: AvroHeartRateRecord) -> float:
        """Assess completeness of heart rate record."""
        score = 1.0

        if not record.samples:
            return 0.0  # No data at all

        # Check for sparse sampling
        expected_duration_ms = record.end_time_epoch_millis - record.start_time_epoch_millis
        if expected_duration_ms > 0:
            sample_density = len(record.samples) / (expected_duration_ms / (1000 * 60))  # samples per minute
            if sample_density < 0.1:  # Less than 1 sample per 10 minutes
                score -= 0.3

        # Check timezone info
        if record.start_zone_offset_id is None or record.end_zone_offset_id is None:
            score -= 0.1

        return max(0.0, score)

    def _assess_sleep_completeness(self, record: AvroSleepSessionRecord) -> float:
        """Assess completeness of sleep session record."""
        score = 1.0

        if not record.stages:
            score -= 0.5  # No stage data significantly reduces value

        # Check for detailed stage information
        if record.stages:
            total_session_time = record.end_time_epoch_millis - record.start_time_epoch_millis
            total_stage_time = sum(
                stage.end_time_epoch_millis - stage.start_time_epoch_millis
                for stage in record.stages
            )

            coverage_ratio = total_stage_time / total_session_time if total_session_time > 0 else 0
            if coverage_ratio < 0.8:  # Less than 80% coverage
                score -= 0.2

        return max(0.0, score)

    def _assess_steps_completeness(self, record: AvroStepsRecord) -> float:
        """Assess completeness of steps record."""
        score = 1.0

        # Steps records are generally complete by nature
        # Check timezone info
        if record.start_zone_offset_id is None or record.end_zone_offset_id is None:
            score -= 0.1

        return max(0.0, score)

    def _assess_calories_completeness(self, record: AvroActiveCaloriesBurnedRecord) -> float:
        """Assess completeness of calories record."""
        score = 1.0

        # Check timezone info
        if record.start_zone_offset_id is None or record.end_zone_offset_id is None:
            score -= 0.1

        return max(0.0, score)

    def _assess_hrv_completeness(self, record: AvroHeartRateVariabilityRmssdRecord) -> float:
        """Assess completeness of HRV record."""
        score = 1.0

        # Check timezone info
        if record.zone_offset_id is None:
            score -= 0.1

        return max(0.0, score)

    def _assess_accuracy(self, record: Any, record_type: str) -> float:
        """Assess data accuracy based on clinical ranges and patterns."""
        # This is a simplified accuracy assessment
        # In practice, accuracy would require comparison with reference standards

        score = 1.0

        # For now, we'll use clinical range adherence as a proxy for accuracy
        if record_type == "blood_glucose":
            glucose_level = record.level_in_milligrams_per_deciliter
            if glucose_level < 20 or glucose_level > 600:
                score -= 0.5  # Highly suspicious values
            elif glucose_level < 50 or glucose_level > 400:
                score -= 0.2  # Somewhat suspicious values

        elif record_type == "heart_rate" and record.samples:
            heart_rates = [sample.beats_per_minute for sample in record.samples]
            avg_hr = sum(heart_rates) / len(heart_rates)
            if avg_hr < 30 or avg_hr > 220:
                score -= 0.5  # Highly suspicious values
            elif avg_hr < 40 or avg_hr > 180:
                score -= 0.2  # Somewhat suspicious values

        return max(0.0, score)

    def _assess_consistency(self, record: Any, record_type: str) -> float:
        """Assess internal consistency of the record."""
        score = 1.0

        # Check timestamp consistency
        if hasattr(record, 'start_time_epoch_millis') and hasattr(record, 'end_time_epoch_millis'):
            if record.start_time_epoch_millis >= record.end_time_epoch_millis:
                score -= 0.5  # Invalid time range

        # Check metadata consistency
        if hasattr(record, 'app_record_fetch_time_epoch_millis'):
            # Fetch time should be after measurement time
            measurement_time = getattr(record, 'time_epoch_millis', None)
            if measurement_time is None:
                measurement_time = getattr(record, 'end_time_epoch_millis', None)

            if (measurement_time and
                record.app_record_fetch_time_epoch_millis < measurement_time):
                score -= 0.3  # Fetch time before measurement time is inconsistent

        # Record-specific consistency checks
        if record_type == "heart_rate" and record.samples:
            # Check for reasonable sampling intervals
            if len(record.samples) > 1:
                intervals = []
                for i in range(1, len(record.samples)):
                    interval = record.samples[i].time_epoch_millis - record.samples[i-1].time_epoch_millis
                    intervals.append(interval)

                # Check for wildly inconsistent intervals
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    max_interval = max(intervals)
                    if max_interval > avg_interval * 10:  # 10x longer than average
                        score -= 0.2

        return max(0.0, score)

    def _assess_timeliness(self, record: Any) -> float:
        """Assess how recent/timely the data is."""
        score = 1.0

        # Get the measurement timestamp
        measurement_time = getattr(record, 'time_epoch_millis', None)
        if measurement_time is None:
            measurement_time = getattr(record, 'end_time_epoch_millis', None)

        if measurement_time:
            current_time = int(datetime.now().timestamp() * 1000)
            age_hours = (current_time - measurement_time) / (1000 * 60 * 60)

            # Newer data is generally more valuable
            if age_hours > 24 * 7:  # Older than a week
                score -= 0.3
            elif age_hours > 24:  # Older than a day
                score -= 0.1

        return max(0.0, score)

    def _assess_clinical_relevance(self, record: Any, record_type: str) -> float:
        """Assess clinical relevance and actionability of the data."""
        score = 1.0

        # Clinical relevance varies by record type and values
        if record_type == "blood_glucose":
            glucose_level = record.level_in_milligrams_per_deciliter
            # Abnormal values have higher clinical relevance
            if glucose_level < 70 or glucose_level > 180:
                score += 0.2  # Clinically significant values

            # Meal context adds clinical value
            from ..types.health_records import AvroBloodGlucoseRelationToMeal
            if record.relation_to_meal != AvroBloodGlucoseRelationToMeal.UNKNOWN:
                score += 0.1

        elif record_type == "sleep_session":
            if record.stages:
                # Detailed sleep stages increase clinical relevance
                score += 0.1

        return min(1.0, score)

    def _add_quality_warnings(self, result: ValidationResult, dimensions: Dict[str, float]):
        """Add warnings based on quality dimension scores."""

        for dimension, score in dimensions.items():
            if score < 0.5:
                result.add_error(ValidationError(
                    field_name=dimension,
                    error_message=f"Poor {dimension} score: {score:.2f}",
                    severity=ValidationSeverity.WARNING,
                    error_code=f"POOR_{dimension.upper()}",
                    current_value=score,
                    expected_value=">= 0.7 for good quality"
                ))
            elif score < 0.7:
                result.add_error(ValidationError(
                    field_name=dimension,
                    error_message=f"Below average {dimension} score: {score:.2f}",
                    severity=ValidationSeverity.INFO,
                    error_code=f"LOW_{dimension.upper()}",
                    current_value=score,
                    expected_value=">= 0.7 for good quality"
                ))

    def get_quality_summary(self, quality_results: List[ValidationResult]) -> Dict[str, Any]:
        """Generate summary statistics for multiple quality assessments."""
        if not quality_results:
            return {"message": "No quality results to summarize"}

        total_records = len(quality_results)
        total_score = sum(result.quality_score for result in quality_results)
        avg_score = total_score / total_records

        # Count records by quality tier
        excellent_count = sum(1 for result in quality_results if result.quality_score >= 0.9)
        good_count = sum(1 for result in quality_results if 0.7 <= result.quality_score < 0.9)
        fair_count = sum(1 for result in quality_results if 0.5 <= result.quality_score < 0.7)
        poor_count = sum(1 for result in quality_results if result.quality_score < 0.5)

        # Aggregate dimension scores
        dimension_scores = {}
        for result in quality_results:
            dimensions = result.metadata.get("quality_dimensions", {})
            for dim, score in dimensions.items():
                if dim not in dimension_scores:
                    dimension_scores[dim] = []
                dimension_scores[dim].append(score)

        avg_dimension_scores = {
            dim: sum(scores) / len(scores)
            for dim, scores in dimension_scores.items()
        }

        return {
            "total_records": total_records,
            "average_quality_score": round(avg_score, 3),
            "quality_distribution": {
                "excellent (>= 0.9)": excellent_count,
                "good (0.7-0.9)": good_count,
                "fair (0.5-0.7)": fair_count,
                "poor (< 0.5)": poor_count
            },
            "dimension_averages": {
                dim: round(score, 3)
                for dim, score in avg_dimension_scores.items()
            },
            "quality_percentage": round((avg_score * 100), 1)
        }