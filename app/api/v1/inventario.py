from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.models.models import ProductoMaestro, Usuario
from app.schemas.inventario import AjusteStockIn, ProductoOut
from database import get_db

router = APIRouter()


@router.get("/", response_model=list[ProductoOut])
def listar_inventario(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return db.query(ProductoMaestro).all()


@router.patch("/{id}/ajuste", response_model=ProductoOut)
def ajustar_stock(
    id: int,
    payload: AjusteStockIn,
    db: Session = Depends(get_db),
    current_user: Usuario = require_role("super_admin"),
):
    producto = db.get(ProductoMaestro, id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")

    nuevo_llenos = producto.stock_llenos + payload.delta_llenos
    nuevo_vacios = producto.stock_vacios + payload.delta_vacios

    if nuevo_llenos < 0:
        raise HTTPException(400, f"Stock insuficiente para formato {producto.formato}")
    if nuevo_vacios < 0:
        raise HTTPException(400, f"Stock insuficiente para formato {producto.formato}")

    try:
        producto.stock_llenos = nuevo_llenos
        producto.stock_vacios = nuevo_vacios
        db.commit()
        db.refresh(producto)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, f"Violación de integridad de stock: {str(e)}")
    return producto
