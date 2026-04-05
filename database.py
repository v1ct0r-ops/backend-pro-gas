from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


# Synchronous engine - appropriate for a standard FastAPI + psycopg2 setup.
# For async (asyncpg driver), see the migration notes at the bottom of this file.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,    # Verifies connection health before each use (needed for Neon.tech)
    pool_recycle=300,      # Recycle connections every 5 minutes
    pool_size=5,           # Neon.tech free tier has a connection limit (~10 max)
    max_overflow=10,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """All SQLAlchemy models should inherit from this Base."""
    pass


def get_db():
    """
    FastAPI dependency that provides a database session.

    Usage in a route:
        from sqlalchemy.orm import Session
        from fastapi import Depends
        from database import get_db

        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Executes a trivial SELECT 1 query to verify database connectivity.
    Returns True on success, raises an exception on failure.
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


# ---------------------------------------------------------------------------
# ASYNC MIGRATION NOTES (for future reference):
#
# If you want to switch to async SQLAlchemy with Neon.tech:
#   1. Replace psycopg2-binary with: asyncpg==0.29.0
#   2. Change DATABASE_URL prefix: postgresql+psycopg2 -> postgresql+asyncpg
#      Remove ?sslmode=require from the URL string; pass ssl via connect_args:
#        connect_args={"ssl": "require"}
#   3. Use:
#        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
#        from sqlalchemy.orm import async_sessionmaker
#   4. Replace create_engine -> create_async_engine
#   5. Replace sessionmaker -> async_sessionmaker
#   6. All DB operations become async/await
#
# The synchronous approach is simpler and fully sufficient for this project's scale.
# ---------------------------------------------------------------------------
