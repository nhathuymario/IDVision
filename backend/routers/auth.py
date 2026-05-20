"""
IDVision — Admin Authentication Router
JWT-based authentication for admin dashboard access.
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models import AdminUser
from schemas import AdminLoginRequest, AdminLoginResponse

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/admin", tags=["Admin Auth"])

# JWT Configuration
JWT_SECRET = settings.TELEGRAM_BOT_TOKEN or "idvision-secret-key-change-me"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer(auto_error=False)


def create_jwt_token(admin_id: int, username: str) -> str:
    """Create a JWT token for admin authentication."""
    payload = {
        "sub": admin_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Dependency to verify admin JWT token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    data: AdminLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Admin login endpoint — returns JWT token."""
    result = await session.execute(
        select(AdminUser).where(AdminUser.username == data.username)
    )
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # Verify password
    if not bcrypt.checkpw(
        data.password.encode("utf-8"),
        admin.password_hash.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # Generate JWT
    token = create_jwt_token(admin.id, admin.username)

    logger.info(f"Admin login: {admin.username}")
    return AdminLoginResponse(
        token=token,
        username=admin.username,
        full_name=admin.full_name,
        message="Đăng nhập thành công.",
    )


@router.get("/me")
async def admin_me(admin: dict = Depends(verify_admin_token)):
    """Get current admin info from token."""
    return {
        "admin_id": admin["sub"],
        "username": admin["username"],
    }
