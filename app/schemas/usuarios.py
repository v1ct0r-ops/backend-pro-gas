from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    rol: Literal["operador", "super_admin"]

    @field_validator("password")
    @classmethod
    def password_minimo(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    rol: Optional[Literal["operador", "super_admin"]] = None
    estado: Optional[bool] = None

    @field_validator("password")
    @classmethod
    def password_minimo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    rol: str
    estado: bool

    model_config = ConfigDict(from_attributes=True)
