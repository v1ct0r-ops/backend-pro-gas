from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.pagination import PaginationParams
from app.models.models import BitacoraLlamada, Usuario
from app.schemas.bitacora import BitacoraCreate, BitacoraOut
from app.schemas.pagination import Page
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


@router.get("/", response_model=Page[BitacoraOut])
def listar_registros(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(BitacoraLlamada)
    total = q.count()
    items = (
        q.order_by(BitacoraLlamada.fecha_hora.desc(), BitacoraLlamada.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}
