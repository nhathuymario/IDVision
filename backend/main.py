"""
IDVision — FastAPI Application Entry Point

Face Recognition Attendance System with:
- InsightFace (ArcFace) for masked face recognition
- PostgreSQL + pgvector for vector storage
- In-memory face cache for ultra-fast matching
- Telegram Bot for real-time notifications
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database import init_db, async_session
from services.face_cache import face_cache
from services.telegram_bot import telegram_notifier
from routers import employees, enrollment, attendance, auth

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("idvision")

settings = get_settings()


# ── Application Lifespan ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    1. Initialize database connection
    2. Load face encodings into memory cache
    3. Initialize Telegram bot
    
    Shutdown:
    1. Cleanup Telegram bot
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

    # 3. Telegram bot
    await telegram_notifier.initialize()

    logger.info("=" * 60)
    logger.info("🟢 IDVision is ready!")
    logger.info(f"   Similarity threshold: {settings.SIMILARITY_THRESHOLD}")
    logger.info(f"   Late threshold: {settings.LATE_THRESHOLD_HOUR:02d}:{settings.LATE_THRESHOLD_MINUTE:02d}")
    logger.info(f"   Anti-spoofing: {'Enabled' if settings.ANTI_SPOOFING_ENABLED else 'Disabled'}")
    logger.info(f"   Duplicate check: {settings.DUPLICATE_CHECK_MINUTES} min")
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
