"""
Tests del endpoint PATCH /inventario/{id}/precio — capa HTTP con mock de BD.

Cubre:
  - super_admin actualiza precio OK → 200
  - operador → 403
  - precio negativo → 400
  - producto inexistente → 404
"""
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.inventario import router as inventario_router
from app.core.dependencies import get_current_user
from database import get_db


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(inventario_router, prefix="/api/v1/inventario")
    return app


def _make_user(rol: str) -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.rol = rol
    u.estado = True
    return u


def _make_producto(
    id: int = 1,
    formato: str = "5kg",
    peso_kg: float = 5.0,
    precio_publico_base: int = 10000,
    stock_llenos: int = 10,
    stock_vacios: int = 5,
) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.formato = formato
    p.peso_kg = peso_kg
    p.precio_publico_base = precio_publico_base
    p.stock_llenos = stock_llenos
    p.stock_vacios = stock_vacios
    return p


def _client_as(rol: str, db_mock: MagicMock) -> TestClient:
    app = _build_app()
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: _make_user(rol)
    return TestClient(app, raise_server_exceptions=False)


def _db_for(producto: MagicMock | None) -> MagicMock:
    db = MagicMock()
    db.get.return_value = producto
    return db


class TestActualizarPrecio:

    def test_super_admin_actualiza_precio_ok(self):
        producto = _make_producto(precio_publico_base=10000)
        db = _db_for(producto)
        client = _client_as("super_admin", db)

        resp = client.patch("/api/v1/inventario/1/precio", json={"precio_publico_base": 15000})

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["precio_publico_base"] == 15000
        assert data["id"] == 1

    def test_precio_cero_es_valido(self):
        producto = _make_producto(precio_publico_base=10000)
        db = _db_for(producto)
        client = _client_as("super_admin", db)

        resp = client.patch("/api/v1/inventario/1/precio", json={"precio_publico_base": 0})

        assert resp.status_code == 200, resp.text
        assert resp.json()["precio_publico_base"] == 0

    def test_operador_no_puede_403(self):
        db = _db_for(_make_producto())
        client = _client_as("operador", db)

        resp = client.patch("/api/v1/inventario/1/precio", json={"precio_publico_base": 15000})

        assert resp.status_code == 403

    def test_precio_negativo_retorna_400(self):
        db = _db_for(_make_producto())
        client = _client_as("super_admin", db)

        resp = client.patch("/api/v1/inventario/1/precio", json={"precio_publico_base": -1})

        assert resp.status_code == 400
        assert "negativo" in resp.json()["detail"]

    def test_producto_inexistente_retorna_404(self):
        db = _db_for(None)
        client = _client_as("super_admin", db)

        resp = client.patch("/api/v1/inventario/99/precio", json={"precio_publico_base": 10000})

        assert resp.status_code == 404
        assert "Producto no encontrado" in resp.json()["detail"]
