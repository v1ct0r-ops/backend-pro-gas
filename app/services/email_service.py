import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)

_ESTADO_EMOJI = {
    "exacto": "✅",
    "faltante": "⚠️",
    "sobrante": "💰",
}


def enviar_resumen_cierre(
    cierre_id: int,
    chofer_nombre: str,
    fecha: str,
    total_ventas_calc: int,
    efectivo_rendido: int,
    vouchers_transbank: int,
    descuentos: int,
    diferencia: int,
    estado_cuadre: str,
) -> None:
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SUPER_ADMIN_EMAIL]):
        logger.warning("SMTP no configurado — resumen de cierre #%d no enviado", cierre_id)
        return

    emoji = _ESTADO_EMOJI.get(estado_cuadre, "")
    total_rendido = efectivo_rendido + vouchers_transbank
    asunto = f"[Pro-Gas] Cierre #{cierre_id} — {estado_cuadre.upper()} {emoji}"

    cuerpo_html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#222">
      <h2>Resumen Cierre Diario #{cierre_id} {emoji}</h2>
      <table cellpadding="8" cellspacing="0" border="1"
             style="border-collapse:collapse;width:100%;max-width:480px">
        <tr><td><b>Chofer</b></td><td>{chofer_nombre}</td></tr>
        <tr><td><b>Fecha</b></td><td>{fecha}</td></tr>
        <tr><td><b>Total Ventas Calculado</b></td>
            <td>${total_ventas_calc:,}</td></tr>
        <tr><td><b>Efectivo Rendido</b></td>
            <td>${efectivo_rendido:,}</td></tr>
        <tr><td><b>Vouchers Transbank</b></td>
            <td>${vouchers_transbank:,}</td></tr>
        <tr><td><b>Descuentos</b></td>
            <td>${descuentos:,}</td></tr>
        <tr><td><b>Total Rendido</b></td>
            <td>${total_rendido:,}</td></tr>
        <tr style="background:#f5f5f5"><td><b>Diferencia</b></td>
            <td><b>${diferencia:,}</b></td></tr>
        <tr style="background:#f5f5f5"><td><b>Estado Cuadre</b></td>
            <td><b>{estado_cuadre.upper()} {emoji}</b></td></tr>
      </table>
      <p style="color:#888;font-size:12px;margin-top:16px">Pro-Gas ERP — mensaje automático</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = settings.SUPER_ADMIN_EMAIL
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(msg["From"], [settings.SUPER_ADMIN_EMAIL], msg.as_string())
        logger.info("Resumen cierre #%d enviado a %s", cierre_id, settings.SUPER_ADMIN_EMAIL)
    except Exception:
        logger.exception("Error al enviar resumen de cierre #%d por email", cierre_id)
