"""
IDVision — Pydantic Schemas
Request/Response models for API validation and serialization.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# Employee Schemas
# ═══════════════════════════════════════════════════════════════

class EmployeeCreate(BaseModel):
    """Schema for creating a new employee."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Nguyễn Nhất Huy"])
    employee_code: str = Field(..., min_length=1, max_length=50, examples=["NV001"])
    department: Optional[str] = Field(None, max_length=100, examples=["Engineering"])
    telegram_chat_id: Optional[str] = Field(None, max_length=50, examples=["123456789"])
    password: Optional[str] = Field(None, min_length=4, max_length=100, description="Password for manual check-in")


class EmployeeUpdate(BaseModel):
    """Schema for updating employee info."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    telegram_chat_id: Optional[str] = Field(None, max_length=50)
    password: Optional[str] = Field(None, min_length=4, max_length=100)
    is_active: Optional[bool] = None


class EmployeeResponse(BaseModel):
    """Schema for employee response."""
    id: int
    name: str
    employee_code: str
    department: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    has_password: bool = False      # Whether password is set
    is_enrolled: bool = False       # Whether face encoding exists
    enrolled_at: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    """Paginated employee list response."""
    total: int
    employees: list[EmployeeResponse]


# ═══════════════════════════════════════════════════════════════
# Enrollment Schemas
# ═══════════════════════════════════════════════════════════════

class EnrollmentResponse(BaseModel):
    """Response after face enrollment."""
    employee_id: int
    employee_name: str
    message: str
    num_faces_processed: int
    enrolled_at: datetime


# ═══════════════════════════════════════════════════════════════
# Attendance / Recognition Schemas
# ═══════════════════════════════════════════════════════════════

class RecognitionRequest(BaseModel):
    """Request from AI service with extracted face embedding."""
    embedding: list[float] = Field(..., min_length=512, max_length=512)
    is_live: bool = True            # Liveness check result from AI service
    liveness_score: float = 1.0
    snapshot_base64: Optional[str] = None   # Base64 encoded snapshot image


class RecognitionResult(BaseModel):
    """Response for recognition request."""
    recognized: bool
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    similarity: Optional[float] = None
    status: Optional[str] = None        # SUCCESS / LATE / LOW_CONFIDENCE
    message: str
    check_in_time: Optional[datetime] = None


class AttendanceLogResponse(BaseModel):
    """Schema for attendance log entry."""
    id: int
    employee_id: int
    employee_name: str
    check_in_time: datetime
    check_method: str = "FACE"      # FACE or PASSWORD
    status: str
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None

    model_config = {"from_attributes": True}


class AttendanceReportResponse(BaseModel):
    """Attendance report for a date range."""
    date_from: str
    date_to: str
    total_records: int
    logs: list[AttendanceLogResponse]


class DailyStatsResponse(BaseModel):
    """Daily attendance statistics."""
    date: str
    total_checkins: int
    on_time: int
    late: int
    low_confidence: int


# ═══════════════════════════════════════════════════════════════
# Password Check-in Schemas
# ═══════════════════════════════════════════════════════════════

class PasswordCheckinRequest(BaseModel):
    """Request for password-based check-in."""
    employee_code: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


# ═══════════════════════════════════════════════════════════════
# Admin Auth Schemas
# ═══════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    """Admin login request."""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AdminLoginResponse(BaseModel):
    """Admin login response with JWT token."""
    token: str
    username: str
    full_name: Optional[str] = None
    message: str = "Login successful"
