from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.core.config import settings
from app.models.base import Base

# Create async engine with optimized pool settings
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_size=20,  # Maximum number of connections in the pool
    max_overflow=10,  # Maximum number of connections that can be created beyond pool_size
    pool_timeout=30,  # Seconds to wait before giving up on getting a connection
    pool_recycle=1800,  # Recycle connections after 30 minutes
    pool_pre_ping=True,  # Enable connection health checks
    poolclass=AsyncAdaptedQueuePool,  # Use queue-based pooling for async
    connect_args={
        "timeout": 10,  # Connection timeout in seconds
        "statement_timeout": 10000,  # Statement timeout in milliseconds
        "command_timeout": 10,  # Command timeout in seconds
        "keepalives": 1,  # Enable TCP keepalive
        "keepalives_idle": 30,  # Idle time before sending keepalive
        "keepalives_interval": 10,  # Interval between keepalives
        "keepalives_count": 5,  # Number of keepalive attempts
    }
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Create declarative base for models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close() 

async def init_db():
    """Initialize database with required extensions and settings."""
    async with engine.begin() as conn:
        # Enable pg_trgm extension for text search if using PostgreSQL
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        except Exception:
            pass  # Ignore if not PostgreSQL or extension already exists
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

async def dispose_db():
    """Properly dispose of database connections."""
    await engine.dispose() 