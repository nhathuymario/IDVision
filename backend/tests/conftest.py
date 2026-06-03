"""
IDVision — Pytest Configuration & Fixtures
Provides shared mock objects and database session mocks for testing face recognition services.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock
from typing import Generator

from services.providers.face_recognition_provider import FaceRecognitionProvider
from services.providers.domain_models import DetectedFace
from services.face_detection_service import FaceDetectionService
from services.face_embedding_service import FaceEmbeddingService
from services.face_matching_service import FaceMatchingService
from services.user_face_profile_service import UserFaceProfileService
from services.attendance_service import AttendanceService

class MockFaceRecognitionProvider(FaceRecognitionProvider):
    """Mock implementation of FaceRecognitionProvider to avoid loading 500MB neural nets in tests."""
    
    def __init__(self):
        self._ready = True
        self.faces = []

    def initialize(self) -> None:
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        return self.faces

    def extract_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        if face.embedding is not None:
            return face.embedding
        # Return a mock 512-dim embedding
        return np.ones(512, dtype=np.float32) * 0.1

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        # Standard cosine similarity mock or actual math
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 > 0:
            emb1 = emb1 / norm1
        if norm2 > 0:
            emb2 = emb2 / norm2
        return float(np.dot(emb1, emb2))


@pytest.fixture
def mock_provider() -> MockFaceRecognitionProvider:
    """Fixture providing a mock FaceRecognitionProvider."""
    return MockFaceRecognitionProvider()


@pytest.fixture
def detection_service(mock_provider) -> FaceDetectionService:
    """Fixture providing FaceDetectionService with a mock provider."""
    return FaceDetectionService(provider=mock_provider)


@pytest.fixture
def embedding_service(mock_provider) -> FaceEmbeddingService:
    """Fixture providing FaceEmbeddingService with a mock provider."""
    return FaceEmbeddingService(provider=mock_provider)


@pytest.fixture
def matching_service() -> FaceMatchingService:
    """Fixture providing FaceMatchingService."""
    return FaceMatchingService(threshold=0.55)


@pytest.fixture
def user_face_profile_service(detection_service, embedding_service) -> UserFaceProfileService:
    """Fixture providing UserFaceProfileService."""
    return UserFaceProfileService(
        detection_service=detection_service,
        embedding_service=embedding_service
    )


@pytest.fixture
def attendance_service(detection_service, embedding_service, matching_service) -> AttendanceService:
    """Fixture providing AttendanceService."""
    return AttendanceService(
        detection_service=detection_service,
        embedding_service=embedding_service,
        matching_service=matching_service
    )


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Fixture providing a mocked SQLAlchemy AsyncSession."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session
