from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import CierreDiario, MediaCarga, ProductoMaestro, VentaRevendedor

SANTIAGO = ZoneInfo("America/Santiago")


def _hoy_santiago() -> date:
    return datetime.now(SANTIAGO).date()


def _fecha_stgo(col):
    """Cast a naive-UTC TIMESTAMP column to a calendar date in America/Santiago."""
    return func.date(func.timezone("America/Santiago", func.timezone("UTC", col)))


def _kilos_cierres_por_dia(db: Session, desde: date, hasta: date) -> dict[date, float]:
    """Kilos sold via sealed cierres diarios, grouped by Santiago calendar date."""
    pesos = {
        p.id: p.peso_kg
        for p in db.query(ProductoMaestro.id, ProductoMaestro.peso_kg).all()
    }

    dia_cierre = _fecha_stgo(CierreDiario.fecha)
    cierres = (
        db.query(CierreDiario.fecha, CierreDiario.lineas_movimiento)
        .filter(
            CierreDiario.is_closed == True,
            CierreDiario.anulado == False,
            dia_cierre >= desde,
            dia_cierre <= hasta,
        )
        .all()
    )

    kilos_por_dia: dict[date, float] = {}
    for cierre in cierres:
        if not cierre.lineas_movimiento:
            continue
        fecha_stgo = (
            cierre.fecha.replace(tzinfo=timezone.utc).astimezone(SANTIAGO).date()
        )
        for linea in cierre.lineas_movimiento:
            producto_id = linea.get("producto_id")
            galones = linea.get("galones_vendidos", 0)
            if producto_id not in pesos or not galones:
                continue
            kilos_por_dia[fecha_stgo] = (
                kilos_por_dia.get(fecha_stgo, 0.0) + galones * pesos[producto_id]
            )

    return kilos_por_dia


def _caja_hoy(db: Session, es_admin: bool) -> dict:
    hoy = _hoy_santiago()

    rows = (
        db.query(
            CierreDiario.is_closed,
            CierreDiario.estado_cuadre,
            CierreDiario.total_ventas_calc,
            CierreDiario.efectivo_rendido,
        )
        .filter(
            _fecha_stgo(CierreDiario.fecha) == hoy,
            CierreDiario.anulado == False,
        )
        .all()
    )

    if not rows:
        return {"existe": False}

    todos_cerrados = all(r.is_closed for r in rows)

    if not todos_cerrados:
        estado_cuadre = None
    elif any(r.estado_cuadre == "faltante" for r in rows):
        estado_cuadre = "faltante"
    elif any(r.estado_cuadre == "sobrante" for r in rows):
        estado_cuadre = "sobrante"
    else:
        estado_cuadre = "exacto"

    return {
        "existe": True,
        "is_closed": todos_cerrados,
        "estado_cuadre": estado_cuadre,
        "total_ventas_calc": sum(r.total_ventas_calc for r in rows) if es_admin else None,
        "efectivo_rendido": sum(r.efectivo_rendido for r in rows) if es_admin else None,
    }


def _ventas_mes(db: Session, es_admin: bool) -> dict:
    hoy = _hoy_santiago()
    inicio_mes = hoy.replace(day=1)

    dia_venta = _fecha_stgo(VentaRevendedor.fecha)
    row_rev = (
        db.query(
            func.sum(VentaRevendedor.total_bruto).label("total_clp"),
            func.coalesce(func.sum(VentaRevendedor.kilos_totales), 0.0).label("kilos"),
        )
        .filter(dia_venta >= inicio_mes, dia_venta <= hoy)
        .one()
    )

    dia_cierre = _fecha_stgo(CierreDiario.fecha)
    row_cierre = (
        db.query(
            func.coalesce(func.sum(CierreDiario.total_ventas_calc), 0).label("total_clp"),
        )
        .filter(
            dia_cierre >= inicio_mes,
            dia_cierre <= hoy,
            CierreDiario.is_closed == True,
            CierreDiario.anulado == False,
        )
        .one()
    )

    kilos_cierres = sum(_kilos_cierres_por_dia(db, inicio_mes, hoy).values())
    total_clp = (row_rev.total_clp or 0) + row_cierre.total_clp

    return {
        "total_clp": int(total_clp) if es_admin else None,
        "kilos_totales": float(row_rev.kilos or 0) + kilos_cierres,
    }


def _salud_cuadres(db: Session) -> dict:
    hoy = _hoy_santiago()
    desde = hoy - timedelta(days=6)

    dia = _fecha_stgo(CierreDiario.fecha)
    count = (
        db.query(func.count(CierreDiario.id))
        .filter(
            dia >= desde,
            dia <= hoy,
            CierreDiario.estado_cuadre == "faltante",
            CierreDiario.anulado == False,
        )
        .scalar()
    )

    return {"cierres_con_faltante": count or 0}


def _grafico_7_dias(db: Session) -> list[dict]:
    hoy = _hoy_santiago()
    desde = hoy - timedelta(days=6)

    # Ventas revendedor: instante UTC → fecha en Santiago
    dia_venta = _fecha_stgo(VentaRevendedor.fecha)
    ventas_rows = (
        db.query(
            dia_venta.label("dia"),
            func.coalesce(func.sum(VentaRevendedor.kilos_totales), 0.0).label("kilos"),
        )
        .filter(dia_venta >= desde, dia_venta <= hoy)
        .group_by(dia_venta)
        .all()
    )
    ventas_map: dict[date, float] = {row.dia: float(row.kilos) for row in ventas_rows}

    # Canal público: kilos por cierres sellados en la ventana de 7 días
    cierres_map = _kilos_cierres_por_dia(db, desde, hoy)

    # Medias cargas: fecha calendario (medianoche) — sin conversión de zona horaria
    dia_carga = func.date(MediaCarga.fecha)
    cargas_rows = (
        db.query(
            dia_carga.label("dia"),
            func.coalesce(func.sum(MediaCarga.kilos_totales), 0.0).label("kilos"),
        )
        .filter(dia_carga >= desde, dia_carga <= hoy)
        .group_by(dia_carga)
        .all()
    )
    cargas_map: dict[date, float] = {row.dia: float(row.kilos) for row in cargas_rows}

    return [
        {
            "fecha": desde + timedelta(days=i),
            "kilos_vendidos": (
                ventas_map.get(desde + timedelta(days=i), 0.0)
                + cierres_map.get(desde + timedelta(days=i), 0.0)
            ),
            "kilos_ingresados": cargas_map.get(desde + timedelta(days=i), 0.0),
        }
        for i in range(7)
    ]


def get_dashboard_resumen(db: Session, es_admin: bool) -> dict:
    return {
        "caja_hoy": _caja_hoy(db, es_admin),
        "ventas_mes_actual": _ventas_mes(db, es_admin),
        "salud_cuadres": _salud_cuadres(db),
        "grafico_7_dias": _grafico_7_dias(db),
    }
