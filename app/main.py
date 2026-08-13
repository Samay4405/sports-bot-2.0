"""FastAPI application — main entry point.

Configures:
- Lifespan: scheduler startup/shutdown + DB initialization
- API routers: tasks, runs, system
- Admin panel: Jinja2 template routes
- Static files: CSS, JS
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    from app.database import init_db
    from app.scheduler.manager import load_tasks_from_db, start_scheduler, shutdown_scheduler
    from app.notifications.telegram import send_startup_notification

    logger.info("🚀 Starting Sports Bot v2...")

    # Initialize database tables (dev mode — use Alembic in production)
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        logger.warning("Continuing without DB — some features will be unavailable")

    # Start the scheduler
    start_scheduler()

    # Load tasks from DB and schedule them
    try:
        await load_tasks_from_db()
    except Exception as e:
        logger.error("Failed to load tasks from DB: %s", e)

    # Send startup notification
    try:
        await send_startup_notification()
    except Exception:
        pass  # Non-critical

    logger.info("✅ Sports Bot v2 is ready!")

    yield

    # Shutdown
    logger.info("Shutting down Sports Bot v2...")
    shutdown_scheduler()
    logger.info("Goodbye! 👋")


# ─── Create App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sports Bot v2",
    description="Agentic sports slot booking bot with LLM-driven browser automation",
    version="2.0.0",
    lifespan=lifespan,
)

# ─── Mount Static Files ───────────────────────────────────────────────────────

static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ─── Include API Routers ──────────────────────────────────────────────────────

from app.api.tasks import router as tasks_router
from app.api.runs import router as runs_router
from app.api.system import router as system_router

app.include_router(tasks_router)
app.include_router(runs_router)
app.include_router(system_router)

# ─── Template Setup ───────────────────────────────────────────────────────────

templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# ─── Admin Panel Routes ───────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Admin dashboard — overview of tasks and recent runs."""
    from sqlalchemy import select, func
    from app.database import async_session_factory
    from app.models.task import BookingTask
    from app.models.run import BookingRun
    from app.scheduler.manager import get_scheduled_jobs

    async with async_session_factory() as session:
        # Get task counts
        total_tasks = (await session.execute(select(func.count(BookingTask.id)))).scalar() or 0
        enabled_tasks = (
            await session.execute(
                select(func.count(BookingTask.id)).where(BookingTask.enabled == True)  # noqa: E712
            )
        ).scalar() or 0

        # Get recent runs
        recent_runs_result = await session.execute(
            select(BookingRun).order_by(BookingRun.executed_at.desc()).limit(10)
        )
        recent_runs = recent_runs_result.scalars().all()

        # Get all tasks for the list
        tasks_result = await session.execute(
            select(BookingTask).order_by(BookingTask.created_at.desc())
        )
        tasks = tasks_result.scalars().all()

    scheduled_jobs = get_scheduled_jobs()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "recent_runs": recent_runs,
            "tasks": tasks,
            "scheduled_jobs": scheduled_jobs,
        },
    )
