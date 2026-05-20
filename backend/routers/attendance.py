"""
IDVision — Attendance Router
Core attendance recognition and reporting endpoints.
"""

import base64
import logging
import os
import uuid
from datetime import datetime, date, timedelta, timezone

import bcrypt

from fastapi import APIRouter, Depends, HTTPException, Query
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
from services.matcher import matcher_service
from services.telegram_bot import telegram_notifier

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


@router.post("/recognize", response_model=RecognitionResult)
async def recognize_face(
    data: RecognitionRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Core recognition endpoint — called by the AI service.
    
    Flow:
    1. Receive face embedding from AI service
    2. Check liveness (if anti-spoofing enabled)
    3. Match against in-memory cache (cosine similarity)
    4. Check for duplicate check-in
    5. Determine status (on-time / late)
    6. Insert attendance log
    7. Send Telegram notification
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: Liveness check ──────────────────────────────
    if settings.ANTI_SPOOFING_ENABLED and not data.is_live:
        logger.warning(
            f"Spoofing attempt detected! Liveness score: {data.liveness_score:.3f}"
        )
        return RecognitionResult(
            recognized=False,
            message="⛔ Phát hiện ảnh giả (spoofing). Vui lòng đến trực tiếp.",
        )

    # ── Step 2: Match face against cache ────────────────────
    match = matcher_service.match_face(data.embedding)

    if match is None:
        return RecognitionResult(
            recognized=False,
            message="❌ Không nhận diện được. Khuôn mặt chưa được đăng ký.",
        )

    # ── Step 3: Check duplicate ─────────────────────────────
    is_duplicate = await matcher_service.check_duplicate(
        session=session,
        employee_id=match.employee_id,
        current_time=now,
    )
    if is_duplicate:
        return RecognitionResult(
            recognized=True,
            employee_id=match.employee_id,
            employee_name=match.employee_name,
            similarity=match.similarity,
            message=(
                f"ℹ️ {match.employee_name} đã chấm công trong "
                f"{settings.DUPLICATE_CHECK_MINUTES} phút gần đây."
            ),
        )

    # ── Step 4: Determine status ────────────────────────────
    status = matcher_service.determine_status(now)
    late_minutes = matcher_service.calculate_late_minutes(now)

    # Override to LOW_CONFIDENCE if below a secondary threshold
    LOW_CONFIDENCE_THRESHOLD = settings.SIMILARITY_THRESHOLD + 0.10
    if match.similarity < LOW_CONFIDENCE_THRESHOLD:
        status = "LOW_CONFIDENCE"

    # ── Step 5: Save snapshot (if provided) ─────────────────
    snapshot_path = None
    if data.snapshot_base64:
        try:
            snapshot_dir = settings.SNAPSHOT_DIR
            os.makedirs(snapshot_dir, exist_ok=True)
            filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{match.employee_id}_{uuid.uuid4().hex[:8]}.jpg"
            snapshot_path = os.path.join(snapshot_dir, filename)
            with open(snapshot_path, "wb") as f:
                f.write(base64.b64decode(data.snapshot_base64))
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            snapshot_path = None

    # ── Step 6: Insert attendance log ───────────────────────
    log = AttendanceLog(
        employee_id=match.employee_id,
        check_in_time=now,
        status=status,
        confidence=match.similarity,
        snapshot_path=snapshot_path,
    )
    session.add(log)
    await session.flush()

    logger.info(
        f"Attendance recorded: {match.employee_name} | "
        f"Status: {status} | Confidence: {match.similarity:.4f}"
    )

    # ── Step 7: Send Telegram notification ──────────────────
    try:
        if status == "SUCCESS":
            await telegram_notifier.send_checkin_success(
                employee_name=match.employee_name,
                check_in_time=now,
                confidence=match.similarity,
                employee_chat_id=match.telegram_chat_id,
            )
        elif status == "LATE":
            await telegram_notifier.send_late_notification(
                employee_name=match.employee_name,
                check_in_time=now,
                late_minutes=late_minutes,
                confidence=match.similarity,
                employee_chat_id=match.telegram_chat_id,
            )
        elif status == "LOW_CONFIDENCE":
            await telegram_notifier.send_low_confidence_alert(
                check_in_time=now,
                confidence=match.similarity,
            )
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        # Don't fail the attendance recording if notification fails

    # ── Build response ──────────────────────────────────────
    status_messages = {
        "SUCCESS": f"✅ {match.employee_name} đã chấm công thành công.",
        "LATE": f"⚠️ {match.employee_name} đến trễ {late_minutes} phút.",
        "LOW_CONFIDENCE": f"🔍 Nhận diện kém. Cần xác minh: {match.employee_name}.",
    }

    return RecognitionResult(
        recognized=True,
        employee_id=match.employee_id,
        employee_name=match.employee_name,
        similarity=match.similarity,
        status=status,
        message=status_messages.get(status, ""),
        check_in_time=now,
    )


@router.post("/password-checkin", response_model=RecognitionResult)
async def password_checkin(
    data: PasswordCheckinRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Password-based check-in — fallback when face recognition is unavailable.
    Employee uses their employee_code + password to check in.
    """
    now = datetime.now(timezone.utc)

    # Find employee by code
    result = await session.execute(
        select(Employee).where(
            Employee.employee_code == data.employee_code,
            Employee.is_active == True,
        )
    )
    employee = result.scalar_one_or_none()

    if not employee:
        return RecognitionResult(
            recognized=False,
            message="❌ Mã nhân viên không tồn tại hoặc đã bị vô hiệu hóa.",
        )

    # Verify password
    if not employee.password_hash:
        return RecognitionResult(
            recognized=False,
            message="❌ Nhân viên chưa được thiết lập mật khẩu. Liên hệ Admin.",
        )

    if not bcrypt.checkpw(data.password.encode("utf-8"), employee.password_hash.encode("utf-8")):
        return RecognitionResult(
            recognized=False,
            message="❌ Mật khẩu không đúng.",
        )

    # Check duplicate
    is_duplicate = await matcher_service.check_duplicate(
        session=session,
        employee_id=employee.id,
        current_time=now,
    )
    if is_duplicate:
        return RecognitionResult(
            recognized=True,
            employee_id=employee.id,
            employee_name=employee.name,
            message=(
                f"ℹ️ {employee.name} đã chấm công trong "
                f"{settings.DUPLICATE_CHECK_MINUTES} phút gần đây."
            ),
        )

    # Determine status
    status = matcher_service.determine_status(now)
    late_minutes = matcher_service.calculate_late_minutes(now)

    # Insert attendance log
    log = AttendanceLog(
        employee_id=employee.id,
        check_in_time=now,
        check_method="PASSWORD",
        status=status,
        confidence=None,
        snapshot_path=None,
    )
    session.add(log)
    await session.flush()

    logger.info(
        f"Password check-in: {employee.name} | Status: {status}"
    )

    # Send Telegram notification
    try:
        if status == "SUCCESS":
            await telegram_notifier.send_checkin_success(
                employee_name=employee.name,
                check_in_time=now,
                confidence=1.0,
                employee_chat_id=employee.telegram_chat_id,
            )
        elif status == "LATE":
            await telegram_notifier.send_late_notification(
                employee_name=employee.name,
                check_in_time=now,
                late_minutes=late_minutes,
                confidence=1.0,
                employee_chat_id=employee.telegram_chat_id,
            )
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")

    status_messages = {
        "SUCCESS": f"✅ {employee.name} đã chấm công thành công (mật khẩu).",
        "LATE": f"⚠️ {employee.name} đến trễ {late_minutes} phút (mật khẩu).",
    }

    return RecognitionResult(
        recognized=True,
        employee_id=employee.id,
        employee_name=employee.name,
        similarity=None,
        status=status,
        message=status_messages.get(status, ""),
        check_in_time=now,
    )


@router.get("/today", response_model=list[AttendanceLogResponse])
async def get_today_attendance(
    session: AsyncSession = Depends(get_db),
):
    """Get all attendance records for today."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_end = today_start + timedelta(days=1)

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
    start = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

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
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_end = today_start + timedelta(days=1)

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
        date=date.today().isoformat(),
        total_checkins=total,
        on_time=stats.get("SUCCESS", 0),
        late=stats.get("LATE", 0),
        low_confidence=stats.get("LOW_CONFIDENCE", 0),
    )
