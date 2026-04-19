from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


# Motor síncrono con psycopg2. Suficiente para la escala actual del proyecto.
# Pool ajustado para Neon.tech, que tiene límite de conexiones en el plan gratuito (~10 max).
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,    # verifica la conexión antes de usarla (necesario con Neon.tech)
    pool_recycle=300,      # recicla conexiones cada 5 minutos
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependencia de FastAPI que provee una sesión de DB por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Ejecuta un SELECT 1 para verificar que la DB responde. Lanza excepción si falla."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


# ---------------------------------------------------------------------------
# NOTAS PARA MIGRACIÓN A ASYNC (por si en algún momento se necesita):
#
#   1. Cambiar psycopg2-binary por asyncpg==0.29.0
#   2. Prefijo DATABASE_URL: postgresql+psycopg2 → postgresql+asyncpg
#      Quitar ?sslmode=require del string; pasarlo así:
#        connect_args={"ssl": "require"}
#   3. Importar:
#        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
#        from sqlalchemy.orm import async_sessionmaker
#   4. Reemplazar create_engine → create_async_engine
#   5. Reemplazar sessionmaker → async_sessionmaker
#   6. Todas las operaciones de DB pasan a ser async/await
#
# Por ahora el modo síncrono es más simple y suficiente.
# ---------------------------------------------------------------------------
