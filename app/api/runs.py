"""Run history API.

Endpoints:
- GET /api/runs          — list recent runs
- GET /api/runs/{id}     — get a single run with its logs
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.run import BookingRun, RunLog, RunStatus, LogLevel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/runs", tags=["runs"])


# ─── Response Schemas ──────────────────────────────────────────────────────────


class RunResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    status: RunStatus
    attempt_count: int
    summary: str
    screenshot_path: Optional[str]
    executed_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class LogResponse(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    level: LogLevel
    message: str
    reasoning: Optional[str]

    model_config = {"from_attributes": True}


class RunDetailResponse(RunResponse):
    logs: list[LogResponse] = []


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[RunResponse])
async def list_runs(
    limit: int = Query(default=50, le=200),
    task_id: uuid.UUID | None = None,
    status: RunStatus | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List recent booking runs with optional filtering."""
    query = select(BookingRun).order_by(BookingRun.executed_at.desc()).limit(limit)

    if task_id:
        query = query.where(BookingRun.task_id == task_id)
    if status:
        query = query.where(BookingRun.status == status)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Get a single run with its full log entries."""
    run = await session.get(BookingRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Fetch logs for this run
    log_result = await session.execute(
        select(RunLog)
        .where(RunLog.run_id == run_id)
        .order_by(RunLog.timestamp.asc())
    )
    logs = log_result.scalars().all()

    return RunDetailResponse(
        **{c: getattr(run, c) for c in RunResponse.model_fields},
        logs=logs,
    )
