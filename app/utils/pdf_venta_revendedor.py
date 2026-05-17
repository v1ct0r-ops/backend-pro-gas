import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

AZUL_PROGAS = colors.HexColor("#1E3A5F")
GRIS_CLARO = colors.HexColor("#F2F2F2")

_styles = getSampleStyleSheet()

_titulo = ParagraphStyle("titulo_vr", parent=_styles["Heading1"], fontSize=18, textColor=AZUL_PROGAS, spaceAfter=4)
_subtitulo = ParagraphStyle("subtitulo_vr", parent=_styles["Normal"], fontSize=10, textColor=colors.grey, spaceAfter=12)
_label = ParagraphStyle("label_vr", parent=_styles["Normal"], fontSize=9, textColor=colors.grey)
_valor = ParagraphStyle("valor_vr", parent=_styles["Normal"], fontSize=10, textColor=colors.black)
_seccion = ParagraphStyle("seccion_vr", parent=_styles["Normal"], fontSize=10, textColor=AZUL_PROGAS, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
_total_label = ParagraphStyle("total_label_vr", parent=_styles["Normal"], fontSize=10, alignment=TA_RIGHT, textColor=colors.grey)
_total_valor = ParagraphStyle("total_valor_vr", parent=_styles["Normal"], fontSize=11, alignment=TA_RIGHT, textColor=AZUL_PROGAS)
_total_bruto_valor = ParagraphStyle("total_bruto_vr", parent=_styles["Normal"], fontSize=13, alignment=TA_RIGHT, textColor=AZUL_PROGAS, fontName="Helvetica-Bold")


def _fmt_clp(monto: int) -> str:
    return f"$ {monto:,}".replace(",", ".")


def _fmt_kilos(kilos: float) -> str:
    return f"{float(kilos):.3f} kg"


def _fmt_dt(dt: datetime | None, solo_fecha: bool = False) -> str:
    if dt is None:
        return "—"
    fmt = "%d/%m/%Y" if solo_fecha else "%d/%m/%Y %H:%M:%S"
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)


def generar_pdf_venta_revendedor(venta) -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story = []

    # --- Encabezado ---
    story.append(Paragraph("Pro-Gas ERP", _titulo))
    story.append(Paragraph("Comprobante de Venta a Revendedor", _subtitulo))
    story.append(HRFlowable(width="100%", thickness=1, color=AZUL_PROGAS, spaceAfter=12))

    # --- Datos del documento ---
    registrado_por = (
        venta.usuario.nombre
        if venta.usuario
        else f"ID {venta.usuario_id}"
    )

    info_data = [
        [
            Paragraph("N° Venta", _label), Paragraph(str(venta.id), _valor),
            Paragraph("RUT Cliente", _label), Paragraph(venta.rut_cliente, _valor),
        ],
        [
            Paragraph("Cliente", _label), Paragraph(venta.nombre_cliente, _valor),
            Paragraph("Fecha Venta", _label), Paragraph(_fmt_dt(venta.fecha, solo_fecha=True), _valor),
        ],
        [
            Paragraph("Registrado por", _label), Paragraph(registrado_por, _valor),
            Paragraph("Fecha Registro", _label), Paragraph(_fmt_dt(venta.created_at), _valor),
        ],
    ]

    info_table = Table(info_data, colWidths=[3.5 * cm, 5.5 * cm, 3.5 * cm, 5.5 * cm])
    info_table.setStyle(TableStyle([
        ("ROWBACKGROUND", (0, 0), (-1, -1), [GRIS_CLARO, colors.white, GRIS_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(info_table)
    story.append(Spacer(1, 0.5 * cm))

    # --- Tabla de líneas ---
    story.append(Paragraph("Detalle de Productos", _seccion))

    header = ["Formato", "Cantidad", "Precio Unit. Factura", "Kilos", "Subtotal Neto"]
    rows = [header]

    for linea in venta.lineas:
        formato = linea.producto.formato if linea.producto else f"ID {linea.producto_id}"
        rows.append([
            formato,
            str(linea.cantidad),
            _fmt_clp(linea.precio_unitario_factura),
            _fmt_kilos(linea.kilos_linea),
            _fmt_clp(linea.subtotal_neto),
        ])

    detalle_table = Table(rows, colWidths=[3.5 * cm, 2.5 * cm, 4 * cm, 2.5 * cm, 4 * cm])
    detalle_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_PROGAS),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(detalle_table)
    story.append(Spacer(1, 0.5 * cm))

    # --- Totales ---
    story.append(Paragraph("Resumen Financiero", _seccion))

    totales_data = [
        [Paragraph("Subtotal Neto:", _total_label), Paragraph(_fmt_clp(venta.total_neto), _total_valor)],
        [Paragraph(f"Descuento por volumen ({_fmt_kilos(venta.kilos_totales)} × $ {venta.descuento_pesos_por_kilo}/kg):", _total_label),
         Paragraph(f"- {_fmt_clp(venta.monto_descuento_total)}", _total_valor)],
        [Paragraph("Total Final:", _total_label), Paragraph(_fmt_clp(venta.total_final), _total_valor)],
        [Paragraph("IVA (19%):", _total_label), Paragraph(_fmt_clp(venta.total_iva), _total_valor)],
        [Paragraph("Total Bruto:", _total_label), Paragraph(_fmt_clp(venta.total_bruto), _total_bruto_valor)],
    ]

    totales_table = Table(totales_data, colWidths=[14 * cm, 4 * cm])
    totales_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, 4), (-1, 4), 1, AZUL_PROGAS),
        ("BACKGROUND", (0, 4), (-1, 4), GRIS_CLARO),
        # Línea separadora antes de Total Final (tras el descuento)
        ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.lightgrey),
    ]))

    story.append(totales_table)
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Paragraph(
        f"Documento generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} — Pro-Gas ERP",
        ParagraphStyle("footer_vr", parent=_styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()
