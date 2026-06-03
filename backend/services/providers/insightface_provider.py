"""
IDVision — InsightFace Provider Implementation
Wraps the InsightFace library to perform face analysis and embedding extraction.
"""

import logging
import numpy as np
from services.providers.face_recognition_provider import FaceRecognitionProvider
from services.providers.domain_models import DetectedFace
from exceptions import ModelNotLoadedError

logger = logging.getLogger(__name__)

class InsightFaceProvider(FaceRecognitionProvider):
    """
    Concrete implementation of FaceRecognitionProvider using InsightFace.
    Implements a thread-safe singleton pattern or is managed as a lifecycle component.
    """

    def __init__(self, model_name: str = "buffalo_l", ctx_id: int = -1, det_size: tuple[int, int] = (640, 640)):
        self.model_name = model_name
        self.ctx_id = ctx_id
        self.det_size = det_size
        self._app = None

    def initialize(self) -> None:
        """Load and initialize the InsightFace model."""
        if self._app is not None:
            return

        try:
            from insightface.app import FaceAnalysis
            logger.info(f"Initializing InsightFace FaceAnalysis with model pack '{self.model_name}' on ctx_id={self.ctx_id}...")
            app = FaceAnalysis(name=self.model_name)
            app.prepare(ctx_id=self.ctx_id, det_size=self.det_size)
            self._app = app
            logger.info("InsightFace FaceAnalysis initialized successfully.")
        except ImportError as e:
            logger.error("Failed to import insightface. Ensure it is installed: pip install insightface onnxruntime")
            raise ModelNotLoadedError("insightface library is not installed on the backend.") from e
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace model: {e}")
            raise ModelNotLoadedError(f"InsightFace model load failed: {str(e)}") from e

    def is_ready(self) -> bool:
        """Checks if the provider is initialized."""
        return self._app is not None

    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        """Detect all faces and retrieve their details."""
        if not self.is_ready():
            raise ModelNotLoadedError()

        # InsightFace processes BGR images
        faces = self._app.get(image)
        results = []

        for face in faces:
            # bbox is a float32 array [x1, y1, x2, y2]
            bbox = [int(x) for x in face.bbox]
            
            # kps contains keypoints
            landmarks = face.kps if hasattr(face, "kps") else np.array([])
            
            # det_score is the detection confidence
            det_score = float(face.det_score)
            
            # embedding is the normalized 512-dim face vector
            embedding = face.normed_embedding if hasattr(face, "normed_embedding") else None

            # Crop aligned face (optional)
            aligned_face = None
            try:
                # Basic crop with padding
                h, w = image.shape[:2]
                x1, y1, x2, y2 = bbox
                # Add padding
                pad_x = int((x2 - x1) * 0.1)
                pad_y = int((y2 - y1) * 0.1)
                x1_pad = max(0, x1 - pad_x)
                y1_pad = max(0, y1 - pad_y)
                x2_pad = min(w, x2 + pad_x)
                y2_pad = min(h, y2 + pad_y)
                if x2_pad > x1_pad and y2_pad > y1_pad:
                    aligned_face = image[y1_pad:y2_pad, x1_pad:x2_pad]
            except Exception as e:
                logger.warning(f"Failed to crop face: {e}")

            results.append(DetectedFace(
                bbox=bbox,
                landmarks=landmarks,
                det_score=det_score,
                aligned_face=aligned_face,
                embedding=embedding
            ))

        return results

    def extract_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        """
        Extract the 512-dim embedding.
        If the embedding is already present in face, return it.
        Otherwise, re-detect/compute it.
        """
        if face.embedding is not None:
            return face.embedding

        if not self.is_ready():
            raise ModelNotLoadedError()

        # If embedding is missing, we re-run app.get on the cropped/full image
        # or since it's already computed during detect_faces, this is a fallback.
        faces = self.detect_faces(image)
        if not faces:
            raise ValueError("No face detected to extract embedding from.")
            
        # Find the face closest to the given bbox
        best_face = None
        min_dist = float("inf")
        for f in faces:
            # Distance between bboxes centers
            c1 = ((f.bbox[0] + f.bbox[2])/2, (f.bbox[1] + f.bbox[3])/2)
            c2 = ((face.bbox[0] + face.bbox[2])/2, (face.bbox[1] + face.bbox[3])/2)
            dist = (c1[0]-c2[0])**2 + (c1[1]-c2[1])**2
            if dist < min_dist:
                min_dist = dist
                best_face = f
                
        if best_face and best_face.embedding is not None:
            return best_face.embedding
            
        raise ValueError("Could not extract embedding for the specified face.")

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity score (dot product since they are normalized)."""
        # Ensure they are normalized
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 > 0:
            emb1 = emb1 / norm1
        if norm2 > 0:
            emb2 = emb2 / norm2
        return float(np.dot(emb1, emb2))
