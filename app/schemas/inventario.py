from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProductoOut(BaseModel):
    id: int
    formato: str
    peso_kg: float
    precio_publico_base: int
    stock_llenos: int
    stock_vacios: int

    model_config = ConfigDict(from_attributes=True)


class AjusteStockIn(BaseModel):
    delta_llenos: int = 0
    delta_vacios: int = 0
    motivo: str


class ProductoUpdate(BaseModel):
    stock_llenos: Optional[int] = None
    stock_vacios: Optional[int] = None
    precio_publico_base: Optional[int] = None
