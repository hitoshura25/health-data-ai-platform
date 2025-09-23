"""
API request/response models for Health Data AI Platform.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class HealthRecordType(str, Enum):
    """Supported health record types."""
    BLOOD_GLUCOSE = "blood_glucose"
    HEART_RATE = "heart_rate"
    SLEEP_SESSION = "sleep_session"
    STEPS = "steps"
    ACTIVE_CALORIES = "active_calories"
    HEART_RATE_VARIABILITY = "heart_rate_variability"


class ProcessingStatus(str, Enum):
    """Processing status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class ErrorCode(str, Enum):
    """Standard error codes."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Base models
class BaseResponse(BaseModel):
    """Base response model with common fields."""
    success: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None


class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: ErrorCode
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseResponse):
    """Standard error response."""
    success: bool = False
    error: ErrorDetail
    trace_id: Optional[str] = None


# Health data upload models
class HealthDataUploadRequest(BaseModel):
    """Request model for health data upload."""
    record_type: HealthRecordType
    file_name: str
    file_size: int
    content_hash: str
    device_info: Optional[Dict[str, str]] = None
    sync_app_version: Optional[str] = None

    @validator('file_size')
    def validate_file_size(cls, v):
        """Validate file size is reasonable."""
        max_size = 100 * 1024 * 1024  # 100MB
        if v > max_size:
            raise ValueError(f"File size {v} exceeds maximum allowed size {max_size}")
        if v <= 0:
            raise ValueError("File size must be positive")
        return v

    @validator('content_hash')
    def validate_content_hash(cls, v):
        """Validate content hash format."""
        if not v or len(v) != 64:  # SHA256 hex string
            raise ValueError("Content hash must be a valid SHA256 hex string")
        return v.lower()


class StorageInfo(BaseModel):
    """Information about stored file."""
    bucket: str
    key: str
    url: str
    expires_at: Optional[datetime] = None


class HealthDataUploadResponse(BaseResponse):
    """Response model for health data upload."""
    upload_id: str
    storage_info: StorageInfo
    processing_status: ProcessingStatus
    estimated_processing_time_seconds: Optional[int] = None


# Processing status models
class ProcessingStep(BaseModel):
    """Individual processing step information."""
    step_name: str
    status: ProcessingStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ProcessingStatusResponse(BaseResponse):
    """Response model for processing status check."""
    upload_id: str
    overall_status: ProcessingStatus
    progress_percentage: float = Field(ge=0.0, le=100.0)
    steps: List[ProcessingStep]
    estimated_completion: Optional[datetime] = None
    result_location: Optional[str] = None


# Query interface models
class QueryRequest(BaseModel):
    """Request model for AI queries."""
    query: str = Field(min_length=1, max_length=1000)
    include_context: bool = True
    max_response_length: Optional[int] = None

    @validator('query')
    def validate_query(cls, v):
        """Validate query content."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class QueryResponse(BaseResponse):
    """Response model for AI queries."""
    query: str
    response: str
    confidence_score: Optional[float] = Field(ge=0.0, le=1.0)
    sources: Optional[List[str]] = None
    conversation_id: Optional[str] = None
    model_version: Optional[str] = None


# Feedback models
class FeedbackRequest(BaseModel):
    """Request model for user feedback."""
    conversation_id: str
    rating: int = Field(ge=1, le=5)
    feedback_text: Optional[str] = None
    improvement_suggestions: Optional[str] = None

    @validator('feedback_text')
    def validate_feedback_text(cls, v):
        """Validate feedback text length."""
        if v and len(v) > 2000:
            raise ValueError("Feedback text cannot exceed 2000 characters")
        return v


class FeedbackResponse(BaseResponse):
    """Response model for feedback submission."""
    feedback_id: str
    message: str = "Feedback received successfully"


# Health check models
class ServiceHealth(BaseModel):
    """Individual service health status."""
    service: str
    status: str  # healthy, degraded, unhealthy
    message: str
    duration_ms: float
    details: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseResponse):
    """Response model for health checks."""
    overall_status: str
    services: Dict[str, ServiceHealth]
    summary: Dict[str, int]


# User management models (if authentication is handled by the service)
class UserRegistration(BaseModel):
    """User registration request."""
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: Optional[datetime] = None

    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserProfile(BaseModel):
    """User profile information."""
    user_id: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True


class LoginRequest(BaseModel):
    """User login request."""
    email: str
    password: str


class LoginResponse(BaseResponse):
    """User login response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_profile: UserProfile


# Data insights models
class InsightSummary(BaseModel):
    """Summary of health insights."""
    insight_type: str
    title: str
    description: str
    importance_level: str  # low, medium, high, critical
    data_points_analyzed: int
    time_period: str
    recommendations: Optional[List[str]] = None


class InsightsResponse(BaseResponse):
    """Response model for health insights."""
    user_id: str
    time_period: str
    insights: List[InsightSummary]
    data_quality_score: float = Field(ge=0.0, le=1.0)
    last_updated: datetime


# Export models for OpenAPI documentation
class OpenAPIModels:
    """Container for OpenAPI documentation models."""

    @staticmethod
    def get_upload_examples():
        """Get example requests/responses for upload endpoint."""
        return {
            "request_example": {
                "record_type": "blood_glucose",
                "file_name": "glucose_readings_20240123.avro",
                "file_size": 2048,
                "content_hash": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
                "device_info": {
                    "manufacturer": "Dexcom",
                    "model": "Stelo",
                    "type": "cgm"
                },
                "sync_app_version": "1.0.0"
            },
            "response_example": {
                "success": True,
                "timestamp": "2024-01-23T10:30:00Z",
                "upload_id": "upload_123456789",
                "storage_info": {
                    "bucket": "health-data",
                    "key": "raw/blood_glucose/2024/01/23/user123_20240123_103000_stelo_a1b2c3d4.avro",
                    "url": "https://minio.example.com/health-data/...",
                    "expires_at": "2024-01-23T11:30:00Z"
                },
                "processing_status": "pending",
                "estimated_processing_time_seconds": 30
            }
        }

    @staticmethod
    def get_query_examples():
        """Get example requests/responses for query endpoint."""
        return {
            "request_example": {
                "query": "What's my average blood glucose over the last week?",
                "include_context": True,
                "max_response_length": 500
            },
            "response_example": {
                "success": True,
                "timestamp": "2024-01-23T10:30:00Z",
                "query": "What's my average blood glucose over the last week?",
                "response": "Based on your data from the last 7 days, your average blood glucose level was 142 mg/dL. This is slightly above the normal range of 70-140 mg/dL. You had 45 readings total, with most values between 120-160 mg/dL.",
                "confidence_score": 0.95,
                "sources": ["blood_glucose_readings", "clinical_guidelines"],
                "conversation_id": "conv_123456789",
                "model_version": "health-ai-v1.2.0"
            }
        }