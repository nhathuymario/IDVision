"""
IDVision — Provider Domain Models
Defines pure Python dataclasses representing entities used in face recognition processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np

@dataclass
class DetectedFace:
    """Represents a face detected in an image."""
    bbox: list[int]                    # [x1, y1, x2, y2]
    landmarks: np.ndarray              # 5-point (or more) landmarks
    det_score: float                   # Confidence score (0.0 to 1.0)
    aligned_face: Optional[np.ndarray] = None  # Aligned crop of the face
    embedding: Optional[np.ndarray] = None     # Normalized 512-dim embedding (if extracted)

    def __repr__(self):
        return f"<DetectedFace(bbox={self.bbox}, score={self.det_score:.3f})>"


@dataclass
class FaceQualityResult:
    """Represents the results of face image quality checking."""
    is_valid: bool                     # Whether quality is sufficient
    issues: list[str] = field(default_factory=list) # List of quality issues
    size: tuple[int, int] = (0, 0)     # Width, height of the face bounding box
    blur_score: float = 0.0            # Calculated Laplacian variance
    brightness: float = 0.0            # Average pixel value


@dataclass
class MatchResult:
    """Result of matching a face embedding against registered employees."""
    employee_id: int
    employee_name: str
    telegram_chat_id: Optional[str]
    similarity: float


@dataclass
class AttendanceResult:
    """Result of processing a check-in request."""
    success: bool
    status: str                        # 'SUCCESS', 'LATE', 'LOW_CONFIDENCE', 'FAILED', etc.
    message: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    check_in_time: Optional[datetime] = None
    similarity: Optional[float] = None
