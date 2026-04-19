from pydantic import BaseModel, EmailStr, ConfigDict


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    rol: str
    model_config = ConfigDict(from_attributes=True)
