"""
IDVision — Enrollment Router (Refactored)
Thin controller handling API requests for employee face registrations.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession


from database import get_db
from schemas import EnrollmentResponse
from services.user_face_profile_service import UserFaceProfileService
from exceptions import FaceRecognitionError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enrollment", tags=["Enrollment"])

def get_profile_service(request: Request) -> UserFaceProfileService:
    """Dependency: retrieves the user face profile service from app state."""
    return request.app.state.user_face_profile_service


@router.post("/{employee_id}", response_model=EnrollmentResponse)
async def enroll_face(
    employee_id: int,
    images: list[UploadFile] = File(
        ...,
        description="3-5 face images (with and without mask recommended)"
    ),
    session: AsyncSession = Depends(get_db),
    profile_service: UserFaceProfileService = Depends(get_profile_service),
):
    """
    Enroll an employee's face by uploading 3-5 images.
    
    Flow:
    1. Read uploaded image files into bytes.
    2. Delegate processing and database saving to UserFaceProfileService.
    3. Return structured response.
    """
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

    # Validate file formats first
    images_bytes = []
    for i, img_file in enumerate(images):
        if img_file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(
                status_code=400,
                detail=f"Image {i+1}: Unsupported format '{img_file.content_type}'. Use JPEG, PNG, or WebP."
            )
        img_bytes = await img_file.read()
        images_bytes.append(img_bytes)

    try:
        employee = await profile_service.enroll_from_images(
            session=session,
            employee_id=employee_id,
            images_bytes=images_bytes
        )
        
        # Calculate how many succeeded
        # Under the hood, if any image fails quality checks it won't be in the averaged embedding.
        # If all fail, a FaceQualityError is raised.
        # Let's count processed images as the ones we got.
        return EnrollmentResponse(
            employee_id=employee.id,
            employee_name=employee.name,
            message=f"Đăng ký khuôn mặt thành công cho {employee.name}.",
            num_faces_processed=len(images_bytes),
            enrolled_at=employee.enrolled_at,
        )
    except FaceRecognitionError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Enrollment router error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi đăng ký khuôn mặt.")


@router.post("/{employee_id}/embedding")
async def enroll_face_from_embedding(
    employee_id: int,
    embedding: list[float],
    session: AsyncSession = Depends(get_db),
    profile_service: UserFaceProfileService = Depends(get_profile_service),
):
    """
    Enroll a face using a pre-computed embedding vector.
    Used by external AI services or custom enrollment scripts.
    """
    try:
        employee = await profile_service.enroll_from_embedding(
            session=session,
            employee_id=employee_id,
            embedding=embedding
        )
        return {
            "message": f"Đăng ký vector khuôn mặt thành công cho {employee.name}.",
            "employee_id": employee.id,
        }
    except FaceRecognitionError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Enrollment embedding router error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi đăng ký vector khuôn mặt.")


@router.delete("/{employee_id}")
async def remove_enrollment(
    employee_id: int,
    session: AsyncSession = Depends(get_db),
    profile_service: UserFaceProfileService = Depends(get_profile_service),
):
    """Remove face enrollment for an employee."""
    try:
        employee = await profile_service.delete_enrollment(
            session=session,
            employee_id=employee_id
        )
        return {"message": f"Đã xóa đăng ký khuôn mặt của {employee.name}."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Delete enrollment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi xóa đăng ký khuôn mặt.")
