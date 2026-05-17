import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Santiago")


def _job_reporte_diario() -> None:
    """Cron job: recopila datos del día y envía el reporte al super_admin."""
    from database import SessionLocal
    from app.core.config import settings
    from app.services.email_service import enviar_reporte_diario

    if not settings.SUPER_ADMIN_EMAIL:
        logger.warning("SUPER_ADMIN_EMAIL no configurado — cron de reporte diario omitido")
        return

    db = SessionLocal()
    try:
        enviar_reporte_diario(db, settings.SUPER_ADMIN_EMAIL)
    finally:
        db.close()


scheduler.add_job(
    func=_job_reporte_diario,
    trigger=CronTrigger(hour=21, minute=0, timezone="America/Santiago"),
    id="reporte_diario_21h",
    replace_existing=True,
)
