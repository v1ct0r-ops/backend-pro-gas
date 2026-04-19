from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.core.security import hash_password
from app.models.models import Usuario
from app.schemas.usuarios import UsuarioCreate, UsuarioOut, UsuarioUpdate
from database import get_db

router = APIRouter()

_admin = require_role("super_admin")


@router.get("/", response_model=list[UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    _: Usuario = _admin,
):
    return db.query(Usuario).all()


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
    _: Usuario = _admin,
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
        usuario.estado = payload.estado

    db.commit()
    db.refresh(usuario)
    return usuario
