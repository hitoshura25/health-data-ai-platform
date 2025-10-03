
from fastapi_users import schemas
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID

class UserRead(schemas.BaseUser[int]):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class UserCreate(schemas.BaseUserCreate):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)

class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)

class UploadResponse(BaseModel):
    status: str
    correlation_id: UUID
    object_key: str
    record_type: str
    record_count: int
    file_size_bytes: int
    upload_timestamp: datetime
    processing_status: str

class UploadStatusResponse(BaseModel):
    correlation_id: UUID
    status: str
    upload_timestamp: datetime
    object_key: str
    record_type: str
    record_count: int
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    narrative_preview: Optional[str] = None
    training_data_generated: Optional[bool] = None
    error_message: Optional[str] = None

class Pagination(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool

class UploadHistoryResponse(BaseModel):
    uploads: List[UploadStatusResponse]
    pagination: Pagination
