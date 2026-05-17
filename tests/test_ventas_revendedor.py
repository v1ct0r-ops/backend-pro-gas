"""
Tests unitarios — venta_revendedor_service.py

Cubre: cálculos de IVA/kilos/descuento, validaciones de stock,
       producto no encontrado, descuento excesivo, errores genéricos.
Sin conexión a BD — todo vía MagicMock.
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

def _make_producto(stock_llenos: int = 50, peso_kg: float = 11.0) -> MagicMock:
    p = MagicMock()
    p.id = 1
    p.stock_llenos = stock_llenos
    p.peso_kg = peso_kg
    p.formato = "11kg"
    return p


def _make_linea_in(producto_id: int = 1, cantidad: int = 2,
                   precio_unitario_factura: int = 12_000) -> MagicMock:
    l = MagicMock()
    l.producto_id = producto_id
    l.cantidad = cantidad
    l.precio_unitario_factura = precio_unitario_factura
    return l


def _make_payload(lineas: list, descuento: int = 0) -> MagicMock:
    p = MagicMock()
    p.lineas = lineas
    p.descuento_pesos_por_kilo = descuento
    p.rut_cliente = "12345678-5"
    p.nombre_cliente = "Distribuidora Test"
    p.fecha = datetime(2026, 5, 16, 10, 0, 0)
    return p


def _make_db(producto: MagicMock) -> MagicMock:
    """Mock de Session con query chain para WITH FOR UPDATE."""
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = producto
    return db


# ===========================================================================
# TEST SUITE 1: cálculos financieros y de kilos
# ===========================================================================

class TestCalculosVentaRevendedor:

    def test_iva_y_totales_correctos(self):
        """
        1 línea: cantidad=2, precio_unit=12000 → subtotal_neto=24000
        sin descuento → total_final=24000
        IVA = round(24000 * 0.19) = 4560
        total_bruto = 28560
        """
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10, peso_kg=11.0)
        payload = _make_payload([_make_linea_in(cantidad=2, precio_unitario_factura=12_000)])
        db = _make_db(producto)

        venta = registrar_venta_revendedor(db, payload, usuario_id=1)

        assert venta.total_neto == 24_000
        assert venta.total_iva == round(24_000 * 0.19)
        assert venta.total_bruto == venta.total_neto + venta.total_iva

    def test_kilos_calculados_por_peso_kg(self):
        """kilos_linea = round(cantidad * peso_kg, 4)"""
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10, peso_kg=11.0)
        payload = _make_payload([_make_linea_in(cantidad=3)])
        db = _make_db(producto)

        venta = registrar_venta_revendedor(db, payload, usuario_id=1)

        assert venta.kilos_totales == round(3 * 11.0, 4)

    def test_descuento_por_kilo_reduce_total_final(self):
        """
        kilos_totales = 2 * 11 = 22 kg
        monto_descuento = round(22 * 500) = 11000
        total_final = 24000 - 11000 = 13000
        """
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10, peso_kg=11.0)
        payload = _make_payload(
            [_make_linea_in(cantidad=2, precio_unitario_factura=12_000)],
            descuento=500,
        )
        db = _make_db(producto)

        venta = registrar_venta_revendedor(db, payload, usuario_id=1)

        assert venta.monto_descuento_total == round(22.0 * 500)
        assert venta.total_final == 24_000 - round(22.0 * 500)

    def test_stock_decrementado_tras_venta(self):
        """El stock del producto debe reducirse en la cantidad vendida."""
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10)
        payload = _make_payload([_make_linea_in(cantidad=3)])
        db = _make_db(producto)

        registrar_venta_revendedor(db, payload, usuario_id=1)

        assert producto.stock_llenos == 7  # 10 - 3


# ===========================================================================
# TEST SUITE 2: validaciones de negocio
# ===========================================================================

class TestValidacionesVentaRevendedor:

    def test_producto_no_encontrado_lanza_404(self):
        from fastapi import HTTPException
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        payload = _make_payload([_make_linea_in()])

        with pytest.raises(HTTPException) as exc:
            registrar_venta_revendedor(db, payload, usuario_id=1)

        assert exc.value.status_code == 404

    def test_stock_insuficiente_lanza_400(self):
        from fastapi import HTTPException
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=1)  # solo 1 disponible
        payload = _make_payload([_make_linea_in(cantidad=5)])  # piden 5
        db = _make_db(producto)

        with pytest.raises(HTTPException) as exc:
            registrar_venta_revendedor(db, payload, usuario_id=1)

        assert exc.value.status_code == 400
        assert "Stock insuficiente" in exc.value.detail

    def test_descuento_supera_total_neto_lanza_400(self):
        """Si el descuento por kilo genera total_final < 0 → HTTP 400."""
        from fastapi import HTTPException
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10, peso_kg=11.0)
        # 2 * 11 = 22 kg; descuento = 10000/kg → monto_descuento = 220000 > total_neto=24000
        payload = _make_payload(
            [_make_linea_in(cantidad=2, precio_unitario_factura=12_000)],
            descuento=10_000,
        )
        db = _make_db(producto)

        with pytest.raises(HTTPException) as exc:
            registrar_venta_revendedor(db, payload, usuario_id=1)

        assert exc.value.status_code == 400

    def test_value_error_capturado_como_400(self):
        """Un @validates del modelo que lance ValueError debe traducirse a HTTP 400."""
        from fastapi import HTTPException
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10)
        payload = _make_payload([_make_linea_in()])
        db = _make_db(producto)
        db.flush.side_effect = ValueError("violación de constraint de stock")

        with pytest.raises(HTTPException) as exc:
            registrar_venta_revendedor(db, payload, usuario_id=1)

        assert exc.value.status_code == 400

    def test_error_generico_lanza_500_con_rollback(self):
        from fastapi import HTTPException
        from app.services.venta_revendedor_service import registrar_venta_revendedor

        producto = _make_producto(stock_llenos=10)
        payload = _make_payload([_make_linea_in()])
        db = _make_db(producto)
        db.commit.side_effect = RuntimeError("timeout conexión")

        with pytest.raises(HTTPException) as exc:
            registrar_venta_revendedor(db, payload, usuario_id=1)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()
