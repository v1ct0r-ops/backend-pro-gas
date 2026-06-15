from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.pagination import PaginationParams
from app.models.models import Cliente, Usuario
from app.schemas.clientes import ClienteCreate, ClienteOut, ClienteUpdate
from app.schemas.pagination import Page
from database import get_db

router = APIRouter()

_admin = require_role("super_admin")


@router.get("/buscar", response_model=list[ClienteOut])
def buscar_clientes(
    q: str = Query(min_length=1, description="Texto a buscar en RUT o nombre"),
    limit: int = Query(default=10, ge=1, le=25, description="Máximo de resultados (1-25)"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return (
        db.query(Cliente)
        .filter(
            Cliente.estado == True,  # noqa: E712
            or_(
                Cliente.rut.ilike(f"%{q}%"),
                Cliente.nombre.ilike(f"%{q}%"),
            ),
        )
        .order_by(Cliente.nombre.asc(), Cliente.id.asc())
        .limit(limit)
        .all()
    )


@router.get("/", response_model=Page[ClienteOut])
def listar_clientes(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(Cliente).filter(Cliente.estado == True)  # noqa: E712
    total = q.count()
    items = (
        q.order_by(Cliente.nombre.asc(), Cliente.id.asc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


@router.get("/{id}", response_model=ClienteOut)
def obtener_cliente(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    cliente = db.get(Cliente, id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return cliente


@router.post("/", response_model=ClienteOut, status_code=201)
def crear_cliente(
    payload: ClienteCreate,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    if db.query(Cliente).filter(Cliente.rut == payload.rut).first():
        raise HTTPException(400, "RUT ya registrado")
    cliente = Cliente(estado=True, **payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.patch("/{id}", response_model=ClienteOut)
def actualizar_cliente(
    id: int,
    payload: ClienteUpdate,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    cliente = db.get(Cliente, id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No se proporcionaron campos para actualizar")

    if "rut" in data and data["rut"] != cliente.rut:
        conflicto = db.query(Cliente).filter(
            Cliente.rut == data["rut"], Cliente.id != id
        ).first()
        if conflicto:
            raise HTTPException(400, "RUT ya registrado por otro cliente")

    for field, value in data.items():
        setattr(cliente, field, value)

    cliente.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/{id}", status_code=204)
def eliminar_cliente(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    cliente = db.get(Cliente, id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    cliente.estado = False
    cliente.updated_at = datetime.now(timezone.utc)
    db.commit()
