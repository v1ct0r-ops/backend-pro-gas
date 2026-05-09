from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.models import Usuario, VentaRevendedor
from app.schemas.ventas_revendedor import VentaRevendedorIn, VentaRevendedorOut
from app.services.venta_revendedor_service import registrar_venta_revendedor
from database import get_db

router = APIRouter()


@router.post("/", response_model=VentaRevendedorOut, status_code=201)
def crear_venta_revendedor(
    payload: VentaRevendedorIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return registrar_venta_revendedor(db, payload, current_user.id)


@router.get("/", response_model=list[VentaRevendedorOut])
def listar_ventas_revendedor(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return db.query(VentaRevendedor).order_by(VentaRevendedor.fecha.desc()).all()


@router.get("/{id}", response_model=VentaRevendedorOut)
def obtener_venta_revendedor(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    venta = db.get(VentaRevendedor, id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    return venta
