from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.models.models import Usuario
from app.services.email_service import enviar_reporte_diario
from database import get_db

router = APIRouter()


class EnviarReporteBody(BaseModel):
    email_destino: EmailStr | None = None


@router.post("/enviar-diario", summary="Enviar reporte diario por correo")
def enviar_reporte_manual(
    body: EnviarReporteBody = EnviarReporteBody(),
    current_user: Usuario = require_role("super_admin"),
    db: Session = Depends(get_db),
) -> dict:
    destino = body.email_destino or current_user.email
    enviar_reporte_diario(db, destino)
    return {"mensaje": f"Reporte diario enviado a {destino}"}
