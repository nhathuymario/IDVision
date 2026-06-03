"""
IDVision — Face Detection Service Tests
Tests face detection count logic and quality check heuristics (blur, brightness, size).
"""

import pytest
import numpy as np
from services.providers.domain_models import DetectedFace
from exceptions import NoFaceDetectedError, MultipleFacesError

def test_detect_single_face_none(detection_service, mock_provider):
    """Should raise NoFaceDetectedError when no faces are detected in image."""
    mock_provider.faces = []
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    
    with pytest.raises(NoFaceDetectedError):
        detection_service.detect_single_face(dummy_img)


def test_detect_single_face_multiple(detection_service, mock_provider):
    """Should raise MultipleFacesError when more than one face is detected."""
    mock_provider.faces = [
        DetectedFace(bbox=[0, 0, 50, 50], landmarks=np.array([]), det_score=0.9),
        DetectedFace(bbox=[60, 60, 110, 110], landmarks=np.array([]), det_score=0.85)
    ]
    dummy_img = np.zeros((200, 200, 3), dtype=np.uint8)
    
    with pytest.raises(MultipleFacesError):
        detection_service.detect_single_face(dummy_img)


def test_detect_single_face_success(detection_service, mock_provider):
    """Should return the DetectedFace when exactly one face is detected."""
    face = DetectedFace(bbox=[10, 10, 90, 90], landmarks=np.array([]), det_score=0.95)
    mock_provider.faces = [face]
    dummy_img = np.zeros((150, 150, 3), dtype=np.uint8)
    
    res = detection_service.detect_single_face(dummy_img)
    assert res == face


def test_validate_face_quality_too_small(detection_service):
    """Should fail quality check when face bounding box is smaller than min_face_size."""
    # Size is 40x40px, default min is 80
    face = DetectedFace(bbox=[10, 10, 50, 50], landmarks=np.array([]), det_score=0.9)
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    
    res = detection_service.validate_face_quality(face, dummy_img)
    assert not res.is_valid
    assert any("quá nhỏ" in issue for issue in res.issues)


def test_validate_face_quality_low_score(detection_service):
    """Should fail quality check when detection score is below threshold."""
    # score is 0.4, default min is 0.5
    face = DetectedFace(bbox=[10, 10, 100, 100], landmarks=np.array([]), det_score=0.4)
    dummy_img = np.zeros((150, 150, 3), dtype=np.uint8)
    
    res = detection_service.validate_face_quality(face, dummy_img)
    assert not res.is_valid
    assert any("thấp" in issue for issue in res.issues)


def test_validate_face_quality_dark_image(detection_service):
    """Should fail quality check when face region is too dark."""
    # Bbox 0 to 100
    face = DetectedFace(bbox=[0, 0, 100, 100], landmarks=np.array([]), det_score=0.9)
    # Brightness will be 0 (too dark, min is 40)
    dummy_dark_img = np.zeros((100, 100, 3), dtype=np.uint8)
    
    res = detection_service.validate_face_quality(face, dummy_dark_img)
    assert not res.is_valid
    assert any("quá tối" in issue for issue in res.issues)
    assert res.brightness == 0.0


def test_validate_face_quality_success(detection_service):
    """Should pass validation when face meets all size, brightness, blur, and det_score conditions."""
    face = DetectedFace(bbox=[0, 0, 100, 100], landmarks=np.array([]), det_score=0.95)
    # Gray image with brightness 128 (within 40-230) and some variance/noise for blur check
    # Let's create an image with random noise around 128
    np.random.seed(42)
    dummy_img = np.random.normal(128, 20, (100, 100, 3)).astype(np.uint8)
    
    res = detection_service.validate_face_quality(face, dummy_img)
    assert res.is_valid
    assert len(res.issues) == 0
    assert res.brightness > 40.0
    assert res.blur_score > 50.0
