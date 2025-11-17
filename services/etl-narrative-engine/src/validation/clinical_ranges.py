"""
Clinical Range Definitions for Health Data Validation

This module defines physiological ranges for health data validation.
Ranges represent extreme but medically possible values.
"""


# Physiological ranges (extreme but possible values)
CLINICAL_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    'BloodGlucoseRecord': {
        'glucose_mg_dl': (20, 600),  # Extreme hypoglycemia to extreme hyperglycemia
    },
    'HeartRateRecord': {
        'heart_rate_bpm': (30, 220),  # Extreme bradycardia to tachycardia
    },
    'SleepSessionRecord': {
        'duration_hours': (0.5, 16),  # Minimum nap to maximum sleep
    },
    'StepsRecord': {
        'count': (0, 100000),  # No steps to extreme athletic performance
    },
    'ActiveCaloriesBurnedRecord': {
        'calories': (0, 10000),  # No activity to extreme endurance activity
    },
    'HeartRateVariabilityRmssdRecord': {
        'rmssd_ms': (1, 300),  # Low HRV to very high HRV
    }
}


def get_clinical_range(record_type: str, field: str) -> tuple[float, float] | None:
    """
    Get clinical range for a specific field in a record type.

    Args:
        record_type: Type of health record (e.g., "BloodGlucoseRecord")
        field: Field name to get range for (e.g., "glucose_mg_dl")

    Returns:
        Tuple of (min, max) if range exists, None otherwise
    """
    return CLINICAL_RANGES.get(record_type, {}).get(field)


def is_value_in_range(value: float, record_type: str, field: str) -> bool:
    """
    Check if a value is within the clinical range.

    Args:
        value: The value to check
        record_type: Type of health record
        field: Field name

    Returns:
        True if value is in range or range not defined, False otherwise
    """
    range_tuple = get_clinical_range(record_type, field)
    if range_tuple is None:
        return True  # No range defined, assume valid

    min_val, max_val = range_tuple
    return min_val <= value <= max_val


def get_all_ranges() -> dict[str, dict[str, tuple[float, float]]]:
    """
    Get all clinical ranges.

    Returns:
        Complete dictionary of clinical ranges
    """
    return CLINICAL_RANGES.copy()
