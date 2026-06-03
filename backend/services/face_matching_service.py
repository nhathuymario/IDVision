"""
IDVision — Face Matching Service
Coordinates face matching against cached employee encodings using threshold-based verification.
"""

import logging
from typing import Optional
import numpy as np
from services.face_cache import face_cache, MatchResult
from config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

class FaceMatchingService:
    """
    Service responsible for matching face embeddings against the in-memory cache
    and applying similarity thresholds.
    """

    def __init__(self, threshold: float = None):
        self.threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD

    def find_best_match(self, embedding: np.ndarray) -> Optional[MatchResult]:
        """
        Matches a face embedding against all enrolled employees.
        
        Args:
            embedding: Normalized 512-dim embedding as a numpy array.
            
        Returns:
            MatchResult if similarity exceeds threshold, else None.
        """
        # Call the in-memory cache matcher
        match = face_cache.match(embedding, threshold=self.threshold)
        
        if match:
            logger.info(f"Face matched: {match.employee_name} (id={match.employee_id}) with similarity={match.similarity:.4f}")
        else:
            logger.info("Face match not found (below threshold or empty cache).")
            
        return match
