from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.models.models import ProductoMaestro, Usuario, VentaRevendedor
from app.schemas.ventas_revendedor import (
    VentaRevendedorIn,
    VentaRevendedorListOut,
    VentaRevendedorOut,
    VentaRevendedorPatch,
)
from app.services.venta_revendedor_service import registrar_venta_revendedor
from app.utils.pdf_venta_revendedor import generar_pdf_venta_revendedor
from database import get_db

router = APIRouter()


@router.post("/", response_model=VentaRevendedorOut, status_code=201)
def crear_venta_revendedor(
    payload: VentaRevendedorIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return registrar_venta_revendedor(db, payload, current_user.id)


@router.get("/", response_model=VentaRevendedorListOut)
def listar_ventas_revendedor(
    fecha_desde: Optional[datetime] = Query(None, description="Filtrar ventas desde esta fecha (ISO 8601)"),
    fecha_hasta: Optional[datetime] = Query(None, description="Filtrar ventas hasta esta fecha (ISO 8601)"),
    rut_cliente: Optional[str] = Query(None, description="Búsqueda parcial por RUT del cliente"),
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(20, ge=1, le=100, description="Registros por página"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(VentaRevendedor)

    if fecha_desde:
        q = q.filter(VentaRevendedor.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(VentaRevendedor.fecha <= fecha_hasta)
    if rut_cliente:
        q = q.filter(VentaRevendedor.rut_cliente.ilike(f"%{rut_cliente}%"))

    total = q.count()
    items = (
        q.order_by(VentaRevendedor.fecha.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {"items": items, "total": total}


@router.get("/{id}/pdf")
def exportar_venta_pdf(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    venta = db.get(VentaRevendedor, id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")

    pdf_bytes = generar_pdf_venta_revendedor(venta)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=venta_{id}.pdf"},
    )


@router.get("/{id}", response_model=VentaRevendedorOut)
def obtener_venta_revendedor(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    venta = db.get(VentaRevendedor, id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    return venta


@router.patch("/{id}", response_model=VentaRevendedorOut)
def actualizar_venta_revendedor(
    id: int,
    payload: VentaRevendedorPatch,
    db: Session = Depends(get_db),
    current_user: Usuario = require_role("super_admin"),
):
    venta = db.get(VentaRevendedor, id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No se proporcionaron campos para actualizar")

    try:
        for field, value in data.items():
            setattr(venta, field, value)
        db.commit()
        db.refresh(venta)
        return venta
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al actualizar la venta: {str(e)}")


@router.delete("/{id}", status_code=204)
def eliminar_venta_revendedor(
    id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = require_role("super_admin"),
):
    venta = db.get(VentaRevendedor, id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")

    try:
        # Reponer stock antes de borrar el registro
        for linea in venta.lineas:
            producto = db.get(ProductoMaestro, linea.producto_id)
            if producto:
                producto.stock_llenos += linea.cantidad

        db.delete(venta)  # cascade elimina las lineas automáticamente
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al eliminar la venta: {str(e)}")
