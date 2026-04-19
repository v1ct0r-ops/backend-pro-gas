from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class BitacoraCreate(BaseModel):
    cliente_nombre: str
    telefono: str
    direccion: str
    detalle_pedido: str

    @field_validator("telefono", "direccion")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Este campo no puede estar vacío")
        return v.strip()


class BitacoraOut(BaseModel):
    id: int
    cliente_nombre: str
    telefono: str
    direccion: str
    detalle_pedido: str
    fecha_hora: datetime
    usuario_id: int

    model_config = ConfigDict(from_attributes=True)
