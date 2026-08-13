"""Telegram Bot API notifications.

Sends booking success/failure/error alerts to the configured Telegram chat.
All notification calls are error-isolated — a Telegram failure will NEVER
crash the booking flow.

Uses httpx for async HTTP with a 10-second timeout.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Reusable HTTP client with timeout
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Get or create a reusable HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def _send_message(text: str) -> None:
    """Send a message via Telegram Bot API.

    Error-isolated: will log warnings but never raise exceptions.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured — skipping notification")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        client = await _get_client()
        response = await client.post(url, json=payload)

        if response.status_code != 200:
            logger.warning(
                "Telegram API returned %d: %s",
                response.status_code,
                response.text[:200],
            )
    except httpx.TimeoutException:
        logger.warning("Telegram notification timed out (10s)")
    except Exception as e:
        logger.warning("Telegram notification failed: %s", e)
        # Swallow the error — notifications must never crash bookings


def _now_ist() -> str:
    """Current time in IST as a formatted string."""
    return datetime.now(IST).strftime("%d-%b-%Y %I:%M:%S %p IST")


async def notify_booking_result(
    sport: str,
    slot_time: str,
    result: object,  # BookingResult — using object to avoid circular imports
) -> None:
    """Send a booking result notification.

    Args:
        sport: Sport name
        slot_time: Target slot time
        result: BookingResult object with success/status/summary
    """
    time_str = _now_ist()

    if result.success:  # type: ignore
        message = (
            f"✅ <b>Booking Confirmed!</b>\n\n"
            f"🏟️ <b>Sport:</b> {sport}\n"
            f"🕐 <b>Slot:</b> {result.slot_booked or slot_time}\n"  # type: ignore
            f"🔄 <b>Attempts:</b> {result.attempt_count}\n"  # type: ignore
            f"⏰ <b>Time:</b> {time_str}\n\n"
            f"Your slot has been successfully booked! 🎉"
        )
    else:
        status_icon = {
            "no_slots": "🚫",
            "failed": "❌",
            "error": "💥",
        }.get(result.status.value, "❓")  # type: ignore

        message = (
            f"{status_icon} <b>Booking Failed</b>\n\n"
            f"🏟️ <b>Sport:</b> {sport}\n"
            f"🕐 <b>Slot:</b> {slot_time}\n"
            f"📊 <b>Status:</b> {result.status.value}\n"  # type: ignore
            f"🔄 <b>Attempts:</b> {result.attempt_count}\n"  # type: ignore
            f"⏰ <b>Time:</b> {time_str}\n\n"
            f"📝 <b>Details:</b>\n{result.summary}"  # type: ignore
        )

    await _send_message(message)


async def send_error_notification(error: str, context: str = "") -> None:
    """Send a system error notification.

    Args:
        error: Error message/description
        context: What was happening when the error occurred
    """
    time_str = _now_ist()
    message = (
        f"⚠️ <b>System Error</b>\n\n"
        f"🔧 <b>Context:</b> {context}\n"
        f"❌ <b>Error:</b> {error[:500]}\n"
        f"⏰ <b>Time:</b> {time_str}\n\n"
        f"Check the admin panel for full logs."
    )
    await _send_message(message)


async def send_startup_notification() -> None:
    """Send a notification when the bot starts up."""
    time_str = _now_ist()
    message = (
        f"🚀 <b>Sports Bot Started</b>\n\n"
        f"⏰ <b>Time:</b> {time_str}\n"
        f"The booking scheduler is now active."
    )
    await _send_message(message)
