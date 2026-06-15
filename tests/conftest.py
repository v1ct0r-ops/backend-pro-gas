"""
conftest.py — Infraestructura central de tests para Pro-Gas ERP.

MECANISMO DE AISLAMIENTO
-------------------------
El bloque "safety guard" (ejecutado a nivel de módulo, antes de cualquier
import de la app) valida TEST_DATABASE_URL y sobreescribe DATABASE_URL en
os.environ.  Como pydantic-settings prioriza las variables de entorno sobre
el archivo .env, cualquier Settings() subsiguiente —incluido el de
app/core/config.py— leerá la URL de la BD de test.  En consecuencia,
database.engine, database.SessionLocal y el engine de main.py apuntan TODOS
a la BD de test sin necesitar parchear fixtures.

Los tests ACID (test_ventas_acidas.py, test_anulacion_cierre_diario.py)
definen sus propios fixtures fastapi_app/session_factory; estos sombrean los
de conftest para sus archivos pero igualmente apuntan a la BD de test porque
leen DATABASE_URL del entorno (ya redirigido aquí).

Los tests con MagicMock no tocan la BD; el autouse clean_tables ejecuta un
TRUNCATE vacío que es prácticamente instantáneo sobre tablas sin datos.
"""
import os

import pytest
from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------
# SAFETY GUARD — se ejecuta durante la recolección, antes de cualquier import
# ---------------------------------------------------------------------------
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
_DEV_DB_URL  = os.environ.get("DATABASE_URL", "").strip()

if not _TEST_DB_URL:
    raise RuntimeError(
        "\n\n"
        "[ERROR] TEST_DATABASE_URL no esta definida.\n"
        "   Los tests se niegan a arrancar sin una BD de test dedicada.\n\n"
        "   PowerShell:\n"
        "     $env:TEST_DATABASE_URL = "
        "'postgresql+psycopg2://victo:local_password@localhost:5433/pro_gas_test'\n"
        "   bash/zsh:\n"
        "     export TEST_DATABASE_URL="
        "'postgresql+psycopg2://victo:local_password@localhost:5433/pro_gas_test'\n\n"
        "   Asegurate de que Docker este corriendo.\n"
        "   conftest intentara crear la BD automaticamente si el usuario\n"
        "   tiene privilegio CREATEDB.\n"
    )

if _TEST_DB_URL == _DEV_DB_URL:
    raise RuntimeError(
        "\n\n"
        "[ERROR] TEST_DATABASE_URL es identica a DATABASE_URL.\n"
        "   Los tests deben apuntar a una BD distinta (ej. pro_gas_test).\n"
        "   Contaminar la BD de desarrollo esta PROHIBIDO.\n"
    )

_test_db_name = _TEST_DB_URL.split("?")[0].rsplit("/", 1)[-1].lower()
if "test" not in _test_db_name:
    raise RuntimeError(
        f"\n\n"
        f"[ERROR] El nombre de la BD de test ('{_test_db_name}') no contiene 'test'.\n"
        f"   Usa un nombre como 'pro_gas_test' para prevenir accidentes con datos reales.\n"
    )

# Redirigir DATABASE_URL para que TODOS los imports posteriores usen la BD de test.
# pydantic-settings: env vars > .env file > defaults.
# conftest.py se carga antes que cualquier módulo de test → el engine de database.py
# y el de app/core/config.py se crean apuntando a TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = _TEST_DB_URL

# ---------------------------------------------------------------------------
# Imports de la app — seguros ahora que DATABASE_URL → BD de test
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402
import database as db_module               # noqa: E402
# db_module.engine y db_module.SessionLocal ya apuntan a la BD de test porque
# database.py leyó settings.DATABASE_URL = TEST_DATABASE_URL al importar.


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _ensure_test_db_exists(db_name: str, test_url: str) -> None:
    """
    Crea la BD de test si no existe, conectando a la BD de mantenimiento 'postgres'
    con AUTOCOMMIT (CREATE DATABASE requiere estar fuera de una transacción).
    Si el usuario no tiene CREATEDB, imprime un warning y deja que create_all falle
    con un mensaje claro.
    """
    base = test_url.split("?")[0]                          # strip ?sslmode=… etc.
    maint_url = base.rsplit("/", 1)[0] + "/postgres"
    try:
        maint_engine = create_engine(
            maint_url,
            isolation_level="AUTOCOMMIT",
            connect_args={"connect_timeout": 10},
        )
        with maint_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": db_name},
            ).fetchone()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        maint_engine.dispose()
    except Exception as exc:
        print(f"\n[conftest] No se pudo auto-crear '{db_name}': {exc}")


# ---------------------------------------------------------------------------
# Fixture de sesión con autouse — se ejecuta UNA vez para toda la sesión
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Punto de entrada único para el esquema de test:
      1. Crea la BD si no existe (conectando a 'postgres' con AUTOCOMMIT).
      2. Crea el esquema con Base.metadata.create_all sobre el engine de test.
      3. En teardown: drop_all + dispose — la BD queda vacía de objetos.

    Al ser autouse + session-scoped, pytest lo ejecuta antes de cualquier otro
    fixture de la sesión, garantizando que el esquema exista cuando los tests
    ACID empiecen a crear datos.
    """
    _ensure_test_db_exists(_test_db_name, _TEST_DB_URL)

    from app.models.models import Base
    Base.metadata.create_all(bind=db_module.engine)

    yield

    from app.models.models import Base as _Base  # noqa: F811
    _Base.metadata.drop_all(bind=db_module.engine)
    db_module.engine.dispose()


# ---------------------------------------------------------------------------
# Fixtures de sesión — disponibles para todos los archivos de test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def session_factory(setup_test_db):
    """
    Fábrica de sesiones SQLAlchemy ligada al engine de test.

    Nota: test_ventas_acidas.py y test_anulacion_cierre_diario.py definen sus
    propios db_engine/session_factory (session/module scope) que sombrean este
    fixture para sus propios tests. Eso es intencional — ambos apuntan a la BD
    de test porque leen DATABASE_URL del entorno (ya redirigido arriba).
    """
    return db_module.SessionLocal


@pytest.fixture(scope="session")
def fastapi_app(setup_test_db):
    """
    Importa la app FastAPI de forma LAZY (dentro del fixture, no a nivel módulo)
    para evitar que main.py ejecute Base.metadata.create_all durante la fase de
    recolección de pytest, cuando Docker puede no estar activo.
    El create_all de main.py será un no-op: setup_test_db ya creó el esquema.
    """
    from main import app
    return app


@pytest.fixture(scope="session")
def client(fastapi_app):
    """
    TestClient síncrono de Starlette.

    Permite invocar endpoints HTTP en tests sin levantar un servidor real.
    raise_server_exceptions=False garantiza que errores 4xx/5xx se traten
    como respuestas normales en lugar de lanzar excepciones en el test.
    """
    with TestClient(fastapi_app, raise_server_exceptions=False) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Fixture autouse por función — aislamiento determinístico entre tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tables(setup_test_db):
    """
    Trunca TODAS las tablas de la aplicación ANTES de cada test.

    • RESTART IDENTITY reinicia las secuencias (IDs desde 1 en cada test).
    • CASCADE resuelve el orden de claves foráneas automáticamente.
    • Corre *antes* del yield → cada test arranca con una BD vacía y limpia.

    Garantía de red: si un test aborta antes de ejecutar su bloque finally,
    el siguiente test igual arranca con estado limpio.

    Para tests con MagicMock (sin BD real), el TRUNCATE es una operación vacía
    prácticamente instantánea (ninguna fila que borrar).
    """
    from app.models.models import Base

    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if table_names:
        with db_module.engine.begin() as conn:
            conn.execute(
                text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
            )
    yield
