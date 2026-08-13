"""APScheduler 3.11 integration for booking task scheduling.

Manages cron-based scheduling of booking tasks:
- On startup: loads all enabled tasks from DB and schedules them
- Dynamic: add/remove/update jobs when tasks are modified via API
- Execution: fires the booking agent 2 minutes before trigger_time,
  then the agent handles precise timing with its retry burst

Uses AsyncIOScheduler which runs in the same event loop as FastAPI,
so no threading complications.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# IST timezone for trigger time interpretation
IST = ZoneInfo("Asia/Kolkata")

# Global scheduler instance (singleton)
scheduler = AsyncIOScheduler(timezone=IST)


def _job_id(task_id: uuid.UUID) -> str:
    """Generate a deterministic job ID from a task UUID."""
    return f"booking_task_{task_id}"


async def _execute_booking_job(
    task_id: str,
    sport: str,
    slot_time: str,
    website_url: str,
    username_encrypted: str,
    password_encrypted: str,
    fallback_slots: list[str],
) -> None:
    """Job function executed by the scheduler.

    This is the bridge between APScheduler and the booking agent.
    It runs the booking agent and handles notifications.
    """
    from app.agent.booking_agent import run_booking
    from app.notifications.telegram import notify_booking_result

    task_uuid = uuid.UUID(task_id)
    logger.info("⏰ Scheduler firing booking job for task %s (%s @ %s)", task_id[:8], sport, slot_time)

    try:
        result = await run_booking(
            task_id=task_uuid,
            sport=sport,
            slot_time=slot_time,
            website_url=website_url,
            username_encrypted=username_encrypted,
            password_encrypted=password_encrypted,
            fallback_slots=fallback_slots,
        )

        # Send notification
        await notify_booking_result(
            sport=sport,
            slot_time=slot_time,
            result=result,
        )

        logger.info(
            "Booking job completed for task %s: %s",
            task_id[:8],
            result.status.value,
        )

    except Exception as e:
        logger.error("Booking job crashed for task %s: %s", task_id[:8], e, exc_info=True)

        # Try to send error notification
        from app.notifications.telegram import send_error_notification
        await send_error_notification(
            error=str(e),
            context=f"Task {task_id[:8]} ({sport} @ {slot_time})",
        )


def schedule_task(
    task_id: uuid.UUID,
    sport: str,
    slot_time: str,
    trigger_time: str,
    website_url: str,
    username_encrypted: str,
    password_encrypted: str,
    fallback_slots: list[str] | None = None,
) -> None:
    """Schedule a booking task to run at the specified trigger time.

    The agent fires 2 minutes before the trigger_time to allow for
    login and navigation before the booking window opens.

    Args:
        task_id: Unique task identifier
        sport: Sport name
        slot_time: Target slot time
        trigger_time: When to trigger, format "HH:MM" in IST
        website_url: Portal URL
        username_encrypted: Encrypted username
        password_encrypted: Encrypted password
        fallback_slots: Optional backup slot times
    """
    job_id = _job_id(task_id)

    # Parse trigger time and subtract 2 minutes for early start
    parts = trigger_time.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) - 2  # Fire 2 minutes early

    # Handle minute underflow
    if minute < 0:
        minute += 60
        hour = (hour - 1) % 24

    # Remove existing job if it exists (for updates)
    remove_task(task_id)

    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=IST,
    )

    scheduler.add_job(
        _execute_booking_job,
        trigger=trigger,
        id=job_id,
        name=f"Book {sport} @ {slot_time}",
        kwargs={
            "task_id": str(task_id),
            "sport": sport,
            "slot_time": slot_time,
            "website_url": website_url,
            "username_encrypted": username_encrypted,
            "password_encrypted": password_encrypted,
            "fallback_slots": fallback_slots or [],
        },
        replace_existing=True,
        misfire_grace_time=120,  # Allow 2 minutes of delay before skipping
    )

    logger.info(
        "📅 Scheduled: %s @ %s → fires at %02d:%02d IST (2 min early)",
        sport,
        slot_time,
        hour,
        minute,
    )


def remove_task(task_id: uuid.UUID) -> None:
    """Remove a scheduled booking task."""
    job_id = _job_id(task_id)
    try:
        scheduler.remove_job(job_id)
        logger.info("Removed scheduled job: %s", job_id)
    except Exception:
        pass  # Job doesn't exist — that's fine


def get_scheduled_jobs() -> list[dict]:
    """Return info about all scheduled jobs.

    Returns:
        List of dicts with job details (id, name, next_run_time)
    """
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": (
                job.next_run_time.isoformat() if job.next_run_time else None
            ),
            "trigger": str(job.trigger),
        })
    return jobs


async def load_tasks_from_db() -> None:
    """Load all enabled booking tasks from the database and schedule them.

    Called on application startup.
    """
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.task import BookingTask

    logger.info("Loading booking tasks from database...")

    async with async_session_factory() as session:
        result = await session.execute(
            select(BookingTask).where(BookingTask.enabled == True)  # noqa: E712
        )
        tasks = result.scalars().all()

    for task in tasks:
        schedule_task(
            task_id=task.id,
            sport=task.sport,
            slot_time=task.slot_time,
            trigger_time=task.trigger_time,
            website_url=task.website_url,
            username_encrypted=task.username_encrypted,
            password_encrypted=task.password_encrypted,
            fallback_slots=task.fallback_slots,
        )

    logger.info("Loaded %d booking tasks", len(tasks))


def start_scheduler() -> None:
    """Start the APScheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("🚀 Scheduler started")


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
