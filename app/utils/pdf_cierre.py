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
VERDE = colors.HexColor("#1A7A4A")
ROJO = colors.HexColor("#C0392B")
NARANJA = colors.HexColor("#E67E22")

_styles = getSampleStyleSheet()

_titulo = ParagraphStyle("titulo", parent=_styles["Heading1"], fontSize=18, textColor=AZUL_PROGAS, spaceAfter=4)
_subtitulo = ParagraphStyle("subtitulo", parent=_styles["Normal"], fontSize=10, textColor=colors.grey, spaceAfter=12)
_label = ParagraphStyle("label", parent=_styles["Normal"], fontSize=9, textColor=colors.grey)
_valor = ParagraphStyle("valor", parent=_styles["Normal"], fontSize=10, textColor=colors.black)
_seccion = ParagraphStyle("seccion", parent=_styles["Normal"], fontSize=10, textColor=AZUL_PROGAS, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
_total_label = ParagraphStyle("total_label", parent=_styles["Normal"], fontSize=10, alignment=TA_RIGHT, textColor=colors.grey)
_total_valor = ParagraphStyle("total_valor", parent=_styles["Normal"], fontSize=11, alignment=TA_RIGHT, textColor=AZUL_PROGAS)
_dif_valor = ParagraphStyle("dif_valor", parent=_styles["Normal"], fontSize=12, alignment=TA_RIGHT, fontName="Helvetica-Bold")


def _fmt_clp(monto: int) -> str:
    return f"$ {monto:,}".replace(",", ".")


def _fmt_dt(dt: datetime | None, solo_fecha: bool = False) -> str:
    if dt is None:
        return "—"
    fmt = "%d/%m/%Y" if solo_fecha else "%d/%m/%Y %H:%M:%S"
    return dt.strftime(fmt)


def _color_estado(estado: str | None) -> colors.Color:
    if estado == "exacto":
        return VERDE
    if estado == "faltante":
        return ROJO
    return NARANJA


def generar_pdf_cierre(cierre) -> bytes:
    """Genera el PDF de resumen de un CierreDiario y retorna los bytes."""
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
    story.append(Paragraph("Cierre Diario — Resumen de Cuadre", _subtitulo))
    story.append(HRFlowable(width="100%", thickness=1, color=AZUL_PROGAS, spaceAfter=12))

    # --- Datos del cierre ---
    estado_str = (cierre.estado_cuadre or "pendiente").upper()
    estado_color = _color_estado(cierre.estado_cuadre)

    cerrado_por = (
        cierre.cerrado_por.nombre
        if cierre.cerrado_por
        else (f"ID {cierre.cerrado_por_id}" if cierre.cerrado_por_id else "—")
    )

    info_data = [
        [
            Paragraph("N° Cierre", _label),
            Paragraph(str(cierre.id), _valor),
            Paragraph("Estado", _label),
            Paragraph(f'<font color="#{_color_hex(estado_color)}"><b>{estado_str}</b></font>', _valor),
        ],
        [
            Paragraph("Chofer", _label),
            Paragraph(cierre.chofer_nombre, _valor),
            Paragraph("Fecha", _label),
            Paragraph(_fmt_dt(cierre.fecha, solo_fecha=True), _valor),
        ],
        [
            Paragraph("Creado", _label),
            Paragraph(_fmt_dt(cierre.created_at), _valor),
            Paragraph("Cerrado", _label),
            Paragraph(_fmt_dt(cierre.closed_at), _valor),
        ],
        [
            Paragraph("Cerrado por", _label),
            Paragraph(cerrado_por, _valor),
            Paragraph("", _label),
            Paragraph("", _valor),
        ],
    ]

    info_table = Table(info_data, colWidths=[3.5 * cm, 5.5 * cm, 3.5 * cm, 5.5 * cm])
    info_table.setStyle(TableStyle([
        ("ROWBACKGROUND", (0, 0), (-1, -1), [GRIS_CLARO, colors.white, GRIS_CLARO, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(info_table)
    story.append(Spacer(1, 0.5 * cm))

    # --- Tabla de cuadre ---
    story.append(Paragraph("Detalle de Cuadre", _seccion))

    total_rendido = cierre.efectivo_rendido + cierre.vouchers_transbank
    diferencia = cierre.diferencia if cierre.diferencia is not None else (cierre.total_ventas_calc - total_rendido)
    dif_color = _color_estado(cierre.estado_cuadre)

    cuadre_data = [
        ["Concepto", "Monto"],
        ["Efectivo Rendido", _fmt_clp(cierre.efectivo_rendido)],
        ["Vouchers Transbank", _fmt_clp(cierre.vouchers_transbank)],
        ["Total Rendido", _fmt_clp(total_rendido)],
        ["Descuentos aplicados", _fmt_clp(cierre.descuentos)],
        ["Total Ventas (Sistema)", _fmt_clp(cierre.total_ventas_calc)],
        [f'<font color="#{_color_hex(dif_color)}"><b>Diferencia</b></font>',
         f'<font color="#{_color_hex(dif_color)}"><b>{_fmt_clp(diferencia)}</b></font>'],
    ]

    cuadre_rows = []
    for i, row in enumerate(cuadre_data):
        if i == 0:
            cuadre_rows.append(row)
        else:
            cuadre_rows.append([Paragraph(row[0], _total_label), Paragraph(row[1], _total_valor)])

    cuadre_table = Table(cuadre_rows, colWidths=[13 * cm, 5 * cm])
    cuadre_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_PROGAS),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ROWBACKGROUND", (0, 1), (-1, -2), [colors.white, GRIS_CLARO]),
        ("BACKGROUND", (0, -1), (-1, -1), GRIS_CLARO),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, AZUL_PROGAS),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        # Línea separadora antes de Total Rendido
        ("LINEABOVE", (0, 4), (-1, 4), 0.5, AZUL_PROGAS),
    ]))

    story.append(cuadre_table)

    # --- Stock Snapshot ---
    if cierre.stock_snapshot:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Snapshot de Stock al Cierre", _seccion))

        stock_header = ["Formato", "Llenos", "Vacíos"]
        stock_rows = [stock_header]
        for item in cierre.stock_snapshot.values():
            stock_rows.append([
                item.get("formato", "—"),
                str(item.get("stock_llenos", 0)),
                str(item.get("stock_vacios", 0)),
            ])

        stock_table = Table(stock_rows, colWidths=[6 * cm, 4 * cm, 4 * cm])
        stock_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_PROGAS),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(stock_table)

    # --- Footer ---
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Paragraph(
        f"Documento generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} — Pro-Gas ERP",
        ParagraphStyle("footer", parent=_styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()


def _color_hex(color: colors.Color) -> str:
    """Convierte un color ReportLab a hex string sin # para usar en Paragraph markup."""
    r, g, b = int(color.red * 255), int(color.green * 255), int(color.blue * 255)
    return f"{r:02X}{g:02X}{b:02X}"
