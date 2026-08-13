"""BookingRun and RunLog models — execution history and diagnostics.

BookingRun tracks each booking attempt (success/failure/error).
RunLog stores step-by-step logs including the LLM's reasoning at each step,
enabling detailed post-mortem debugging.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class RunStatus(str, Enum):
    """Possible outcomes of a booking run."""

    SUCCESS = "success"
    FAILED = "failed"
    NO_SLOTS = "no_slots"
    ERROR = "error"
    RUNNING = "running"


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class BookingRun(SQLModel, table=True):
    """A single execution of a booking task."""

    __tablename__ = "booking_runs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="Unique run identifier",
    )
    task_id: uuid.UUID = Field(
        ...,
        foreign_key="booking_tasks.id",
        index=True,
        description="The task that spawned this run",
    )

    # ── Outcome ───────────────────────────────────────────────────────────
    status: RunStatus = Field(
        default=RunStatus.RUNNING,
        description="Current status of this run",
    )
    attempt_count: int = Field(
        default=0,
        description="Number of booking attempts made during this run",
    )
    summary: str = Field(
        default="",
        max_length=1000,
        description="Human-readable outcome summary",
    )

    # ── Diagnostics ───────────────────────────────────────────────────────
    screenshot_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Path to failure screenshot (if any)",
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the run started (UTC)",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When the run finished (UTC)",
    )

    def __repr__(self) -> str:
        icon = {
            RunStatus.SUCCESS: "✅",
            RunStatus.FAILED: "❌",
            RunStatus.NO_SLOTS: "🚫",
            RunStatus.ERROR: "💥",
            RunStatus.RUNNING: "🔄",
        }.get(self.status, "❓")
        return f"<BookingRun {icon} {self.status.value} attempts={self.attempt_count}>"


class RunLog(SQLModel, table=True):
    """A single log entry within a booking run.

    Captures both human-readable messages and the LLM's reasoning
    at each step, enabling full post-mortem analysis.
    """

    __tablename__ = "run_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    run_id: uuid.UUID = Field(
        ...,
        foreign_key="booking_runs.id",
        index=True,
        description="The run this log entry belongs to",
    )

    # ── Content ───────────────────────────────────────────────────────────
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this log was recorded (UTC)",
    )
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log severity level",
    )
    message: str = Field(
        ...,
        max_length=2000,
        description="Human-readable log message",
    )
    reasoning: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="LLM's reasoning at this step (if applicable)",
    )

    def __repr__(self) -> str:
        return f"<RunLog [{self.level.value.upper()}] {self.message[:60]}>"
