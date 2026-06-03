"""
IDVision — Attendance Service
Implements business logic for employee face check-in, duplicate checks, and status reporting.
"""

import os
import uuid
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import numpy as np
import cv2
import bcrypt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import AttendanceLog, Employee
from services.face_cache import MatchResult
from services.face_detection_service import FaceDetectionService
from services.face_embedding_service import FaceEmbeddingService
from services.face_matching_service import FaceMatchingService
from services.telegram_bot import telegram_notifier
from services.payroll import (
    calculate_employee_month_stats,
    determine_status,
    determine_period_type,
    get_or_create_policy,
    to_local,
)
from exceptions import (
    FaceQualityError,
    NoMatchFoundError,
    DuplicateCheckinError,
    FaceRecognitionError
)
from services.providers.domain_models import AttendanceResult

logger = logging.getLogger(__name__)
settings = get_settings()

class AttendanceService:
    """
    Main business logic service for processing attendance check-ins.
    Handles liveness validation, face detection/embedding matching, duplicate prevention,
    and recording logs with notifications.
    """

    def __init__(
        self,
        detection_service: FaceDetectionService,
        embedding_service: FaceEmbeddingService,
        matching_service: FaceMatchingService
    ):
        self.detection_service = detection_service
        self.embedding_service = embedding_service
        self.matching_service = matching_service

    async def process_checkin_from_image(
        self,
        session: AsyncSession,
        image: np.ndarray,
        device_info: str = "WEBCAM"
    ) -> AttendanceResult:
        """
        Processes check-in using an image uploaded from the client (e.g. Frontend Webcam).
        Detects face, validates quality, extracts embedding, matches against DB,
        records attendance, and sends Telegram alert.
        """
        now = datetime.now(timezone.utc)

        # 1. Detect and validate face
        face = self.detection_service.detect_single_face(image)
        quality = self.detection_service.validate_face_quality(face, image)
        if not quality.is_valid:
            raise FaceQualityError("\n".join(quality.issues))

        # 2. Extract embedding
        embedding = self.embedding_service.generate_embedding(image, face)

        # 3. Match embedding
        match = self.matching_service.find_best_match(embedding)
        if not match:
            raise NoMatchFoundError()

        # 4. Save snapshot
        snapshot_path = None
        try:
            _, buffer = cv2.imencode(".jpg", image)
            snapshot_bytes = buffer.tobytes()
            snapshot_path = await self._save_snapshot_file(match.employee_id, now, snapshot_bytes)
        except Exception as e:
            logger.error(f"Failed to save image snapshot: {e}")

        # 5. Complete check-in registration
        return await self._register_checkin(
            session=session,
            match=match,
            now=now,
            confidence=match.similarity,
            check_method="FACE",
            snapshot_path=snapshot_path
        )

    async def process_checkin_from_embedding(
        self,
        session: AsyncSession,
        embedding: list[float],
        snapshot_base64: Optional[str] = None,
        is_live: bool = True,
        liveness_score: float = 1.0
    ) -> AttendanceResult:
        """
        Processes check-in using a pre-computed embedding (e.g. from AI camera service).
        Validates liveness, matches embedding against DB, records attendance, and sends Telegram alert.
        """
        now = datetime.now(timezone.utc)

        # 1. Liveness verification
        if settings.ANTI_SPOOFING_ENABLED and not is_live:
            logger.warning(f"Check-in rejected due to spoofing detection. Score: {liveness_score:.3f}")
            return AttendanceResult(
                success=False,
                status="FAILED",
                message="⛔ Phát hiện ảnh giả (spoofing). Vui lòng đến trực tiếp."
            )

        # 2. Find best match in database cache
        emb_arr = np.array(embedding, dtype=np.float32)
        match = self.matching_service.find_best_match(emb_arr)
        if not match:
            raise NoMatchFoundError()

        # 3. Save snapshot from base64 (if provided)
        snapshot_path = None
        if snapshot_base64:
            try:
                snapshot_bytes = base64.b64decode(snapshot_base64)
                snapshot_path = await self._save_snapshot_file(match.employee_id, now, snapshot_bytes)
            except Exception as e:
                logger.error(f"Failed to save base64 snapshot: {e}")

        # 4. Complete check-in registration
        return await self._register_checkin(
            session=session,
            match=match,
            now=now,
            confidence=match.similarity,
            check_method="FACE",
            snapshot_path=snapshot_path
        )

    async def process_checkin_from_password(
        self,
        session: AsyncSession,
        employee_code: str,
        password: str
    ) -> AttendanceResult:
        """
        Processes check-in using employee code and password.
        Used as a fallback when face recognition is unavailable.
        """
        now = datetime.now(timezone.utc)

        # 1. Look up employee
        result = await session.execute(
            select(Employee).where(
                Employee.employee_code == employee_code,
                Employee.is_active == True
            )
        )
        employee = result.scalar_one_or_none()
        if not employee:
            return AttendanceResult(
                success=False,
                status="FAILED",
                message="❌ Mã nhân viên không tồn tại hoặc đã bị vô hiệu hóa."
            )

        # 2. Verify password exists
        if not employee.password_hash:
            return AttendanceResult(
                success=False,
                status="FAILED",
                message="❌ Nhân viên chưa được thiết lập mật khẩu. Liên hệ Admin."
            )

        # 3. Check password
        if not bcrypt.checkpw(password.encode("utf-8"), employee.password_hash.encode("utf-8")):
            return AttendanceResult(
                success=False,
                status="FAILED",
                message="❌ Mật khẩu không đúng."
            )

        # 4. Wrap employee into MatchResult for _register_checkin
        match = MatchResult(
            employee_id=employee.id,
            employee_name=employee.name,
            telegram_chat_id=employee.telegram_chat_id,
            similarity=1.0  # Passwords are 100% accurate matches
        )

        # 5. Complete check-in registration
        return await self._register_checkin(
            session=session,
            match=match,
            now=now,
            confidence=None,
            check_method="PASSWORD",
            snapshot_path=None
        )

    async def check_duplicate(
        self,
        session: AsyncSession,
        employee_id: int,
        current_time: datetime
    ) -> bool:
        """Checks if employee has checked in within settings.DUPLICATE_CHECK_MINUTES."""
        window_start = current_time - timedelta(minutes=settings.DUPLICATE_CHECK_MINUTES)
        
        stmt = (
            select(func.count(AttendanceLog.id))
            .where(
                AttendanceLog.employee_id == employee_id,
                AttendanceLog.check_in_time >= window_start,
                AttendanceLog.check_in_time <= current_time
            )
        )
        result = await session.execute(stmt)
        count = result.scalar_one()
        
        return count > 0

    async def _register_checkin(
        self,
        session: AsyncSession,
        match: MatchResult,
        now: datetime,
        confidence: Optional[float],
        check_method: str = "FACE",
        snapshot_path: Optional[str] = None
    ) -> AttendanceResult:
        """
        Saves the attendance log to database, checks duplicates, calculates work statuses,
        and fires off Telegram notifications.
        """
        # Duplicate verification
        is_duplicate = await self.check_duplicate(session, match.employee_id, now)
        if is_duplicate:
            msg = f"ℹ️ {match.employee_name} đã chấm công trong {settings.DUPLICATE_CHECK_MINUTES} phút gần đây."
            return AttendanceResult(
                success=True,
                status="DUPLICATE",
                message=msg,
                employee_id=match.employee_id,
                employee_name=match.employee_name,
                check_in_time=now,
                similarity=confidence
            )

        # Retrieve policy rules & evaluate check-in status
        policy = await get_or_create_policy(session)
        status, late_minutes = determine_status(now, policy)
        period_type = determine_period_type(now, policy)

        # Confidence logic override
        if confidence is not None:
            LOW_CONFIDENCE_THRESHOLD = settings.SIMILARITY_THRESHOLD + 0.10
            if confidence < LOW_CONFIDENCE_THRESHOLD:
                status = "LOW_CONFIDENCE"

        # Record check-in log
        log = AttendanceLog(
            employee_id=match.employee_id,
            check_in_time=now,
            check_method=check_method,
            period_type=period_type,
            status=status,
            confidence=confidence,
            snapshot_path=snapshot_path
        )
        session.add(log)
        await session.flush()

        logger.info(f"Check-in registered: {match.employee_name} (id={match.employee_id}) -> status={status}")

        # Send Telegram Bot notification
        try:
            local_now = to_local(now, policy)
            month_str = local_now.strftime("%Y-%m")
            month_stats = await calculate_employee_month_stats(
                session=session,
                employee_id=match.employee_id,
                month_str=month_str,
                policy=policy
            )
            
            if status == "SUCCESS":
                await telegram_notifier.send_checkin_success(
                    employee_name=match.employee_name,
                    check_in_time=local_now,
                    confidence=confidence or 1.0,
                    worked_days=month_stats.worked_days,
                    worked_hours=month_stats.worked_hours,
                    employee_chat_id=match.telegram_chat_id
                )
            elif status == "LATE":
                await telegram_notifier.send_late_notification(
                    employee_name=match.employee_name,
                    check_in_time=local_now,
                    late_minutes=late_minutes,
                    confidence=confidence or 1.0,
                    worked_days=month_stats.worked_days,
                    worked_hours=month_stats.worked_hours,
                    employee_chat_id=match.telegram_chat_id
                )
            elif status == "LOW_CONFIDENCE":
                await telegram_notifier.send_low_confidence_alert(
                    check_in_time=local_now,
                    confidence=confidence
                )
        except Exception as te:
            logger.error(f"Telegram notification dispatch failed: {te}")

        # Setup messages based on status
        status_messages = {
            "SUCCESS": f"✅ {match.employee_name} đã chấm công thành công.",
            "LATE": f"⚠️ {match.employee_name} đến trễ {late_minutes} phút.",
            "LOW_CONFIDENCE": f"🔍 Nhận diện kém. Cần xác minh: {match.employee_name}.",
        }

        # For password checkin, customize message
        if check_method == "PASSWORD":
            status_messages = {
                "SUCCESS": f"✅ {match.employee_name} đã chấm công thành công (mật khẩu).",
                "LATE": f"⚠️ {match.employee_name} đến trễ {late_minutes} phút (mật khẩu).",
            }

        return AttendanceResult(
            success=True,
            status=status,
            message=status_messages.get(status, "Thành công."),
            employee_id=match.employee_id,
            employee_name=match.employee_name,
            check_in_time=now,
            similarity=confidence
        )

    async def _save_snapshot_file(
        self,
        employee_id: int,
        timestamp: datetime,
        image_bytes: bytes
    ) -> str:
        """Saves image bytes to snapshot directory and returns the absolute file path."""
        snapshot_dir = settings.SNAPSHOT_DIR
        os.makedirs(snapshot_dir, exist_ok=True)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{employee_id}_{uuid.uuid4().hex[:8]}.jpg"
        snapshot_path = os.path.join(snapshot_dir, filename)
        with open(snapshot_path, "wb") as f:
            f.write(image_bytes)
        return snapshot_path
