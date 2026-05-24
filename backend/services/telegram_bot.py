"""
IDVision — Telegram Bot Notification Service
Sends real-time attendance notifications via Telegram Bot API.
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramNotifier:
    """Handles sending attendance notifications via Telegram."""

    def __init__(self):
        self._bot: Optional[Bot] = None
        self._enabled: bool = False

    async def initialize(self) -> None:
        """Initialize the Telegram bot."""
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            logger.warning(
                "Telegram bot not configured. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
            )
            self._enabled = False
            return

        try:
            self._bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            # Verify bot token is valid
            bot_info = await self._bot.get_me()
            logger.info(f"Telegram bot initialized: @{bot_info.username}")
            self._enabled = True
        except TelegramError as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self._enabled = False

    async def shutdown(self) -> None:
        """Cleanup bot resources."""
        if self._bot:
            await self._bot.shutdown()
            logger.info("Telegram bot shut down.")

    async def send_checkin_success(
        self,
        employee_name: str,
        check_in_time: datetime,
        confidence: float,
        worked_days: int,
        worked_hours: float,
        employee_chat_id: Optional[str] = None,
    ) -> None:
        """
        Send successful check-in notification.
        
        Sends to:
        1. Group chat (TELEGRAM_CHAT_ID)
        2. Employee's personal chat (if telegram_chat_id is set)
        """
        if not self._enabled:
            return

        time_str = check_in_time.strftime("%H:%M:%S")
        date_str = check_in_time.strftime("%d/%m/%Y")

        message = (
            f"✅ *[IDVision]* Nhân viên *{self._escape_md(employee_name)}* "
            f"đã chấm công thành công\\.\n"
            f"🕐 Giờ vào ca: `{time_str}` ngày `{date_str}`\n"
            f"📊 Độ chính xác: `{confidence:.1%}`\n"
            f"📅 Tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ"
        )

        await self._send_message(settings.TELEGRAM_CHAT_ID, message)

        # Also send to employee's personal chat if configured
        if employee_chat_id:
            personal_msg = (
                f"✅ Xin chào *{self._escape_md(employee_name)}*\\!\n"
                f"Bạn đã chấm công thành công lúc `{time_str}` ngày `{date_str}`\\.\n"
                f"📅 Tích lũy tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ\\.\n"
                f"Chúc bạn ngày làm việc hiệu quả\\! 💪"
            )
            await self._send_message(employee_chat_id, personal_msg)

    async def send_late_notification(
        self,
        employee_name: str,
        check_in_time: datetime,
        late_minutes: int,
        confidence: float,
        worked_days: int,
        worked_hours: float,
        employee_chat_id: Optional[str] = None,
    ) -> None:
        """Send late check-in notification."""
        if not self._enabled:
            return

        time_str = check_in_time.strftime("%H:%M:%S")
        date_str = check_in_time.strftime("%d/%m/%Y")

        message = (
            f"⚠️ *[IDVision]* Nhân viên *{self._escape_md(employee_name)}* đến trễ\\.\n"
            f"🕐 Giờ vào: `{time_str}` ngày `{date_str}`\n"
            f"⏰ Trễ: *{late_minutes} phút*\n"
            f"📊 Độ chính xác: `{confidence:.1%}`\n"
            f"📅 Tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ"
        )

        await self._send_message(settings.TELEGRAM_CHAT_ID, message)

        if employee_chat_id:
            personal_msg = (
                f"⚠️ Xin chào *{self._escape_md(employee_name)}*\\,\n"
                f"Bạn đã đến trễ *{late_minutes} phút* hôm nay\\.\n"
                f"Giờ vào: `{time_str}` ngày `{date_str}`\\.\n"
                f"📅 Tích lũy tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ\\."
            )
            await self._send_message(employee_chat_id, personal_msg)

    async def send_low_confidence_alert(
        self,
        check_in_time: datetime,
        confidence: float,
    ) -> None:
        """Send alert for low confidence recognition."""
        if not self._enabled:
            return

        time_str = check_in_time.strftime("%H:%M:%S")
        date_str = check_in_time.strftime("%d/%m/%Y")

        message = (
            f"🔍 *[IDVision]* Phát hiện khuôn mặt nhận diện kém\\.\n"
            f"🕐 Thời gian: `{time_str}` ngày `{date_str}`\n"
            f"📊 Độ chính xác: `{confidence:.1%}`\n"
            f"⚡ Vui lòng kiểm tra snapshot để xác minh\\."
        )

        await self._send_message(settings.TELEGRAM_CHAT_ID, message)

    async def _send_message(self, chat_id: str, text: str) -> None:
        """Send a message to a Telegram chat with error handling."""
        if not self._bot:
            return

        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
            )
            logger.debug(f"Telegram message sent to chat_id={chat_id}")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', 
                         '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text


# Global singleton
telegram_notifier = TelegramNotifier()
