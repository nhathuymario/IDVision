"""
IDVision — User Face Profile Service
Manages employee face profile creation, update, and deletion in the database and cache.
"""

import logging
from datetime import datetime, timezone
import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Employee
from services.face_cache import face_cache
from services.face_detection_service import FaceDetectionService
from services.face_embedding_service import FaceEmbeddingService
from exceptions import FaceQualityError, EmbeddingFormatError

logger = logging.getLogger(__name__)

class UserFaceProfileService:
    """
    Service responsible for enrolling, deleting, and updating employee face encodings.
    """

    def __init__(
        self,
        detection_service: FaceDetectionService,
        embedding_service: FaceEmbeddingService
    ):
        self.detection_service = detection_service
        self.embedding_service = embedding_service

    async def enroll_from_images(
        self,
        session: AsyncSession,
        employee_id: int,
        images_bytes: list[bytes]
    ) -> Employee:
        """
        Enrolls employee face from multiple image byte arrays.
        Detects face, validates quality, averages embeddings, saves to DB and updates cache.
        """
        # Validate employee
        result = await session.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.is_active == True
            )
        )
        employee = result.scalar_one_or_none()
        if not employee:
            raise ValueError(f"Không tìm thấy nhân viên hoạt động với ID {employee_id}.")

        embeddings = []
        all_issues = []

        for idx, img_bytes in enumerate(images_bytes):
            # Convert bytes to OpenCV BGR image
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                all_issues.append(f"Ảnh {idx+1}: Định dạng ảnh không hợp lệ.")
                continue

            try:
                # Detect and validate single face
                face = self.detection_service.detect_single_face(img)
                quality = self.detection_service.validate_face_quality(face, img)
                
                if not quality.is_valid:
                    # Collect quality issues
                    all_issues.extend([f"Ảnh {idx+1}: {issue}" for issue in quality.issues])
                    continue
                    
                # Generate embedding
                embedding = self.embedding_service.generate_embedding(img, face)
                embeddings.append(embedding)
            except Exception as e:
                all_issues.append(f"Ảnh {idx+1}: {str(e)}")

        if not embeddings:
            raise FaceQualityError(
                "Đăng ký thất bại: Không có ảnh nào đạt yêu cầu chất lượng.\n" + "\n".join(all_issues)
            )

        # Average and normalize
        avg_embedding = self.embedding_service.generate_average_embedding(embeddings)

        # Update database
        employee.face_encoding = avg_embedding.tolist()
        employee.enrolled_at = datetime.now(timezone.utc)
        await session.flush()

        # Update cache
        face_cache.add_or_update(
            employee_id=employee.id,
            employee_name=employee.name,
            telegram_chat_id=employee.telegram_chat_id,
            encoding=avg_embedding
        )

        logger.info(f"Enrolled employee {employee.name} (id={employee_id}) successfully using {len(embeddings)}/{len(images_bytes)} images.")
        return employee

    async def enroll_from_embedding(
        self,
        session: AsyncSession,
        employee_id: int,
        embedding: list[float]
    ) -> Employee:
        """Enrolls employee face from a pre-computed 512-dim embedding."""
        if len(embedding) != 512:
            raise EmbeddingFormatError()

        result = await session.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.is_active == True
            )
        )
        employee = result.scalar_one_or_none()
        if not employee:
            raise ValueError(f"Không tìm thấy nhân viên hoạt động với ID {employee_id}.")

        emb_array = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb_array)
        if norm > 0:
            emb_array = emb_array / norm

        # Update database
        employee.face_encoding = emb_array.tolist()
        employee.enrolled_at = datetime.now(timezone.utc)
        await session.flush()

        # Update cache
        face_cache.add_or_update(
            employee_id=employee.id,
            employee_name=employee.name,
            telegram_chat_id=employee.telegram_chat_id,
            encoding=emb_array
        )

        logger.info(f"Enrolled employee {employee.name} (id={employee_id}) from pre-computed embedding.")
        return employee

    async def delete_enrollment(
        self,
        session: AsyncSession,
        employee_id: int
    ) -> Employee:
        """Removes face enrollment for an employee."""
        result = await session.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = result.scalar_one_or_none()
        if not employee:
            raise ValueError(f"Không tìm thấy nhân viên với ID {employee_id}.")

        employee.face_encoding = None
        employee.enrolled_at = None
        await session.flush()

        # Remove from cache
        face_cache.remove(employee_id)

        logger.info(f"Deleted face enrollment for employee {employee.name} (id={employee_id}).")
        return employee
