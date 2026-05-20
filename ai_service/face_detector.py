"""
IDVision — Face Detector Module
InsightFace wrapper for face detection and embedding extraction.
Uses the buffalo_l model pack (SCRFD + ArcFace, 512-dim embeddings).
"""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FaceResult:
    """Result of face detection and embedding extraction."""
    bbox: list[int]                  # [x1, y1, x2, y2]
    embedding: np.ndarray            # 512-dim normalized vector
    landmarks: np.ndarray            # 5-point facial landmarks
    det_score: float                 # Detection confidence (0-1)
    face_image: Optional[np.ndarray] = None  # Cropped face for liveness check


class FaceDetector:
    """
    Face detection and feature extraction using InsightFace buffalo_l.
    
    buffalo_l includes:
    - SCRFD: High-performance face detector
    - ArcFace: 512-dim face embedding extraction
    - 2D/3D landmark detection
    """

    def __init__(self, ctx_id: int = -1, det_size: tuple = (640, 640)):
        """
        Initialize the face detector.
        
        Args:
            ctx_id: GPU context ID. -1 for CPU, 0 for first GPU.
            det_size: Detection input size. Larger = more accurate but slower.
        """
        self._app = None
        self._ctx_id = ctx_id
        self._det_size = det_size

    def initialize(self) -> None:
        """
        Load the InsightFace model.
        Models are auto-downloaded on first use (~300MB).
        """
        try:
            from insightface.app import FaceAnalysis

            logger.info("Loading InsightFace buffalo_l model...")
            self._app = FaceAnalysis(name="buffalo_l")
            self._app.prepare(ctx_id=self._ctx_id, det_size=self._det_size)
            logger.info(
                f"InsightFace initialized (ctx_id={self._ctx_id}, "
                f"det_size={self._det_size})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            raise

    def detect_faces(self, frame: np.ndarray) -> list[FaceResult]:
        """
        Detect all faces in a frame and extract embeddings.
        
        Args:
            frame: BGR image (OpenCV format).
            
        Returns:
            List of FaceResult with embeddings and bounding boxes.
        """
        if self._app is None:
            raise RuntimeError("FaceDetector not initialized. Call initialize() first.")

        faces = self._app.get(frame)
        results = []

        for face in faces:
            bbox = face.bbox.astype(int).tolist()

            # Crop face for liveness detection
            x1, y1, x2, y2 = bbox
            # Add padding around the face
            h, w = frame.shape[:2]
            pad = 20
            x1_pad = max(0, x1 - pad)
            y1_pad = max(0, y1 - pad)
            x2_pad = min(w, x2 + pad)
            y2_pad = min(h, y2 + pad)
            face_crop = frame[y1_pad:y2_pad, x1_pad:x2_pad].copy()

            results.append(FaceResult(
                bbox=bbox,
                embedding=face.normed_embedding,  # Already L2-normalized
                landmarks=face.landmark_2d_106 if hasattr(face, 'landmark_2d_106') 
                          else face.kps,
                det_score=float(face.det_score),
                face_image=face_crop,
            ))

        return results

    def extract_single(self, frame: np.ndarray) -> Optional[FaceResult]:
        """
        Detect and extract embedding for the most prominent face.
        
        Args:
            frame: BGR image.
            
        Returns:
            FaceResult for the best face, or None if no face detected.
        """
        faces = self.detect_faces(frame)
        if not faces:
            return None

        # Return face with highest detection score
        return max(faces, key=lambda f: f.det_score)

    @staticmethod
    def preprocess_frame(frame: np.ndarray, max_size: int = 960) -> np.ndarray:
        """
        Preprocess frame for better detection.
        Resize if too large, apply CLAHE for low-light conditions.
        
        Args:
            frame: Input BGR image.
            max_size: Maximum dimension (resize if larger).
            
        Returns:
            Preprocessed frame.
        """
        h, w = frame.shape[:2]

        # Resize if too large (improves speed without losing accuracy)
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            frame = cv2.resize(frame, None, fx=scale, fy=scale)

        # Apply CLAHE for contrast enhancement (helps in low-light)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return frame
