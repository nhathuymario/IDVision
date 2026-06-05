"""
IDVision — Enrollment Router
Face enrollment endpoints: upload images to register an employee's face encoding.
"""

import base64
import io
import logging
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

from database import get_db
from models import Employee
from schemas import EnrollmentResponse
from services.face_cache import face_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enrollment", tags=["Enrollment"])


def _extract_embedding_from_image(image_bytes: bytes) -> np.ndarray | None:
    """
    Extract face embedding from image bytes by calling the AI Service.
    """
    import httpx
    try:
        # Call the ai_service container at port 8001
        with httpx.Client(timeout=15.0) as client:
            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
            response = client.post("http://ai_service:8001/extract-embedding", files=files)
            
            if response.status_code == 200:
                data = response.json()
                return np.array(data["embedding"], dtype=np.float32)
            elif response.status_code == 404:
                logger.warning("No face detected in image sent to AI service.")
                return None
            else:
                logger.error(f"AI Service returned error {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"AI Service failed to process image: {response.text}"
                )
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to AI Service: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI Service is currently unavailable. Please try again later."
        )
    except Exception as e:
        logger.error(f"Error communicating with AI Service: {e}")
        return None


@router.post("/{employee_id}", response_model=EnrollmentResponse)
async def enroll_face(
    employee_id: int,
    images: list[UploadFile] = File(
        ...,
        description="3-5 face images (with and without mask recommended)"
    ),
    session: AsyncSession = Depends(get_db),
):
    """
    Enroll an employee's face by uploading 3-5 images.
    
    The system will:
    1. Detect the face in each image
    2. Extract 512-dim ArcFace embedding from each
    3. Compute the average normalized embedding
    4. Store in the database and update the in-memory cache
    
    Recommended: Upload images both with and without mask for better accuracy.
    """
    # Validate employee exists
    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    if len(images) < 1:
        raise HTTPException(
            status_code=400,
            detail="At least 1 image is required. 3-5 recommended."
        )
    if len(images) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 images allowed."
        )

    # Extract embeddings from each image
    embeddings = []
    for i, image_file in enumerate(images):
        # Validate file type
        if image_file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(
                status_code=400,
                detail=f"Image {i+1}: Unsupported format '{image_file.content_type}'. "
                       f"Use JPEG, PNG, or WebP."
            )

        image_bytes = await image_file.read()
        embedding = _extract_embedding_from_image(image_bytes)

        if embedding is None:
            logger.warning(f"No face detected in image {i+1} for employee {employee.name}")
            continue

        embeddings.append(embedding)

    if not embeddings:
        raise HTTPException(
            status_code=400,
            detail="No face detected in any of the uploaded images. "
                   "Ensure the face is clearly visible."
        )

    # Compute average normalized embedding
    avg_embedding = np.mean(embeddings, axis=0).astype(np.float32)
    norm = np.linalg.norm(avg_embedding)
    if norm > 0:
        avg_embedding = avg_embedding / norm

    # Update database
    employee.face_encoding = avg_embedding.tolist()
    employee.enrolled_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(employee)

    # Update in-memory cache
    face_cache.add_or_update(
        employee_id=employee.id,
        employee_name=employee.name,
        telegram_chat_id=employee.telegram_chat_id,
        encoding=avg_embedding,
    )

    logger.info(
        f"Enrolled face for {employee.name}: "
        f"{len(embeddings)}/{len(images)} images processed."
    )

    return EnrollmentResponse(
        employee_id=employee.id,
        employee_name=employee.name,
        message=(
            f"Face enrolled successfully from {len(embeddings)}/{len(images)} images. "
            f"Cache updated."
        ),
        num_faces_processed=len(embeddings),
        enrolled_at=employee.enrolled_at,
    )


@router.post("/{employee_id}/embedding")
async def enroll_face_from_embedding(
    employee_id: int,
    embedding: list[float],
    session: AsyncSession = Depends(get_db),
):
    """
    Enroll a face using a pre-computed embedding vector.
    Used by the AI service after processing images externally.
    """
    if len(embedding) != 512:
        raise HTTPException(
            status_code=400,
            detail=f"Embedding must be 512-dimensional. Got {len(embedding)}."
        )

    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    # Normalize
    emb_array = np.array(embedding, dtype=np.float32)
    norm = np.linalg.norm(emb_array)
    if norm > 0:
        emb_array = emb_array / norm

    employee.face_encoding = emb_array.tolist()
    employee.enrolled_at = datetime.now(timezone.utc)
    await session.flush()

    face_cache.add_or_update(
        employee_id=employee.id,
        employee_name=employee.name,
        telegram_chat_id=employee.telegram_chat_id,
        encoding=emb_array,
    )

    return {
        "message": f"Embedding enrolled for {employee.name}.",
        "employee_id": employee.id,
    }


@router.delete("/{employee_id}")
async def remove_enrollment(
    employee_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Remove face enrollment for an employee."""
    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    employee.face_encoding = None
    employee.enrolled_at = None
    await session.flush()

    face_cache.remove(employee_id)

    logger.info(f"Removed enrollment for {employee.name} (id={employee_id})")
    return {"message": f"Face enrollment removed for {employee.name}."}
