from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.models import CierreDiario, Usuario
from app.schemas.cierres_diarios import CierreDiarioCreate, CierreDiarioOut, CierreDiarioUpdate
from app.services.cierre_diario_service import (
    actualizar_cierre,
    cerrar_cierre,
    crear_cierre,
    eliminar_cierre,
    tarea_email_cierre,
)
from app.utils.pdf_cierre import generar_pdf_cierre
from database import get_db

router = APIRouter()


@router.post("/", response_model=CierreDiarioOut, status_code=201)
def crear(
    payload: CierreDiarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return crear_cierre(db, payload, current_user.id)


@router.get("/", response_model=list[CierreDiarioOut])
def listar(
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    chofer: Optional[str] = Query(default=None),
    is_closed: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(CierreDiario)
    if fecha_desde:
        q = q.filter(CierreDiario.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(CierreDiario.fecha <= fecha_hasta)
    if chofer:
        q = q.filter(CierreDiario.chofer_nombre.ilike(f"%{chofer}%"))
    if is_closed is not None:
        q = q.filter(CierreDiario.is_closed == is_closed)
    return q.order_by(CierreDiario.fecha.desc()).offset((page - 1) * limit).limit(limit).all()


@router.get("/{id}/pdf")
def exportar_pdf(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    cierre = db.get(CierreDiario, id)
    if not cierre:
        raise HTTPException(404, "Cierre no encontrado")
    pdf_bytes = generar_pdf_cierre(cierre)
    filename = f"cierre_diario_{cierre.id}_{cierre.chofer_nombre.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{id}", response_model=CierreDiarioOut)
def obtener(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    cierre = db.get(CierreDiario, id)
    if not cierre:
        raise HTTPException(404, "Cierre no encontrado")
    return cierre


@router.patch("/{id}/cerrar", response_model=CierreDiarioOut)
def cerrar(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cierre, datos_email = cerrar_cierre(db, id, current_user.id)
    background_tasks.add_task(tarea_email_cierre, datos_email)
    return cierre


@router.patch("/{id}", response_model=CierreDiarioOut)
def actualizar(
    id: int,
    payload: CierreDiarioUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return actualizar_cierre(db, id, payload)


@router.delete("/{id}", status_code=204)
def eliminar(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    eliminar_cierre(db, id)
