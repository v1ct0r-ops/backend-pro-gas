"""
Tests del módulo Usuarios — baja lógica, eliminación y salvaguardas.

Cubre:
  - PATCH estado=False: OK para otro usuario, auto-baja bloqueada (400),
    último super_admin bloqueado (409)
  - PATCH estado=True: reactivación OK
  - DELETE sin referencias: hard delete (204)
  - DELETE con referencias: soft-delete + 409
  - DELETE self: bloqueado (400)
  - DELETE último super_admin: bloqueado (409)
  - DELETE no encontrado: 404
  - DELETE operador: 403
"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.usuarios import router as usuarios_router
from app.core.dependencies import get_current_user
from database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(usuarios_router, prefix="/api/v1/usuarios")
    return app


def _make_user(id: int = 1, rol: str = "super_admin", estado: bool = True) -> MagicMock:
    u = MagicMock()
    u.id = id
    u.rol = rol
    u.estado = estado
    u.nombre = f"Usuario {id}"
    u.email = f"user{id}@test.com"
    return u


def _client_as(rol: str, db_mock: MagicMock, user_id: int = 1) -> TestClient:
    app = _build_app()
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: _make_user(id=user_id, rol=rol)
    return TestClient(app, raise_server_exceptions=False)


def _db_simple(target: MagicMock) -> MagicMock:
    """DB mock básico: get retorna target; query chain retorna valores neutros."""
    db = MagicMock()
    db.get.return_value = target
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 2
    return db


# ===========================================================================
# TEST SUITE 1: PATCH estado — salvaguardas
# ===========================================================================

class TestPatchEstadoSafeguards:

    def test_inhabilitar_otro_usuario_ok(self):
        """super_admin puede inhabilitar a un operador distinto."""
        target = _make_user(id=2, rol="operador", estado=True)
        db = _db_simple(target)
        client = _client_as("super_admin", db, user_id=1)

        resp = client.patch("/api/v1/usuarios/2", json={"estado": False})

        assert resp.status_code == 200
        assert target.estado is False

    def test_reactivar_usuario_ok(self):
        """super_admin puede reactivar a un usuario inactivo."""
        target = _make_user(id=2, rol="operador", estado=False)
        db = _db_simple(target)
        client = _client_as("super_admin", db, user_id=1)

        resp = client.patch("/api/v1/usuarios/2", json={"estado": True})

        assert resp.status_code == 200
        assert target.estado is True

    def test_auto_baja_bloqueada_400(self):
        """Un usuario no puede inhabilitarse a sí mismo vía PATCH."""
        target = _make_user(id=1, rol="super_admin", estado=True)
        db = _db_simple(target)
        client = _client_as("super_admin", db, user_id=1)

        resp = client.patch("/api/v1/usuarios/1", json={"estado": False})

        assert resp.status_code == 400
        assert "propia cuenta" in resp.json()["detail"]

    def test_ultimo_super_admin_bloqueado_patch_409(self):
        """No se puede inhabilitar al único super_admin activo."""
        target = _make_user(id=2, rol="super_admin", estado=True)
        db = _db_simple(target)
        db.query.return_value.filter.return_value.count.return_value = 1  # único activo
        client = _client_as("super_admin", db, user_id=1)

        resp = client.patch("/api/v1/usuarios/2", json={"estado": False})

        assert resp.status_code == 409
        assert "super_admin" in resp.json()["detail"]

    def test_patch_operador_sin_estado_no_usa_safeguards(self):
        """PATCH sin tocar estado no activa salvaguardas (sólo cambia nombre)."""
        target = _make_user(id=2, rol="operador", estado=True)
        db = _db_simple(target)
        client = _client_as("super_admin", db, user_id=1)

        resp = client.patch("/api/v1/usuarios/2", json={"nombre": "Nuevo Nombre"})

        assert resp.status_code == 200


# ===========================================================================
# TEST SUITE 2: DELETE — hard delete, soft delete y salvaguardas
# ===========================================================================

class TestDeleteUsuario:

    def test_delete_sin_referencias_hard_delete_204(self):
        """Sin registros asociados → hard delete físico, 204."""
        target = _make_user(id=2, rol="operador", estado=True)
        db = _db_simple(target)
        db.query.return_value.filter.return_value.first.return_value = None  # sin refs
        client = _client_as("super_admin", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/2")

        assert resp.status_code == 204
        db.delete.assert_called_once_with(target)

    def test_delete_con_referencias_soft_delete_409(self):
        """Con registros asociados → soft-delete (estado=False) y 409."""
        target = _make_user(id=2, rol="operador", estado=True)
        db = _db_simple(target)
        db.query.return_value.filter.return_value.first.return_value = MagicMock()  # tiene refs
        client = _client_as("super_admin", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/2")

        assert resp.status_code == 409
        assert "inhabilitado" in resp.json()["detail"]
        assert target.estado is False
        db.delete.assert_not_called()

    def test_delete_self_bloqueado_400(self):
        """Un usuario no puede eliminar su propia cuenta."""
        target = _make_user(id=1, rol="super_admin", estado=True)
        db = _db_simple(target)
        client = _client_as("super_admin", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/1")

        assert resp.status_code == 400
        assert "propia cuenta" in resp.json()["detail"]
        db.delete.assert_not_called()

    def test_delete_ultimo_super_admin_bloqueado_409(self):
        """No se puede eliminar al único super_admin activo."""
        target = _make_user(id=2, rol="super_admin", estado=True)
        db = _db_simple(target)
        db.query.return_value.filter.return_value.count.return_value = 1  # único activo
        client = _client_as("super_admin", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/2")

        assert resp.status_code == 409
        assert "super_admin" in resp.json()["detail"]
        db.delete.assert_not_called()

    def test_delete_no_encontrado_404(self):
        """Eliminar un id inexistente → 404."""
        db = MagicMock()
        db.get.return_value = None
        client = _client_as("super_admin", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/999")

        assert resp.status_code == 404

    def test_delete_operador_retorna_403(self):
        """Un operador no tiene permiso para eliminar usuarios."""
        db = MagicMock()
        client = _client_as("operador", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/2")

        assert resp.status_code == 403
        db.delete.assert_not_called()

    def test_delete_super_admin_inactivo_sin_refs_ok(self):
        """Eliminar un super_admin ya INACTIVO (no afecta conteo) sin refs → 204."""
        target = _make_user(id=2, rol="super_admin", estado=False)  # ya inactivo
        db = _db_simple(target)
        db.query.return_value.filter.return_value.first.return_value = None  # sin refs
        client = _client_as("super_admin", db, user_id=1)

        resp = client.delete("/api/v1/usuarios/2")

        assert resp.status_code == 204
        db.delete.assert_called_once_with(target)
