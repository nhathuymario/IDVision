"""
IDVision — Face Profile Service Tests
Tests employee face enrollment (images and vectors), validation issues, and deleting face profiles.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import numpy as np


from exceptions import FaceQualityError, EmbeddingFormatError
from services.providers.domain_models import DetectedFace, FaceQualityResult

@pytest.mark.asyncio
async def test_enroll_from_images_employee_not_found(user_face_profile_service, mock_db_session):
    """Should raise ValueError when employee ID is not found or is inactive."""
    # Stub query to return None
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_res
    
    with pytest.raises(ValueError, match="Không tìm thấy nhân viên"):
        await user_face_profile_service.enroll_from_images(
            session=mock_db_session,
            employee_id=99,
            images_bytes=[b"image1"]
        )


@pytest.mark.asyncio
async def test_enroll_from_images_all_bad_quality(user_face_profile_service, mock_db_session):
    """Should raise FaceQualityError when all provided photos fail quality check."""
    employee = MagicMock()
    employee.name = "NV1"
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = employee
    mock_db_session.execute.return_value = mock_execute_res
    
    # Stub face detection to return face but bad quality
    face = DetectedFace(bbox=[0, 0, 50, 50], landmarks=np.array([]), det_score=0.9)
    user_face_profile_service.detection_service.detect_single_face = MagicMock(return_value=face)
    
    quality = FaceQualityResult(is_valid=False, issues=["Ảnh mờ"], size=(50, 50))
    user_face_profile_service.detection_service.validate_face_quality = MagicMock(return_value=quality)
    
    with pytest.raises(FaceQualityError, match="đạt yêu cầu chất lượng"):
        # We pass some dummy image bytes (e.g. 1x1 black pixel) so cv2.imdecode doesn't fail
        # JPEG 1x1 pixel image bytes
        jpeg_1x1 = b'\xff\xd8\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
        await user_face_profile_service.enroll_from_images(
            session=mock_db_session,
            employee_id=1,
            images_bytes=[jpeg_1x1]
        )


@pytest.mark.asyncio
async def test_enroll_from_images_success(user_face_profile_service, mock_db_session):
    """Should update employee's face vector and database when at least one image is good."""
    employee = MagicMock()
    employee.name = "NV1"
    employee.telegram_chat_id = "123"
    employee.face_encoding = None
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = employee
    mock_db_session.execute.return_value = mock_execute_res
    
    # Stub detect & quality
    face = DetectedFace(bbox=[0, 0, 100, 100], landmarks=np.array([]), det_score=0.95)
    user_face_profile_service.detection_service.detect_single_face = MagicMock(return_value=face)
    
    quality = FaceQualityResult(is_valid=True, issues=[], size=(100, 100))
    user_face_profile_service.detection_service.validate_face_quality = MagicMock(return_value=quality)
    
    # Mock embedding generator to return a specific mock embedding
    mock_emb = np.ones(512, dtype=np.float32) * 0.1
    user_face_profile_service.embedding_service.generate_embedding = MagicMock(return_value=mock_emb)
    
    # Update cache mock
    with patch("services.user_face_profile_service.face_cache") as mock_cache:
        jpeg_1x1 = b'\xff\xd8\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
        res = await user_face_profile_service.enroll_from_images(
            session=mock_db_session,
            employee_id=1,
            images_bytes=[jpeg_1x1]
        )
        
        assert res == employee
        assert employee.face_encoding is not None
        assert len(employee.face_encoding) == 512
        assert employee.enrolled_at is not None
        mock_cache.add_or_update.assert_called_once()


@pytest.mark.asyncio
async def test_enroll_from_embedding_invalid_shape(user_face_profile_service, mock_db_session):
    """Should raise EmbeddingFormatError when input embedding dimension is not 512."""
    with pytest.raises(EmbeddingFormatError):
        await user_face_profile_service.enroll_from_embedding(
            session=mock_db_session,
            employee_id=1,
            embedding=[0.1] * 128  # wrong size
        )


@pytest.mark.asyncio
async def test_enroll_from_embedding_success(user_face_profile_service, mock_db_session):
    """Should successfully enroll employee with a pre-computed vector."""
    employee = MagicMock()
    employee.name = "NV2"
    employee.telegram_chat_id = "456"
    employee.face_encoding = None
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = employee
    mock_db_session.execute.return_value = mock_execute_res
    
    # 512-dim mock vector
    dummy_emb = [0.1] * 512
    
    with patch("services.user_face_profile_service.face_cache") as mock_cache:
        res = await user_face_profile_service.enroll_from_embedding(
            session=mock_db_session,
            employee_id=2,
            embedding=dummy_emb
        )
        
        assert res == employee
        assert employee.face_encoding is not None
        assert len(employee.face_encoding) == 512
        assert employee.enrolled_at is not None
        mock_cache.add_or_update.assert_called_once()


@pytest.mark.asyncio
async def test_delete_enrollment_success(user_face_profile_service, mock_db_session):
    """Should clear database fields and remove face from cache on deletion."""
    employee = MagicMock()
    employee.name = "NV3"
    employee.face_encoding = [0.1] * 512
    employee.enrolled_at = datetime.now()
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = employee
    mock_db_session.execute.return_value = mock_execute_res
    
    with patch("services.user_face_profile_service.face_cache") as mock_cache:
        res = await user_face_profile_service.delete_enrollment(
            session=mock_db_session,
            employee_id=3
        )
        
        assert res == employee
        assert employee.face_encoding is None
        assert employee.enrolled_at is None
        mock_cache.remove.assert_called_once_with(3)
