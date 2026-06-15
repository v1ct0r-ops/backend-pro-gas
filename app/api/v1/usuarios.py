from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.core.pagination import PaginationParams
from app.core.security import hash_password
from app.models.models import (
    BitacoraLlamada,
    CierreDiario,
    MediaCarga,
    MediaCargaHistorial,
    Usuario,
    VentaRevendedor,
)
from app.schemas.pagination import Page
from app.schemas.usuarios import UsuarioCreate, UsuarioOut, UsuarioUpdate
from database import get_db

router = APIRouter()

_admin = require_role("super_admin")


def _tiene_referencias(db: Session, usuario_id: int) -> bool:
    """True si el usuario tiene registros en alguna tabla que referencia usuarios.id."""
    return bool(
        db.query(BitacoraLlamada).filter(BitacoraLlamada.usuario_id == usuario_id).first()
        or db.query(MediaCarga)
        .filter(or_(MediaCarga.usuario_id == usuario_id, MediaCarga.anulado_por_id == usuario_id))
        .first()
        or db.query(CierreDiario)
        .filter(
            or_(CierreDiario.usuario_id == usuario_id, CierreDiario.cerrado_por_id == usuario_id)
        )
        .first()
        or db.query(VentaRevendedor).filter(VentaRevendedor.usuario_id == usuario_id).first()
        or db.query(MediaCargaHistorial)
        .filter(MediaCargaHistorial.registrado_por_id == usuario_id)
        .first()
    )


def _check_baja_segura(db: Session, usuario: Usuario, current_user: Usuario) -> None:
    """Lanza HTTPException si dar de baja a `usuario` viola las salvaguardas."""
    if usuario.id == current_user.id:
        raise HTTPException(400, "No puedes dar de baja tu propia cuenta")
    if usuario.rol == "super_admin" and usuario.estado:
        activos = (
            db.query(Usuario)
            .filter(Usuario.estado == True, Usuario.rol == "super_admin")
            .count()
        )
        if activos <= 1:
            raise HTTPException(409, "Debe existir al menos un super_admin activo")


@router.get("/", response_model=Page[UsuarioOut])
def listar_usuarios(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    q = db.query(Usuario)
    total = q.count()
    items = (
        q.order_by(Usuario.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


@router.get("/{id}", response_model=UsuarioOut)
def obtener_usuario(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    usuario = db.get(Usuario, id)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    return usuario


@router.post("/", response_model=UsuarioOut, status_code=201)
def crear_usuario(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(400, "El email ya está registrado")
    usuario = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
        estado=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch("/{id}", response_model=UsuarioOut)
def actualizar_usuario(
    id: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = _admin,
):
    usuario = db.get(Usuario, id)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    if payload.nombre is not None:
        usuario.nombre = payload.nombre
    if payload.email is not None:
        if db.query(Usuario).filter(Usuario.email == payload.email, Usuario.id != id).first():
            raise HTTPException(400, "El email ya está en uso por otro usuario")
        usuario.email = payload.email
    if payload.password is not None:
        usuario.password_hash = hash_password(payload.password)
    if payload.rol is not None:
        usuario.rol = payload.rol
    if payload.estado is not None:
        if not payload.estado:
            _check_baja_segura(db, usuario, current_user)
        usuario.estado = payload.estado

    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{id}")
def eliminar_usuario(
    id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = _admin,
):
    usuario = db.get(Usuario, id)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    _check_baja_segura(db, usuario, current_user)

    if _tiene_referencias(db, id):
        usuario.estado = False
        db.commit()
        raise HTTPException(
            409, "El usuario tiene registros asociados; fue inhabilitado en su lugar"
        )

    db.delete(usuario)
    db.commit()
    return Response(status_code=204)
