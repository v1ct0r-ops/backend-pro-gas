from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import MediaCarga, MediaCargaLinea, ProductoMaestro
from app.schemas.medias_cargas import MediaCargaIn


def procesar_media_carga(
    db: Session,
    payload: MediaCargaIn,
    usuario_id: int,
) -> MediaCarga:
    try:
        lineas_data = []
        total_neto = 0
        kilos_totales = 0.0

        for linea_in in payload.lineas:
            producto = db.get(ProductoMaestro, linea_in.producto_id)
            if not producto:
                raise HTTPException(404, f"Producto {linea_in.producto_id} no encontrado")

            # Capa 3 de clamping: validación explícita a nivel de servicio
            if linea_in.cantidad_llenos < 1:
                raise HTTPException(400, f"cantidad_llenos debe ser >= 1 para formato {producto.formato}")

            subtotal = linea_in.cantidad_llenos * linea_in.precio_unitario_neto
            total_neto += subtotal
            kilos_totales += linea_in.cantidad_llenos * producto.peso_kg

            lineas_data.append({
                "producto": producto,
                "cantidad_llenos": linea_in.cantidad_llenos,
                "precio_unitario_neto": linea_in.precio_unitario_neto,
                "subtotal_neto": subtotal,
            })

        total_iva = round(total_neto * 0.19)
        total_bruto = total_neto + total_iva

        media_carga = MediaCarga(
            numero_guia=payload.numero_guia,
            fecha=payload.fecha,
            total_neto=total_neto,
            total_iva=total_iva,
            total_bruto=total_bruto,
            kilos_totales=kilos_totales,
            usuario_id=usuario_id,
        )
        db.add(media_carga)
        db.flush()

        for data in lineas_data:
            linea = MediaCargaLinea(
                media_carga_id=media_carga.id,
                producto_id=data["producto"].id,
                cantidad_llenos=data["cantidad_llenos"],
                precio_unitario_neto=data["precio_unitario_neto"],
                subtotal_neto=data["subtotal_neto"],
            )
            db.add(linea)
            data["producto"].stock_llenos += data["cantidad_llenos"]

        db.commit()
        db.refresh(media_carga)
        return media_carga

    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        # Captura errores de @validates en el modelo (clamping capa 2)
        db.rollback()
        raise HTTPException(400, f"Violación de integridad de stock: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error procesando media carga: {str(e)}")
