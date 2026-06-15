from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.rut import normalizar_validar_rut


class VentaRevendedorLineaIn(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario_factura: int  # precio proveedor por cilindro en CLP (Integer)

    @field_validator("cantidad")
    @classmethod
    def cantidad_positiva(cls, v: int) -> int:
        if v < 1:
            raise ValueError("cantidad debe ser >= 1")
        return v

    @field_validator("precio_unitario_factura")
    @classmethod
    def precio_positivo(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("precio_unitario_factura debe ser > 0")
        return v


class VentaRevendedorIn(BaseModel):
    rut_cliente: str
    nombre_cliente: str
    fecha: datetime
    descuento_pesos_por_kilo: int = 0
    lineas: list[VentaRevendedorLineaIn]

    @field_validator("descuento_pesos_por_kilo")
    @classmethod
    def descuento_no_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("descuento_pesos_por_kilo no puede ser negativo")
        return v

    @field_validator("rut_cliente")
    @classmethod
    def validar_rut(cls, v: str) -> str:
        return normalizar_validar_rut(v)

    @field_validator("nombre_cliente")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nombre_cliente no puede estar vacío")
        return v.strip()

    @field_validator("lineas")
    @classmethod
    def minimo_una_linea(cls, v: list) -> list:
        if len(v) < 1:
            raise ValueError("La venta debe tener al menos una línea de producto")
        return v


class VentaRevendedorPatch(BaseModel):
    """Solo permite corregir campos de identificación. Los montos son inmutables post-registro."""
    rut_cliente: Optional[str] = None
    nombre_cliente: Optional[str] = None
    fecha: Optional[datetime] = None

    @field_validator("rut_cliente")
    @classmethod
    def validar_rut(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return normalizar_validar_rut(v)
        return v

    @field_validator("nombre_cliente")
    @classmethod
    def nombre_no_vacio(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("nombre_cliente no puede estar vacío")
            return v.strip()
        return v


class VentaRevendedorLineaOut(BaseModel):
    id: int
    producto_id: int
    cantidad: int
    precio_unitario_factura: int
    kilos_linea: float
    descuento_aplicado: Optional[float] = None
    subtotal_neto: int
    precio_tipo: str  # "revendedor" | "publico"

    model_config = ConfigDict(from_attributes=True)


class VentaRevendedorOut(BaseModel):
    id: int
    rut_cliente: str
    nombre_cliente: str
    fecha: datetime
    created_at: Optional[datetime] = None
    total_neto: int
    descuento_pesos_por_kilo: int
    monto_descuento_total: int
    total_final: int
    total_iva: int
    total_bruto: int
    kilos_totales: float
    usuario_id: int
    lineas: list[VentaRevendedorLineaOut]

    model_config = ConfigDict(from_attributes=True)
