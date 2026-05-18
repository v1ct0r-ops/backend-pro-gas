"""
Tests de integración HTTP — capa de routers (sin BD real).

Estrategia: se monta una mini-app FastAPI con solo los routers bajo prueba.
Esto evita importar main.py y llamar a Base.metadata.create_all(),
por lo que los tests corren sin Docker ni conexión a PostgreSQL.

Las dependencias get_db y get_current_user se reemplazan con mocks
mediante app.dependency_overrides, aislando la capa HTTP completamente.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.cierres_diarios import router as cierres_router
from app.api.v1.inventario import router as inventario_router
from app.core.dependencies import get_current_user
from database import get_db


# ===========================================================================
# Helpers: mini-app y fixtures de cliente
# ===========================================================================

def _build_app() -> FastAPI:
    """
    Construye una app FastAPI mínima con los routers necesarios.
    Una nueva instancia por fixture para evitar contaminación entre tests.
    """
    app = FastAPI()
    app.include_router(cierres_router, prefix="/api/v1/cierres-diarios")
    app.include_router(inventario_router, prefix="/api/v1/inventario")
    return app


def _mock_usuario(rol: str) -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.rol = rol
    user.estado = True
    return user


@pytest.fixture
def client_operador():
    """TestClient autenticado como usuario con rol='operador'."""
    app = _build_app()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: _mock_usuario("operador")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def client_admin():
    """TestClient autenticado como usuario con rol='super_admin'."""
    app = _build_app()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: _mock_usuario("super_admin")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ===========================================================================
# TEST SUITE 1: validación de esquema — HTTP 422
# ===========================================================================

class TestValidacionEsquemaCierres:

    def test_post_sin_chofer_nombre_retorna_422(self, client_operador):
        """
        POST /api/v1/cierres-diarios/ sin el campo requerido 'chofer_nombre'
        debe ser rechazado por Pydantic con HTTP 422 Unprocessable Entity
        antes de que el servicio siquiera se ejecute.
        """
        payload_incompleto = {
            "fecha": "2026-05-16T10:00:00",
            "total_ventas_calc": 10_000,
            "efectivo_rendido": 8_000,
        }

        resp = client_operador.post("/api/v1/cierres-diarios/", json=payload_incompleto)

        assert resp.status_code == 422, (
            f"Esperado HTTP 422, recibido {resp.status_code}.\nBody: {resp.text}"
        )

        # Verificar que el error apunta al campo correcto
        detalle = resp.json().get("detail", [])
        campos_error = [e["loc"][-1] for e in detalle if "loc" in e]
        assert "chofer_nombre" in campos_error, (
            f"El 422 debería mencionar 'chofer_nombre'. Campos recibidos: {campos_error}"
        )

    def test_post_payload_vacio_retorna_422(self, client_operador):
        """Un payload completamente vacío {} debe retornar HTTP 422."""
        resp = client_operador.post("/api/v1/cierres-diarios/", json={})

        assert resp.status_code == 422

    def test_post_monto_negativo_retorna_422(self, client_operador):
        """
        El @field_validator de CierreDiarioCreate rechaza montos negativos.
        efectivo_rendido=-1 debe retornar HTTP 422 (validación Pydantic, no servicio).
        """
        payload_invalido = {
            "chofer_nombre": "Carlos Soto",
            "fecha": "2026-05-16T10:00:00",
            "efectivo_rendido": -1,
        }

        resp = client_operador.post("/api/v1/cierres-diarios/", json=payload_invalido)

        assert resp.status_code == 422


# ===========================================================================
# TEST SUITE 2: control de acceso por rol — HTTP 403
# ===========================================================================

class TestControlAccesoInventario:

    def test_patch_ajuste_con_operador_retorna_403(self, client_operador):
        """
        PATCH /api/v1/inventario/{id}/ajuste está protegido con require_role('super_admin').
        Un usuario con rol='operador' debe recibir HTTP 403 Forbidden.
        El servicio nunca se ejecuta.
        """
        payload_valido = {
            "delta_llenos": 10,
            "delta_vacios": 0,
            "motivo": "ajuste de prueba",
        }

        resp = client_operador.patch("/api/v1/inventario/1/ajuste", json=payload_valido)

        assert resp.status_code == 403, (
            f"Esperado HTTP 403, recibido {resp.status_code}.\nBody: {resp.text}"
        )
        assert "Permisos insuficientes" in resp.json().get("detail", ""), (
            f"Mensaje inesperado: {resp.json()}"
        )

    def test_patch_ajuste_con_admin_no_retorna_403(self, client_admin):
        """
        Un usuario 'super_admin' NO debe ser bloqueado por el control de acceso.
        El test verifica que el 403 no aparece (puede ser 404 por producto inexistente).
        """
        payload_valido = {
            "delta_llenos": 0,
            "delta_vacios": 0,
            "motivo": "verificación de acceso",
        }

        resp = client_admin.patch("/api/v1/inventario/999/ajuste", json=payload_valido)

        assert resp.status_code != 403, (
            f"El super_admin no debe recibir 403. Status: {resp.status_code}"
        )

    def test_get_inventario_con_operador_retorna_200(self, client_operador):
        """
        GET /api/v1/inventario/ solo requiere autenticación (cualquier rol).
        Un operador debe poder listar el inventario sin restricciones.
        """
        db_mock = MagicMock()
        db_mock.query.return_value.all.return_value = []

        app = _build_app()
        app.dependency_overrides[get_db] = lambda: db_mock
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario("operador")

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/inventario/")

        assert resp.status_code == 200
        assert resp.json() == []
