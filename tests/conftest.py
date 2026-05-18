"""
conftest.py — Infraestructura central de testing (cargado automáticamente por pytest).

¿Por qué conftest.py?
    pytest descubre y carga este archivo ANTES de ejecutar cualquier test.
    Los fixtures aquí definidos están disponibles en todos los archivos de
    la carpeta tests/ sin importación explícita. Es el único lugar donde
    centralizar el TestClient, overrides de dependencias, y la estrategia
    de aislamiento de base de datos.

Estrategia de BD:
    - Tests UNITARIOS (test_cierres.py): usan MagicMock — cero conexiones a BD.
    - Tests ACID (test_ventas_acidas.py): conectan a PostgreSQL real (Docker local).
    El fixture `client` aquí provisto sirve para futuros tests de integración
    HTTP sin tocar el entorno ACID.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    """
    Importación LAZY de la app FastAPI.

    No se importa a nivel de módulo para evitar que main.py ejecute
    Base.metadata.create_all(bind=engine) durante la fase de recolección
    (collection) de pytest, cuando Docker puede no estar activo.
    La importación ocurre en la fase de ejecución, donde la BD ya está lista.
    """
    from main import app as fastapi_app  # noqa: PLC0415
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """
    TestClient síncrono de Starlette.

    Permite invocar endpoints HTTP en tests sin levantar un servidor real.
    raise_server_exceptions=False garantiza que errores 4xx/5xx se traten
    como respuestas normales en lugar de lanzar excepciones en el test.
    """
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
