from datetime import datetime, timezone
from typing import Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import CierreDiario, ProductoMaestro
from app.schemas.cierres_diarios import CierreDiarioCreate, CierreDiarioUpdate
from app.services.email_service import enviar_resumen_cierre


def crear_cierre(db: Session, payload: CierreDiarioCreate, usuario_id: int) -> CierreDiario:
    cierre = CierreDiario(
        chofer_nombre=payload.chofer_nombre,
        fecha=payload.fecha,
        efectivo_rendido=payload.efectivo_rendido,
        vouchers_transbank=payload.vouchers_transbank,
        descuentos=payload.descuentos,
        total_ventas_calc=payload.total_ventas_calc,
        is_closed=False,
        usuario_id=usuario_id,
    )
    try:
        db.add(cierre)
        db.commit()
        db.refresh(cierre)
        return cierre
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al crear cierre: {e}")


def cerrar_cierre(db: Session, cierre_id: int, usuario_id: int) -> Tuple[CierreDiario, dict]:
    try:
        cierre = db.get(CierreDiario, cierre_id, with_for_update=True)
        if not cierre:
            raise HTTPException(404, "Cierre no encontrado")
        if cierre.is_closed:
            raise HTTPException(403, "Este cierre ya está cerrado y es inmutable")

        total_rendido = cierre.efectivo_rendido + cierre.vouchers_transbank
        diferencia = cierre.total_ventas_calc - total_rendido

        if diferencia == 0:
            estado_cuadre = "exacto"
        elif diferencia > 0:
            estado_cuadre = "faltante"
        else:
            estado_cuadre = "sobrante"

        productos = db.query(ProductoMaestro).all()
        stock_snapshot = {
            str(p.id): {
                "formato": p.formato,
                "stock_llenos": p.stock_llenos,
                "stock_vacios": p.stock_vacios,
            }
            for p in productos
        }

        cierre.is_closed = True
        cierre.diferencia = diferencia
        cierre.estado_cuadre = estado_cuadre
        cierre.stock_snapshot = stock_snapshot
        cierre.closed_at = datetime.now(timezone.utc)
        cierre.cerrado_por_id = usuario_id

        db.commit()
        db.refresh(cierre)
        return cierre, _datos_email(cierre)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al cerrar cierre: {str(e)}")


def actualizar_cierre(db: Session, cierre_id: int, payload: CierreDiarioUpdate) -> CierreDiario:
    try:
        cierre = db.get(CierreDiario, cierre_id)
        if not cierre:
            raise HTTPException(404, "Cierre no encontrado")
        if cierre.is_closed:
            raise HTTPException(403, "Este cierre ya está cerrado y es inmutable")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(cierre, field, value)

        db.commit()
        db.refresh(cierre)
        return cierre
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al actualizar cierre: {e}")


def eliminar_cierre(db: Session, cierre_id: int) -> None:
    try:
        cierre = db.get(CierreDiario, cierre_id)
        if not cierre:
            raise HTTPException(404, "Cierre no encontrado")
        if cierre.is_closed:
            raise HTTPException(403, "Este cierre ya está cerrado y es inmutable")

        db.delete(cierre)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al eliminar cierre: {e}")


def _datos_email(cierre: CierreDiario) -> dict:
    return {
        "cierre_id": cierre.id,
        "chofer_nombre": cierre.chofer_nombre,
        "fecha": cierre.fecha.strftime("%d/%m/%Y %H:%M"),
        "total_ventas_calc": cierre.total_ventas_calc,
        "efectivo_rendido": cierre.efectivo_rendido,
        "vouchers_transbank": cierre.vouchers_transbank,
        "descuentos": cierre.descuentos,
        "diferencia": cierre.diferencia,
        "estado_cuadre": cierre.estado_cuadre,
    }


def tarea_email_cierre(datos: dict) -> None:
    enviar_resumen_cierre(**datos)
