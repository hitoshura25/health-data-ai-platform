"""
Type definitions for health record data structures.
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from .common import AvroMetadata


# Blood Glucose Enums
class AvroBloodGlucoseSpecimenSource(Enum):
    """Source of blood glucose specimen for measurement accuracy context."""
    INTERSTITIAL_FLUID = "INTERSTITIAL_FLUID"
    CAPILLARY_BLOOD = "CAPILLARY_BLOOD"
    PLASMA = "PLASMA"
    SERUM = "SERUM"
    TEARS = "TEARS"
    WHOLE_BLOOD = "WHOLE_BLOOD"
    UNKNOWN = "UNKNOWN"


class AvroBloodGlucoseMealType(Enum):
    """Type of meal for clinical interpretation of glucose levels."""
    UNKNOWN = "UNKNOWN"
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"
    SNACK = "SNACK"


class AvroBloodGlucoseRelationToMeal(Enum):
    """Timing relative to meal for clinical glucose interpretation."""
    UNKNOWN = "UNKNOWN"
    GENERAL = "GENERAL"
    FASTING = "FASTING"
    BEFORE_MEAL = "BEFORE_MEAL"
    AFTER_MEAL = "AFTER_MEAL"


# Sleep Stage Enum
class AvroSleepStageType(Enum):
    """Sleep stage classification for analysis."""
    UNKNOWN = "UNKNOWN"
    AWAKE = "AWAKE"
    SLEEPING = "SLEEPING"
    OUT_OF_BED = "OUT_OF_BED"
    LIGHT = "LIGHT"
    DEEP = "DEEP"
    REM = "REM"


# Health Record Data Classes
@dataclass
class AvroBloodGlucoseRecord:
    """Blood glucose measurement record with clinical context."""

    metadata: AvroMetadata
    time_epoch_millis: int
    level_in_milligrams_per_deciliter: float
    specimen_source: AvroBloodGlucoseSpecimenSource
    meal_type: AvroBloodGlucoseMealType
    relation_to_meal: AvroBloodGlucoseRelationToMeal
    app_record_fetch_time_epoch_millis: int
    zone_offset_id: Optional[str] = None

    def is_normal_range(self) -> bool:
        """Check if glucose level is within normal range (70-140 mg/dL)."""
        return 70.0 <= self.level_in_milligrams_per_deciliter <= 140.0

    def is_hypoglycemic(self) -> bool:
        """Check if glucose level indicates hypoglycemia (<70 mg/dL)."""
        return self.level_in_milligrams_per_deciliter < 70.0

    def is_hyperglycemic(self) -> bool:
        """Check if glucose level indicates hyperglycemia (>180 mg/dL)."""
        return self.level_in_milligrams_per_deciliter > 180.0


@dataclass
class AvroHeartRateSample:
    """Individual heart rate measurement sample."""

    time_epoch_millis: int
    beats_per_minute: int

    def is_normal_resting_rate(self) -> bool:
        """Check if heart rate is within normal resting range (60-100 bpm)."""
        return 60 <= self.beats_per_minute <= 100


@dataclass
class AvroHeartRateRecord:
    """Heart rate measurement record with time-series sample data."""

    metadata: AvroMetadata
    start_time_epoch_millis: int
    end_time_epoch_millis: int
    app_record_fetch_time_epoch_millis: int
    samples: List[AvroHeartRateSample]
    start_zone_offset_id: Optional[str] = None
    end_zone_offset_id: Optional[str] = None

    def get_average_heart_rate(self) -> Optional[float]:
        """Calculate average heart rate across all samples."""
        if not self.samples:
            return None
        return sum(sample.beats_per_minute for sample in self.samples) / len(self.samples)

    def get_min_max_heart_rate(self) -> tuple[Optional[int], Optional[int]]:
        """Get minimum and maximum heart rate from samples."""
        if not self.samples:
            return None, None
        rates = [sample.beats_per_minute for sample in self.samples]
        return min(rates), max(rates)


@dataclass
class AvroSleepStageRecord:
    """Individual sleep stage period within the session."""

    start_time_epoch_millis: int
    end_time_epoch_millis: int
    stage: AvroSleepStageType

    def get_duration_minutes(self) -> float:
        """Get duration of this sleep stage in minutes."""
        duration_ms = self.end_time_epoch_millis - self.start_time_epoch_millis
        return duration_ms / (1000 * 60)


@dataclass
class AvroSleepSessionRecord:
    """Sleep session record with detailed sleep stage tracking."""

    metadata: AvroMetadata
    start_time_epoch_millis: int
    end_time_epoch_millis: int
    app_record_fetch_time_epoch_millis: int
    stages: List[AvroSleepStageRecord]
    title: Optional[str] = None
    notes: Optional[str] = None
    start_zone_offset_id: Optional[str] = None
    end_zone_offset_id: Optional[str] = None
    duration_millis: Optional[int] = None

    def get_total_sleep_time_hours(self) -> float:
        """Calculate total sleep time excluding awake periods."""
        sleep_stages = [AvroSleepStageType.LIGHT, AvroSleepStageType.DEEP, AvroSleepStageType.REM, AvroSleepStageType.SLEEPING]
        total_sleep_ms = sum(
            stage.end_time_epoch_millis - stage.start_time_epoch_millis
            for stage in self.stages
            if stage.stage in sleep_stages
        )
        return total_sleep_ms / (1000 * 60 * 60)

    def get_sleep_efficiency(self) -> float:
        """Calculate sleep efficiency (sleep time / time in bed)."""
        total_time_ms = self.end_time_epoch_millis - self.start_time_epoch_millis
        if total_time_ms == 0:
            return 0.0

        sleep_time_hours = self.get_total_sleep_time_hours()
        total_time_hours = total_time_ms / (1000 * 60 * 60)
        return sleep_time_hours / total_time_hours


@dataclass
class AvroStepsRecord:
    """Step count measurement record over a time period."""

    metadata: AvroMetadata
    start_time_epoch_millis: int
    end_time_epoch_millis: int
    count: int
    app_record_fetch_time_epoch_millis: int
    start_zone_offset_id: Optional[str] = None
    end_zone_offset_id: Optional[str] = None

    def get_steps_per_hour(self) -> float:
        """Calculate steps per hour for this time period."""
        duration_ms = self.end_time_epoch_millis - self.start_time_epoch_millis
        if duration_ms == 0:
            return 0.0
        duration_hours = duration_ms / (1000 * 60 * 60)
        return self.count / duration_hours


@dataclass
class AvroActiveCaloriesBurnedRecord:
    """Active calories burned measurement record over a time period."""

    metadata: AvroMetadata
    start_time_epoch_millis: int
    end_time_epoch_millis: int
    energy_in_kilocalories: float
    app_record_fetch_time_epoch_millis: int
    start_zone_offset_id: Optional[str] = None
    end_zone_offset_id: Optional[str] = None

    def get_calories_per_hour(self) -> float:
        """Calculate calories burned per hour for this time period."""
        duration_ms = self.end_time_epoch_millis - self.start_time_epoch_millis
        if duration_ms == 0:
            return 0.0
        duration_hours = duration_ms / (1000 * 60 * 60)
        return self.energy_in_kilocalories / duration_hours


@dataclass
class AvroHeartRateVariabilityRmssdRecord:
    """Heart Rate Variability RMSSD measurement record."""

    metadata: AvroMetadata
    time_epoch_millis: int
    heart_rate_variability_rmssd: float
    app_record_fetch_time_epoch_millis: int
    zone_offset_id: Optional[str] = None

    def is_normal_hrv_range(self) -> bool:
        """Check if HRV is within normal range for adults (20-50ms)."""
        return 20.0 <= self.heart_rate_variability_rmssd <= 50.0

    def get_hrv_status(self) -> str:
        """Get descriptive HRV status."""
        if self.heart_rate_variability_rmssd < 20:
            return "LOW"
        elif self.heart_rate_variability_rmssd > 50:
            return "HIGH"
        else:
            return "NORMAL"