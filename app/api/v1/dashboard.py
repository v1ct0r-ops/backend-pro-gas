from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.models import Usuario
from app.schemas.dashboard import DashboardResumen
from app.services.dashboard_service import get_dashboard_resumen
from database import get_db

router = APIRouter()


@router.get("/resumen", response_model=DashboardResumen)
def resumen_dashboard(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    es_admin = current_user.rol == "super_admin"
    return get_dashboard_resumen(db, es_admin)
