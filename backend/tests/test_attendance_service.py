"""
IDVision — Attendance Service Tests
Tests face check-in validation, anti-spoofing rejection, duplicate check-ins, and database log creation.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
import numpy as np
import bcrypt

from services.face_cache import MatchResult
from exceptions import NoMatchFoundError, FaceQualityError
from models import AttendancePolicy, AttendanceLog
from services.providers.domain_models import DetectedFace, FaceQualityResult


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mocks external services (Telegram, Payroll rules) to keep tests isolated."""
    with patch("services.attendance_service.get_or_create_policy") as mock_policy, \
         patch("services.attendance_service.determine_status") as mock_status, \
         patch("services.attendance_service.determine_period_type") as mock_period, \
         patch("services.attendance_service.calculate_employee_month_stats") as mock_stats, \
         patch("services.attendance_service.telegram_notifier", new_callable=AsyncMock) as mock_tg:
         
        # Default mock setups
        policy = AttendancePolicy(
            work_start_time=datetime.strptime("08:00", "%H:%M").time(),
            break_start_time=datetime.strptime("12:00", "%H:%M").time(),
            break_end_time=datetime.strptime("13:00", "%H:%M").time(),
            work_end_time=datetime.strptime("17:30", "%H:%M").time(),
            late_grace_minutes=0,
            hourly_wage=100.0,
            timezone="Asia/Ho_Chi_Minh"
        )
        mock_policy.return_value = policy
        mock_status.return_value = ("SUCCESS", 0)
        mock_period.return_value = "MORNING_START"
        
        stats = MagicMock()
        stats.worked_days = 5
        stats.worked_hours = 40.0
        mock_stats.return_value = stats
        
        yield {
            "policy": mock_policy,
            "status": mock_status,
            "period": mock_period,
            "stats": mock_stats,
            "telegram": mock_tg
        }


@pytest.mark.asyncio
async def test_checkin_liveness_fail(attendance_service, mock_db_session):
    """Should return failure and not record attendance when liveness check fails."""
    # Settings has liveness enabled
    res = await attendance_service.process_checkin_from_embedding(
        session=mock_db_session,
        embedding=[0.1] * 512,
        is_live=False,  # Spoof detected
        liveness_score=0.2
    )
    
    assert not res.success
    assert res.status == "FAILED"
    assert "spoofing" in res.message
    # Verify no log was added to DB session
    mock_db_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_checkin_no_match(attendance_service, mock_db_session):
    """Should raise NoMatchFoundError when query face is not recognized (no match in cache)."""
    # Force matching service to return None
    attendance_service.matching_service.find_best_match = MagicMock(return_value=None)
    
    with pytest.raises(NoMatchFoundError):
        await attendance_service.process_checkin_from_embedding(
            session=mock_db_session,
            embedding=[0.1] * 512,
            is_live=True
        )


@pytest.mark.asyncio
async def test_checkin_duplicate(attendance_service, mock_db_session):
    """Should return status DUPLICATE and skip DB insertion when checking in twice recently."""
    match = MatchResult(employee_id=1, employee_name="NV1", telegram_chat_id="123", similarity=0.9)
    attendance_service.matching_service.find_best_match = MagicMock(return_value=match)
    
    # Stub duplicate check to return True
    attendance_service.check_duplicate = AsyncMock(return_value=True)
    
    res = await attendance_service.process_checkin_from_embedding(
        session=mock_db_session,
        embedding=[0.1] * 512,
        is_live=True
    )
    
    assert res.success
    assert res.status == "DUPLICATE"
    assert "gần đây" in res.message
    # Should not save another log
    mock_db_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_checkin_success(attendance_service, mock_db_session, mock_dependencies):
    """Should save attendance log, return SUCCESS, and notify Telegram on a valid check-in."""
    match = MatchResult(employee_id=1, employee_name="NV1", telegram_chat_id="123", similarity=0.9)
    attendance_service.matching_service.find_best_match = MagicMock(return_value=match)
    attendance_service.check_duplicate = AsyncMock(return_value=False)
    
    res = await attendance_service.process_checkin_from_embedding(
        session=mock_db_session,
        embedding=[0.1] * 512,
        is_live=True,
        snapshot_base64="ZHVtbXliYXNlNjQ="  # 'dummybase64'
    )
    
    assert res.success
    assert res.status == "SUCCESS"
    assert res.employee_name == "NV1"
    
    # Verify DB save
    mock_db_session.add.assert_called_once()
    saved_log = mock_db_session.add.call_args[0][0]
    assert isinstance(saved_log, AttendanceLog)
    assert saved_log.employee_id == 1
    assert saved_log.status == "SUCCESS"
    assert saved_log.confidence == 0.9
    
    # Verify Telegram notification was triggered
    mock_dependencies["telegram"].send_checkin_success.assert_called_once()


@pytest.mark.asyncio
async def test_checkin_from_image_quality_fail(attendance_service, mock_db_session):
    """Should fail when the face image quality is bad (e.g., too blurry)."""
    face = DetectedFace(bbox=[10, 10, 100, 100], landmarks=np.array([]), det_score=0.9)
    # Mock face detection service to return face and failed quality
    attendance_service.detection_service.detect_single_face = MagicMock(return_value=face)
    
    quality = FaceQualityResult(is_valid=False, issues=["Ảnh quá mờ"], size=(90, 90))
    attendance_service.detection_service.validate_face_quality = MagicMock(return_value=quality)
    
    dummy_img = np.zeros((150, 150, 3), dtype=np.uint8)
    
    with pytest.raises(FaceQualityError):
        await attendance_service.process_checkin_from_image(
            session=mock_db_session,
            image=dummy_img
        )


@pytest.mark.asyncio
async def test_password_checkin_success(attendance_service, mock_db_session):
    """Should check in successfully using employee code and password."""
    # Setup mock employee in database query
    employee = MagicMock()
    employee.id = 5
    employee.name = "NV5"
    employee.employee_code = "NV005"
    # bcrypt hash for 'pass123'
    employee.password_hash = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode("utf-8")
    employee.telegram_chat_id = "555"

    
    # Mock select employee query
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = employee
    mock_db_session.execute.return_value = mock_execute_res
    
    attendance_service.check_duplicate = AsyncMock(return_value=False)
    
    res = await attendance_service.process_checkin_from_password(
        session=mock_db_session,
        employee_code="NV005",
        password="pass123"
    )
    
    assert res.success
    assert res.employee_name == "NV5"
    assert res.status == "SUCCESS"
    
    # Verify log saved
    mock_db_session.add.assert_called_once()
    saved_log = mock_db_session.add.call_args[0][0]
    assert saved_log.check_method == "PASSWORD"
    assert saved_log.employee_id == 5
