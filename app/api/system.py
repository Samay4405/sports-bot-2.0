"""System API — health checks and scheduler status.

Endpoints:
- GET /api/health           — health check (DB, scheduler)
- GET /api/scheduler/jobs   — list all scheduled jobs
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.scheduler.manager import get_scheduled_jobs, scheduler

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check — verifies database and scheduler are operational."""
    checks = {
        "status": "healthy",
        "database": "unknown",
        "scheduler": "unknown",
    }

    # Check database
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"
        checks["status"] = "degraded"

    # Check scheduler
    checks["scheduler"] = "running" if scheduler.running else "stopped"
    if not scheduler.running:
        checks["status"] = "degraded"

    return checks


@router.get("/scheduler/jobs")
async def list_scheduled_jobs():
    """List all scheduled booking jobs with their next fire times."""
    jobs = get_scheduled_jobs()
    return {
        "scheduler_running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
    }
