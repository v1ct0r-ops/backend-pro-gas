from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class LineaMovimientoCierre(BaseModel):
    producto_id: int
    galones_vendidos: int = 0
    vacios_devueltos: int = 0

    @field_validator("galones_vendidos", "vacios_devueltos")
    @classmethod
    def no_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Las cantidades no pueden ser negativas")
        return v


class CierreDiarioCreate(BaseModel):
    chofer_nombre: str
    fecha: datetime
    efectivo_rendido: int = 0
    vouchers_transbank: int = 0
    descuentos: int = 0
    total_ventas_calc: int = 0
    lineas_movimiento: list[LineaMovimientoCierre] = []

    @field_validator("efectivo_rendido", "vouchers_transbank", "descuentos", "total_ventas_calc")
    @classmethod
    def no_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Los montos no pueden ser negativos")
        return v


class CierreDiarioUpdate(BaseModel):
    chofer_nombre: Optional[str] = None
    fecha: Optional[datetime] = None
    efectivo_rendido: Optional[int] = None
    vouchers_transbank: Optional[int] = None
    descuentos: Optional[int] = None
    total_ventas_calc: Optional[int] = None

    @field_validator("efectivo_rendido", "vouchers_transbank", "descuentos", "total_ventas_calc", mode="before")
    @classmethod
    def no_negativo(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Los montos no pueden ser negativos")
        return v

    @model_validator(mode="after")
    def al_menos_un_campo(self) -> "CierreDiarioUpdate":
        if not self.model_fields_set:
            raise ValueError("Debe enviar al menos un campo para actualizar")
        return self


class CierreDiarioOut(BaseModel):
    id: int
    chofer_nombre: str
    fecha: datetime
    efectivo_rendido: int
    vouchers_transbank: int
    descuentos: int
    total_ventas_calc: int
    is_closed: bool
    diferencia: Optional[int]
    estado_cuadre: Optional[str]
    stock_snapshot: Optional[Any]
    lineas_movimiento: Optional[Any]
    usuario_id: int
    created_at: Optional[datetime]
    closed_at: Optional[datetime]
    cerrado_por_id: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class CierreDiarioPaginado(BaseModel):
    items: list[CierreDiarioOut]
    total: int
