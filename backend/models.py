"""
IDVision — SQLAlchemy ORM Models
Defines Employee and AttendanceLog tables with pgvector support.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, 
    DateTime, ForeignKey, CheckConstraint, Time
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from database import Base


class Employee(Base):
    """Employee table with face encoding stored as 512-dim vector."""
    
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    employee_code = Column(String(50), unique=True, nullable=False, index=True)
    department = Column(String(100), nullable=True)
    telegram_chat_id = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=True)    # Bcrypt hash for password check-in
    face_encoding = Column(Vector(512), nullable=True)  # ArcFace 512-dim embedding
    enrolled_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    # Relationships
    attendance_logs = relationship("AttendanceLog", back_populates="employee", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Employee(id={self.id}, name='{self.name}', code='{self.employee_code}')>"


class AttendanceLog(Base):
    """Attendance log recording each check-in event."""
    
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(
        Integer, 
        ForeignKey("employees.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    check_in_time = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    check_method = Column(String(20), default="FACE", nullable=False)  # FACE or PASSWORD
    status = Column(
        String(50), 
        nullable=False,
        # Valid statuses: SUCCESS, LATE, LOW_CONFIDENCE
    )
    confidence = Column(Float, nullable=True)           # Cosine similarity score
    snapshot_path = Column(String(500), nullable=True)   # Path to snapshot image
    created_at = Column(DateTime(timezone=True), default=datetime.now)

    __table_args__ = (
        CheckConstraint(
            "status IN ('SUCCESS', 'LATE', 'LOW_CONFIDENCE')",
            name="valid_status"
        ),
    )

    # Relationships
    employee = relationship("Employee", back_populates="attendance_logs")

    def __repr__(self):
        return (
            f"<AttendanceLog(id={self.id}, employee_id={self.employee_id}, "
            f"status='{self.status}', time='{self.check_in_time}')>"
        )


class AdminUser(Base):
    """Admin user for dashboard access."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)

    def __repr__(self):
        return f"<AdminUser(id={self.id}, username='{self.username}')>"


class AttendancePolicy(Base):
    """Global attendance and payroll policy configured from admin dashboard."""

    __tablename__ = "attendance_policies"

    id = Column(Integer, primary_key=True, index=True)
    timezone = Column(String(100), nullable=False, default="Asia/Ho_Chi_Minh")
    work_start_time = Column(Time, nullable=False)
    break_start_time = Column(Time, nullable=False)
    break_end_time = Column(Time, nullable=False)
    work_end_time = Column(Time, nullable=False)
    late_grace_minutes = Column(Integer, nullable=False, default=0)
    hourly_wage = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return (
            f"<AttendancePolicy(id={self.id}, timezone='{self.timezone}', "
            f"work_start='{self.work_start_time}', work_end='{self.work_end_time}')>"
        )

