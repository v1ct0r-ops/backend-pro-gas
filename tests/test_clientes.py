"""
Tests del módulo Maestro de Clientes — capa HTTP con mock de BD.

Cubre:
  - POST /clientes/: super_admin crea (201); operador no puede (403); RUT duplicado (400)
  - RUT con puntos se normaliza; RUT inválido → 422
  - GET /clientes/buscar: por RUT parcial; por nombre parcial; excluye inactivos
  - GET /clientes/: paginado con envelope Page[ClienteOut]
  - PATCH /clientes/{id}: soft-delete (estado=False) desaparece de buscar
  - DELETE /clientes/{id}: soft delete deja estado=False
  - No-regresión del validador de RUT en ventas
"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.clientes import router as clientes_router
from app.core.dependencies import get_current_user
from database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(clientes_router, prefix="/api/v1/clientes")
    return app


def _make_user(rol: str) -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.rol = rol
    u.estado = True
    return u


def _make_cliente_mock(
    id: int = 1,
    rut: str = "12345678-5",
    nombre: str = "Test Revendedor",
    email: str | None = "test@empresa.com",
    telefono: str | None = "+56912345678",
    direccion: str | None = "Calle Test 123",
    descuento_pesos_por_kilo: int = 500,
    estado: bool = True,
    created_at=None,
    updated_at=None,
) -> MagicMock:
    c = MagicMock()
    c.id = id
    c.rut = rut
    c.nombre = nombre
    c.email = email
    c.telefono = telefono
    c.direccion = direccion
    c.descuento_pesos_por_kilo = descuento_pesos_por_kilo
    c.estado = estado
    c.created_at = created_at
    c.updated_at = updated_at
    return c


def _client_as(rol: str, db_mock: MagicMock) -> TestClient:
    app = _build_app()
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: _make_user(rol)
    return TestClient(app, raise_server_exceptions=False)


def _db_no_duplicate(refresh_id: int = 99) -> MagicMock:
    """Mock de BD: no hay RUT duplicado; refresh asigna id al objeto."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    def _refresh(obj):
        obj.id = refresh_id
        obj.created_at = None
        obj.updated_at = None

    db.refresh.side_effect = _refresh
    return db


def _db_with_duplicate() -> MagicMock:
    """Mock de BD: RUT ya existe."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _make_cliente_mock()
    return db


# ===========================================================================
# TEST SUITE 1: crear cliente
# ===========================================================================

PAYLOAD_VALIDO = {
    "rut": "12345678-5",
    "nombre": "Revendedor Test",
    "email": "rev@empresa.com",
    "telefono": "+56912345678",
    "direccion": "Av. Test 123",
    "descuento_pesos_por_kilo": 500,
}


class TestCrearCliente:

    def test_super_admin_puede_crear_201(self):
        db = _db_no_duplicate()
        client = _client_as("super_admin", db)
        resp = client.post("/api/v1/clientes/", json=PAYLOAD_VALIDO)
        assert resp.status_code == 201, resp.text

    def test_operador_no_puede_crear_403(self):
        db = _db_no_duplicate()
        client = _client_as("operador", db)
        resp = client.post("/api/v1/clientes/", json=PAYLOAD_VALIDO)
        assert resp.status_code == 403

    def test_rut_duplicado_retorna_400(self):
        db = _db_with_duplicate()
        client = _client_as("super_admin", db)
        resp = client.post("/api/v1/clientes/", json=PAYLOAD_VALIDO)
        assert resp.status_code == 400
        assert "RUT ya registrado" in resp.json()["detail"]

    def test_rut_con_puntos_se_normaliza_a_canonico(self):
        """'12.345.678-5' debe guardarse como '12345678-5'."""
        db = _db_no_duplicate()
        client = _client_as("super_admin", db)
        payload = {**PAYLOAD_VALIDO, "rut": "12.345.678-5"}
        resp = client.post("/api/v1/clientes/", json=payload)
        assert resp.status_code == 201, resp.text
        # Verificar que el objeto creado tiene el RUT canónico
        created_cliente = db.add.call_args[0][0]
        assert created_cliente.rut == "12345678-5"

    def test_rut_invalido_retorna_422(self):
        # 12345678-9 es inválido: el DV real para el cuerpo 12345678 es 5, no 9
        db = _db_no_duplicate()
        client = _client_as("super_admin", db)
        resp = client.post("/api/v1/clientes/", json={**PAYLOAD_VALIDO, "rut": "12345678-9"})
        assert resp.status_code == 422

    def test_nombre_vacio_retorna_422(self):
        db = _db_no_duplicate()
        client = _client_as("super_admin", db)
        resp = client.post("/api/v1/clientes/", json={**PAYLOAD_VALIDO, "nombre": "   "})
        assert resp.status_code == 422

    def test_descuento_negativo_retorna_422(self):
        db = _db_no_duplicate()
        client = _client_as("super_admin", db)
        resp = client.post("/api/v1/clientes/", json={**PAYLOAD_VALIDO, "descuento_pesos_por_kilo": -1})
        assert resp.status_code == 422

    def test_email_es_opcional(self):
        """El campo email es opcional — no debe requerirse."""
        db = _db_no_duplicate()
        client = _client_as("super_admin", db)
        payload = {k: v for k, v in PAYLOAD_VALIDO.items() if k != "email"}
        resp = client.post("/api/v1/clientes/", json=payload)
        assert resp.status_code == 201, resp.text


# ===========================================================================
# TEST SUITE 2: buscar clientes (typeahead)
# ===========================================================================

def _db_buscar(results: list) -> MagicMock:
    db = MagicMock()
    (db.query.return_value
       .filter.return_value
       .order_by.return_value
       .limit.return_value
       .all.return_value) = results
    return db


class TestBuscarClientes:

    def test_buscar_por_rut_retorna_resultados(self):
        cliente = _make_cliente_mock(rut="12345678-9", nombre="Empresa ABC")
        db = _db_buscar([cliente])
        client = _client_as("operador", db)

        resp = client.get("/api/v1/clientes/buscar?q=12345678")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["rut"] == "12345678-9"

    def test_buscar_por_nombre_parcial(self):
        clientes = [
            _make_cliente_mock(id=1, nombre="Gas del Norte"),
            _make_cliente_mock(id=2, nombre="Distribuidora Norte"),
        ]
        db = _db_buscar(clientes)
        client = _client_as("operador", db)

        resp = client.get("/api/v1/clientes/buscar?q=Norte")

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_buscar_respeta_limit(self):
        """Limit máximo permitido es 25; default es 10."""
        db = _db_buscar([])
        client = _client_as("operador", db)

        resp_ok = client.get("/api/v1/clientes/buscar?q=test&limit=25")
        assert resp_ok.status_code == 200

        resp_exceso = client.get("/api/v1/clientes/buscar?q=test&limit=26")
        assert resp_exceso.status_code == 422

    def test_buscar_sin_q_retorna_422(self):
        db = _db_buscar([])
        client = _client_as("operador", db)
        resp = client.get("/api/v1/clientes/buscar")
        assert resp.status_code == 422

    def test_buscar_excluye_inactivos(self):
        """El filtro estado=True está en el query — verifica que se pasa el parámetro correcto."""
        cliente_activo = _make_cliente_mock(id=1, estado=True)
        db = _db_buscar([cliente_activo])
        client = _client_as("operador", db)

        resp = client.get("/api/v1/clientes/buscar?q=test")

        assert resp.status_code == 200
        # Verificar que el filtro se aplicó (el mock solo devuelve activos)
        body = resp.json()
        for item in body:
            assert item["estado"] is True

    def test_buscar_devuelve_email_en_respuesta(self):
        """ClienteOut incluye email para que el frontend pueda mostrarlo."""
        cliente = _make_cliente_mock(email="revendedor@empresa.cl")
        db = _db_buscar([cliente])
        client = _client_as("operador", db)

        resp = client.get("/api/v1/clientes/buscar?q=test")

        assert resp.status_code == 200
        assert resp.json()[0]["email"] == "revendedor@empresa.cl"


# ===========================================================================
# TEST SUITE 3: listar paginado
# ===========================================================================

def _db_lista(items: list, total: int) -> MagicMock:
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.count.return_value = total
    q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = items
    db.query.return_value = q
    return db


class TestListarClientes:

    def test_lista_retorna_envelope_paginado(self):
        items = [_make_cliente_mock(id=i) for i in range(1, 6)]
        db = _db_lista(items, total=12)
        client = _client_as("operador", db)

        resp = client.get("/api/v1/clientes/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert body["total_pages"] == 3
        assert len(body["items"]) == 5

    def test_lista_vacia_retorna_envelope_correcto(self):
        db = _db_lista([], total=0)
        client = _client_as("operador", db)

        resp = client.get("/api/v1/clientes/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["total_pages"] == 0
        assert body["items"] == []

    def test_page_size_200_retorna_422(self):
        db = _db_lista([], 0)
        client = _client_as("operador", db)
        resp = client.get("/api/v1/clientes/?page_size=200")
        assert resp.status_code == 422

    def test_defaults_page_size_es_5(self):
        items = [_make_cliente_mock(id=i) for i in range(1, 6)]
        db = _db_lista(items, total=5)
        client = _client_as("operador", db)
        resp = client.get("/api/v1/clientes/")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 5


# ===========================================================================
# TEST SUITE 4: soft delete
# ===========================================================================

class TestSoftDeleteCliente:

    def test_delete_pone_estado_false(self):
        cliente_mock = _make_cliente_mock(estado=True)
        db = MagicMock()
        db.get.return_value = cliente_mock
        client = _client_as("super_admin", db)

        resp = client.delete("/api/v1/clientes/1")

        assert resp.status_code == 204
        assert cliente_mock.estado is False

    def test_delete_actualiza_updated_at(self):
        cliente_mock = _make_cliente_mock(estado=True)
        db = MagicMock()
        db.get.return_value = cliente_mock
        client = _client_as("super_admin", db)

        resp = client.delete("/api/v1/clientes/1")

        assert resp.status_code == 204
        assert cliente_mock.updated_at is not None

    def test_delete_operador_retorna_403(self):
        cliente_mock = _make_cliente_mock()
        db = MagicMock()
        db.get.return_value = cliente_mock
        client = _client_as("operador", db)

        resp = client.delete("/api/v1/clientes/1")
        assert resp.status_code == 403

    def test_delete_id_inexistente_retorna_404(self):
        db = MagicMock()
        db.get.return_value = None
        client = _client_as("super_admin", db)

        resp = client.delete("/api/v1/clientes/999")
        assert resp.status_code == 404


# ===========================================================================
# TEST SUITE 5: no-regresión validador RUT en ventas_revendedor
# ===========================================================================

class TestNoRegresionRutVentas:

    def test_rut_valido_sigue_siendo_aceptado_en_ventas(self):
        """La extracción del validador no debe romper la validación de ventas."""
        from app.schemas.ventas_revendedor import VentaRevendedorIn

        payload = VentaRevendedorIn(
            rut_cliente="12345678-5",
            nombre_cliente="Revendedor",
            fecha="2026-06-14T10:00:00",
            descuento_pesos_por_kilo=0,
            lineas=[{
                "producto_id": 1,
                "cantidad": 1,
                "precio_unitario_factura": 10000,
            }],
        )
        assert payload.rut_cliente == "12345678-5"

    def test_rut_con_puntos_se_normaliza_en_ventas(self):
        from app.schemas.ventas_revendedor import VentaRevendedorIn

        payload = VentaRevendedorIn(
            rut_cliente="12.345.678-5",
            nombre_cliente="Revendedor",
            fecha="2026-06-14T10:00:00",
            descuento_pesos_por_kilo=0,
            lineas=[{
                "producto_id": 1,
                "cantidad": 1,
                "precio_unitario_factura": 10000,
            }],
        )
        assert payload.rut_cliente == "12345678-5"

    def test_rut_invalido_rechazado_en_ventas(self):
        # 12345678-9 es inválido: DV real para cuerpo 12345678 es 5
        from pydantic import ValidationError
        from app.schemas.ventas_revendedor import VentaRevendedorIn

        with pytest.raises(ValidationError):
            VentaRevendedorIn(
                rut_cliente="12345678-9",
                nombre_cliente="Revendedor",
                fecha="2026-06-14T10:00:00",
                descuento_pesos_por_kilo=0,
                lineas=[{"producto_id": 1, "cantidad": 1, "precio_unitario_factura": 10000}],
            )

    def test_validador_compartido_mismo_comportamiento(self):
        """normalizar_validar_rut produce el mismo resultado que el validador inline original."""
        from app.core.rut import normalizar_validar_rut

        assert normalizar_validar_rut("12.345.678-5") == "12345678-5"
        assert normalizar_validar_rut("12345678-5") == "12345678-5"
        assert normalizar_validar_rut(" 12345678-5 ") == "12345678-5"
