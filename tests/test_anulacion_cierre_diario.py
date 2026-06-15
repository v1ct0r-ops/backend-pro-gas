"""
Tests de anulación de cierre diario — criterios de aceptación.

Cubre (servicio, MagicMock — sin BD real):
  - Anula último sellado: revierte stock exacto, marca todos los campos de anulación.
  - Dos líneas de movimiento: ambos productos revertidos correctamente.
  - Reversión que deja stock_vacios < 0 → HTTPException 400 + rollback, stock intacto.
  - No es el último cierre activo → 409 correlatividad.
  - Cierre ya anulado → 409, sin segunda reversión.
  - Cierre abierto (is_closed=False) → 400.
  - Cierre inexistente → 404.
  - Fallo genérico en commit → 500 + rollback.
  - Sin lineas_movimiento: anulación exitosa sin tocar productos.
  - Producto referenciado en línea inexistente en BD → 404.

Cubre (HTTP, dependency_overrides — sin BD real):
  - Rol operador → 403.
  - Rol super_admin → no 403.
  - Body sin motivo_anulacion → 422.
  - motivo_anulacion demasiado corto (< 3 chars) → 422.

Tests ACID (BD real, Docker en puerto 5433):
  - Invariante de oro: stock_inicial == stock tras sellar+anular (golden path).
  - Atomicidad: si la reversión falla (vacíos insuficientes en un producto),
    ni el stock ni el flag anulado quedan aplicados (todo o nada).
"""
import asyncio
import os
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.cierres_diarios import router as cierres_router
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password
from app.models.models import CierreDiario, ProductoMaestro, Usuario
from database import get_db


_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://victo:local_password@localhost:5433/pro_gas_erp",
)


# ===========================================================================
# Helpers compartidos — tests unitarios (MagicMock)
# ===========================================================================

def _make_cierre_sellado(
    cierre_id: int = 1,
    lineas: list | None = None,
    anulado: bool = False,
) -> MagicMock:
    c = MagicMock()
    c.id = cierre_id
    c.is_closed = True
    c.anulado = anulado
    c.fecha = datetime(2026, 5, 16, 10, 0, 0)
    c.lineas_movimiento = lineas if lineas is not None else []
    return c


def _make_producto(
    pid: int = 1,
    formato: str = "11kg",
    stock_llenos: int = 10,
    stock_vacios: int = 5,
) -> MagicMock:
    p = MagicMock()
    p.id = pid
    p.formato = formato
    p.stock_llenos = stock_llenos
    p.stock_vacios = stock_vacios
    return p


def _make_db_anular(
    cierre: MagicMock,
    productos: list | None = None,
    hay_posterior: bool = False,
) -> MagicMock:
    """
    Mock de sesión SQLAlchemy listo para anular_cierre:
      - db.get: [cierre, *productos] (orden de llamadas)
      - db.query: simula correlatividad (hay_posterior controla si existe cierre posterior)
    """
    db = MagicMock()
    db.get.side_effect = [cierre] + (productos or [])
    db.query.return_value.filter.return_value.first.return_value = (
        MagicMock() if hay_posterior else None
    )
    return db


# ===========================================================================
# TEST SUITE 1: unitarios del servicio anular_cierre (sin BD real)
# ===========================================================================

class TestAnularCierreServicio:

    def test_revierte_stock_y_marca_todos_los_campos(self):
        """
        Happy path: anular el último cierre sellado activo.
        Invariantes:
          stock_llenos += galones_vendidos, stock_vacios -= vacios_devueltos.
          anulado=True, anulado_por_id, anulado_at, motivo_anulacion escritos.
          is_closed sigue True (NO se reabre).
          Un solo commit, cero rollbacks.
        """
        from app.services.cierre_diario_service import anular_cierre

        producto = _make_producto(pid=1, stock_llenos=7, stock_vacios=5)
        lineas = [{"producto_id": 1, "galones_vendidos": 3, "vacios_devueltos": 2}]
        cierre = _make_cierre_sellado(lineas=lineas)
        db = _make_db_anular(cierre, productos=[producto])

        anular_cierre(db, cierre_id=1, usuario_id=42, motivo="prueba contable")

        assert producto.stock_llenos == 10          # 7 + 3
        assert producto.stock_vacios == 3           # 5 - 2
        assert cierre.anulado is True
        assert cierre.anulado_por_id == 42
        assert cierre.anulado_at is not None
        assert cierre.motivo_anulacion == "prueba contable"
        assert cierre.is_closed is True             # no se reabre
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    def test_multiples_lineas_revierte_todos_los_productos(self):
        """Cierre con 2 líneas de movimiento: ambos productos revertidos correctamente."""
        from app.services.cierre_diario_service import anular_cierre

        p1 = _make_producto(pid=1, formato="11kg", stock_llenos=5, stock_vacios=3)
        p2 = _make_producto(pid=2, formato="45kg", stock_llenos=8, stock_vacios=1)
        lineas = [
            {"producto_id": 1, "galones_vendidos": 5, "vacios_devueltos": 2},
            {"producto_id": 2, "galones_vendidos": 2, "vacios_devueltos": 1},
        ]
        cierre = _make_cierre_sellado(lineas=lineas)
        db = _make_db_anular(cierre, productos=[p1, p2])

        anular_cierre(db, cierre_id=1, usuario_id=1, motivo="corrección")

        assert p1.stock_llenos == 10    # 5 + 5
        assert p1.stock_vacios == 1     # 3 - 2
        assert p2.stock_llenos == 10    # 8 + 2
        assert p2.stock_vacios == 0     # 1 - 1
        db.commit.assert_called_once()

    def test_reversion_vacios_insuficientes_lanza_400_stock_intacto(self):
        """
        stock_vacios(1) - vacios_devueltos(5) = -4 < 0 →
        HTTP 400, rollback, stock sin cambios.
        """
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        producto = _make_producto(pid=1, stock_llenos=10, stock_vacios=1)
        lineas = [{"producto_id": 1, "galones_vendidos": 3, "vacios_devueltos": 5}]
        cierre = _make_cierre_sellado(lineas=lineas)
        db = _make_db_anular(cierre, productos=[producto])

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="x")

        assert exc.value.status_code == 400
        assert "Reversión imposible" in exc.value.detail
        assert producto.stock_vacios == 1    # sin cambios
        assert producto.stock_llenos == 10   # sin cambios
        db.rollback.assert_called_once()
        db.commit.assert_not_called()

    def test_atomicidad_primer_producto_pasa_segundo_falla_ninguno_cambia(self):
        """
        p1 pasa validación (stock_vacios 3 ≥ vacios_devueltos 2).
        p2 falla validación (stock_vacios 1 < vacios_devueltos 5).
        Dado que se valida todo ANTES de aplicar, p1 tampoco debe ser modificado.
        """
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        p1 = _make_producto(pid=1, stock_llenos=5, stock_vacios=3)
        p2 = _make_producto(pid=2, stock_llenos=8, stock_vacios=1)
        lineas = [
            {"producto_id": 1, "galones_vendidos": 5, "vacios_devueltos": 2},  # pasa
            {"producto_id": 2, "galones_vendidos": 2, "vacios_devueltos": 5},  # falla
        ]
        cierre = _make_cierre_sellado(lineas=lineas)
        db = _make_db_anular(cierre, productos=[p1, p2])

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="x")

        assert exc.value.status_code == 400
        assert p1.stock_llenos == 5    # sin cambios
        assert p1.stock_vacios == 3    # sin cambios
        assert p2.stock_llenos == 8    # sin cambios
        assert p2.stock_vacios == 1    # sin cambios
        db.commit.assert_not_called()

    def test_no_ultimo_cierre_activo_lanza_409(self):
        """Existe un cierre posterior sellado activo → HTTP 409 correlatividad."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        cierre = _make_cierre_sellado()
        db = _make_db_anular(cierre, hay_posterior=True)

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="motivo")

        assert exc.value.status_code == 409
        assert "último cierre" in exc.value.detail.lower()
        db.commit.assert_not_called()

    def test_ya_anulado_lanza_409_sin_segunda_reversion(self):
        """Cierre ya marcado anulado → HTTP 409, sin segunda reversión."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        cierre = _make_cierre_sellado(anulado=True)
        db = _make_db_anular(cierre)

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="re-intento")

        assert exc.value.status_code == 409
        db.commit.assert_not_called()

    def test_cierre_abierto_lanza_400(self):
        """Cierre no sellado (is_closed=False) → HTTP 400."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        cierre = MagicMock()
        cierre.is_closed = False
        cierre.anulado = False
        db = MagicMock()
        db.get.return_value = cierre

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="motivo")

        assert exc.value.status_code == 400
        assert "sellado" in exc.value.detail.lower()
        db.commit.assert_not_called()

    def test_cierre_inexistente_lanza_404(self):
        """Cierre no encontrado en BD → HTTP 404."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=999, usuario_id=1, motivo="motivo")

        assert exc.value.status_code == 404

    def test_fallo_generico_commit_lanza_500_y_rollback(self):
        """db.commit() lanza excepción genérica → HTTP 500 + rollback."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        cierre = _make_cierre_sellado(lineas=[])
        db = _make_db_anular(cierre)
        db.commit.side_effect = RuntimeError("timeout de BD")

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="motivo")

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()

    def test_sin_lineas_movimiento_marca_anulado_sin_tocar_productos(self):
        """
        Cierre sellado sin líneas de movimiento: la anulación es válida.
        Se marcan los campos de anulación; ningún producto es tocado.
        """
        from app.services.cierre_diario_service import anular_cierre

        cierre = _make_cierre_sellado(lineas=[])
        db = _make_db_anular(cierre)

        anular_cierre(db, cierre_id=1, usuario_id=5, motivo="ajuste manual sin galones")

        assert cierre.anulado is True
        assert cierre.anulado_por_id == 5
        assert cierre.motivo_anulacion == "ajuste manual sin galones"
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    def test_producto_no_encontrado_en_linea_lanza_404(self):
        """Producto referenciado en una línea de movimiento no existe en BD → 404."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import anular_cierre

        lineas = [{"producto_id": 99, "galones_vendidos": 2, "vacios_devueltos": 0}]
        cierre = _make_cierre_sellado(lineas=lineas)
        db = _make_db_anular(cierre, productos=[None])   # db.get devuelve None para el producto

        with pytest.raises(HTTPException) as exc:
            anular_cierre(db, cierre_id=1, usuario_id=1, motivo="motivo")

        assert exc.value.status_code == 404


# ===========================================================================
# TEST SUITE 2: integración HTTP con dependency_overrides (sin BD real)
# ===========================================================================

def _build_app_http() -> FastAPI:
    app = FastAPI()
    app.include_router(cierres_router, prefix="/api/v1/cierres-diarios")
    return app


def _mock_usuario_http(rol: str) -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.rol = rol
    u.estado = True
    return u


class TestAnularCierreEndpointHttp:

    def test_operador_recibe_403(self):
        """Rol 'operador' → PATCH /{id}/anular bloqueado con HTTP 403."""
        app = _build_app_http()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario_http("operador")

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                "/api/v1/cierres-diarios/1/anular",
                json={"motivo_anulacion": "prueba de acceso"},
            )

        assert resp.status_code == 403, (
            f"Esperado 403, recibido {resp.status_code}.\nBody: {resp.text}"
        )

    def test_admin_no_recibe_403(self):
        """Rol 'super_admin' pasa el control de acceso (puede ser otro código, no 403)."""
        app = _build_app_http()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario_http("super_admin")

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                "/api/v1/cierres-diarios/1/anular",
                json={"motivo_anulacion": "prueba de acceso"},
            )

        assert resp.status_code != 403, (
            f"super_admin no debe recibir 403. Status: {resp.status_code}"
        )

    def test_sin_motivo_anulacion_retorna_422(self):
        """Body {} sin 'motivo_anulacion' → Pydantic rechaza con HTTP 422."""
        app = _build_app_http()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario_http("super_admin")

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch("/api/v1/cierres-diarios/1/anular", json={})

        assert resp.status_code == 422, (
            f"Esperado 422, recibido {resp.status_code}.\nBody: {resp.text}"
        )
        detalle = resp.json().get("detail", [])
        campos = [e["loc"][-1] for e in detalle if "loc" in e]
        assert "motivo_anulacion" in campos, (
            f"El 422 debería mencionar 'motivo_anulacion'. Campos: {campos}"
        )

    def test_motivo_demasiado_corto_retorna_422(self):
        """motivo_anulacion con menos de 3 caracteres (min_length=3) → HTTP 422."""
        app = _build_app_http()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario_http("super_admin")

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                "/api/v1/cierres-diarios/1/anular",
                json={"motivo_anulacion": "ab"},   # 2 chars < min_length=3
            )

        assert resp.status_code == 422, (
            f"Esperado 422, recibido {resp.status_code}.\nBody: {resp.text}"
        )


# ===========================================================================
# Fixtures e helpers compartidos — tests ACID (BD real)
# ===========================================================================

@pytest.fixture(scope="module")
def fastapi_app():
    """Importación lazy de la app — evita Base.metadata.create_all durante collection."""
    from main import app  # noqa: PLC0415
    return app


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        _DB_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 10},
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


def _make_admin_user(session: Session) -> Usuario:
    """Crea un super_admin real en la BD con email único."""
    user = Usuario(
        nombre=f"Admin ACID {int(time.time() * 1000)}",
        email=f"acid_admin_{int(time.time() * 1000)}@progas.test",
        password_hash=hash_password("test1234"),
        rol="super_admin",
        estado=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _bearer(usuario_id: int) -> dict:
    token = create_access_token({"sub": str(usuario_id)})
    return {"Authorization": f"Bearer {token}"}


def _delete_cierre(session: Session, cierre_id: int | None) -> None:
    if cierre_id is None:
        return
    obj = session.get(CierreDiario, cierre_id)
    if obj:
        session.delete(obj)


def _delete_obj(session: Session, obj) -> None:
    if obj is None:
        return
    fresh = session.get(type(obj), obj.id)
    if fresh:
        session.delete(fresh)


# ===========================================================================
# TEST ACID 1 — Invariante de oro: stock_inicial == stock tras sellar + anular
# ===========================================================================

def test_invariante_oro_sellar_luego_anular(fastapi_app, session_factory):
    """
    Escenario:
        Producto con stock_llenos=10, stock_vacios=5.
        Cierre con una línea: galones_vendidos=5, vacios_devueltos=3.

    Tras sellar:
        stock_llenos = 10 - 5 = 5
        stock_vacios = 5  + 3 = 8

    Tras anular:
        stock_llenos = 5  + 5 = 10  (restaurado)
        stock_vacios = 8  - 3 = 5   (restaurado)

    Invariante: stock final == stock inicial para ambas dimensiones.
    """
    session = session_factory()
    user = producto = None
    cierre_id = None

    try:
        user = _make_admin_user(session)
        producto = ProductoMaestro(
            formato=f"11kg-ACID-ORO-{int(time.time())}",
            peso_kg=11.0,
            precio_publico_base=15_000,
            stock_llenos=10,
            stock_vacios=5,
        )
        session.add(producto)
        session.commit()
        session.refresh(producto)

        stock_llenos_inicial = producto.stock_llenos   # 10
        stock_vacios_inicial = producto.stock_vacios   # 5

        headers = _bearer(user.id)

        async def _flujo():
            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                # 1. Crear cierre con lineas de movimiento
                r_crear = await client.post(
                    "/api/v1/cierres-diarios/",
                    json={
                        "chofer_nombre": "Chofer ACID",
                        "fecha": datetime.now(timezone.utc).isoformat(),
                        "efectivo_rendido": 10_000,
                        "total_ventas_calc": 10_000,
                        "lineas_movimiento": [
                            {
                                "producto_id": producto.id,
                                "galones_vendidos": 5,
                                "vacios_devueltos": 3,
                            }
                        ],
                    },
                    headers=headers,
                )
                assert r_crear.status_code == 201, (
                    f"Crear falló: {r_crear.status_code} — {r_crear.text}"
                )
                nonlocal cierre_id
                cierre_id = r_crear.json()["id"]

                # 2. Sellar el cierre (mutación de inventario)
                r_cerrar = await client.patch(
                    f"/api/v1/cierres-diarios/{cierre_id}/cerrar",
                    headers=headers,
                )
                assert r_cerrar.status_code == 200, (
                    f"Cerrar falló: {r_cerrar.status_code} — {r_cerrar.text}"
                )

                # 3. Anular el cierre (reversión de inventario)
                r_anular = await client.patch(
                    f"/api/v1/cierres-diarios/{cierre_id}/anular",
                    json={"motivo_anulacion": "Anulación por test ACID invariante"},
                    headers=headers,
                )
                return r_cerrar, r_anular

        r_cerrar, r_anular = asyncio.run(_flujo())

        # Verificar respuesta de anulación
        assert r_anular.status_code == 200, (
            f"Anular falló: {r_anular.status_code} — {r_anular.text}"
        )
        body = r_anular.json()
        assert body["anulado"] is True
        assert body["is_closed"] is True            # sigue sellado
        assert body["motivo_anulacion"] == "Anulación por test ACID invariante"

        # Verificar invariante de stock contra la BD real
        session.expire(producto)
        session.refresh(producto)
        assert producto.stock_llenos == stock_llenos_inicial, (
            f"INVARIANTE ROTA: stock_llenos inicial={stock_llenos_inicial}, "
            f"final={producto.stock_llenos}"
        )
        assert producto.stock_vacios == stock_vacios_inicial, (
            f"INVARIANTE ROTA: stock_vacios inicial={stock_vacios_inicial}, "
            f"final={producto.stock_vacios}"
        )

    finally:
        _delete_cierre(session, cierre_id)
        _delete_obj(session, producto)
        _delete_obj(session, user)
        session.commit()
        session.close()


# ===========================================================================
# TEST ACID 2 — Atomicidad: fallo parcial no aplica ningún cambio
# ===========================================================================

def test_atomicidad_fallo_vacios_insuficientes(fastapi_app, session_factory):
    """
    Escenario de "todo o nada":
        Cierre sellado con dos productos. Entre el sellado y la anulación,
        stock_vacios del producto B se drena (simulando consumo externo).
        La anulación falla porque B no puede revertir sus vacíos devueltos.

    Se verifica que:
        1. La respuesta es HTTP 400.
        2. stock de A NO fue revertido (aunque A pasa la validación individual).
        3. stock de B NO fue revertido.
        4. El flag cierre.anulado sigue siendo False.
    """
    session = session_factory()
    user = producto_a = producto_b = None
    cierre_id = None

    try:
        user = _make_admin_user(session)

        # Producto A: galones_vendidos=5, vacios_devueltos=3
        producto_a = ProductoMaestro(
            formato=f"11kg-ACID-ATOM-A-{int(time.time())}",
            peso_kg=11.0,
            precio_publico_base=15_000,
            stock_llenos=10,
            stock_vacios=0,
        )
        # Producto B: galones_vendidos=2, vacios_devueltos=1
        producto_b = ProductoMaestro(
            formato=f"5kg-ACID-ATOM-B-{int(time.time())}",
            peso_kg=5.0,
            precio_publico_base=8_000,
            stock_llenos=5,
            stock_vacios=0,
        )
        session.add_all([producto_a, producto_b])
        session.commit()
        session.refresh(producto_a)
        session.refresh(producto_b)

        headers = _bearer(user.id)

        async def _crear_y_sellar():
            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                r = await client.post(
                    "/api/v1/cierres-diarios/",
                    json={
                        "chofer_nombre": "Chofer ACID ATOM",
                        "fecha": datetime.now(timezone.utc).isoformat(),
                        "efectivo_rendido": 20_000,
                        "total_ventas_calc": 20_000,
                        "lineas_movimiento": [
                            {"producto_id": producto_a.id, "galones_vendidos": 5, "vacios_devueltos": 3},
                            {"producto_id": producto_b.id, "galones_vendidos": 2, "vacios_devueltos": 1},
                        ],
                    },
                    headers=headers,
                )
                assert r.status_code == 201, f"Crear falló: {r.status_code} — {r.text}"
                nonlocal cierre_id
                cierre_id = r.json()["id"]

                r2 = await client.patch(
                    f"/api/v1/cierres-diarios/{cierre_id}/cerrar",
                    headers=headers,
                )
                assert r2.status_code == 200, f"Cerrar falló: {r2.status_code} — {r2.text}"

        asyncio.run(_crear_y_sellar())

        # Verificar estado post-sellado
        session.expire(producto_a)
        session.expire(producto_b)
        session.refresh(producto_a)
        session.refresh(producto_b)
        assert producto_a.stock_llenos == 5   # 10 - 5
        assert producto_a.stock_vacios == 3   # 0  + 3
        assert producto_b.stock_llenos == 3   # 5  - 2
        assert producto_b.stock_vacios == 1   # 0  + 1

        # Drenar stock_vacios de B a 0 (simula consumo externo entre sellado y anulación)
        # Con 0, la reversión de vacios_devueltos=1 daría 0-1=-1 < 0 → FALLO
        session.query(ProductoMaestro).filter(
            ProductoMaestro.id == producto_b.id
        ).update({"stock_vacios": 0})
        session.commit()

        # A sigue con stock_vacios=3 → revertiría 3-3=0 ≥ 0 → PASA individualmente
        # B tiene stock_vacios=0 → revertiría 0-1=-1 < 0 → FALLA → rollback total

        async def _intentar_anular():
            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.patch(
                    f"/api/v1/cierres-diarios/{cierre_id}/anular",
                    json={"motivo_anulacion": "Test atomicidad ACID"},
                    headers=headers,
                )

        r_anular = asyncio.run(_intentar_anular())

        # Aserción 1: la reversión falla con 400
        assert r_anular.status_code == 400, (
            f"Esperado HTTP 400 por vacíos insuficientes, "
            f"recibido {r_anular.status_code}.\nBody: {r_anular.text}"
        )
        assert "Reversión imposible" in r_anular.json().get("detail", ""), (
            f"Mensaje inesperado: {r_anular.json()}"
        )

        # Aserción 2: stock de A no fue revertido (sigue en estado post-sellado)
        session.expire(producto_a)
        session.refresh(producto_a)
        assert producto_a.stock_llenos == 5, (
            f"ATOMICIDAD ROTA: stock_llenos de A cambió de 5 a {producto_a.stock_llenos}"
        )
        assert producto_a.stock_vacios == 3, (
            f"ATOMICIDAD ROTA: stock_vacios de A cambió de 3 a {producto_a.stock_vacios}"
        )

        # Aserción 3: stock de B no fue revertido
        session.expire(producto_b)
        session.refresh(producto_b)
        assert producto_b.stock_llenos == 3, (
            f"ATOMICIDAD ROTA: stock_llenos de B cambió de 3 a {producto_b.stock_llenos}"
        )
        assert producto_b.stock_vacios == 0, (
            f"ATOMICIDAD ROTA: stock_vacios de B cambió de 0 a {producto_b.stock_vacios}"
        )

        # Aserción 4: el flag anulado sigue en False (el cierre sigue activo)
        session.expire_all()
        cierre_obj = session.get(CierreDiario, cierre_id)
        assert cierre_obj is not None
        assert cierre_obj.anulado is False, (
            f"ATOMICIDAD ROTA: cierre.anulado debería ser False, es {cierre_obj.anulado}"
        )
        assert cierre_obj.is_closed is True     # sigue sellado

    finally:
        _delete_cierre(session, cierre_id)
        _delete_obj(session, producto_b)
        _delete_obj(session, producto_a)
        _delete_obj(session, user)
        session.commit()
        session.close()
