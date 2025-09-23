"""
Shared type definitions for Health Data AI Platform

This module provides Python type definitions corresponding to Avro schemas,
enabling type-safe development across all platform services.
"""

from .common import AvroMetadata, AvroDevice
from .health_records import (
    AvroBloodGlucoseRecord,
    AvroHeartRateRecord,
    AvroSleepSessionRecord,
    AvroStepsRecord,
    AvroActiveCaloriesBurnedRecord,
    AvroHeartRateVariabilityRmssdRecord,
)
from .processing import (
    HealthDataProcessingMessage,
    ETLProcessingResult,
    ErrorMessage,
    HealthRecordType,
    ProcessingStatus,
    ErrorType,
    ServiceComponent,
)

__all__ = [
    # Common types
    "AvroMetadata",
    "AvroDevice",

    # Health record types
    "AvroBloodGlucoseRecord",
    "AvroHeartRateRecord",
    "AvroSleepSessionRecord",
    "AvroStepsRecord",
    "AvroActiveCaloriesBurnedRecord",
    "AvroHeartRateVariabilityRmssdRecord",

    # Processing types
    "HealthDataProcessingMessage",
    "ETLProcessingResult",
    "ErrorMessage",

    # Enums
    "HealthRecordType",
    "ProcessingStatus",
    "ErrorType",
    "ServiceComponent",
]