from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.models import CierreDiario, Usuario
from app.schemas.cierres_diarios import CierreDiarioCreate, CierreDiarioOut
from app.services.cierre_diario_service import cerrar_cierre, crear_cierre, tarea_email_cierre
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
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return db.query(CierreDiario).order_by(CierreDiario.fecha.desc()).all()


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
    _: Usuario = Depends(get_current_user),
):
    cierre, datos_email = cerrar_cierre(db, id)
    background_tasks.add_task(tarea_email_cierre, datos_email)
    return cierre
