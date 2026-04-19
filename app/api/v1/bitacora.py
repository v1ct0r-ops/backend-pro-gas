from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.models import BitacoraLlamada, Usuario
from app.schemas.bitacora import BitacoraCreate, BitacoraOut
from app.services.logger_service import registrar_llamada
from database import get_db

router = APIRouter()


@router.post("/", response_model=BitacoraOut, status_code=201)
def crear_registro(
    payload: BitacoraCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return registrar_llamada(db, payload, current_user.id)


@router.get("/", response_model=list[BitacoraOut])
def listar_registros(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return db.query(BitacoraLlamada).order_by(BitacoraLlamada.fecha_hora.desc()).all()
