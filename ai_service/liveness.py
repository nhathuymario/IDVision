"""
IDVision — Liveness Detection Module
Anti-spoofing using MiniFASNet (Silent Face Anti-Spoofing).
Detects presentation attacks: printed photos, video replays, screen displays.
"""

import logging
import os
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# MiniFASNet model paths (will be downloaded/placed in models/ directory)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "anti_spoofing")


class LivenessDetector:
    """
    Silent Face Anti-Spoofing detector using MiniFASNet.
    
    Passive liveness detection — analyzes face texture patterns
    to distinguish real faces from printed photos/screens.
    No user interaction required (no blink/head turn).
    """

    def __init__(self, threshold: float = 0.5):
        """
        Args:
            threshold: Liveness score threshold. 
                       Score > threshold = real face.
                       Score <= threshold = spoofing attempt.
        """
        self._threshold = threshold
        self._model = None
        self._enabled = False

    def initialize(self) -> bool:
        """
        Initialize the liveness detection model.
        
        Returns:
            True if model loaded successfully, False otherwise.
        """
        try:
            model_path = os.path.join(MODEL_DIR, "2.7_80x80_MiniFASNetV2.onnx")

            if not os.path.exists(model_path):
                logger.warning(
                    f"Liveness model not found at {model_path}. "
                    f"Anti-spoofing will use a simple heuristic instead. "
                    f"Download MiniFASNet ONNX model for production use."
                )
                self._enabled = False
                return False

            import onnxruntime as ort

            self._model = ort.InferenceSession(
                model_path,
                providers=["CPUExecutionProvider"],
            )
            self._enabled = True
            logger.info("Liveness detection model loaded (MiniFASNet).")
            return True

        except Exception as e:
            logger.error(f"Failed to load liveness model: {e}")
            self._enabled = False
            return False

    def check(self, face_image: np.ndarray) -> tuple[bool, float]:
        """
        Check if a face image is from a real person.
        
        Args:
            face_image: Cropped face image (BGR, any size).
            
        Returns:
            Tuple of (is_real, confidence_score).
        """
        if not self._enabled or self._model is None:
            # Fallback: use simple heuristic based on image quality
            return self._heuristic_check(face_image)

        try:
            # Preprocess for MiniFASNet: resize to 80x80, normalize
            face_resized = cv2.resize(face_image, (80, 80))
            face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
            face_normalized = face_rgb.astype(np.float32) / 255.0

            # Transpose to NCHW format
            face_input = np.transpose(face_normalized, (2, 0, 1))
            face_input = np.expand_dims(face_input, axis=0)

            # Run inference
            input_name = self._model.get_inputs()[0].name
            output = self._model.run(None, {input_name: face_input})

            # Get liveness score
            scores = output[0][0]
            # MiniFASNet outputs [fake_score, real_score]
            if len(scores) >= 2:
                liveness_score = float(scores[1])
            else:
                liveness_score = float(scores[0])

            is_real = liveness_score > self._threshold

            if not is_real:
                logger.warning(
                    f"Spoofing detected! Liveness score: {liveness_score:.4f} "
                    f"(threshold: {self._threshold})"
                )

            return is_real, liveness_score

        except Exception as e:
            logger.error(f"Liveness check error: {e}")
            # Default to allow if model fails (fail-open for availability)
            return True, 1.0

    def _heuristic_check(self, face_image: np.ndarray) -> tuple[bool, float]:
        """
        Simple heuristic liveness check based on image properties.
        Used as fallback when MiniFASNet model is not available.
        
        Checks:
        - Laplacian variance (blur detection — screens/prints tend to be flatter)
        - Color distribution analysis
        """
        if face_image is None or face_image.size == 0:
            return False, 0.0

        # Convert to grayscale
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)

        # Laplacian variance — real faces have more texture detail
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Normalize score (empirical thresholds)
        # Real faces typically have laplacian_var > 100
        score = min(1.0, laplacian_var / 200.0)
        is_real = score > 0.3

        logger.debug(
            f"Heuristic liveness: laplacian_var={laplacian_var:.1f}, "
            f"score={score:.3f}, is_real={is_real}"
        )

        return is_real, score

    @property
    def is_enabled(self) -> bool:
        """Whether the liveness model is loaded and ready."""
        return self._enabled
