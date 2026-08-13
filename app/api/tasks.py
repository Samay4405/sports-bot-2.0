"""CRUD API for booking tasks.

Endpoints:
- GET    /api/tasks          — list all tasks
- POST   /api/tasks          — create a new task
- GET    /api/tasks/{id}     — get a single task
- PUT    /api/tasks/{id}     — update a task
- DELETE /api/tasks/{id}     — delete a task
- POST   /api/tasks/{id}/toggle  — enable/disable a task
- POST   /api/tasks/{id}/trigger — manually trigger a booking run
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.task import BookingTask
from app.security.crypto import encrypt

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ─── Request/Response Schemas ──────────────────────────────────────────────────


class TaskCreate(BaseModel):
    """Schema for creating a new booking task."""

    sport: str = Field(..., min_length=1, max_length=100)
    slot_time: str = Field(..., min_length=1, max_length=50)
    website_url: str = Field(default="https://sports.mitwpu.edu.in", max_length=500)
    username: str = Field(..., min_length=1, description="Plaintext — will be encrypted")
    password: str = Field(..., min_length=1, description="Plaintext — will be encrypted")
    trigger_time: str = Field(
        ...,
        pattern=r"^\d{2}:\d{2}$",
        description="HH:MM in IST",
    )
    fallback_slots: list[str] = Field(default_factory=list)
    notes: str | None = None


class TaskUpdate(BaseModel):
    """Schema for updating a booking task."""

    sport: str | None = None
    slot_time: str | None = None
    website_url: str | None = None
    username: str | None = Field(default=None, description="Plaintext — will be re-encrypted")
    password: str | None = Field(default=None, description="Plaintext — will be re-encrypted")
    trigger_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    fallback_slots: list[str] | None = None
    notes: str | None = None


class TaskResponse(BaseModel):
    """Schema for task in API responses (no encrypted data exposed)."""

    id: uuid.UUID
    sport: str
    slot_time: str
    website_url: str
    trigger_time: str
    enabled: bool
    fallback_slots: list[str]
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[TaskResponse])
async def list_tasks(session: AsyncSession = Depends(get_session)):
    """List all booking tasks."""
    result = await session.execute(select(BookingTask).order_by(BookingTask.created_at.desc()))
    tasks = result.scalars().all()
    return tasks


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, session: AsyncSession = Depends(get_session)):
    """Create a new booking task with encrypted credentials."""
    key = settings.encryption_key_bytes

    task = BookingTask(
        sport=data.sport,
        slot_time=data.slot_time,
        website_url=data.website_url,
        username_encrypted=encrypt(data.username, key),
        password_encrypted=encrypt(data.password, key),
        trigger_time=data.trigger_time,
        fallback_slots=data.fallback_slots,
        notes=data.notes,
    )

    session.add(task)
    await session.flush()
    await session.refresh(task)

    # Schedule the task
    from app.scheduler.manager import schedule_task

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

    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Get a single booking task by ID."""
    task = await session.get(BookingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a booking task. Re-encrypts credentials if changed."""
    task = await session.get(BookingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    key = settings.encryption_key_bytes

    # Update fields that were provided
    if data.sport is not None:
        task.sport = data.sport
    if data.slot_time is not None:
        task.slot_time = data.slot_time
    if data.website_url is not None:
        task.website_url = data.website_url
    if data.username is not None:
        task.username_encrypted = encrypt(data.username, key)
    if data.password is not None:
        task.password_encrypted = encrypt(data.password, key)
    if data.trigger_time is not None:
        task.trigger_time = data.trigger_time
    if data.fallback_slots is not None:
        task.fallback_slots = data.fallback_slots
    if data.notes is not None:
        task.notes = data.notes

    task.updated_at = datetime.now(timezone.utc)

    session.add(task)
    await session.flush()
    await session.refresh(task)

    # Re-schedule if the task is enabled
    if task.enabled:
        from app.scheduler.manager import schedule_task

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

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Delete a booking task and remove its scheduled job."""
    task = await session.get(BookingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Remove from scheduler
    from app.scheduler.manager import remove_task

    remove_task(task_id)

    await session.delete(task)


@router.post("/{task_id}/toggle", response_model=TaskResponse)
async def toggle_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Toggle a task's enabled status."""
    task = await session.get(BookingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.enabled = not task.enabled
    task.updated_at = datetime.now(timezone.utc)

    session.add(task)
    await session.flush()
    await session.refresh(task)

    from app.scheduler.manager import schedule_task, remove_task

    if task.enabled:
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
    else:
        remove_task(task_id)

    return task


@router.post("/{task_id}/trigger", response_model=dict)
async def trigger_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Manually trigger a booking run for a task (runs immediately)."""
    import asyncio

    task = await session.get(BookingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Fire the booking agent in the background
    from app.agent.booking_agent import run_booking

    asyncio.create_task(
        run_booking(
            task_id=task.id,
            sport=task.sport,
            slot_time=task.slot_time,
            website_url=task.website_url,
            username_encrypted=task.username_encrypted,
            password_encrypted=task.password_encrypted,
            fallback_slots=task.fallback_slots,
        )
    )

    return {"message": f"Booking triggered for {task.sport} @ {task.slot_time}"}
