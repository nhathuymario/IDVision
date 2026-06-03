"""
IDVision — Face Detection Service
Handles face detection and image quality validation (size, blurriness, brightness).
"""

import logging
import cv2
import numpy as np
from services.providers.face_recognition_provider import FaceRecognitionProvider
from services.providers.domain_models import DetectedFace, FaceQualityResult
from exceptions import NoFaceDetectedError, MultipleFacesError, FaceTooSmallError, FaceQualityError

logger = logging.getLogger(__name__)

class FaceDetectionService:
    """
    Service responsible for detecting faces in images and checking their visual quality
    before extracting feature embeddings.
    """

    def __init__(
        self, 
        provider: FaceRecognitionProvider,
        min_face_size: int = 80,
        min_det_score: float = 0.5,
        min_blur_score: float = 50.0,
        min_brightness: float = 40.0,
        max_brightness: float = 230.0
    ):
        self.provider = provider
        self.min_face_size = min_face_size
        self.min_det_score = min_det_score
        self.min_blur_score = min_blur_score
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness

    def detect_single_face(self, image: np.ndarray) -> DetectedFace:
        """
        Detect exactly one face in an image.
        Throws exceptions if 0 or more than 1 face is found.
        """
        faces = self.provider.detect_faces(image)
        
        if not faces:
            raise NoFaceDetectedError()
            
        if len(faces) > 1:
            raise MultipleFacesError()
            
        return faces[0]

    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        """Detect all faces in an image."""
        return self.provider.detect_faces(image)

    def validate_face_quality(self, face: DetectedFace, image: np.ndarray) -> FaceQualityResult:
        """
        Validates the visual quality of a detected face:
        - Bounding box size (width & height must be >= min_face_size)
        - Blurriness (Laplacian variance score)
        - Brightness (average pixel value of gray scale)
        - Detection score
        """
        issues = []
        
        # 1. Check detection confidence score
        if face.det_score < self.min_det_score:
            issues.append(f"Độ tự tin nhận diện khuôn mặt thấp ({face.det_score:.2f} < {self.min_det_score})")

        # 2. Check face bounding box size
        x1, y1, x2, y2 = face.bbox
        w = x2 - x1
        h = y2 - y1
        if w < self.min_face_size or h < self.min_face_size:
            issues.append(f"Khuôn mặt quá nhỏ ({w}x{h}px < {self.min_face_size}x{self.min_face_size}px)")
            
        # Get face region of interest
        face_img = face.aligned_face
        if face_img is None or face_img.size == 0:
            # Fallback to cropping from image directly
            h_img, w_img = image.shape[:2]
            x1_crop = max(0, x1)
            y1_crop = max(0, y1)
            x2_crop = min(w_img, x2)
            y2_crop = min(h_img, y2)
            if x2_crop > x1_crop and y2_crop > y1_crop:
                face_img = image[y1_crop:y2_crop, x1_crop:x2_crop]
            else:
                face_img = image

        blur_score = 0.0
        brightness = 0.0
        
        if face_img is not None and face_img.size > 0:
            # Convert to grayscale
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            
            # 3. Calculate blur score (Laplacian variance)
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if blur_score < self.min_blur_score:
                issues.append(f"Ảnh quá mờ (độ nét: {blur_score:.1f} < {self.min_blur_score})")
                
            # 4. Calculate brightness
            brightness = float(np.mean(gray))
            if brightness < self.min_brightness:
                issues.append(f"Ảnh quá tối (độ sáng: {brightness:.1f} < {self.min_brightness})")
            elif brightness > self.max_brightness:
                issues.append(f"Ảnh quá sáng (độ sáng: {brightness:.1f} > {self.max_brightness})")
        else:
            issues.append("Không thể cắt ảnh khuôn mặt để kiểm tra chất lượng")

        is_valid = len(issues) == 0
        
        return FaceQualityResult(
            is_valid=is_valid,
            issues=issues,
            size=(w, h),
            blur_score=blur_score,
            brightness=brightness
        )
