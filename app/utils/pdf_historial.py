import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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

_titulo = ParagraphStyle(
    "titulo",
    parent=_styles["Heading1"],
    fontSize=18,
    textColor=AZUL_PROGAS,
    spaceAfter=4,
)
_subtitulo = ParagraphStyle(
    "subtitulo",
    parent=_styles["Normal"],
    fontSize=10,
    textColor=colors.grey,
    spaceAfter=12,
)
_label = ParagraphStyle(
    "label",
    parent=_styles["Normal"],
    fontSize=9,
    textColor=colors.grey,
)
_valor = ParagraphStyle(
    "valor",
    parent=_styles["Normal"],
    fontSize=10,
    textColor=colors.black,
)
_total_label = ParagraphStyle(
    "total_label",
    parent=_styles["Normal"],
    fontSize=10,
    alignment=TA_RIGHT,
    textColor=colors.grey,
)
_total_valor = ParagraphStyle(
    "total_valor",
    parent=_styles["Normal"],
    fontSize=11,
    alignment=TA_RIGHT,
    textColor=AZUL_PROGAS,
)
_total_bruto_valor = ParagraphStyle(
    "total_bruto_valor",
    parent=_styles["Normal"],
    fontSize=13,
    alignment=TA_RIGHT,
    textColor=AZUL_PROGAS,
    fontName="Helvetica-Bold",
)
_banner_anulada = ParagraphStyle(
    "banner_anulada",
    parent=_styles["Normal"],
    fontSize=14,
    textColor=colors.white,
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)


def _fmt_clp(monto: int) -> str:
    return f"$ {monto:,}".replace(",", ".")


def _fmt_kilos(kilos: float) -> str:
    valor = round(float(kilos), 2)
    if valor == int(valor):
        parte_entera = f"{int(valor):,}".replace(",", ".")
        return f"{parte_entera} kg"
    decimal_str = f"{valor:.2f}".rstrip("0")
    int_part, dec_part = decimal_str.split(".")
    int_formatted = f"{int(int_part):,}".replace(",", ".")
    return f"{int_formatted},{dec_part} kg"


def generar_pdf_historial(historial) -> bytes:
    """Genera el PDF de un MediaCargaHistorial y retorna los bytes."""
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
    story.append(Paragraph("Historial de Ingreso de Galones — Media Carga", _subtitulo))
    story.append(HRFlowable(width="100%", thickness=1, color=AZUL_PROGAS, spaceAfter=12))

    if getattr(historial, "media_carga", None) and historial.media_carga.anulada:
        banner_table = Table(
            [[Paragraph("DOCUMENTO ANULADO", _banner_anulada)]],
            colWidths=[17 * cm],
        )
        banner_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.red),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 0.3 * cm))

    # --- Datos del documento ---
    fecha_doc = historial.fecha_documento
    if isinstance(fecha_doc, datetime):
        fecha_doc_str = fecha_doc.strftime("%d/%m/%Y")
    else:
        fecha_doc_str = str(fecha_doc)

    fecha_reg = historial.fecha_registro
    if isinstance(fecha_reg, datetime):
        fecha_reg_str = fecha_reg.strftime("%d/%m/%Y %H:%M:%S")
    else:
        fecha_reg_str = str(fecha_reg)

    registrado_por = (
        historial.registrado_por.nombre
        if historial.registrado_por
        else f"ID {historial.registrado_por_id}"
    )

    info_data = [
        [Paragraph("N° Guía", _label), Paragraph(historial.numero_guia, _valor),
         Paragraph("Proveedor", _label), Paragraph(historial.proveedor, _valor)],
        [Paragraph("Fecha Documento", _label), Paragraph(fecha_doc_str, _valor),
         Paragraph("Fecha Registro", _label), Paragraph(fecha_reg_str, _valor)],
        [Paragraph("Registrado por", _label), Paragraph(registrado_por, _valor),
         Paragraph("Kilos Totales", _label), Paragraph(_fmt_kilos(historial.kilos_totales), _valor)],
    ]

    info_table = Table(info_data, colWidths=[3.5 * cm, 5.5 * cm, 3.5 * cm, 5.5 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLARO),
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
    header = ["Formato", "Llenos", "Vacíos", "Precio Unit. Neto", "Kilos", "Subtotal Neto"]
    rows = [header]

    for linea in historial.lineas:
        rows.append([
            linea.formato_producto,
            str(linea.cantidad_llenos),
            str(linea.cantidad_vacios),
            _fmt_clp(linea.precio_unitario_neto),
            _fmt_kilos(linea.kilos_linea),
            _fmt_clp(linea.subtotal_neto),
        ])

    detalle_table = Table(
        rows,
        colWidths=[3 * cm, 2 * cm, 2 * cm, 4 * cm, 3 * cm, 4 * cm],
    )
    detalle_table.setStyle(TableStyle([
        # Encabezado
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_PROGAS),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Filas de datos
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
    totales_data = [
        [Paragraph("Neto:", _total_label), Paragraph(_fmt_clp(historial.total_neto), _total_valor)],
        [Paragraph("IVA (19%):", _total_label), Paragraph(_fmt_clp(historial.total_iva), _total_valor)],
        [Paragraph("Total Bruto:", _total_label), Paragraph(_fmt_clp(historial.total_bruto), _total_bruto_valor)],
    ]

    totales_table = Table(totales_data, colWidths=[14 * cm, 4 * cm])
    totales_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, 2), (-1, 2), 1, AZUL_PROGAS),
        ("BACKGROUND", (0, 2), (-1, 2), GRIS_CLARO),
    ]))

    story.append(totales_table)
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Paragraph(
        f"Documento generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} — Pro-Gas ERP",
        ParagraphStyle("footer", parent=_styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()
