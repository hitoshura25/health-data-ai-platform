"""
API contracts and OpenAPI specifications for Health Data AI Platform.

This module contains shared API contracts, request/response models,
and OpenAPI specifications used across services.
"""

from .api_models import (
    HealthDataUploadRequest,
    HealthDataUploadResponse,
    ProcessingStatusResponse,
    ErrorResponse,
    HealthCheckResponse,
)
from .message_contracts import (
    MessageContract,
    HealthDataProcessingContract,
    ETLResultContract,
    ErrorMessageContract,
)

__all__ = [
    # API Models
    "HealthDataUploadRequest",
    "HealthDataUploadResponse",
    "ProcessingStatusResponse",
    "ErrorResponse",
    "HealthCheckResponse",

    # Message Contracts
    "MessageContract",
    "HealthDataProcessingContract",
    "ETLResultContract",
    "ErrorMessageContract",
]