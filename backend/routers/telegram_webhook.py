"""
IDVision — Telegram Integration Router
Endpoints for deep linking, bot status, and employee Telegram pairing.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Employee
from routers.auth import verify_admin_token
from schemas import TelegramBotStatus, TelegramLinkResponse
from services.telegram_bot import telegram_notifier

router = APIRouter(prefix="/api/admin/telegram", tags=["Admin Telegram"])


@router.get("/status", response_model=TelegramBotStatus)
async def telegram_status(
    _: dict = Depends(verify_admin_token),
):
    """Get Telegram bot status and info."""
    if not telegram_notifier.is_enabled:
        return TelegramBotStatus(enabled=False)

    return TelegramBotStatus(
        enabled=True,
        bot_username=telegram_notifier.bot_username,
        bot_name=telegram_notifier.bot_name,
        deep_link_base=f"https://t.me/{telegram_notifier.bot_username}?start=",
    )


@router.get("/link/{employee_id}", response_model=TelegramLinkResponse)
async def get_telegram_link(
    employee_id: int,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Generate a Telegram deep link for an employee.
    
    The employee can click this link to automatically pair their
    Telegram account with the system.
    """
    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not telegram_notifier.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")

    deep_link = telegram_notifier.get_deep_link(employee.employee_code)

    return TelegramLinkResponse(
        employee_id=employee.id,
        employee_name=employee.name,
        employee_code=employee.employee_code,
        deep_link=deep_link,
        bot_username=telegram_notifier.bot_username,
        is_linked=bool(employee.telegram_chat_id),
    )
