from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.pagination import PaginationParams
from app.models.models import CierreDiario, Usuario
from app.schemas.cierres_diarios import (
    CierreDiarioAnular,
    CierreDiarioCreate,
    CierreDiarioOut,
    CierreDiarioUpdate,
)
from app.schemas.pagination import Page
from app.services.cierre_diario_service import (
    actualizar_cierre,
    anular_cierre,
    cerrar_cierre,
    crear_cierre,
    eliminar_cierre,
    tarea_email_cierre,
)
from app.utils.pdf_cierre import generar_pdf_cierre
from database import get_db

router = APIRouter()

_admin = require_role("super_admin")


@router.post("/", response_model=CierreDiarioOut, status_code=201)
def crear(
    payload: CierreDiarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return crear_cierre(db, payload, current_user.id)


@router.get("/", response_model=Page[CierreDiarioOut])
def listar(
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    chofer: Optional[str] = Query(default=None),
    is_closed: Optional[bool] = Query(default=None),
    incluir_anulados: bool = Query(default=False),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(CierreDiario)
    if not incluir_anulados:
        q = q.filter(CierreDiario.anulado == False)
    if fecha_desde:
        q = q.filter(CierreDiario.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(CierreDiario.fecha <= fecha_hasta)
    if chofer:
        q = q.filter(CierreDiario.chofer_nombre.ilike(f"%{chofer}%"))
    if is_closed is not None:
        q = q.filter(CierreDiario.is_closed == is_closed)

    total = q.count()
    items = (
        q.order_by(CierreDiario.fecha.desc(), CierreDiario.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


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
    current_user: Usuario = _admin,
):
    cierre, datos_email = cerrar_cierre(db, id, current_user.id)
    background_tasks.add_task(tarea_email_cierre, datos_email)
    return cierre


@router.patch("/{id}/anular", response_model=CierreDiarioOut)
def anular(
    id: int,
    payload: CierreDiarioAnular,
    db: Session = Depends(get_db),
    current_user: Usuario = _admin,
):
    return anular_cierre(db, id, current_user.id, payload.motivo_anulacion)


@router.patch("/{id}", response_model=CierreDiarioOut)
def actualizar(
    id: int,
    payload: CierreDiarioUpdate,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    return actualizar_cierre(db, id, payload)


@router.delete("/{id}", status_code=204)
def eliminar(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    eliminar_cierre(db, id)
