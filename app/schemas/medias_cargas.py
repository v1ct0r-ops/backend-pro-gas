from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class MediaCargaLineaIn(BaseModel):
    producto_id: int
    cantidad_llenos: int
    precio_unitario_neto: int

    @field_validator("cantidad_llenos")
    @classmethod
    def cantidad_positiva(cls, v: int) -> int:
        if v < 1:
            raise ValueError("cantidad_llenos debe ser >= 1")
        return v

    @field_validator("precio_unitario_neto")
    @classmethod
    def precio_positivo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("precio_unitario_neto debe ser >= 0")
        return v


class MediaCargaIn(BaseModel):
    numero_guia: str
    proveedor: str
    fecha: datetime
    lineas: list[MediaCargaLineaIn]

    @field_validator("proveedor")
    @classmethod
    def proveedor_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("proveedor no puede estar vacío")
        return v.strip()

    @field_validator("lineas")
    @classmethod
    def minimo_una_linea(cls, v: list) -> list:
        if len(v) < 1:
            raise ValueError("El documento debe tener al menos una línea")
        return v


class MediaCargaLineaOut(BaseModel):
    id: int
    producto_id: int
    cantidad_llenos: int
    precio_unitario_neto: int
    subtotal_neto: int

    model_config = ConfigDict(from_attributes=True)


class MediaCargaOut(BaseModel):
    id: int
    numero_guia: str
    proveedor: Optional[str]
    fecha: datetime
    total_neto: int
    total_iva: int
    total_bruto: int
    kilos_totales: float
    usuario_id: int
    lineas: list[MediaCargaLineaOut]

    model_config = ConfigDict(from_attributes=True)


# --- Historial schemas ---

class MediaCargaHistorialLineaOut(BaseModel):
    id: int
    formato_producto: str
    cantidad_llenos: int
    cantidad_vacios: int
    precio_unitario_neto: int
    kilos_linea: float
    subtotal_neto: int

    model_config = ConfigDict(from_attributes=True)


class MediaCargaHistorialOut(BaseModel):
    id: int
    media_carga_id: Optional[int]
    numero_guia: str
    proveedor: str
    fecha_documento: datetime
    total_neto: int
    total_iva: int
    total_bruto: int
    kilos_totales: float
    fecha_registro: datetime
    registrado_por_id: int
    registrado_por_nombre: Optional[str] = None
    lineas: list[MediaCargaHistorialLineaOut]

    model_config = ConfigDict(from_attributes=True)
