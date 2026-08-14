"""Async SQLAlchemy engine and session management.

Provides:
- `engine`: Async SQLAlchemy engine (PostgreSQL or SQLite)
- `get_session()`: FastAPI dependency yielding an async session
- `init_db()`: Creates all tables (for development; use Alembic in production)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.config import settings

# Detect database type for engine configuration
_is_sqlite = settings.database_url.startswith("sqlite")

# Create the async engine with appropriate settings
_engine_kwargs = {
    "echo": False,
}

if not _is_sqlite:
    # PostgreSQL-specific settings
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)

# Session factory
async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Usage:
        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables defined by SQLModel metadata.

    Use this for development/testing only. In production, use Alembic migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
