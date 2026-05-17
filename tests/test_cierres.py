"""
Tests unitarios — cierre_diario_service.py

Cubre: crear_cierre, cerrar_cierre (matemática, inventario, errores),
       actualizar_cierre, eliminar_cierre, tarea_email_cierre.
Sin conexión a BD — todo vía MagicMock.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Helpers compartidos
# ===========================================================================

def _make_cierre(
    total_ventas_calc: int = 10_000,
    descuentos: int = 0,
    efectivo_rendido: int = 10_000,
    vouchers_transbank: int = 0,
) -> MagicMock:
    cierre = MagicMock()
    cierre.is_closed = False
    cierre.lineas_movimiento = []
    cierre.fecha = datetime(2026, 5, 16, 10, 0, 0)
    cierre.id = 1
    cierre.chofer_nombre = "Chofer Test"
    cierre.total_ventas_calc = total_ventas_calc
    cierre.descuentos = descuentos
    cierre.efectivo_rendido = efectivo_rendido
    cierre.vouchers_transbank = vouchers_transbank
    return cierre


def _make_db(cierre: MagicMock) -> MagicMock:
    db = MagicMock()
    db.get.return_value = cierre
    db.query.return_value.all.return_value = []
    return db


# ===========================================================================
# TEST SUITE 1: aritmética del cuadre financiero
# ===========================================================================

class TestMatematicaCierreDiario:

    def test_cuadre_exacto(self):
        """
        Escenario principal: ventas=10000, desc=2000, efectivo=8000, vouchers=0
        → diferencia=0, estado='exacto'
        """
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre(total_ventas_calc=10_000, descuentos=2_000,
                               efectivo_rendido=8_000, vouchers_transbank=0)
        db = _make_db(cierre)

        cerrar_cierre(db, cierre_id=1, usuario_id=99)

        assert cierre.diferencia == 0
        assert cierre.estado_cuadre == "exacto"
        assert cierre.is_closed is True
        db.commit.assert_called_once()

    def test_cuadre_faltante(self):
        """efectivo=5000, ventas_netas=8000 → diferencia=3000, estado='faltante'"""
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre(total_ventas_calc=10_000, descuentos=2_000,
                               efectivo_rendido=5_000, vouchers_transbank=0)
        cerrar_cierre(_make_db(cierre), cierre_id=1, usuario_id=99)

        assert cierre.diferencia == 3_000
        assert cierre.estado_cuadre == "faltante"

    def test_cuadre_sobrante(self):
        """efectivo=9000, ventas_netas=8000 → diferencia=-1000, estado='sobrante'"""
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre(total_ventas_calc=10_000, descuentos=2_000,
                               efectivo_rendido=9_000, vouchers_transbank=0)
        cerrar_cierre(_make_db(cierre), cierre_id=1, usuario_id=99)

        assert cierre.diferencia == -1_000
        assert cierre.estado_cuadre == "sobrante"

    def test_cuadre_exacto_con_vouchers(self):
        """efectivo=6000 + vouchers=4000 = ventas_netas=10000 → exacto"""
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre(total_ventas_calc=10_000, descuentos=0,
                               efectivo_rendido=6_000, vouchers_transbank=4_000)
        cerrar_cierre(_make_db(cierre), cierre_id=1, usuario_id=99)

        assert cierre.diferencia == 0
        assert cierre.estado_cuadre == "exacto"

    def test_descuentos_none_tratados_como_cero(self):
        """descuentos=None en BD no debe romper la aritmética."""
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre(total_ventas_calc=5_000, efectivo_rendido=5_000)
        cierre.descuentos = None
        cerrar_cierre(_make_db(cierre), cierre_id=1, usuario_id=99)

        assert cierre.diferencia == 0
        assert cierre.estado_cuadre == "exacto"


# ===========================================================================
# TEST SUITE 2: reglas de negocio — inmutabilidad y existencia
# ===========================================================================

class TestReglasNegocioCierre:

    def test_cierre_ya_cerrado_lanza_http_403(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = MagicMock()
        cierre.is_closed = True
        db = MagicMock()
        db.get.return_value = cierre

        with pytest.raises(HTTPException) as exc:
            cerrar_cierre(db, cierre_id=1, usuario_id=99)

        assert exc.value.status_code == 403

    def test_cierre_inexistente_lanza_http_404(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import cerrar_cierre

        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            cerrar_cierre(db, cierre_id=999, usuario_id=99)

        assert exc.value.status_code == 404


# ===========================================================================
# TEST SUITE 3: crear_cierre
# ===========================================================================

class TestCrearCierre:

    def test_crear_cierre_exitoso(self):
        """crear_cierre persiste el objeto y lo retorna."""
        from app.services.cierre_diario_service import crear_cierre

        payload = MagicMock()
        payload.lineas_movimiento = []
        db = MagicMock()

        resultado = crear_cierre(db, payload, usuario_id=5)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_crear_cierre_error_db_lanza_http_500(self):
        """Si la BD falla, crear_cierre debe lanzar HTTPException 500 y hacer rollback."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import crear_cierre

        payload = MagicMock()
        payload.lineas_movimiento = []
        db = MagicMock()
        db.commit.side_effect = RuntimeError("conexión perdida")

        with pytest.raises(HTTPException) as exc:
            crear_cierre(db, payload, usuario_id=5)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()


# ===========================================================================
# TEST SUITE 4: cerrar_cierre — actualización de inventario
# ===========================================================================

class TestCerrarCierreInventario:

    def test_cierre_con_lineas_actualiza_stock(self):
        """galones_vendidos descuenta stock_llenos; vacios_devueltos suma stock_vacios."""
        from app.services.cierre_diario_service import cerrar_cierre

        producto = MagicMock()
        producto.stock_llenos = 10
        producto.stock_vacios = 5
        producto.formato = "11kg"

        cierre = _make_cierre(total_ventas_calc=10_000, efectivo_rendido=10_000)
        cierre.lineas_movimiento = [
            {"producto_id": 1, "galones_vendidos": 3, "vacios_devueltos": 2}
        ]

        db = MagicMock()
        db.get.side_effect = [cierre, producto]
        db.query.return_value.all.return_value = []

        cerrar_cierre(db, cierre_id=1, usuario_id=99)

        assert producto.stock_llenos == 7   # 10 - 3
        assert producto.stock_vacios == 7   # 5 + 2

    def test_cierre_stock_insuficiente_en_linea_lanza_400(self):
        """Si galones_vendidos > stock_llenos disponible, debe lanzar HTTP 400."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import cerrar_cierre

        producto = MagicMock()
        producto.stock_llenos = 1
        producto.formato = "11kg"

        cierre = _make_cierre()
        cierre.lineas_movimiento = [
            {"producto_id": 1, "galones_vendidos": 5, "vacios_devueltos": 0}
        ]

        db = MagicMock()
        db.get.side_effect = [cierre, producto]

        with pytest.raises(HTTPException) as exc:
            cerrar_cierre(db, cierre_id=1, usuario_id=99)

        assert exc.value.status_code == 400

    def test_cierre_producto_no_encontrado_en_linea_lanza_404(self):
        """Si el producto de la línea no existe en BD, debe lanzar HTTP 404."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre()
        cierre.lineas_movimiento = [
            {"producto_id": 99, "galones_vendidos": 1, "vacios_devueltos": 0}
        ]

        db = MagicMock()
        db.get.side_effect = [cierre, None]  # segundo get retorna None

        with pytest.raises(HTTPException) as exc:
            cerrar_cierre(db, cierre_id=1, usuario_id=99)

        assert exc.value.status_code == 404

    def test_cierre_error_generico_lanza_http_500(self):
        """Si db.commit() falla inesperadamente, debe lanzar HTTP 500 y hacer rollback."""
        from fastapi import HTTPException
        from app.services.cierre_diario_service import cerrar_cierre

        cierre = _make_cierre()
        db = _make_db(cierre)
        db.commit.side_effect = RuntimeError("timeout de BD")

        with pytest.raises(HTTPException) as exc:
            cerrar_cierre(db, cierre_id=1, usuario_id=99)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()


# ===========================================================================
# TEST SUITE 5: actualizar_cierre
# ===========================================================================

class TestActualizarCierre:

    def test_actualizar_cierre_exitoso(self):
        """Actualizar un campo en un cierre abierto debe persistir el cambio."""
        from app.services.cierre_diario_service import actualizar_cierre

        cierre = MagicMock()
        cierre.is_closed = False
        db = MagicMock()
        db.get.return_value = cierre

        payload = MagicMock()
        payload.model_dump.return_value = {"efectivo_rendido": 9_000}

        actualizar_cierre(db, cierre_id=1, payload=payload)

        assert cierre.efectivo_rendido == 9_000
        db.commit.assert_called_once()

    def test_actualizar_cierre_inmutable_lanza_403(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import actualizar_cierre

        cierre = MagicMock()
        cierre.is_closed = True
        db = MagicMock()
        db.get.return_value = cierre

        with pytest.raises(HTTPException) as exc:
            actualizar_cierre(db, cierre_id=1, payload=MagicMock())

        assert exc.value.status_code == 403

    def test_actualizar_cierre_no_encontrado_lanza_404(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import actualizar_cierre

        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            actualizar_cierre(db, cierre_id=999, payload=MagicMock())

        assert exc.value.status_code == 404

    def test_actualizar_cierre_error_db_lanza_500(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import actualizar_cierre

        cierre = MagicMock()
        cierre.is_closed = False
        db = MagicMock()
        db.get.return_value = cierre
        db.commit.side_effect = RuntimeError("fallo BD")

        payload = MagicMock()
        payload.model_dump.return_value = {}

        with pytest.raises(HTTPException) as exc:
            actualizar_cierre(db, cierre_id=1, payload=payload)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()


# ===========================================================================
# TEST SUITE 6: eliminar_cierre
# ===========================================================================

class TestEliminarCierre:

    def test_eliminar_cierre_exitoso(self):
        from app.services.cierre_diario_service import eliminar_cierre

        cierre = MagicMock()
        cierre.is_closed = False
        db = MagicMock()
        db.get.return_value = cierre

        eliminar_cierre(db, cierre_id=1)

        db.delete.assert_called_once_with(cierre)
        db.commit.assert_called_once()

    def test_eliminar_cierre_inmutable_lanza_403(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import eliminar_cierre

        cierre = MagicMock()
        cierre.is_closed = True
        db = MagicMock()
        db.get.return_value = cierre

        with pytest.raises(HTTPException) as exc:
            eliminar_cierre(db, cierre_id=1)

        assert exc.value.status_code == 403

    def test_eliminar_cierre_no_encontrado_lanza_404(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import eliminar_cierre

        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            eliminar_cierre(db, cierre_id=999)

        assert exc.value.status_code == 404

    def test_eliminar_cierre_error_db_lanza_500(self):
        from fastapi import HTTPException
        from app.services.cierre_diario_service import eliminar_cierre

        cierre = MagicMock()
        cierre.is_closed = False
        db = MagicMock()
        db.get.return_value = cierre
        db.commit.side_effect = RuntimeError("fallo BD")

        with pytest.raises(HTTPException) as exc:
            eliminar_cierre(db, cierre_id=1)

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()


# ===========================================================================
# TEST SUITE 7: tarea_email_cierre
# ===========================================================================

class TestTareaEmailCierre:

    def test_tarea_email_cierre_llama_enviar_resumen(self):
        """tarea_email_cierre debe delegar en enviar_resumen_cierre con los datos exactos."""
        from app.services.cierre_diario_service import tarea_email_cierre

        datos = {
            "cierre_id": 1, "chofer_nombre": "Test", "fecha": "16/05/2026",
            "total_ventas_calc": 10_000, "efectivo_rendido": 8_000,
            "vouchers_transbank": 0, "descuentos": 2_000,
            "diferencia": 0, "estado_cuadre": "exacto",
        }

        with patch("app.services.cierre_diario_service.enviar_resumen_cierre") as mock_email:
            tarea_email_cierre(datos)
            mock_email.assert_called_once_with(**datos)
