"""
IDVision — Application Configuration
Centralized settings using Pydantic BaseSettings with .env support.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg://idvision:password@localhost:5432/idvision"

    # ── Telegram Bot ──────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""  # Group chat ID for attendance notifications

    # ── Face Recognition ──────────────────────────────────────
    SIMILARITY_THRESHOLD: float = 0.55       # Cosine similarity threshold for match
    ANTI_SPOOFING_ENABLED: bool = True
    LIVENESS_THRESHOLD: float = 0.5         # MiniFASNet liveness score threshold

    # ── Attendance Rules ──────────────────────────────────────
    LATE_THRESHOLD_HOUR: int = 8            # Work start hour
    LATE_THRESHOLD_MINUTE: int = 0          # Work start minute
    DUPLICATE_CHECK_MINUTES: int = 30       # Prevent duplicate check-in within N minutes

    # ── Camera ────────────────────────────────────────────────
    CAMERA_SOURCE: str = "0"                # Webcam index or RTSP URL
    BACKEND_URL: str = "http://backend:8000"

    # ── Storage ───────────────────────────────────────────────
    SNAPSHOT_DIR: str = "/app/snapshots"     # Directory for check-in face snapshots

    model_config = {
        # Support running from either repo root or backend/ directory.
        "env_file": (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (singleton)."""
    return Settings()
