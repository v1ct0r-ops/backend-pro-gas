"""
Tests de paginación server-side — capa de routers con mock de BD.

Valida para medias_cargas (GET /), bitacora (GET /) y usuarios (GET /):
  - page=1 page_size=5 → 5 items y total correcto
  - page=2 → resto de items sin solapamiento con page 1
  - total_pages correcto
  - page_size=200 → 422
  - page=0 → 422
  - tabla vacía → items=[], total=0, total_pages=0
  - orden estable: recorrer todas las páginas no duplica ni omite ids
"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.bitacora import router as bitacora_router
from app.api.v1.medias_cargas import router as medias_cargas_router
from app.api.v1.usuarios import router as usuarios_router
from app.core.dependencies import get_current_user
from database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(medias_cargas_router, prefix="/api/v1/medias-cargas")
    app.include_router(bitacora_router, prefix="/api/v1/bitacora")
    app.include_router(usuarios_router, prefix="/api/v1/usuarios")
    return app


def _mock_usuario():
    user = MagicMock()
    user.id = 1
    user.rol = "operador"
    user.estado = True
    return user


def _mock_admin():
    user = MagicMock()
    user.id = 1
    user.rol = "super_admin"
    user.estado = True
    return user


def _make_item(id: int, model_fields: dict | None = None):
    """Crea un objeto mock con un id determinístico."""
    item = MagicMock()
    item.id = id
    if model_fields:
        for k, v in model_fields.items():
            setattr(item, k, v)
    return item


def _make_db_mock(items: list, total: int) -> MagicMock:
    """
    Simula db.query(Model) con soporte para count() y order_by/offset/limit/all.
    El mismo query_mock sirve para ambas rutas porque MagicMock encadena métodos.
    filter() devuelve el mismo mock para soportar filtros opcionales (ej. anulada==False).
    """
    query_mock = MagicMock()
    query_mock.count.return_value = total
    query_mock.filter.return_value = query_mock  # soporta .filter(...) encadenado
    # Cadena: .order_by(...).offset(...).limit(...).all() → items
    query_mock.order_by.return_value.offset.return_value.limit.return_value.all.return_value = items
    db = MagicMock()
    db.query.return_value = query_mock
    return db


@pytest.fixture
def client_with_items():
    """
    Fixture que retorna una función factory: client_with_items(items, total).
    Permite reusar la lógica en distintos tests con diferentes datos.
    """
    def _factory(items: list, total: int) -> TestClient:
        db_mock = _make_db_mock(items, total)
        app = _build_app()
        app.dependency_overrides[get_db] = lambda: db_mock
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario()
        return TestClient(app, raise_server_exceptions=False)

    return _factory


# ---------------------------------------------------------------------------
# Fixtures de datos — 12 items para poder recorrer 3 páginas de 5
# ---------------------------------------------------------------------------

TOTAL = 12
ALL_IDS = list(range(1, TOTAL + 1))  # [1..12]


def _make_medias_cargas_items(ids: list[int]):
    items = []
    for i in ids:
        mc = MagicMock()
        mc.id = i
        mc.numero_guia = f"SEED-{i:04d}"
        mc.proveedor = "Proveedor Seed"
        mc.total_neto = 100000
        mc.total_iva = 19000
        mc.total_bruto = 119000
        mc.kilos_totales = 11.0
        mc.fecha = "2026-01-01T00:00:00"
        mc.usuario_id = 1
        mc.lineas = []
        items.append(mc)
    return items


def _make_bitacora_items(ids: list[int]):
    items = []
    for i in ids:
        b = MagicMock()
        b.id = i
        b.cliente_nombre = f"Cliente {i}"
        b.telefono = f"+5691234{i:04d}"
        b.direccion = f"Calle {i}"
        b.detalle_pedido = f"Pedido {i}"
        b.fecha_hora = "2026-01-01T00:00:00"
        b.usuario_id = 1
        items.append(b)
    return items


# ===========================================================================
# TEST SUITE 1: medias-cargas
# ===========================================================================

class TestPaginacionMediasCargas:

    def test_page1_retorna_5_items_y_total(self, client_with_items):
        page1_items = _make_medias_cargas_items(ALL_IDS[:5])
        client = client_with_items(page1_items, TOTAL)

        resp = client.get("/api/v1/medias-cargas/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == TOTAL
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert len(body["items"]) == 5

    def test_total_pages_correcto(self, client_with_items):
        # 12 items / 5 por página = ceil(12/5) = 3 páginas
        page1_items = _make_medias_cargas_items(ALL_IDS[:5])
        client = client_with_items(page1_items, TOTAL)

        resp = client.get("/api/v1/medias-cargas/?page=1&page_size=5")

        assert resp.json()["total_pages"] == 3

    def test_page2_sin_solapamiento_con_page1(self, client_with_items):
        page1_ids = ALL_IDS[:5]
        page2_ids = ALL_IDS[5:10]

        # Primera llamada: página 1
        client1 = client_with_items(_make_medias_cargas_items(page1_ids), TOTAL)
        resp1 = client1.get("/api/v1/medias-cargas/?page=1&page_size=5")
        ids_page1 = {item["id"] for item in resp1.json()["items"]}

        # Segunda llamada: página 2
        client2 = client_with_items(_make_medias_cargas_items(page2_ids), TOTAL)
        resp2 = client2.get("/api/v1/medias-cargas/?page=2&page_size=5")
        ids_page2 = {item["id"] for item in resp2.json()["items"]}

        assert ids_page1.isdisjoint(ids_page2), (
            f"Solapamiento entre páginas: {ids_page1 & ids_page2}"
        )

    def test_orden_estable_sin_duplicados_ni_omisiones(self, client_with_items):
        """Recorre las 3 páginas y verifica que la unión sea exactamente ALL_IDS."""
        seen_ids: list[int] = []

        page_sizes = [ALL_IDS[:5], ALL_IDS[5:10], ALL_IDS[10:12]]
        for page_num, ids_chunk in enumerate(page_sizes, start=1):
            client = client_with_items(_make_medias_cargas_items(ids_chunk), TOTAL)
            resp = client.get(f"/api/v1/medias-cargas/?page={page_num}&page_size=5")
            seen_ids.extend(item["id"] for item in resp.json()["items"])

        assert sorted(seen_ids) == sorted(ALL_IDS), (
            f"IDs vistos: {seen_ids}\nEsperado: {ALL_IDS}"
        )
        assert len(seen_ids) == len(set(seen_ids)), "Hay IDs duplicados entre páginas"

    def test_page_size_200_retorna_422(self, client_with_items):
        client = client_with_items([], 0)
        resp = client.get("/api/v1/medias-cargas/?page_size=200")
        assert resp.status_code == 422

    def test_page_0_retorna_422(self, client_with_items):
        client = client_with_items([], 0)
        resp = client.get("/api/v1/medias-cargas/?page=0")
        assert resp.status_code == 422

    def test_tabla_vacia_retorna_envelope_correcto(self, client_with_items):
        client = client_with_items([], 0)
        resp = client.get("/api/v1/medias-cargas/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["total_pages"] == 0
        assert body["page"] == 1
        assert body["page_size"] == 5

    def test_defaults_page_size_es_5(self, client_with_items):
        """Sin params explícitos, page_size debe ser 5 (no 20 ni 50 del código viejo)."""
        client = client_with_items(_make_medias_cargas_items(ALL_IDS[:5]), TOTAL)
        resp = client.get("/api/v1/medias-cargas/")

        assert resp.status_code == 200
        assert resp.json()["page_size"] == 5


# ===========================================================================
# TEST SUITE 2: bitacora
# ===========================================================================

class TestPaginacionBitacora:

    def test_page1_retorna_5_items_y_total(self, client_with_items):
        page1_items = _make_bitacora_items(ALL_IDS[:5])
        client = client_with_items(page1_items, TOTAL)

        resp = client.get("/api/v1/bitacora/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == TOTAL
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert len(body["items"]) == 5

    def test_total_pages_con_12_items_y_5_por_pagina(self, client_with_items):
        client = client_with_items(_make_bitacora_items(ALL_IDS[:5]), TOTAL)
        resp = client.get("/api/v1/bitacora/?page=1&page_size=5")
        assert resp.json()["total_pages"] == 3

    def test_page2_sin_solapamiento_con_page1(self, client_with_items):
        page1_ids = ALL_IDS[:5]
        page2_ids = ALL_IDS[5:10]

        client1 = client_with_items(_make_bitacora_items(page1_ids), TOTAL)
        resp1 = client1.get("/api/v1/bitacora/?page=1&page_size=5")
        ids_page1 = {item["id"] for item in resp1.json()["items"]}

        client2 = client_with_items(_make_bitacora_items(page2_ids), TOTAL)
        resp2 = client2.get("/api/v1/bitacora/?page=2&page_size=5")
        ids_page2 = {item["id"] for item in resp2.json()["items"]}

        assert ids_page1.isdisjoint(ids_page2)

    def test_orden_estable_sin_duplicados_ni_omisiones(self, client_with_items):
        seen_ids: list[int] = []

        page_sizes = [ALL_IDS[:5], ALL_IDS[5:10], ALL_IDS[10:12]]
        for page_num, ids_chunk in enumerate(page_sizes, start=1):
            client = client_with_items(_make_bitacora_items(ids_chunk), TOTAL)
            resp = client.get(f"/api/v1/bitacora/?page={page_num}&page_size=5")
            seen_ids.extend(item["id"] for item in resp.json()["items"])

        assert sorted(seen_ids) == sorted(ALL_IDS)
        assert len(seen_ids) == len(set(seen_ids))

    def test_page_size_200_retorna_422(self, client_with_items):
        client = client_with_items([], 0)
        resp = client.get("/api/v1/bitacora/?page_size=200")
        assert resp.status_code == 422

    def test_page_0_retorna_422(self, client_with_items):
        client = client_with_items([], 0)
        resp = client.get("/api/v1/bitacora/?page=0")
        assert resp.status_code == 422

    def test_tabla_vacia_retorna_envelope_correcto(self, client_with_items):
        client = client_with_items([], 0)
        resp = client.get("/api/v1/bitacora/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["total_pages"] == 0

    def test_defaults_page_size_es_5(self, client_with_items):
        client = client_with_items(_make_bitacora_items(ALL_IDS[:5]), TOTAL)
        resp = client.get("/api/v1/bitacora/")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 5


# ===========================================================================
# TEST SUITE 3: usuarios — incluye regresión EmailStr en UsuarioOut
# ===========================================================================

def _make_usuario_items(ids: list[int], emails: list[str] | None = None):
    """Construye mocks de Usuario. Acepta emails arbitrarios para blindar serialización."""
    items = []
    for i, uid in enumerate(ids):
        u = MagicMock()
        u.id = uid
        u.nombre = f"Usuario {uid}"
        u.email = (emails[i] if emails and i < len(emails) else f"user{uid}@example.com")
        u.rol = "operador"
        u.estado = True
        items.append(u)
    return items


class TestPaginacionUsuarios:

    @pytest.fixture
    def client_admin_with_items(self):
        """Factory que monta la mini-app con rol super_admin."""
        def _factory(items: list, total: int) -> TestClient:
            db_mock = _make_db_mock(items, total)
            app = _build_app()
            app.dependency_overrides[get_db] = lambda: db_mock
            app.dependency_overrides[get_current_user] = lambda: _mock_admin()
            return TestClient(app, raise_server_exceptions=False)
        return _factory

    def test_page1_retorna_200_con_envelope_correcto(self, client_admin_with_items):
        items = _make_usuario_items(ALL_IDS[:5])
        client = client_admin_with_items(items, TOTAL)

        resp = client.get("/api/v1/usuarios/?page=1&page_size=5")

        assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert "total_pages" in body
        assert body["total"] == TOTAL
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert body["total_pages"] == 3
        assert len(body["items"]) == 5

    def test_email_legacy_dot_local_no_causa_500(self, client_admin_with_items):
        """
        Regresión: UsuarioOut.email era EmailStr y reventaba al serializar dominios
        reservados como '.local' (progas.local, seed.local, etc.).
        Con email: str la serialización siempre funciona.
        """
        emails_legacy = [
            "operador1@progas.local",     # .local — dominio reservado
            "seed@progas.local",          # el usuario seed del script
            "legacy+tag@internal",        # sin TLD
            "admin@empresa.local",        # otro .local
            "user@127.0.0.1",             # IP literal
        ]
        items = _make_usuario_items(ALL_IDS[:5], emails=emails_legacy)
        client = client_admin_with_items(items, TOTAL)

        resp = client.get("/api/v1/usuarios/?page=1&page_size=5")

        assert resp.status_code == 200, (
            f"EmailStr en UsuarioOut causó 500 con emails legacy. "
            f"Status: {resp.status_code}, body: {resp.text[:500]}"
        )
        body = resp.json()
        returned_emails = [item["email"] for item in body["items"]]
        assert returned_emails == emails_legacy, (
            "Los emails deben devolverse tal cual están en la BD, sin validación"
        )

    def test_tabla_vacia_retorna_envelope_correcto(self, client_admin_with_items):
        client = client_admin_with_items([], 0)
        resp = client.get("/api/v1/usuarios/?page=1&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["total_pages"] == 0

    def test_page_size_200_retorna_422(self, client_admin_with_items):
        client = client_admin_with_items([], 0)
        resp = client.get("/api/v1/usuarios/?page_size=200")
        assert resp.status_code == 422

    def test_page_0_retorna_422(self, client_admin_with_items):
        client = client_admin_with_items([], 0)
        resp = client.get("/api/v1/usuarios/?page=0")
        assert resp.status_code == 422
