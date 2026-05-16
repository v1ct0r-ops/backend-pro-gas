from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import CierreDiario, MediaCarga, VentaRevendedor

SANTIAGO = ZoneInfo("America/Santiago")


def _hoy_santiago() -> date:
    return datetime.now(SANTIAGO).date()


def _caja_hoy(db: Session, es_admin: bool) -> dict:
    hoy = _hoy_santiago()

    # Fetch only the scalar columns needed — no full ORM hydration
    row = (
        db.query(
            CierreDiario.is_closed,
            CierreDiario.estado_cuadre,
            CierreDiario.total_ventas_calc,
            CierreDiario.efectivo_rendido,
        )
        .filter(func.date(CierreDiario.fecha) == hoy)
        .order_by(CierreDiario.id.desc())
        .first()
    )

    if row is None:
        return {"existe": False}

    return {
        "existe": True,
        "is_closed": row.is_closed,
        "estado_cuadre": row.estado_cuadre,
        "total_ventas_calc": row.total_ventas_calc if es_admin else None,
        "efectivo_rendido": row.efectivo_rendido if es_admin else None,
    }


def _ventas_mes(db: Session, es_admin: bool) -> dict:
    hoy = _hoy_santiago()
    inicio_mes = hoy.replace(day=1)

    dia = func.date(VentaRevendedor.fecha)
    row = (
        db.query(
            func.sum(VentaRevendedor.total_final).label("total_clp"),
            func.coalesce(func.sum(VentaRevendedor.kilos_totales), 0.0).label("kilos"),
        )
        .filter(dia >= inicio_mes, dia <= hoy)
        .one()
    )

    return {
        "total_clp": int(row.total_clp) if (es_admin and row.total_clp is not None) else None,
        "kilos_totales": float(row.kilos or 0),
    }


def _salud_cuadres(db: Session) -> dict:
    hoy = _hoy_santiago()
    desde = hoy - timedelta(days=6)

    dia = func.date(CierreDiario.fecha)
    count = (
        db.query(func.count(CierreDiario.id))
        .filter(
            dia >= desde,
            dia <= hoy,
            CierreDiario.estado_cuadre == "faltante",
        )
        .scalar()
    )

    return {"cierres_con_faltante": count or 0}


def _grafico_7_dias(db: Session) -> list[dict]:
    hoy = _hoy_santiago()
    desde = hoy - timedelta(days=6)

    # Aggregate ventas revendedor by day — pure DB aggregation, no Python iteration
    dia_venta = func.date(VentaRevendedor.fecha)
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

    # Aggregate medias cargas (ingresos) by day
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
            "kilos_vendidos": ventas_map.get(desde + timedelta(days=i), 0.0),
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
