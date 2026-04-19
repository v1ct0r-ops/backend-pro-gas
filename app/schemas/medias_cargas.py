from datetime import datetime

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
    fecha: datetime
    lineas: list[MediaCargaLineaIn]

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
    fecha: datetime
    total_neto: int
    total_iva: int
    total_bruto: int
    kilos_totales: float
    usuario_id: int
    lineas: list[MediaCargaLineaOut]

    model_config = ConfigDict(from_attributes=True)
