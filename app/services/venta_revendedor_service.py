from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import (
    ProductoMaestro,
    VentaRevendedor,
    VentaRevendedorLinea,
)
from app.schemas.ventas_revendedor import VentaRevendedorIn


def registrar_venta_revendedor(
    db: Session,
    payload: VentaRevendedorIn,
    usuario_id: int,
) -> VentaRevendedor:
    try:
        lineas_data = []
        total_neto = 0
        kilos_totales = 0.0

        for linea_in in payload.lineas:
            # Bloqueo pesimista: evita race condition de stock bajo carga concurrente
            producto = (
                db.query(ProductoMaestro)
                .filter(ProductoMaestro.id == linea_in.producto_id)
                .with_for_update()
                .first()
            )
            if not producto:
                raise HTTPException(404, f"Producto con id={linea_in.producto_id} no encontrado")

            # Capa 3 de clamping: validación explícita antes de tocar el modelo
            if producto.stock_llenos < linea_in.cantidad:
                raise HTTPException(
                    400,
                    f"Stock insuficiente para {producto.formato}: "
                    f"disponible={producto.stock_llenos}, solicitado={linea_in.cantidad}",
                )

            kilos_linea = round(linea_in.cantidad * producto.peso_kg, 4)
            subtotal_neto = linea_in.precio_unitario_factura * linea_in.cantidad

            total_neto += subtotal_neto
            kilos_totales += kilos_linea

            lineas_data.append({
                "producto": producto,
                "cantidad": linea_in.cantidad,
                "precio_unitario_factura": linea_in.precio_unitario_factura,
                "kilos_linea": kilos_linea,
                "descuento_aplicado": None,
                "subtotal_neto": subtotal_neto,
                "precio_tipo": "revendedor",
            })

        kilos_totales = round(kilos_totales, 4)
        monto_descuento_total = round(kilos_totales * payload.descuento_pesos_por_kilo)
        total_final = total_neto - monto_descuento_total
        if total_final < 0:
            raise HTTPException(
                400,
                f"El descuento por volumen ({monto_descuento_total} CLP) supera el total neto ({total_neto} CLP).",
            )
        total_iva = round(total_final * 0.19)
        total_bruto = total_final + total_iva

        venta = VentaRevendedor(
            rut_cliente=payload.rut_cliente,
            nombre_cliente=payload.nombre_cliente,
            fecha=payload.fecha,
            total_neto=total_neto,
            descuento_pesos_por_kilo=payload.descuento_pesos_por_kilo,
            monto_descuento_total=monto_descuento_total,
            total_final=total_final,
            total_iva=total_iva,
            total_bruto=total_bruto,
            kilos_totales=kilos_totales,
            usuario_id=usuario_id,
        )
        db.add(venta)
        db.flush()  # Obtener venta.id sin hacer commit todavía

        for data in lineas_data:
            linea = VentaRevendedorLinea(
                venta_id=venta.id,
                producto_id=data["producto"].id,
                cantidad=data["cantidad"],
                precio_unitario_factura=data["precio_unitario_factura"],
                kilos_linea=data["kilos_linea"],
                descuento_aplicado=data["descuento_aplicado"],
                subtotal_neto=data["subtotal_neto"],
                precio_tipo=data["precio_tipo"],
            )
            db.add(linea)
            # Descontar stock: capa 2 (@validates) y CheckConstraint en DB son la red de seguridad
            data["producto"].stock_llenos -= data["cantidad"]

        db.commit()
        db.refresh(venta)
        return venta

    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        # Captura @validates del modelo (capa 2 de clamping)
        db.rollback()
        raise HTTPException(400, f"Violación de integridad de stock: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al registrar la venta: {str(e)}")
