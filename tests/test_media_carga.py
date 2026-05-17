"""
Tests unitarios — media_carga_service.py

Cubre: cálculos de IVA/kilos, incremento de stock, validaciones,
       errores genéricos. Sin conexión a BD — todo vía MagicMock.
"""
from unittest.mock import MagicMock

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

def _make_producto(peso_kg: float = 11.0, stock_llenos: int = 0) -> MagicMock:
    p = MagicMock()
    p.id = 1
    p.peso_kg = peso_kg
    p.stock_llenos = stock_llenos
    p.formato = "11kg"
    return p


def _make_linea_in(producto_id: int = 1, cantidad_llenos: int = 10,
                   precio_unitario_neto: int = 5_000) -> MagicMock:
    l = MagicMock()
    l.producto_id = producto_id
    l.cantidad_llenos = cantidad_llenos
    l.precio_unitario_neto = precio_unitario_neto
    return l


def _make_payload(lineas: list) -> MagicMock:
    from datetime import datetime
    p = MagicMock()
    p.lineas = lineas
    p.numero_guia = "G-001"
    p.proveedor = "Proveedor Test"
    p.fecha = datetime(2026, 5, 16, 10, 0, 0)
    return p


def _make_db(producto: MagicMock) -> MagicMock:
    db = MagicMock()
    db.get.return_value = producto
    return db


# ===========================================================================
# TEST SUITE 1: cálculos financieros
# ===========================================================================

class TestCalculosMediaCarga:

    def test_iva_y_totales_correctos(self):
        """
        cantidad_llenos=10, precio_unit=5000 → subtotal=50000
        total_iva = round(50000 * 0.19) = 9500
        total_bruto = 59500
        """
        from app.services.media_carga_service import procesar_media_carga

        producto = _make_producto(peso_kg=11.0)
        payload = _make_payload([_make_linea_in(cantidad_llenos=10, precio_unitario_neto=5_000)])
        db = _make_db(producto)

        media_carga = procesar_media_carga(db, payload, usuario_id=1)

        assert media_carga.total_neto == 50_000
        assert media_carga.total_iva == round(50_000 * 0.19)
        assert media_carga.total_bruto == media_carga.total_neto + media_carga.total_iva

    def test_kilos_totales_calculados(self):
        """kilos_totales = cantidad_llenos * peso_kg"""
        from app.services.media_carga_service import procesar_media_carga

        producto = _make_producto(peso_kg=11.0)
        payload = _make_payload([_make_linea_in(cantidad_llenos=5)])
        db = _make_db(producto)

        media_carga = procesar_media_carga(db, payload, usuario_id=1)

        assert media_carga.kilos_totales == 5 * 11.0

    def test_stock_llenos_incrementado(self):
        """La media carga debe sumar cantidad_llenos al stock del producto."""
        from app.services.media_carga_service import procesar_media_carga

        producto = _make_producto(peso_kg=11.0, stock_llenos=20)
        payload = _make_payload([_make_linea_in(cantidad_llenos=10)])
        db = _make_db(producto)

        procesar_media_carga(db, payload, usuario_id=1)

        assert producto.stock_llenos == 30  # 20 + 10


# ===========================================================================
# TEST SUITE 2: validaciones de negocio
# ===========================================================================

class TestValidacionesMediaCarga:

    def test_producto_no_encontrado_lanza_404(self):
        from fastapi import HTTPException
        from app.services.media_carga_service import procesar_media_carga

        db = MagicMock()
        db.get.return_value = None
        payload = _make_payload([_make_linea_in()])

        with pytest.raises(HTTPException) as exc:
            procesar_media_carga(db, payload, usuario_id=1)

        assert exc.value.status_code == 404

    def test_cantidad_llenos_cero_lanza_400(self):
        """cantidad_llenos debe ser >= 1; si es 0 o negativo → HTTP 400."""
        from fastapi import HTTPException
        from app.services.media_carga_service import procesar_media_carga

        producto = _make_producto()
        db = _make_db(producto)
        payload = _make_payload([_make_linea_in(cantidad_llenos=0)])

        with pytest.raises(HTTPException) as exc:
            procesar_media_carga(db, payload, usuario_id=1)

        assert exc.value.status_code == 400

    def test_value_error_capturado_como_400(self):
        """ValueError de @validates del modelo debe traducirse a HTTP 400."""
        from fastapi import HTTPException
        from app.services.media_carga_service import procesar_media_carga

        producto = _make_producto()
        db = _make_db(producto)
        db.flush.side_effect = ValueError("violación de constraint")
        payload = _make_payload([_make_linea_in()])

        with pytest.raises(HTTPException) as exc:
            procesar_media_carga(db, payload, usuario_id=1)

        assert exc.value.status_code == 400

    def test_error_generico_lanza_500_con_rollback(self):
        from fastapi import HTTPException
        from app.services.media_carga_service import procesar_media_carga

        producto = _make_producto()
        db = _make_db(producto)
        db.commit.side_effect = RuntimeError("fallo en BD")
        payload = _make_payload([_make_linea_in()])

        with pytest.raises(HTTPException) as exc:
            procesar_media_carga(db, payload, usuario_id=1)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()
