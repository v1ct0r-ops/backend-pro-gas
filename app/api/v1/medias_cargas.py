from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import exists, func
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, require_role
from app.core.pagination import PaginationParams
from app.models.models import MediaCarga, MediaCargaHistorial, Usuario
from app.schemas.medias_cargas import (
    MediaCargaHistorialOut,
    MediaCargaIn,
    MediaCargaOut,
)
from app.schemas.pagination import Page
from app.services.media_carga_service import (
    anular_media_carga as _svc_anular,
    procesar_media_carga,
)
from app.utils.pdf_historial import generar_pdf_historial
from database import get_db

router = APIRouter()

_admin = require_role("super_admin")


@router.post("/", response_model=MediaCargaOut, status_code=201)
def crear_media_carga(
    payload: MediaCargaIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return procesar_media_carga(db, payload, current_user.id)


@router.get("/", response_model=Page[MediaCargaOut])
def listar_medias_cargas(
    pagination: PaginationParams = Depends(),
    incluir_anuladas: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(MediaCarga)
    if not incluir_anuladas:
        q = q.filter(MediaCarga.anulada == False)  # noqa: E712
    total = q.count()
    items = (
        q.order_by(MediaCarga.fecha.desc(), MediaCarga.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


# IMPORTANTE: /historial debe ir ANTES de /{id} para que FastAPI no lo interprete como un ID
@router.get("/historial", response_model=Page[MediaCargaHistorialOut])
def listar_historial(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    mc_anulada = exists().where(
        (MediaCarga.id == MediaCargaHistorial.media_carga_id) & (MediaCarga.anulada == True)  # noqa: E712
    )
    total = db.query(func.count(MediaCargaHistorial.id)).filter(~mc_anulada).scalar()

    # Paginamos sobre IDs primero para evitar que el JOIN de lineas distorsione limit/offset
    id_rows = (
        db.query(MediaCargaHistorial.id)
        .filter(~mc_anulada)
        .order_by(MediaCargaHistorial.fecha_registro.desc(), MediaCargaHistorial.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    ids = [r[0] for r in id_rows]

    if ids:
        registros = (
            db.query(MediaCargaHistorial)
            .options(
                joinedload(MediaCargaHistorial.lineas),
                joinedload(MediaCargaHistorial.registrado_por),
                joinedload(MediaCargaHistorial.media_carga),
            )
            .filter(MediaCargaHistorial.id.in_(ids))
            .order_by(MediaCargaHistorial.fecha_registro.desc(), MediaCargaHistorial.id.desc())
            .all()
        )
    else:
        registros = []

    return {
        "items": [_historial_to_out(r) for r in registros],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }


@router.get("/historial/{historial_id}", response_model=MediaCargaHistorialOut)
def obtener_historial(
    historial_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    registro = (
        db.query(MediaCargaHistorial)
        .options(
            joinedload(MediaCargaHistorial.lineas),
            joinedload(MediaCargaHistorial.registrado_por),
            joinedload(MediaCargaHistorial.media_carga),
        )
        .filter(MediaCargaHistorial.id == historial_id)
        .first()
    )
    if not registro:
        raise HTTPException(404, "Registro de historial no encontrado")
    return _historial_to_out(registro)


@router.get("/historial/{historial_id}/pdf")
def exportar_historial_pdf(
    historial_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    registro = (
        db.query(MediaCargaHistorial)
        .options(
            joinedload(MediaCargaHistorial.lineas),
            joinedload(MediaCargaHistorial.registrado_por),
            joinedload(MediaCargaHistorial.media_carga),
        )
        .filter(MediaCargaHistorial.id == historial_id)
        .first()
    )
    if not registro:
        raise HTTPException(404, "Registro de historial no encontrado")

    pdf_bytes = generar_pdf_historial(registro)
    filename = f"media_carga_{registro.numero_guia}_{registro.id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.delete("/{id}", response_model=MediaCargaOut)
def anular_media_carga(
    id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = _admin,
):
    return _svc_anular(db, id, current_user.id)


def _historial_to_out(h: MediaCargaHistorial) -> MediaCargaHistorialOut:
    data = MediaCargaHistorialOut.model_validate(h)
    data.registrado_por_nombre = h.registrado_por.nombre if h.registrado_por else None
    data.anulada = h.media_carga.anulada if h.media_carga else False
    return data
