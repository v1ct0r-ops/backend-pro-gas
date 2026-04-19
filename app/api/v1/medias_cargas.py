from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.models import MediaCarga, Usuario
from app.schemas.medias_cargas import MediaCargaIn, MediaCargaOut
from app.services.media_carga_service import procesar_media_carga
from database import get_db

router = APIRouter()


@router.post("/", response_model=MediaCargaOut, status_code=201)
def crear_media_carga(
    payload: MediaCargaIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return procesar_media_carga(db, payload, current_user.id)


@router.get("/", response_model=list[MediaCargaOut])
def listar_medias_cargas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return db.query(MediaCarga).order_by(MediaCarga.fecha.desc()).all()


@router.get("/{id}", response_model=MediaCargaOut)
def obtener_media_carga(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    mc = db.get(MediaCarga, id)
    if not mc:
        raise HTTPException(404, "Media carga no encontrada")
    return mc
