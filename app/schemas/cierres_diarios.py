from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CierreDiarioCreate(BaseModel):
    chofer_nombre: str
    fecha: datetime
    efectivo_rendido: int = 0
    vouchers_transbank: int = 0
    descuentos: int = 0
    total_ventas_calc: int = 0

    @field_validator("efectivo_rendido", "vouchers_transbank", "descuentos", "total_ventas_calc")
    @classmethod
    def no_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Los montos no pueden ser negativos")
        return v


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
    usuario_id: int

    model_config = ConfigDict(from_attributes=True)
