import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import resend
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import CierreDiario, VentaRevendedor

SANTIAGO = ZoneInfo("America/Santiago")

_MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

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


# ---------------------------------------------------------------------------
# Reporte Diario — enviado vía Resend
# ---------------------------------------------------------------------------

def _fmt_clp(monto: int) -> str:
    """Formatea un entero como pesos chilenos: $ 1.250.000"""
    return "$ " + f"{monto:,}".replace(",", ".")


def _construir_html_reporte(
    fecha_str: str,
    total_ventas: int,
    kilos_movidos: float,
    total_cierres: int,
    cerrados: int,
    pendientes: int,
    faltantes_detalle: list[tuple[str, int]],
) -> str:
    # --- Sección Alertas ---
    if faltantes_detalle:
        filas_faltantes = "".join(
            f"""
            <tr>
              <td style="padding:10px 12px;border:1px solid #fecdd3;color:#374151">{chofer}</td>
              <td style="padding:10px 12px;border:1px solid #fecdd3;color:#dc2626;font-weight:bold;text-align:right">
                {_fmt_clp(abs(diferencia))}
              </td>
            </tr>"""
            for chofer, diferencia in faltantes_detalle
        )
        alertas_html = f"""
        <div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:6px;overflow:hidden">
          <div style="background:#dc2626;color:white;padding:10px 16px;font-size:13px;font-weight:bold">
            ⚠️ {len(faltantes_detalle)} cierre(s) con FALTANTE detectado(s)
          </div>
          <table style="width:100%;border-collapse:collapse">
            <thead>
              <tr style="background:#fee2e2">
                <th style="padding:8px 12px;border:1px solid #fecdd3;text-align:left;font-size:12px;color:#374151">Chofer</th>
                <th style="padding:8px 12px;border:1px solid #fecdd3;text-align:right;font-size:12px;color:#374151">Faltante</th>
              </tr>
            </thead>
            <tbody>{filas_faltantes}</tbody>
          </table>
        </div>"""
    else:
        alertas_html = """
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:14px 16px;
                    color:#15803d;font-weight:bold;font-size:14px">
          ✅ Sin alertas — todos los cierres cuadran correctamente
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">
<div style="max-width:600px;margin:0 auto;padding:20px">

  <!-- Encabezado -->
  <div style="background:#0f172a;color:white;padding:28px 24px;border-radius:10px 10px 0 0;text-align:center">
    <div style="font-size:28px;margin-bottom:4px">⛽</div>
    <h1 style="margin:0;font-size:20px;font-weight:700;letter-spacing:0.5px">Pro-Gas ERP</h1>
    <p style="margin:6px 0 0;opacity:0.65;font-size:13px">Reporte Diario Automatizado — {fecha_str}</p>
  </div>

  <!-- El Gancho -->
  <div style="background:white;padding:24px;margin-top:2px">
    <h2 style="margin:0 0 16px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px">
      📊 El Gancho — Totales del Día
    </h2>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="width:50%;padding:0 8px 0 0">
          <div style="background:#eff6ff;border-radius:8px;padding:18px;text-align:center">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
              Total Ventas
            </div>
            <div style="font-size:22px;font-weight:800;color:#1e40af">{_fmt_clp(total_ventas)}</div>
          </div>
        </td>
        <td style="width:50%;padding:0 0 0 8px">
          <div style="background:#f0fdf4;border-radius:8px;padding:18px;text-align:center">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
              Kilos Movidos
            </div>
            <div style="font-size:22px;font-weight:800;color:#15803d">{kilos_movidos:,.1f} kg</div>
          </div>
        </td>
      </tr>
    </table>
  </div>

  <!-- La Operación -->
  <div style="background:white;padding:24px;margin-top:2px">
    <h2 style="margin:0 0 16px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px">
      🚚 La Operación — Estado de Cajas
    </h2>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="padding:11px 14px;border:1px solid #e2e8f0;color:#475569;font-size:14px">
          Cierres registrados hoy
        </td>
        <td style="padding:11px 14px;border:1px solid #e2e8f0;font-weight:700;text-align:right;font-size:14px">
          {total_cierres}
        </td>
      </tr>
      <tr style="background:#f8fafc">
        <td style="padding:11px 14px;border:1px solid #e2e8f0;color:#475569;font-size:14px">
          ✅ Cerrados y cuadrados
        </td>
        <td style="padding:11px 14px;border:1px solid #e2e8f0;font-weight:700;color:#15803d;text-align:right;font-size:14px">
          {cerrados}
        </td>
      </tr>
      <tr>
        <td style="padding:11px 14px;border:1px solid #e2e8f0;color:#475569;font-size:14px">
          ⏳ Pendientes de cerrar
        </td>
        <td style="padding:11px 14px;border:1px solid #e2e8f0;font-weight:700;color:#d97706;text-align:right;font-size:14px">
          {pendientes}
        </td>
      </tr>
    </table>
  </div>

  <!-- Alertas -->
  <div style="background:white;padding:24px;margin-top:2px;border-radius:0 0 10px 10px">
    <h2 style="margin:0 0 16px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px">
      🚨 Alertas — Faltantes Detectados
    </h2>
    {alertas_html}
  </div>

  <!-- Footer -->
  <p style="text-align:center;color:#94a3b8;font-size:11px;margin-top:20px;line-height:1.6">
    Pro-Gas ERP · Reporte automático generado a las 21:00 hrs (América/Santiago)<br>
    No responder a este correo.
  </p>

</div>
</body>
</html>"""


def enviar_reporte_diario(db: Session, email_destino: str) -> None:
    """Recopila métricas del día (zona horaria Santiago) y envía el reporte por Resend."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY no configurada — reporte diario no enviado a %s", email_destino)
        return

    hoy = datetime.now(SANTIAGO).date()
    fecha_str = f"{hoy.day} de {_MESES_ES[hoy.month - 1]} de {hoy.year}"

    # --- El Gancho: totales de ventas revendedor del día ---
    ventas_row = (
        db.query(
            func.coalesce(func.sum(VentaRevendedor.total_bruto), 0).label("total_ventas"),
            func.coalesce(func.sum(VentaRevendedor.kilos_totales), 0.0).label("kilos"),
        )
        .filter(func.date(VentaRevendedor.fecha) == hoy)
        .one()
    )
    total_ventas = int(ventas_row.total_ventas)
    kilos_movidos = float(ventas_row.kilos)

    # --- La Operación: estado de cierres diarios ---
    cierres_row = (
        db.query(
            func.count(CierreDiario.id).label("total"),
            func.sum(case((CierreDiario.is_closed.is_(True), 1), else_=0)).label("cerrados"),
            func.sum(case((CierreDiario.is_closed.is_(False), 1), else_=0)).label("pendientes"),
        )
        .filter(func.date(CierreDiario.fecha) == hoy)
        .one()
    )
    total_cierres = int(cierres_row.total or 0)
    cerrados = int(cierres_row.cerrados or 0)
    pendientes = int(cierres_row.pendientes or 0)

    # --- Alertas: detalle de faltantes ---
    faltantes_rows = (
        db.query(CierreDiario.chofer_nombre, CierreDiario.diferencia)
        .filter(
            func.date(CierreDiario.fecha) == hoy,
            CierreDiario.estado_cuadre == "faltante",
        )
        .all()
    )
    faltantes_detalle = [(r.chofer_nombre, r.diferencia or 0) for r in faltantes_rows]

    html_body = _construir_html_reporte(
        fecha_str=fecha_str,
        total_ventas=total_ventas,
        kilos_movidos=kilos_movidos,
        total_cierres=total_cierres,
        cerrados=cerrados,
        pendientes=pendientes,
        faltantes_detalle=faltantes_detalle,
    )

    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [email_destino],
            "subject": f"[Pro-Gas] Reporte Diario — {fecha_str}",
            "html": html_body,
        })
        logger.info("Reporte diario enviado a %s (fecha: %s)", email_destino, fecha_str)
    except Exception:
        logger.exception("Error al enviar reporte diario a %s", email_destino)
