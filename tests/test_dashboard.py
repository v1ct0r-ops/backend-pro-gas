"""
Tests unitarios — dashboard_service.py

Cubre todas las funciones privadas (_caja_hoy, _ventas_mes, _salud_cuadres,
_grafico_7_dias) y la función pública get_dashboard_resumen.
Sin conexión a BD — todo vía MagicMock con cadenas de query SQLAlchemy mockeadas.
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# TEST SUITE 1: _caja_hoy
# ===========================================================================

class TestCajaHoy:

    def test_sin_cierre_hoy_retorna_existe_false(self):
        from app.services.dashboard_service import _caja_hoy

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        resultado = _caja_hoy(db, es_admin=True)

        assert resultado == {"existe": False}

    def test_con_cierre_admin_muestra_datos_financieros(self):
        """es_admin=True: total_ventas_calc y efectivo_rendido son visibles."""
        from app.services.dashboard_service import _caja_hoy

        row = MagicMock()
        row.is_closed = True
        row.estado_cuadre = "exacto"
        row.total_ventas_calc = 50_000
        row.efectivo_rendido = 50_000

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [row]

        resultado = _caja_hoy(db, es_admin=True)

        assert resultado["existe"] is True
        assert resultado["is_closed"] is True
        assert resultado["estado_cuadre"] == "exacto"
        assert resultado["total_ventas_calc"] == 50_000
        assert resultado["efectivo_rendido"] == 50_000

    def test_con_cierre_operador_oculta_datos_financieros(self):
        """es_admin=False: los campos financieros deben ser None."""
        from app.services.dashboard_service import _caja_hoy

        row = MagicMock()
        row.is_closed = False
        row.estado_cuadre = None
        row.total_ventas_calc = 50_000
        row.efectivo_rendido = 50_000

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [row]

        resultado = _caja_hoy(db, es_admin=False)

        assert resultado["existe"] is True
        assert resultado["total_ventas_calc"] is None
        assert resultado["efectivo_rendido"] is None

    def test_todos_cerrados_con_faltante_retorna_estado_faltante(self):
        """Múltiples cierres todos cerrados: si hay faltante → 'faltante'."""
        from app.services.dashboard_service import _caja_hoy

        row1 = MagicMock()
        row1.is_closed = True
        row1.estado_cuadre = "exacto"
        row1.total_ventas_calc = 10_000
        row1.efectivo_rendido = 10_000

        row2 = MagicMock()
        row2.is_closed = True
        row2.estado_cuadre = "faltante"
        row2.total_ventas_calc = 8_000
        row2.efectivo_rendido = 7_000

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [row1, row2]

        resultado = _caja_hoy(db, es_admin=True)

        assert resultado["estado_cuadre"] == "faltante"
        assert resultado["is_closed"] is True

    def test_todos_cerrados_sin_faltante_con_sobrante_retorna_sobrante(self):
        """Múltiples cierres todos cerrados, ninguno faltante pero sí sobrante → 'sobrante'."""
        from app.services.dashboard_service import _caja_hoy

        row1 = MagicMock()
        row1.is_closed = True
        row1.estado_cuadre = "exacto"
        row1.total_ventas_calc = 10_000
        row1.efectivo_rendido = 10_000

        row2 = MagicMock()
        row2.is_closed = True
        row2.estado_cuadre = "sobrante"
        row2.total_ventas_calc = 8_000
        row2.efectivo_rendido = 9_000

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [row1, row2]

        resultado = _caja_hoy(db, es_admin=True)

        assert resultado["estado_cuadre"] == "sobrante"


# ===========================================================================
# TEST SUITE 2: _ventas_mes
# ===========================================================================

class TestVentasMes:

    def test_sin_ventas_total_es_cero_para_admin(self):
        """Sin ventas revendedor ni cierres en el mes, total_clp agregado es 0 (coalesce)."""
        from app.services.dashboard_service import _ventas_mes

        row_rev = MagicMock()
        row_rev.total_clp = None
        row_rev.kilos = 0.0
        row_cierre = MagicMock()
        row_cierre.total_clp = 0

        db = MagicMock()
        db.query.return_value.filter.return_value.one.side_effect = [row_rev, row_cierre]

        resultado = _ventas_mes(db, es_admin=True)

        assert resultado["total_clp"] == 0
        assert resultado["kilos_totales"] == 0.0

    def test_con_ventas_admin_suma_revendedor_y_cierres(self):
        """total_clp agrega ventas revendedor + ventas por cierres sellados del mes."""
        from app.services.dashboard_service import _ventas_mes

        row_rev = MagicMock()
        row_rev.total_clp = 100_000
        row_rev.kilos = 88.5
        row_cierre = MagicMock()
        row_cierre.total_clp = 50_000

        db = MagicMock()
        db.query.return_value.filter.return_value.one.side_effect = [row_rev, row_cierre]

        resultado = _ventas_mes(db, es_admin=True)

        assert resultado["total_clp"] == 150_000
        assert resultado["kilos_totales"] == 88.5

    def test_operador_no_ve_total_clp(self):
        from app.services.dashboard_service import _ventas_mes

        row = MagicMock()
        row.total_clp = 150_000
        row.kilos = 88.5

        db = MagicMock()
        db.query.return_value.filter.return_value.one.return_value = row

        resultado = _ventas_mes(db, es_admin=False)

        assert resultado["total_clp"] is None
        assert resultado["kilos_totales"] == 88.5


# ===========================================================================
# TEST SUITE 3: _salud_cuadres
# ===========================================================================

class TestSaludCuadres:

    def test_sin_faltantes_retorna_cero(self):
        from app.services.dashboard_service import _salud_cuadres

        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 0

        resultado = _salud_cuadres(db)

        assert resultado == {"cierres_con_faltante": 0}

    def test_con_faltantes_retorna_conteo(self):
        from app.services.dashboard_service import _salud_cuadres

        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 3

        resultado = _salud_cuadres(db)

        assert resultado == {"cierres_con_faltante": 3}

    def test_scalar_none_tratado_como_cero(self):
        """Si no hay registros, scalar() puede retornar None — debe tratarse como 0."""
        from app.services.dashboard_service import _salud_cuadres

        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = None

        resultado = _salud_cuadres(db)

        assert resultado == {"cierres_con_faltante": 0}


# ===========================================================================
# TEST SUITE 4: _grafico_7_dias
# ===========================================================================

class TestGrafico7Dias:

    def test_retorna_exactamente_7_dias(self):
        """El gráfico siempre debe tener 7 entradas (hoy - 6 días hasta hoy)."""
        from app.services.dashboard_service import _grafico_7_dias

        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
            [],  # ventas: sin datos
            [],  # cargas: sin datos
        ]

        resultado = _grafico_7_dias(db)

        assert len(resultado) == 7

    def test_dias_con_ventas_tienen_kilos_correctos(self):
        """Los kilos de un día con venta deben mapearse correctamente."""
        from app.services.dashboard_service import _grafico_7_dias

        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        venta_row = MagicMock()
        venta_row.dia = ayer
        venta_row.kilos = 55.0

        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
            [venta_row],  # ventas
            [],           # cargas
        ]

        resultado = _grafico_7_dias(db)

        # Buscar el día correspondiente a ayer en el resultado
        dia_ayer = next((r for r in resultado if r["fecha"] == ayer), None)
        assert dia_ayer is not None
        assert dia_ayer["kilos_vendidos"] == 55.0
        assert dia_ayer["kilos_ingresados"] == 0.0

    def test_dias_sin_datos_tienen_kilos_cero(self):
        from app.services.dashboard_service import _grafico_7_dias

        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [[], []]

        resultado = _grafico_7_dias(db)

        for dia in resultado:
            assert dia["kilos_vendidos"] == 0.0
            assert dia["kilos_ingresados"] == 0.0


# ===========================================================================
# TEST SUITE 5: get_dashboard_resumen
# ===========================================================================

class TestGetDashboardResumen:

    def test_resumen_combina_todas_las_secciones(self):
        """get_dashboard_resumen debe retornar las 4 claves del dashboard."""
        from app.services.dashboard_service import get_dashboard_resumen

        caja = {"existe": False}
        ventas = {"total_clp": None, "kilos_totales": 0.0}
        salud = {"cierres_con_faltante": 0}
        grafico = [{"fecha": date.today(), "kilos_vendidos": 0.0, "kilos_ingresados": 0.0}] * 7

        with patch("app.services.dashboard_service._caja_hoy", return_value=caja), \
             patch("app.services.dashboard_service._ventas_mes", return_value=ventas), \
             patch("app.services.dashboard_service._salud_cuadres", return_value=salud), \
             patch("app.services.dashboard_service._grafico_7_dias", return_value=grafico):

            resultado = get_dashboard_resumen(db=MagicMock(), es_admin=True)

        assert resultado["caja_hoy"] == caja
        assert resultado["ventas_mes_actual"] == ventas
        assert resultado["salud_cuadres"] == salud
        assert resultado["grafico_7_dias"] == grafico


# ===========================================================================
# TEST SUITE 6: _kilos_cierres_por_dia
# ===========================================================================

class TestKilosCierresPorDia:

    def test_acumula_kilos_y_salta_cierres_vacios_y_lineas_invalidas(self):
        """Cubre las ramas internas del bucle de _kilos_cierres_por_dia:
        - Cierre sin lineas_movimiento → continue
        - Linea con producto desconocido → skip
        - Linea con galones=0 → skip
        - Linea válida → acumula kilos (galones × peso_kg)
        """
        from datetime import datetime
        from app.services.dashboard_service import _kilos_cierres_por_dia

        hoy = date.today()

        prod = MagicMock()
        prod.id = 1
        prod.peso_kg = 11.0

        c_vacio = MagicMock()
        c_vacio.lineas_movimiento = []

        c_con_lineas = MagicMock()
        c_con_lineas.fecha = datetime(hoy.year, hoy.month, hoy.day, 10, 0, 0)
        c_con_lineas.lineas_movimiento = [
            {"producto_id": 1, "galones_vendidos": 5, "vacios_devueltos": 0},
            {"producto_id": 99, "galones_vendidos": 3, "vacios_devueltos": 0},
            {"producto_id": 1, "galones_vendidos": 0, "vacios_devueltos": 0},
        ]

        db = MagicMock()
        db.query.return_value.all.return_value = [prod]
        db.query.return_value.filter.return_value.all.return_value = [c_vacio, c_con_lineas]

        resultado = _kilos_cierres_por_dia(db, hoy, hoy)

        assert resultado == {hoy: 55.0}
