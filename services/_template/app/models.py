"""
Service Data Models Template

This module defines data models specific to your service.
Use these in addition to the shared models from shared.contracts.api_models.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field, validator

# Import shared models
from shared.contracts.api_models import BaseResponse, ProcessingStatus
from shared.types import AvroMetadata


class ServiceTaskStatus(str, Enum):
    """Service-specific task statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ServiceModel(BaseModel):
    """Base model for service entities."""

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskRequest(BaseModel):
    """Template for service task requests."""

    task_type: str = Field(..., description="Type of task to perform")
    input_data: Dict[str, Any] = Field(..., description="Input data for the task")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (1-10)")
    timeout_seconds: Optional[int] = Field(default=300, description="Task timeout")
    callback_url: Optional[str] = Field(None, description="Callback URL for results")

    @validator('task_type')
    def validate_task_type(cls, v):
        """Validate task type."""
        allowed_types = ["example_task", "another_task"]  # Define your task types
        if v not in allowed_types:
            raise ValueError(f"Task type must be one of {allowed_types}")
        return v


class TaskResponse(BaseResponse):
    """Template for service task responses."""

    task_id: str = Field(..., description="Unique task identifier")
    status: ServiceTaskStatus = Field(..., description="Current task status")
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    estimated_completion: Optional[datetime] = None
    result_url: Optional[str] = None


class TaskResult(ServiceModel):
    """Template for service task results."""

    task_id: str = Field(..., description="Associated task ID")
    status: ServiceTaskStatus = Field(..., description="Final task status")
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time_seconds: Optional[float] = None


# Example domain-specific models (customize for your service)

class HealthDataTask(TaskRequest):
    """Example: Health data processing task."""

    record_type: str = Field(..., description="Type of health record")
    file_path: str = Field(..., description="Path to data file")
    validation_rules: Optional[List[str]] = None

    @validator('record_type')
    def validate_record_type(cls, v):
        """Validate health record type."""
        allowed_types = ["blood_glucose", "heart_rate", "sleep_session", "steps"]
        if v not in allowed_types:
            raise ValueError(f"Record type must be one of {allowed_types}")
        return v


class ProcessingResult(ServiceModel):
    """Example: Data processing result."""

    source_file: str = Field(..., description="Source file path")
    records_processed: int = Field(default=0, description="Number of records processed")
    records_failed: int = Field(default=0, description="Number of failed records")
    validation_errors: List[str] = Field(default_factory=list)
    output_location: Optional[str] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class MLPredictionRequest(BaseModel):
    """Example: ML prediction request."""

    model_name: str = Field(..., description="Name of the model to use")
    model_version: Optional[str] = Field(default="latest", description="Model version")
    input_features: Dict[str, Any] = Field(..., description="Input features for prediction")
    explain: bool = Field(default=False, description="Include prediction explanation")

    @validator('input_features')
    def validate_input_features(cls, v):
        """Validate input features are not empty."""
        if not v:
            raise ValueError("Input features cannot be empty")
        return v


class MLPredictionResponse(BaseResponse):
    """Example: ML prediction response."""

    model_name: str = Field(..., description="Model used for prediction")
    model_version: str = Field(..., description="Model version used")
    predictions: List[Dict[str, Any]] = Field(..., description="Prediction results")
    confidence_scores: Optional[List[float]] = None
    explanation: Optional[Dict[str, Any]] = None
    inference_time_ms: Optional[float] = None


class ServiceMetrics(BaseModel):
    """Service performance metrics."""

    service_name: str = Field(..., description="Name of the service")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    requests_total: int = Field(default=0, description="Total requests processed")
    requests_successful: int = Field(default=0, description="Successful requests")
    requests_failed: int = Field(default=0, description="Failed requests")
    average_response_time_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


class ConfigurationUpdate(BaseModel):
    """Service configuration update request."""

    parameter_name: str = Field(..., description="Configuration parameter name")
    new_value: Any = Field(..., description="New parameter value")
    restart_required: bool = Field(default=False, description="Whether restart is required")
    effective_immediately: bool = Field(default=True, description="Apply immediately")

    @validator('parameter_name')
    def validate_parameter_name(cls, v):
        """Validate parameter name."""
        # Define allowed configuration parameters
        allowed_params = [
            "max_workers", "timeout_seconds", "batch_size",
            "cache_ttl", "rate_limit_requests"
        ]
        if v not in allowed_params:
            raise ValueError(f"Parameter must be one of {allowed_params}")
        return v


# Database models (if using an ORM like SQLAlchemy)
# Uncomment and customize if your service uses a database

# from sqlalchemy import Column, Integer, String, DateTime, JSON, Float
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.sql import func
#
# Base = declarative_base()
#
#
# class TaskORM(Base):
#     """Database model for tasks."""
#
#     __tablename__ = "tasks"
#
#     id = Column(String, primary_key=True)
#     task_type = Column(String, nullable=False)
#     status = Column(String, nullable=False)
#     input_data = Column(JSON)
#     result_data = Column(JSON)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     processing_time_seconds = Column(Float)


# Response models for API documentation
class OpenAPIExamples:
    """Example requests/responses for OpenAPI documentation."""

    @staticmethod
    def get_task_examples():
        """Get example task requests/responses."""
        return {
            "request_example": {
                "task_type": "example_task",
                "input_data": {
                    "file_path": "/data/health_records.avro",
                    "record_type": "blood_glucose"
                },
                "priority": 7,
                "timeout_seconds": 600
            },
            "response_example": {
                "success": True,
                "timestamp": "2024-01-23T10:30:00Z",
                "task_id": "task_123456789",
                "status": "processing",
                "progress_percentage": 25.0,
                "estimated_completion": "2024-01-23T10:40:00Z"
            }
        }