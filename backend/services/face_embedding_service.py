"""
IDVision — Face Embedding Service
Handles 512-dimensional embedding generation and averaging from multiple pictures.
"""

import logging
import numpy as np
from services.providers.face_recognition_provider import FaceRecognitionProvider
from services.providers.domain_models import DetectedFace

logger = logging.getLogger(__name__)

class FaceEmbeddingService:
    """
    Service responsible for extracting feature embeddings from face images,
    and generating averaged embeddings for robust enrollment profiles.
    """

    def __init__(self, provider: FaceRecognitionProvider):
        self.provider = provider

    def generate_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        """Extract a single 512-dimensional normalized embedding."""
        emb = self.provider.extract_embedding(image, face)
        
        # Ensure it is normalized (InsightFace normed_embedding usually is, but let's be safe)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
            
        return emb.astype(np.float32)

    def generate_average_embedding(self, embeddings: list[np.ndarray]) -> np.ndarray:
        """
        Computes the average embedding vector from multiple face embeddings
        and normalizes it to a unit vector.
        """
        if not embeddings:
            raise ValueError("embeddings list cannot be empty.")
            
        # Compute mean along the 0-th axis
        avg_emb = np.mean(embeddings, axis=0).astype(np.float32)
        
        # L2 normalize the average vector
        norm = np.linalg.norm(avg_emb)
        if norm > 0:
            avg_emb = avg_emb / norm
            
        return avg_emb
