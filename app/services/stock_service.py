from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import ProductoMaestro, TratadoComercial


def validar_y_descontar(
    db: Session,
    producto: ProductoMaestro,
    cantidad_llenos: int = 0,
    cantidad_vacios: int = 0,
) -> ProductoMaestro:
    nuevo_llenos = producto.stock_llenos - cantidad_llenos
    nuevo_vacios = producto.stock_vacios - cantidad_vacios

    if nuevo_llenos < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente para formato {producto.formato}",
        )
    if nuevo_vacios < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente para formato {producto.formato}",
        )

    producto.stock_llenos = nuevo_llenos
    producto.stock_vacios = nuevo_vacios
    db.flush()
    db.refresh(producto)
    return producto


def calcular_precio_cliente(
    db: Session,
    rut: str,
    producto: ProductoMaestro,
    precio_factura_proveedor: int,
    kilos_totales: float,
) -> dict:
    tratado = (
        db.query(TratadoComercial)
        .filter(
            TratadoComercial.rut_cliente == rut,
            TratadoComercial.formato_id == producto.id,
            TratadoComercial.vigente.is_(True),
        )
        .first()
    )

    if tratado:
        neto = precio_factura_proveedor - round(kilos_totales * tratado.descuento_por_kilo)
        return {
            "tipo": "revendedor",
            "neto": neto,
            "iva": round(neto * 0.19),
            "total": round(neto * 1.19),
            "descuento_aplicado": tratado.descuento_por_kilo,
            "tratado_id": tratado.id,
        }

    neto = producto.precio_publico_base
    return {
        "tipo": "publico",
        "neto": neto,
        "iva": round(neto * 0.19),
        "total": round(neto * 1.19),
        "descuento_aplicado": None,
        "tratado_id": None,
    }
