"""
IDVision — Attendance Router (Refactored)
Thin controller handling API requests for face recognition and password check-ins.
"""

import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_settings
from database import get_db
from models import AttendanceLog, Employee
from schemas import (
    RecognitionRequest,
    RecognitionResult,
    PasswordCheckinRequest,
    AttendanceLogResponse,
    AttendanceReportResponse,
    DailyStatsResponse,
)
from services.attendance_service import AttendanceService
from services.payroll import (
    get_or_create_policy,
    local_date_bounds_to_utc,
    to_local,
)
from exceptions import FaceRecognitionError

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/attendance", tags=["Attendance"])

def get_attendance_service(request: Request) -> AttendanceService:
    """Dependency: retrieves the attendance service from app state."""
    return request.app.state.attendance_service


@router.post("/recognize", response_model=RecognitionResult)
async def recognize_face(
    data: RecognitionRequest,
    session: AsyncSession = Depends(get_db),
    attendance_service: AttendanceService = Depends(get_attendance_service),
):
    """
    Core recognition endpoint — called by the AI service.
    
    Flow:
    1. Delegate checking to AttendanceService (takes embedding, liveness, snapshot).
    2. Convert Domain result to API Schema format.
    """
    try:
        res = await attendance_service.process_checkin_from_embedding(
            session=session,
            embedding=data.embedding,
            snapshot_base64=data.snapshot_base64,
            is_live=data.is_live,
            liveness_score=data.liveness_score
        )
        
        return RecognitionResult(
            recognized=res.success and res.status != "FAILED",
            employee_id=res.employee_id,
            employee_name=res.employee_name,
            similarity=res.similarity,
            status=res.status if res.status != "FAILED" else None,
            message=res.message,
            check_in_time=res.check_in_time,
        )
    except FaceRecognitionError as e:
        # Business level recognition failure (e.g. NoMatchFoundError) should return 200 with recognized=False
        return RecognitionResult(
            recognized=False,
            message=e.message,
        )
    except Exception as e:
        logger.error(f"Recognition router error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi nhận diện chấm công.")


@router.post("/password-checkin", response_model=RecognitionResult)
async def password_checkin(
    data: PasswordCheckinRequest,
    session: AsyncSession = Depends(get_db),
    attendance_service: AttendanceService = Depends(get_attendance_service),
):
    """
    Password-based check-in — fallback when face recognition is unavailable.
    """
    try:
        res = await attendance_service.process_checkin_from_password(
            session=session,
            employee_code=data.employee_code,
            password=data.password
        )
        
        return RecognitionResult(
            recognized=res.success and res.status != "FAILED",
            employee_id=res.employee_id,
            employee_name=res.employee_name,
            similarity=res.similarity,
            status=res.status if res.status != "FAILED" else None,
            message=res.message,
            check_in_time=res.check_in_time,
        )
    except Exception as e:
        logger.error(f"Password check-in router error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi chấm công bằng mật khẩu.")


@router.get("/today", response_model=list[AttendanceLogResponse])
async def get_today_attendance(
    session: AsyncSession = Depends(get_db),
):
    """Get all attendance records for today."""
    policy = await get_or_create_policy(session)
    local_today = to_local(datetime.now(timezone.utc), policy).date()
    today_start, today_end = local_date_bounds_to_utc(local_today, policy)

    stmt = (
        select(AttendanceLog)
        .options(joinedload(AttendanceLog.employee))
        .where(
            and_(
                AttendanceLog.check_in_time >= today_start,
                AttendanceLog.check_in_time < today_end,
            )
        )
        .order_by(AttendanceLog.check_in_time.desc())
    )
    result = await session.execute(stmt)
    logs = result.scalars().unique().all()

    return [
        AttendanceLogResponse(
            id=log.id,
            employee_id=log.employee_id,
            employee_name=log.employee.name,
            check_in_time=log.check_in_time,
            check_method=log.check_method or "FACE",
            status=log.status,
            confidence=log.confidence,
            snapshot_path=log.snapshot_path,
        )
        for log in logs
    ]


@router.get("/report", response_model=AttendanceReportResponse)
async def get_attendance_report(
    date_from: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date (YYYY-MM-DD)"),
    employee_id: int | None = Query(None, description="Filter by employee ID"),
    session: AsyncSession = Depends(get_db),
):
    """Get attendance report for a date range."""
    policy = await get_or_create_policy(session)
    start, _ = local_date_bounds_to_utc(date_from, policy)
    end, _ = local_date_bounds_to_utc(date_to + timedelta(days=1), policy)

    stmt = (
        select(AttendanceLog)
        .options(joinedload(AttendanceLog.employee))
        .where(
            and_(
                AttendanceLog.check_in_time >= start,
                AttendanceLog.check_in_time < end,
            )
        )
    )

    if employee_id:
        stmt = stmt.where(AttendanceLog.employee_id == employee_id)

    stmt = stmt.order_by(AttendanceLog.check_in_time.desc())

    result = await session.execute(stmt)
    logs = result.scalars().unique().all()

    return AttendanceReportResponse(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        total_records=len(logs),
        logs=[
            AttendanceLogResponse(
                id=log.id,
                employee_id=log.employee_id,
                employee_name=log.employee.name,
                check_in_time=log.check_in_time,
                check_method=log.check_method or "FACE",
                status=log.status,
                confidence=log.confidence,
                snapshot_path=log.snapshot_path,
            )
            for log in logs
        ],
    )


@router.get("/stats/today", response_model=DailyStatsResponse)
async def get_today_stats(
    session: AsyncSession = Depends(get_db),
):
    """Get today's attendance statistics summary."""
    policy = await get_or_create_policy(session)
    local_today = to_local(datetime.now(timezone.utc), policy).date()
    today_start, today_end = local_date_bounds_to_utc(local_today, policy)

    base_filter = and_(
        AttendanceLog.check_in_time >= today_start,
        AttendanceLog.check_in_time < today_end,
    )

    # Total
    total_result = await session.execute(
        select(func.count(AttendanceLog.id)).where(base_filter)
    )
    total = total_result.scalar_one()

    # By status
    stats = {}
    for status in ["SUCCESS", "LATE", "LOW_CONFIDENCE"]:
        result = await session.execute(
            select(func.count(AttendanceLog.id)).where(
                and_(base_filter, AttendanceLog.status == status)
            )
        )
        stats[status] = result.scalar_one()

    return DailyStatsResponse(
        date=local_today.isoformat(),
        total_checkins=total,
        on_time=stats.get("SUCCESS", 0),
        late=stats.get("LATE", 0),
        low_confidence=stats.get("LOW_CONFIDENCE", 0),
    )
