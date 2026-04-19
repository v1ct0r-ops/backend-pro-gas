from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.models.models import ProductoMaestro, TratadoComercial, Usuario
from app.schemas.tratados_comerciales import (
    PrecioClienteIn,
    PrecioClienteOut,
    TratadoComercialIn,
    TratadoComercialOut,
    TratadoComercialUpdate,
)
from app.services.stock_service import calcular_precio_cliente
from database import get_db

router = APIRouter()


@router.get("/", response_model=list[TratadoComercialOut])
def listar_tratados(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return db.query(TratadoComercial).all()


@router.get("/{id}", response_model=TratadoComercialOut)
def obtener_tratado(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    tratado = db.get(TratadoComercial, id)
    if not tratado:
        raise HTTPException(404, "Tratado comercial no encontrado")
    return tratado


@router.post("/", response_model=TratadoComercialOut, status_code=201)
def crear_tratado(
    payload: TratadoComercialIn,
    db: Session = Depends(get_db),
    current_user: Usuario = require_role("super_admin"),
):
    if not db.get(ProductoMaestro, payload.formato_id):
        raise HTTPException(404, f"Formato con id={payload.formato_id} no encontrado")

    tratado = TratadoComercial(
        rut_cliente=payload.rut_cliente,
        nombre_cliente=payload.nombre_cliente,
        formato_id=payload.formato_id,
        descuento_por_kilo=payload.descuento_por_kilo,
        vigente=True,
        admin_id=current_user.id,
    )
    db.add(tratado)
    db.commit()
    db.refresh(tratado)
    return tratado


@router.patch("/{id}", response_model=TratadoComercialOut)
def actualizar_tratado(
    id: int,
    payload: TratadoComercialUpdate,
    db: Session = Depends(get_db),
    _: Usuario = require_role("super_admin"),
):
    tratado = db.get(TratadoComercial, id)
    if not tratado:
        raise HTTPException(404, "Tratado comercial no encontrado")

    if payload.descuento_por_kilo is not None:
        tratado.descuento_por_kilo = payload.descuento_por_kilo
    if payload.vigente is not None:
        tratado.vigente = payload.vigente

    db.commit()
    db.refresh(tratado)
    return tratado


@router.delete("/{id}", status_code=204)
def eliminar_tratado(
    id: int,
    db: Session = Depends(get_db),
    _: Usuario = require_role("super_admin"),
):
    tratado = db.get(TratadoComercial, id)
    if not tratado:
        raise HTTPException(404, "Tratado comercial no encontrado")
    db.delete(tratado)
    db.commit()


@router.post("/calcular-precio", response_model=PrecioClienteOut)
def calcular_precio(
    payload: PrecioClienteIn,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    producto = db.get(ProductoMaestro, payload.producto_id)
    if not producto:
        raise HTTPException(404, f"Producto con id={payload.producto_id} no encontrado")

    resultado = calcular_precio_cliente(
        db=db,
        rut=payload.rut_cliente,
        producto=producto,
        precio_factura_proveedor=payload.precio_factura_proveedor,
        kilos_totales=payload.kilos_totales,
    )
    return resultado
