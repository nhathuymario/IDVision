"""
IDVision — Face Recognition Provider Interface
Abstract class defining the contract for face detection, embedding extraction, and comparison.
"""

from abc import ABC, abstractmethod
import numpy as np
from services.providers.domain_models import DetectedFace

class FaceRecognitionProvider(ABC):
    """
    Interface for face recognition technology.
    Ensures Dependency Inversion Principle (DIP) and Open/Closed Principle (OCP).
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize and load the AI models."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True if models are loaded and ready to process images."""
        pass

    @abstractmethod
    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        """
        Detect all faces in a BGR image.
        
        Args:
            image: BGR image as a numpy array.
            
        Returns:
            A list of DetectedFace objects.
        """
        pass

    @abstractmethod
    def extract_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        """
        Extract the 512-dimensional face embedding for a detected face.
        
        Args:
            image: BGR image.
            face: The DetectedFace object.
            
        Returns:
            Normalized 512-dim face embedding as a numpy float32 array.
        """
        pass

    @abstractmethod
    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Compute similarity score between two face embeddings.
        Typically cosine similarity in range [-1.0, 1.0].
        """
        pass
