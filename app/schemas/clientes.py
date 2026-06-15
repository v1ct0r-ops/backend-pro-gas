from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.rut import normalizar_validar_rut


class ClienteCreate(BaseModel):
    rut: str
    nombre: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    descuento_pesos_por_kilo: int = 0

    @field_validator("rut")
    @classmethod
    def validar_rut(cls, v: str) -> str:
        return normalizar_validar_rut(v)

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nombre no puede estar vacío")
        return v.strip()

    @field_validator("descuento_pesos_por_kilo")
    @classmethod
    def descuento_no_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("descuento_pesos_por_kilo no puede ser negativo")
        return v


class ClienteUpdate(BaseModel):
    rut: Optional[str] = None
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    descuento_pesos_por_kilo: Optional[int] = None
    estado: Optional[bool] = None

    @field_validator("rut")
    @classmethod
    def validar_rut(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return normalizar_validar_rut(v)
        return v

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("nombre no puede estar vacío")
            return v.strip()
        return v

    @field_validator("descuento_pesos_por_kilo")
    @classmethod
    def descuento_no_negativo(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("descuento_pesos_por_kilo no puede ser negativo")
        return v


class ClienteOut(BaseModel):
    id: int
    rut: str
    nombre: str
    email: Optional[str]
    telefono: Optional[str]
    direccion: Optional[str]
    descuento_pesos_por_kilo: int
    estado: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
