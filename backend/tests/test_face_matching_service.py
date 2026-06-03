"""
IDVision — Face Matching Service Tests
Tests matching logic against the cached employee face vectors.
"""

import pytest
import numpy as np
from services.face_cache import face_cache

@pytest.fixture(autouse=True)
def clean_face_cache():
    """Resets face_cache between tests."""
    face_cache._encodings = None
    face_cache._employee_ids = []
    face_cache._employee_names = []
    face_cache._telegram_chat_ids = []
    face_cache._count = 0
    yield


def test_find_best_match_empty(matching_service):
    """Should return None if face cache is empty."""
    query = np.ones(512, dtype=np.float32)
    res = matching_service.find_best_match(query)
    assert res is None


def test_find_best_match_success(matching_service):
    """Should return MatchResult when a face matches above the threshold."""
    # Register employee NV1 with a specific encoding
    emb1 = np.zeros(512, dtype=np.float32)
    emb1[0] = 1.0  # Vector pointing along axis 0
    face_cache.add_or_update(1, "NV1", "123", emb1)

    # Register employee NV2 with a different encoding
    emb2 = np.zeros(512, dtype=np.float32)
    emb2[1] = 1.0  # Vector pointing along axis 1
    face_cache.add_or_update(2, "NV2", "456", emb2)

    # Query matching emb1 exactly
    query = np.zeros(512, dtype=np.float32)
    query[0] = 1.0
    
    res = matching_service.find_best_match(query)
    assert res is not None
    assert res.employee_id == 1
    assert res.employee_name == "NV1"
    assert res.telegram_chat_id == "123"
    assert res.similarity == 1.0


def test_find_best_match_below_threshold(matching_service):
    """Should return None when highest match score is below settings threshold."""
    # Register employee NV1
    emb1 = np.zeros(512, dtype=np.float32)
    emb1[0] = 1.0
    face_cache.add_or_update(1, "NV1", "123", emb1)

    # Query with a vector orthogonal (similarity 0.0) or low similarity
    query = np.zeros(512, dtype=np.float32)
    query[1] = 1.0  # orthogonal to axis 0
    
    # threshold is 0.55, 0.0 similarity is below it
    res = matching_service.find_best_match(query)
    assert res is None
