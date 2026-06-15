from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.models.models import (
    MediaCarga,
    MediaCargaHistorial,
    MediaCargaHistorialLinea,
    MediaCargaLinea,
    ProductoMaestro,
)
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
            proveedor=payload.proveedor,
            fecha=payload.fecha,
            total_neto=total_neto,
            total_iva=total_iva,
            total_bruto=total_bruto,
            kilos_totales=kilos_totales,
            usuario_id=usuario_id,
        )
        db.add(media_carga)
        db.flush()

        # Snapshot de auditoría — misma transacción ACID que la media carga
        historial = MediaCargaHistorial(
            media_carga_id=media_carga.id,
            numero_guia=payload.numero_guia,
            proveedor=payload.proveedor,
            fecha_documento=payload.fecha,
            total_neto=total_neto,
            total_iva=total_iva,
            total_bruto=total_bruto,
            kilos_totales=Decimal(str(round(kilos_totales, 3))),
            registrado_por_id=usuario_id,
        )
        db.add(historial)
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

            hist_linea = MediaCargaHistorialLinea(
                historial_id=historial.id,
                formato_producto=data["producto"].formato,
                cantidad_llenos=data["cantidad_llenos"],
                cantidad_vacios=0,
                precio_unitario_neto=data["precio_unitario_neto"],
                kilos_linea=Decimal(str(round(data["cantidad_llenos"] * data["producto"].peso_kg, 3))),
                subtotal_neto=data["subtotal_neto"],
            )
            db.add(hist_linea)

            data["producto"].stock_llenos += data["cantidad_llenos"]

        db.commit()
        db.refresh(media_carga)
        return media_carga

    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, f"Violación de integridad de stock: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error procesando media carga: {str(e)}")


def anular_media_carga(db: Session, media_carga_id: int, usuario_id: int) -> MediaCarga:
    try:
        mc = (
            db.query(MediaCarga)
            .options(selectinload(MediaCarga.lineas))
            .filter(MediaCarga.id == media_carga_id)
            .first()
        )
        if not mc:
            raise HTTPException(404, "Media carga no encontrada")
        if mc.anulada:
            raise HTTPException(409, "Esta media carga ya fue anulada")

        # Lock all involved products — prevents concurrent race conditions
        producto_ids = list({linea.producto_id for linea in mc.lineas})
        productos_map = {
            p.id: p
            for p in db.query(ProductoMaestro)
            .filter(ProductoMaestro.id.in_(producto_ids))
            .with_for_update()
            .all()
        }

        # Aggregate cantidad_llenos per product (a document may have multiple lines for same product)
        totales: dict[int, int] = {}
        for linea in mc.lineas:
            totales[linea.producto_id] = totales.get(linea.producto_id, 0) + linea.cantidad_llenos

        # Full pre-validation — collect ALL deficits before touching any stock
        deficits = []
        for prod_id, total_llenos in totales.items():
            producto = productos_map[prod_id]
            if producto.stock_llenos - total_llenos < 0:
                deficits.append(
                    f"Formato {producto.formato} (id={prod_id}): "
                    f"tiene {producto.stock_llenos}, necesita {total_llenos}"
                )
        if deficits:
            raise HTTPException(
                400,
                f"No se puede anular: stock insuficiente en [{'; '.join(deficits)}]",
            )

        # Apply reversal only after all validations pass
        for prod_id, total_llenos in totales.items():
            productos_map[prod_id].stock_llenos -= total_llenos

        mc.anulada = True
        mc.anulada_at = datetime.now(timezone.utc)
        mc.anulado_por_id = usuario_id

        db.commit()
        db.refresh(mc)
        return mc

    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, f"Violación de integridad de stock: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error anulando media carga: {str(e)}")
