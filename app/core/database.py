"""Database configuration and session management."""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from sqlalchemy.pool import NullPool
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Convert DATABASE_URL to use asyncpg driver for async SQLAlchemy support
db_url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    db_url,
    poolclass=NullPool
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

async def init_db():
    """Initialize database on startup."""
    logger.info("Initializing database connection")

async def close_db():
    """Close database connection on shutdown."""
    logger.info("Closing database connection")
    await engine.dispose()

