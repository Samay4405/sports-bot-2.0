"""BookingTask model — represents a scheduled booking job.

Each task defines what sport/slot to book, when to trigger, and the
encrypted credentials needed to authenticate on the sports portal.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class BookingTask(SQLModel, table=True):
    """A scheduled booking task for a specific sport and time slot."""

    __tablename__ = "booking_tasks"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="Unique task identifier",
    )

    # ── What to book ──────────────────────────────────────────────────────
    sport: str = Field(
        ...,
        max_length=100,
        description='Sport name as shown on the portal, e.g. "Swimming Pool"',
    )
    slot_time: str = Field(
        ...,
        max_length=50,
        description='Target slot time, e.g. "5:00 PM – 5:40 PM"',
    )
    website_url: str = Field(
        default="https://sports.mitwpu.edu.in",
        max_length=500,
        description="Sports portal URL",
    )

    # ── Credentials (encrypted at rest) ───────────────────────────────────
    username_encrypted: str = Field(
        ...,
        description="AES-256-GCM encrypted username (hex-encoded ciphertext)",
    )
    password_encrypted: str = Field(
        ...,
        description="AES-256-GCM encrypted password (hex-encoded ciphertext)",
    )

    # ── Scheduling ────────────────────────────────────────────────────────
    trigger_time: str = Field(
        ...,
        max_length=5,
        description='When to trigger the booking attempt, e.g. "05:00" (HH:MM in IST)',
    )
    enabled: bool = Field(
        default=True,
        description="Whether this task is active and scheduled",
    )

    # ── Fallback strategy ─────────────────────────────────────────────────
    fallback_slots: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=[]),
        description='Backup slot times to try if primary is full, e.g. ["6:00 PM – 6:40 PM"]',
    )

    # ── Metadata ──────────────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the task was created (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the task was last updated (UTC)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional user notes about this task",
    )

    def __repr__(self) -> str:
        status = "✅" if self.enabled else "⏸️"
        return f"<BookingTask {status} {self.sport} @ {self.slot_time} [{self.trigger_time}]>"
