"""
Data Validation Module

This module provides comprehensive data validation and quality assessment
for health data files.

Public API:
    - ValidationResult: Validation result dataclass
    - DataQualityValidator: Main validation class
    - ValidationConfig: Validation configuration
    - Clinical ranges utilities
"""

from .clinical_ranges import CLINICAL_RANGES, get_all_ranges, get_clinical_range, is_value_in_range
from .config import ValidationConfig
from .data_quality import DataQualityValidator, ValidationResult

__all__ = [
    'ValidationResult',
    'DataQualityValidator',
    'ValidationConfig',
    'CLINICAL_RANGES',
    'get_clinical_range',
    'is_value_in_range',
    'get_all_ranges',
]
