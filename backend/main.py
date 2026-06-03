"""
IDVision — FastAPI Application Entry Point

Face Recognition Attendance System with:
- InsightFace (ArcFace) for masked face recognition
- PostgreSQL + pgvector for vector storage
- In-memory face cache for ultra-fast matching
- Telegram Bot for real-time notifications + deep linking
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from sqlalchemy import select

from config import get_settings
from database import init_db, async_session
from models import Employee
from services.face_cache import face_cache
from services.telegram_bot import telegram_notifier
from routers import employees, enrollment, attendance, auth, policy, salary
from routers import telegram_webhook

# Import face recognition services & provider
from services.providers.insightface_provider import InsightFaceProvider
from services.face_detection_service import FaceDetectionService
from services.face_embedding_service import FaceEmbeddingService
from services.face_matching_service import FaceMatchingService
from services.user_face_profile_service import UserFaceProfileService
from services.attendance_service import AttendanceService
from exceptions import FaceRecognitionError

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("idvision")

settings = get_settings()


# ── Telegram Deep Link Callback ─────────────────────────────
async def _on_telegram_link(employee_code: str, chat_id: str) -> bool:
    """Called when an employee clicks a Telegram deep link and sends /start.
    
    Looks up the employee by code and saves their chat_id.
    Returns True if successful.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Employee).where(
                Employee.employee_code == employee_code,
                Employee.is_active == True,
            )
        )
        employee = result.scalar_one_or_none()
        if not employee:
            logger.warning(f"Telegram deep link: employee '{employee_code}' not found.")
            return False

        employee.telegram_chat_id = chat_id
        await session.commit()
        logger.info(
            f"Telegram linked: {employee.name} ({employee_code}) → chat_id={chat_id}"
        )
        return True


# ── Application Lifespan ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    1. Initialize database connection
    2. Load face encodings into memory cache
    3. Initialize Face Recognition Provider & Services
    4. Initialize Telegram bot
    5. Start Telegram polling for deep links
    
    Shutdown:
    1. Stop Telegram polling
    2. Cleanup Telegram bot
    """
    logger.info("=" * 60)
    logger.info("🚀 IDVision — Starting up...")
    logger.info("=" * 60)

    # 1. Database
    await init_db()
    logger.info("✅ Database connection verified.")

    # 2. Face cache
    async with async_session() as session:
        count = await face_cache.load_from_db(session)
        logger.info(f"✅ Face cache loaded: {count} enrolled employees.")

    # 3. Face Recognition Provider & Services
    # Check if GPU is available (InsightFace can use ctx_id=0 for first GPU, -1 for CPU)
    # Defaulting to -1 (CPU) for standard Docker/local deployments unless overridden
    provider = InsightFaceProvider(ctx_id=-1)
    provider.initialize()
    
    detection_service = FaceDetectionService(provider=provider)
    embedding_service = FaceEmbeddingService(provider=provider)
    matching_service = FaceMatchingService()
    user_face_profile_service = UserFaceProfileService(
        detection_service=detection_service,
        embedding_service=embedding_service
    )
    attendance_service = AttendanceService(
        detection_service=detection_service,
        embedding_service=embedding_service,
        matching_service=matching_service
    )
    
    # Store services in app.state for request dependency access
    app.state.provider = provider
    app.state.detection_service = detection_service
    app.state.embedding_service = embedding_service
    app.state.matching_service = matching_service
    app.state.user_face_profile_service = user_face_profile_service
    app.state.attendance_service = attendance_service
    logger.info("✅ Face recognition provider & services initialized.")

    # 4. Telegram bot
    await telegram_notifier.initialize()

    # 5. Start Telegram polling for deep links
    if telegram_notifier.is_enabled:
        await telegram_notifier.start_polling(on_link_callback=_on_telegram_link)
        logger.info("✅ Telegram deep link polling started.")

    logger.info("=" * 60)
    logger.info("🟢 IDVision is ready!")
    logger.info(f"   Similarity threshold: {settings.SIMILARITY_THRESHOLD}")
    logger.info(f"   Late threshold: {settings.LATE_THRESHOLD_HOUR:02d}:{settings.LATE_THRESHOLD_MINUTE:02d}")
    logger.info(f"   Anti-spoofing: {'Enabled' if settings.ANTI_SPOOFING_ENABLED else 'Disabled'}")
    logger.info(f"   Duplicate check: {settings.DUPLICATE_CHECK_MINUTES} min")
    if telegram_notifier.is_enabled:
        logger.info(f"   Telegram bot: @{telegram_notifier.bot_username}")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("🔴 IDVision — Shutting down...")
    await telegram_notifier.shutdown()
    logger.info("Goodbye!")


# ── FastAPI App ─────────────────────────────────────────────
app = FastAPI(
    title="IDVision",
    description=(
        "Hệ thống chấm công bằng nhận diện khuôn mặt AI. "
        "Hỗ trợ nhận diện khẩu trang, chống giả mạo, "
        "thông báo real-time qua Telegram."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Exception handler for Domain Exception: FaceRecognitionError
@app.exception_handler(FaceRecognitionError)
async def face_recognition_exception_handler(request: Request, exc: FaceRecognitionError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message}
    )

# ── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────
app.include_router(employees.router)
app.include_router(enrollment.router)
app.include_router(attendance.router)
app.include_router(auth.router)
app.include_router(policy.router)
app.include_router(salary.router)
app.include_router(telegram_webhook.router)


# ── Static Files (Frontend) ─────────────────────────────────
import os
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(os.path.join(frontend_dir, "employee")):
    app.mount("/employee", StaticFiles(directory=os.path.join(frontend_dir, "employee"), html=True), name="employee-frontend")
if os.path.isdir(os.path.join(frontend_dir, "admin")):
    app.mount("/admin", StaticFiles(directory=os.path.join(frontend_dir, "admin"), html=True), name="admin-frontend")


# ── Root & Health ───────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint — system info."""
    return {
        "service": "IDVision",
        "version": "1.0.0",
        "description": "AI Face Recognition Attendance System",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "face_cache_size": face_cache.size,
        "face_cache_loaded": face_cache.is_loaded,
    }


@app.post("/api/cache/refresh", tags=["Admin"])
async def refresh_cache():
    """Manually refresh the face encoding cache from database."""
    async with async_session() as session:
        count = await face_cache.refresh(session)
    return {
        "message": "Face cache refreshed.",
        "enrolled_count": count,
    }

if __name__ == "__main__":
    import uvicorn
    # Chạy server với uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)