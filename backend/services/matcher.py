"""
IDVision — Vector Matching Service
Handles face embedding comparison logic with threshold-based decisions.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import AttendanceLog
from services.face_cache import face_cache, MatchResult

logger = logging.getLogger(__name__)
settings = get_settings()


class MatcherService:
    """Service for face matching and attendance status determination."""

    @staticmethod
    def match_face(embedding: list[float]) -> Optional[MatchResult]:
        """
        Match a face embedding against the cache.
        
        Args:
            embedding: 512-dim face embedding from ArcFace.
            
        Returns:
            MatchResult if match found, None otherwise.
        """
        return face_cache.match(
            query_embedding=np.array(embedding, dtype=np.float32),
            threshold=settings.SIMILARITY_THRESHOLD,
        )

    @staticmethod
    def determine_status(check_in_time: datetime) -> str:
        """
        Determine attendance status based on check-in time.
        
        Returns:
            'SUCCESS' if on-time, 'LATE' if after threshold.
        """
        # Build the threshold time for today in the same timezone
        threshold_time = check_in_time.replace(
            hour=settings.LATE_THRESHOLD_HOUR,
            minute=settings.LATE_THRESHOLD_MINUTE,
            second=0,
            microsecond=0,
        )

        if check_in_time <= threshold_time:
            return "SUCCESS"
        return "LATE"

    @staticmethod
    def calculate_late_minutes(check_in_time: datetime) -> int:
        """Calculate how many minutes late the employee is."""
        threshold_time = check_in_time.replace(
            hour=settings.LATE_THRESHOLD_HOUR,
            minute=settings.LATE_THRESHOLD_MINUTE,
            second=0,
            microsecond=0,
        )
        if check_in_time <= threshold_time:
            return 0
        delta = check_in_time - threshold_time
        return int(delta.total_seconds() / 60)

    @staticmethod
    async def check_duplicate(
        session: AsyncSession,
        employee_id: int,
        current_time: datetime,
    ) -> bool:
        """
        Check if employee has already checked in within the duplicate window.
        
        Returns:
            True if duplicate (already checked in recently), False otherwise.
        """
        window_start = current_time - timedelta(minutes=settings.DUPLICATE_CHECK_MINUTES)

        stmt = (
            select(func.count(AttendanceLog.id))
            .where(AttendanceLog.employee_id == employee_id)
            .where(AttendanceLog.check_in_time >= window_start)
            .where(AttendanceLog.check_in_time <= current_time)
        )
        result = await session.execute(stmt)
        count = result.scalar_one()

        if count > 0:
            logger.info(
                f"Duplicate check-in detected for employee_id={employee_id} "
                f"within {settings.DUPLICATE_CHECK_MINUTES} minutes."
            )
            return True
        return False


# Global singleton
matcher_service = MatcherService()
