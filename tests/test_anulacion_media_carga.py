"""
Tests de anulación de media carga — criterios de aceptación FASE B.

Cubre (service, MagicMock):
  (b) Anular revierte stock_llenos exactamente y marca anulada/anulada_at/anulado_por_id
  (c) Déficit de stock → HTTP 400, sin tocar nada, mensaje con todos los déficits
  (d) Re-anulación → HTTP 409

Cubre (HTTP, dependency_overrides):
  (e) Operador → 403; admin → 200 con anulada=True en response
"""
from unittest.mock import MagicMock, patch, call
from collections import defaultdict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.medias_cargas import router as medias_router
from app.core.dependencies import get_current_user
from database import get_db


# ===========================================================================
# Helpers compartidos
# ===========================================================================

def _make_linea(producto_id: int, cantidad_llenos: int) -> MagicMock:
    l = MagicMock()
    l.producto_id = producto_id
    l.cantidad_llenos = cantidad_llenos
    return l


def _make_producto(pid: int, formato: str, stock_llenos: int) -> MagicMock:
    p = MagicMock()
    p.id = pid
    p.formato = formato
    p.stock_llenos = stock_llenos
    return p


def _make_media_carga(mc_id: int, lineas: list, anulada: bool = False) -> MagicMock:
    mc = MagicMock()
    mc.id = mc_id
    mc.anulada = anulada
    mc.lineas = lineas
    return mc


def _make_db(mc: MagicMock, productos: list) -> MagicMock:
    """
    Monta un db mock que devuelve mc en la query de MediaCarga y
    los productos en la query with_for_update.
    """
    db = MagicMock()

    # query(MediaCarga).options(...).filter(...).first()
    mc_query = MagicMock()
    mc_query.options.return_value.filter.return_value.first.return_value = mc

    # query(ProductoMaestro).filter(...).with_for_update().all()
    prod_query = MagicMock()
    prod_query.filter.return_value.with_for_update.return_value.all.return_value = productos

    db.query.side_effect = lambda model: mc_query if "MediaCarga" in str(model) else prod_query
    return db


def _mock_usuario(rol: str) -> MagicMock:
    u = MagicMock()
    u.id = 99
    u.rol = rol
    u.estado = True
    return u


# ===========================================================================
# TEST SUITE — service anular_media_carga (MagicMock, sin BD real)
# ===========================================================================

class TestAnularMediaCargaService:

    def test_b_revierte_stock_y_marca_anulada(self):
        """(b) Anular descuenta stock_llenos exactamente y marca los 3 campos."""
        from app.services.media_carga_service import anular_media_carga

        lineas = [_make_linea(1, 10), _make_linea(2, 5)]
        mc = _make_media_carga(mc_id=1, lineas=lineas)
        prod1 = _make_producto(1, "11kg", stock_llenos=20)
        prod2 = _make_producto(2, "45kg", stock_llenos=8)
        db = _make_db(mc, [prod1, prod2])

        resultado = anular_media_carga(db, 1, usuario_id=7)

        assert prod1.stock_llenos == 10   # 20 - 10
        assert prod2.stock_llenos == 3    # 8 - 5
        assert mc.anulada is True
        assert mc.anulado_por_id == 7
        assert mc.anulada_at is not None
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    def test_b_agrega_cantidades_misma_linea(self):
        """(b corr.2) Dos líneas del mismo producto: se agregan antes de validar y descontar."""
        from app.services.media_carga_service import anular_media_carga

        lineas = [_make_linea(1, 6), _make_linea(1, 4)]  # mismo producto, total = 10
        mc = _make_media_carga(mc_id=2, lineas=lineas)
        prod = _make_producto(1, "11kg", stock_llenos=15)
        db = _make_db(mc, [prod])

        anular_media_carga(db, 2, usuario_id=1)

        assert prod.stock_llenos == 5   # 15 - (6+4)

    def test_c_deficit_unico_lanza_400_sin_cambios(self):
        """(c) Stock insuficiente → HTTP 400, stock NO cambia, sin commit."""
        from fastapi import HTTPException
        from app.services.media_carga_service import anular_media_carga

        lineas = [_make_linea(1, 20)]
        mc = _make_media_carga(mc_id=3, lineas=lineas)
        prod = _make_producto(1, "11kg", stock_llenos=5)  # solo 5, necesita 20
        db = _make_db(mc, [prod])

        with pytest.raises(HTTPException) as exc:
            anular_media_carga(db, 3, usuario_id=1)

        assert exc.value.status_code == 400
        assert "stock insuficiente" in exc.value.detail
        assert "11kg" in exc.value.detail
        assert "tiene 5" in exc.value.detail
        assert "necesita 20" in exc.value.detail
        assert prod.stock_llenos == 5   # sin cambios
        db.commit.assert_not_called()

    def test_c_multiples_deficits_listados(self):
        """(c) Varios déficits: el 400 los lista todos (no solo el primero)."""
        from fastapi import HTTPException
        from app.services.media_carga_service import anular_media_carga

        lineas = [_make_linea(1, 15), _make_linea(2, 10)]
        mc = _make_media_carga(mc_id=4, lineas=lineas)
        prod1 = _make_producto(1, "11kg", stock_llenos=5)   # déficit: 10
        prod2 = _make_producto(2, "45kg", stock_llenos=3)   # déficit: 7
        db = _make_db(mc, [prod1, prod2])

        with pytest.raises(HTTPException) as exc:
            anular_media_carga(db, 4, usuario_id=1)

        assert exc.value.status_code == 400
        # Ambos formatos deben aparecer en el mensaje
        assert "11kg" in exc.value.detail
        assert "45kg" in exc.value.detail
        # Stock intacto en ambos
        assert prod1.stock_llenos == 5
        assert prod2.stock_llenos == 3

    def test_d_re_anulacion_lanza_409(self):
        """(d) Media carga ya anulada → HTTP 409."""
        from fastapi import HTTPException
        from app.services.media_carga_service import anular_media_carga

        mc = _make_media_carga(mc_id=5, lineas=[], anulada=True)
        db = _make_db(mc, [])

        with pytest.raises(HTTPException) as exc:
            anular_media_carga(db, 5, usuario_id=1)

        assert exc.value.status_code == 409

    def test_404_si_no_existe(self):
        """Media carga inexistente → HTTP 404."""
        from fastapi import HTTPException
        from app.services.media_carga_service import anular_media_carga

        db = MagicMock()
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = None
        db.query.return_value = q

        with pytest.raises(HTTPException) as exc:
            anular_media_carga(db, 999, usuario_id=1)

        assert exc.value.status_code == 404

    def test_value_error_en_commit_lanza_400(self):
        """db.commit() lanza ValueError (violación check constraint) → HTTP 400 + rollback."""
        from fastapi import HTTPException
        from app.services.media_carga_service import anular_media_carga

        lineas = [_make_linea(1, 5)]
        mc = _make_media_carga(mc_id=10, lineas=lineas)
        prod = _make_producto(1, "11kg", stock_llenos=10)
        db = _make_db(mc, [prod])
        db.commit.side_effect = ValueError("check constraint violado")

        with pytest.raises(HTTPException) as exc:
            anular_media_carga(db, 10, usuario_id=1)

        assert exc.value.status_code == 400
        assert "integridad" in exc.value.detail
        db.rollback.assert_called_once()

    def test_exception_generica_en_commit_lanza_500(self):
        """db.commit() lanza excepción genérica → HTTP 500 + rollback."""
        from fastapi import HTTPException
        from app.services.media_carga_service import anular_media_carga

        lineas = [_make_linea(1, 5)]
        mc = _make_media_carga(mc_id=11, lineas=lineas)
        prod = _make_producto(1, "11kg", stock_llenos=10)
        db = _make_db(mc, [prod])
        db.commit.side_effect = RuntimeError("timeout de BD")

        with pytest.raises(HTTPException) as exc:
            anular_media_carga(db, 11, usuario_id=1)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()


# ===========================================================================
# TEST SUITE — HTTP endpoint DELETE /medias-cargas/{id}
# ===========================================================================

def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(medias_router, prefix="/api/v1/medias-cargas")
    return app


class TestDeleteEndpointHttp:

    def test_e_operador_recibe_403(self):
        """(e) Operador no puede anular — require_role('super_admin') → 403."""
        app = _build_app()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario("operador")

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.delete("/api/v1/medias-cargas/1")

        assert resp.status_code == 403

    def test_admin_puede_anular_devuelve_200(self):
        """Admin recibe 200 con anulada=True cuando el service retorna exitosamente."""
        from app.models.models import MediaCarga

        mc_mock = MagicMock(spec=MediaCarga)
        mc_mock.id = 1
        mc_mock.anulada = True
        mc_mock.numero_guia = "G-TEST"
        mc_mock.proveedor = "Test"
        mc_mock.fecha = __import__("datetime").datetime(2026, 1, 1)
        mc_mock.total_neto = 1000
        mc_mock.total_iva = 190
        mc_mock.total_bruto = 1190
        mc_mock.kilos_totales = 11.0
        mc_mock.usuario_id = 1
        mc_mock.lineas = []

        app = _build_app()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario("super_admin")

        with patch("app.api.v1.medias_cargas._svc_anular", return_value=mc_mock):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.delete("/api/v1/medias-cargas/1")

        assert resp.status_code == 200
        assert resp.json()["anulada"] is True
