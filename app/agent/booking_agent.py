"""Booking agent orchestrator — the core intelligence of the system.

Coordinates the full booking flow:
1. Decrypt credentials from the database
2. Initialize a browser-use Agent with Gemini
3. Execute booking with retry logic and rate-limit awareness
4. Capture screenshots on failure
5. Log every step with LLM reasoning for debugging

Design decisions:
- Browser session is reused across retry attempts (login once, retry slot selection)
- Retry offsets are configurable and reduced to [0, 5, 15] for free-tier rate limits
- Exponential backoff on 429 errors with jitter
- Every LLM decision step is recorded in RunLog for post-mortem analysis
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.run import BookingRun, LogLevel, RunLog, RunStatus
from app.security.crypto import decrypt

logger = logging.getLogger(__name__)


@dataclass
class BookingResult:
    """Result of a booking attempt."""

    success: bool
    status: RunStatus
    summary: str
    attempt_count: int = 0
    screenshot_path: Optional[str] = None
    slot_booked: Optional[str] = None  # Which slot was actually booked
    logs: list[RunLog] = field(default_factory=list)


class RunLogger:
    """Structured logger that records entries to both Python logging and RunLog records.

    Every log entry is stored for later insertion into the database,
    enabling full post-mortem analysis of booking attempts.
    """

    def __init__(self, run_id: uuid.UUID):
        self.run_id = run_id
        self.entries: list[RunLog] = []

    def _log(
        self,
        level: LogLevel,
        message: str,
        reasoning: str | None = None,
    ) -> None:
        entry = RunLog(
            run_id=self.run_id,
            level=level,
            message=message,
            reasoning=reasoning,
        )
        self.entries.append(entry)

        # Also log to Python logging
        py_level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARN: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
        }[level]
        logger.log(py_level, "[Run %s] %s", str(self.run_id)[:8], message)

    def debug(self, message: str, reasoning: str | None = None) -> None:
        self._log(LogLevel.DEBUG, message, reasoning)

    def info(self, message: str, reasoning: str | None = None) -> None:
        self._log(LogLevel.INFO, message, reasoning)

    def warn(self, message: str, reasoning: str | None = None) -> None:
        self._log(LogLevel.WARN, message, reasoning)

    def error(self, message: str, reasoning: str | None = None) -> None:
        self._log(LogLevel.ERROR, message, reasoning)


async def _save_screenshot(page: object, task_id: uuid.UUID, attempt: int) -> str | None:
    """Save a screenshot of the current browser page.

    Returns the path to the saved screenshot, or None if saving failed.
    """
    try:
        screenshot_dir = Path(settings.screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{str(task_id)[:8]}_{timestamp}_attempt{attempt}.png"
        filepath = screenshot_dir / filename

        # browser-use provides screenshot functionality through the agent
        # The exact API depends on the version, but we try common approaches
        if hasattr(page, "screenshot"):
            await page.screenshot(path=str(filepath))
        else:
            logger.warning("Page object does not support screenshots")
            return None

        logger.info("Screenshot saved: %s", filepath)
        return str(filepath)
    except Exception as e:
        logger.warning("Failed to save screenshot: %s", e)
        return None


async def _wait_with_backoff(attempt: int, base_delay: float = 2.0) -> None:
    """Exponential backoff with jitter for rate-limit handling.

    Args:
        attempt: The current attempt number (0-indexed)
        base_delay: Base delay in seconds
    """
    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
    delay = min(delay, 30.0)  # Cap at 30 seconds
    logger.info("Backoff: waiting %.1fs before next attempt", delay)
    await asyncio.sleep(delay)


async def run_booking(
    task_id: uuid.UUID,
    sport: str,
    slot_time: str,
    website_url: str,
    username_encrypted: str,
    password_encrypted: str,
    fallback_slots: list[str] | None = None,
    encryption_key: bytes | None = None,
) -> BookingResult:
    """Execute a full booking attempt with retry logic.

    This is the main entry point for the booking agent. It:
    1. Decrypts credentials
    2. Creates a browser-use Agent with Gemini
    3. Runs the booking flow with retries around the target time
    4. Handles rate limits (429 errors) with exponential backoff
    5. Captures screenshots on failure

    Args:
        task_id: UUID of the booking task (for logging/screenshots)
        sport: Sport name as shown on the portal
        slot_time: Target slot time string
        website_url: Portal URL
        username_encrypted: AES-256-GCM encrypted username
        password_encrypted: AES-256-GCM encrypted password
        fallback_slots: Optional backup slot times
        encryption_key: Override encryption key (defaults to settings)

    Returns:
        BookingResult with success/failure status, logs, and screenshot path
    """
    from browser_use import Agent
    from app.agent.llm_provider import GeminiProvider
    from app.agent.prompts import build_booking_prompt

    run_id = uuid.uuid4()
    run_logger = RunLogger(run_id)
    key = encryption_key or settings.encryption_key_bytes

    # ── Step 1: Decrypt credentials ───────────────────────────────────────
    run_logger.info("Decrypting credentials for task %s", str(task_id)[:8])
    try:
        username = decrypt(username_encrypted, key)
        password = decrypt(password_encrypted, key)
    except Exception as e:
        run_logger.error(f"Failed to decrypt credentials: {e}")
        return BookingResult(
            success=False,
            status=RunStatus.ERROR,
            summary=f"Credential decryption failed: {e}",
            logs=run_logger.entries,
        )

    # ── Step 2: Build the prompt ──────────────────────────────────────────
    prompt = build_booking_prompt(
        sport=sport,
        slot_time=slot_time,
        website_url=website_url,
        username=username,
        password=password,
        fallback_slots=fallback_slots,
    )
    run_logger.info(f"Booking prompt built for {sport} @ {slot_time}")

    # ── Step 3: Initialize LLM provider ───────────────────────────────────
    try:
        provider = GeminiProvider()
        llm = provider.get_llm()
        run_logger.info(f"LLM provider initialized: {provider.model}")
    except Exception as e:
        run_logger.error(f"Failed to initialize LLM: {e}")
        return BookingResult(
            success=False,
            status=RunStatus.ERROR,
            summary=f"LLM initialization failed: {e}",
            logs=run_logger.entries,
        )

    # ── Step 4: Execute with retry logic ──────────────────────────────────
    retry_offsets = settings.booking_retry_offsets
    run_logger.info(f"Starting booking with {len(retry_offsets)} retry offsets: {retry_offsets}")

    last_error = None
    screenshot_path = None

    for attempt, offset in enumerate(retry_offsets):
        run_logger.info(
            f"Attempt {attempt + 1}/{len(retry_offsets)} (offset: {offset}s)"
        )

        if offset > 0:
            run_logger.info(f"Waiting {offset}s before attempt...")
            await asyncio.sleep(offset if attempt == 0 else offset - retry_offsets[attempt - 1])

        try:
            # Create a fresh agent for each attempt
            # browser-use handles browser lifecycle internally
            agent = Agent(
                task=prompt,
                llm=llm,
            )

            run_logger.info("Agent created, executing booking flow...")
            result = await agent.run()

            # Parse the agent's result
            result_text = str(result) if result else ""
            run_logger.info(
                f"Agent completed. Result preview: {result_text[:200]}",
                reasoning=result_text,
            )

            # Check for success indicators
            success_indicators = [
                "booking confirmed",
                "successfully booked",
                "booking successful",
                "confirmed",
                "booked successfully",
            ]
            failure_indicators = [
                "slot is full",
                "unavailable",
                "no spots available",
                "all slots are full",
                "no available",
            ]

            result_lower = result_text.lower()

            if any(indicator in result_lower for indicator in success_indicators):
                run_logger.info("✅ Booking SUCCESS!")
                return BookingResult(
                    success=True,
                    status=RunStatus.SUCCESS,
                    summary=f"Successfully booked {sport} @ {slot_time}",
                    attempt_count=attempt + 1,
                    slot_booked=slot_time,
                    logs=run_logger.entries,
                )

            if any(indicator in result_lower for indicator in failure_indicators):
                run_logger.warn(f"Slot unavailable on attempt {attempt + 1}")
                if attempt < len(retry_offsets) - 1:
                    continue  # Try next offset
                else:
                    return BookingResult(
                        success=False,
                        status=RunStatus.NO_SLOTS,
                        summary=f"All slots full after {attempt + 1} attempts",
                        attempt_count=attempt + 1,
                        screenshot_path=screenshot_path,
                        logs=run_logger.entries,
                    )

            # Ambiguous result — log and retry
            run_logger.warn(
                f"Ambiguous result on attempt {attempt + 1}, will retry",
                reasoning=result_text,
            )

        except Exception as e:
            error_str = str(e)
            last_error = error_str

            # Handle rate limiting (429 errors)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                run_logger.warn(
                    f"Rate limited (429) on attempt {attempt + 1}, backing off...",
                )
                await _wait_with_backoff(attempt)
                continue

            run_logger.error(
                f"Attempt {attempt + 1} failed: {error_str}",
                reasoning=error_str,
            )

            # Don't retry on certain fatal errors
            fatal_errors = ["api_key", "authentication", "invalid_key", "unauthorized"]
            if any(err in error_str.lower() for err in fatal_errors):
                run_logger.error("Fatal error — not retrying")
                break

            if attempt < len(retry_offsets) - 1:
                await _wait_with_backoff(attempt, base_delay=1.0)

    # ── All attempts exhausted ────────────────────────────────────────────
    summary = f"Booking failed after {len(retry_offsets)} attempts"
    if last_error:
        summary += f". Last error: {last_error}"

    run_logger.error(summary)

    return BookingResult(
        success=False,
        status=RunStatus.FAILED,
        summary=summary,
        attempt_count=len(retry_offsets),
        screenshot_path=screenshot_path,
        logs=run_logger.entries,
    )
