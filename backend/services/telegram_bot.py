"""
IDVision — Telegram Bot Notification Service
Sends real-time attendance notifications via Telegram Bot API.
Supports deep linking for automatic employee chat ID registration.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramNotifier:
    """Handles sending attendance notifications via Telegram."""

    def __init__(self):
        self._bot: Optional[Bot] = None
        self._app: Optional[Application] = None
        self._enabled: bool = False
        self._bot_username: str = ""
        self._bot_name: str = ""
        self._polling_task: Optional[asyncio.Task] = None
        # Callback to save chat_id — set by main.py after DB is ready
        self._on_link_callback = None

    @property
    def bot_username(self) -> str:
        return self._bot_username

    @property
    def bot_name(self) -> str:
        return self._bot_name

    @property
    def is_enabled(self) -> bool:
        return self._enabled

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
            self._bot_username = bot_info.username or ""
            self._bot_name = bot_info.first_name or ""
            logger.info(f"Telegram bot initialized: @{self._bot_username}")
            self._enabled = True
        except TelegramError as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self._enabled = False

    async def start_polling(self, on_link_callback) -> None:
        """Start polling for incoming messages (deep link /start commands).
        
        Args:
            on_link_callback: async function(employee_code: str, chat_id: str) -> bool
                Called when a user sends /start <employee_code>.
                Should return True if linking was successful.
        """
        if not self._enabled:
            logger.warning("Cannot start polling — bot not enabled.")
            return

        self._on_link_callback = on_link_callback

        try:
            self._app = (
                Application.builder()
                .token(settings.TELEGRAM_BOT_TOKEN)
                .build()
            )

            # Register /start handler for deep linking
            self._app.add_handler(CommandHandler("start", self._handle_start))

            # Initialize the application
            await self._app.initialize()
            await self._app.start()

            # Start polling in the background
            await self._app.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot polling started (listening for /start deep links).")

        except Exception as e:
            logger.error(f"Failed to start Telegram polling: {e}")

    async def stop_polling(self) -> None:
        """Stop the polling loop."""
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
                logger.info("Telegram bot polling stopped.")
            except Exception as e:
                logger.error(f"Error stopping polling: {e}")

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command with deep link payload.
        
        When user clicks t.me/BotName?start=NV001, Telegram sends:
        /start NV001
        
        We extract the employee_code and save the chat_id.
        """
        if not update.effective_message or not update.effective_chat:
            return

        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name if update.effective_user else "bạn"
        args = context.args or []

        if not args:
            # No deep link payload — just a plain /start
            await update.effective_message.reply_text(
                f"👋 Xin chào {user_name}!\n\n"
                "Đây là bot IDVision — Hệ thống chấm công thông minh.\n\n"
                "Để liên kết tài khoản Telegram, vui lòng sử dụng link "
                "được cung cấp bởi quản trị viên."
            )
            return

        employee_code = args[0].strip().upper()
        logger.info(f"Deep link received: employee_code={employee_code}, chat_id={chat_id}")

        if self._on_link_callback:
            try:
                success = await self._on_link_callback(employee_code, chat_id)
                if success:
                    await update.effective_message.reply_text(
                        f"✅ Liên kết thành công!\n\n"
                        f"Tài khoản Telegram của bạn đã được liên kết với mã nhân viên "
                        f"**{employee_code}**.\n\n"
                        f"📩 Bạn sẽ nhận phiếu lương và thông báo chấm công qua đây.\n"
                        f"Cảm ơn bạn! 🎉",
                        parse_mode="Markdown",
                    )
                else:
                    await update.effective_message.reply_text(
                        f"❌ Không tìm thấy nhân viên với mã **{employee_code}**.\n\n"
                        "Vui lòng liên hệ quản trị viên để kiểm tra lại.",
                        parse_mode="Markdown",
                    )
            except Exception as e:
                logger.error(f"Error in deep link callback: {e}")
                await update.effective_message.reply_text(
                    "⚠️ Đã xảy ra lỗi khi liên kết. Vui lòng thử lại sau."
                )
        else:
            await update.effective_message.reply_text(
                "⚠️ Hệ thống chưa sẵn sàng. Vui lòng thử lại sau."
            )

    def get_deep_link(self, employee_code: str) -> str:
        """Generate a Telegram deep link URL for an employee.
        
        Args:
            employee_code: Employee code (e.g. "NV001")
            
        Returns:
            Deep link URL: https://t.me/BotName?start=NV001
        """
        if not self._bot_username:
            return ""
        return f"https://t.me/{self._bot_username}?start={employee_code}"

    async def shutdown(self) -> None:
        """Cleanup bot resources."""
        await self.stop_polling()
        if self._bot:
            await self._bot.shutdown()
            logger.info("Telegram bot shut down.")

    async def send_document(self, chat_id: str, file_bytes: bytes, filename: str, caption: str = "") -> bool:
        """Send a document (e.g. PDF) to a Telegram chat.
        
        Args:
            chat_id: Telegram chat ID
            file_bytes: File content as bytes
            filename: Filename to display
            caption: Optional caption text
            
        Returns:
            True if sent successfully
        """
        if not self._bot:
            return False

        try:
            import io
            doc = io.BytesIO(file_bytes)
            doc.name = filename

            escaped_caption = self._escape_md(caption) if caption else ""

            await self._bot.send_document(
                chat_id=chat_id,
                document=doc,
                filename=filename,
                caption=escaped_caption,
                parse_mode="MarkdownV2" if escaped_caption else None,
            )
            logger.info(f"Document '{filename}' sent to chat_id={chat_id}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send document to {chat_id}: {e}")
            return False

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
            f"đã chấm công thành công\\.\\n"
            f"🕐 Giờ vào ca: `{time_str}` ngày `{date_str}`\\n"
            f"📊 Độ chính xác: `{confidence:.1%}`\\n"
            f"📅 Tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ"
        )

        await self._send_message(settings.TELEGRAM_CHAT_ID, message)

        # Also send to employee's personal chat if configured
        if employee_chat_id:
            personal_msg = (
                f"✅ Xin chào *{self._escape_md(employee_name)}*\\!\\n"
                f"Bạn đã chấm công thành công lúc `{time_str}` ngày `{date_str}`\\.\\n"
                f"📅 Tích lũy tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ\\.\\n"
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
            f"⚠️ *[IDVision]* Nhân viên *{self._escape_md(employee_name)}* đến trễ\\.\\n"
            f"🕐 Giờ vào: `{time_str}` ngày `{date_str}`\\n"
            f"⏰ Trễ: *{late_minutes} phút*\\n"
            f"📊 Độ chính xác: `{confidence:.1%}`\\n"
            f"📅 Tháng này: *{worked_days} ngày* \\| `{worked_hours:.2f}` giờ"
        )

        await self._send_message(settings.TELEGRAM_CHAT_ID, message)

        if employee_chat_id:
            personal_msg = (
                f"⚠️ Xin chào *{self._escape_md(employee_name)}*\\,\\n"
                f"Bạn đã đến trễ *{late_minutes} phút* hôm nay\\.\\n"
                f"Giờ vào: `{time_str}` ngày `{date_str}`\\.\\n"
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
            f"🔍 *[IDVision]* Phát hiện khuôn mặt nhận diện kém\\.\\n"
            f"🕐 Thời gian: `{time_str}` ngày `{date_str}`\\n"
            f"📊 Độ chính xác: `{confidence:.1%}`\\n"
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
