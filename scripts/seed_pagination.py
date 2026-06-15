"""
seed_pagination.py — Inserta datos de prueba para validar paginación.
Idempotente: no duplica si ya existen filas suficientes.
USO: python scripts/seed_pagination.py
Solo para la BD local (Docker). NUNCA contra Neon.tech/producción.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from database import SessionLocal
from app.core.security import hash_password
from app.models.models import (
    BitacoraLlamada,
    CierreDiario,
    MediaCarga,
    MediaCargaLinea,
    ProductoMaestro,
    Usuario,
    VentaRevendedor,
    VentaRevendedorLinea,
)

MIN_ROWS = 12


def _ensure_user(db) -> Usuario:
    user = db.query(Usuario).filter(Usuario.email == "seed@progas.local").first()
    if not user:
        user = Usuario(
            nombre="Seed User",
            email="seed@progas.local",
            password_hash=hash_password("seed1234"),
            rol="super_admin",
            estado=True,
        )
        db.add(user)
        db.flush()
    return user


def _ensure_producto(db) -> ProductoMaestro:
    producto = db.query(ProductoMaestro).first()
    if not producto:
        producto = ProductoMaestro(
            formato="11kg",
            peso_kg=11.0,
            precio_publico_base=15000,
            stock_llenos=500,
            stock_vacios=0,
        )
        db.add(producto)
        db.flush()
    return producto


def seed_bitacora(db, user: Usuario):
    count = db.query(BitacoraLlamada).count()
    if count >= MIN_ROWS:
        print(f"  bitacora_llamadas: {count} filas — sin cambios")
        return
    to_add = MIN_ROWS - count
    base = datetime.now(timezone.utc)
    for i in range(to_add):
        db.add(BitacoraLlamada(
            cliente_nombre=f"Cliente Seed {i + 1}",
            telefono=f"+56912345{i:03d}",
            direccion=f"Calle Seed {i + 1}, Santiago",
            detalle_pedido=f"Pedido de prueba #{i + 1}",
            fecha_hora=base - timedelta(hours=i),
            usuario_id=user.id,
        ))
    print(f"  bitacora_llamadas: agregados {to_add} registros")


def seed_medias_cargas(db, user: Usuario, producto: ProductoMaestro):
    count = db.query(MediaCarga).count()
    if count >= MIN_ROWS:
        print(f"  medias_cargas: {count} filas — sin cambios")
        return
    to_add = MIN_ROWS - count
    base = datetime.now(timezone.utc)
    for i in range(to_add):
        mc = MediaCarga(
            numero_guia=f"SEED-{i + 1:04d}",
            proveedor="Proveedor Seed",
            total_neto=100000 + i * 1000,
            total_iva=19000 + i * 190,
            total_bruto=119000 + i * 1190,
            kilos_totales=11.0,
            fecha=base - timedelta(days=i),
            usuario_id=user.id,
        )
        db.add(mc)
        db.flush()
        db.add(MediaCargaLinea(
            media_carga_id=mc.id,
            producto_id=producto.id,
            cantidad_llenos=1,
            precio_unitario_neto=100000 + i * 1000,
            subtotal_neto=100000 + i * 1000,
        ))
    print(f"  medias_cargas: agregados {to_add} registros")


def seed_cierres_diarios(db, user: Usuario):
    count = db.query(CierreDiario).count()
    if count >= MIN_ROWS:
        print(f"  cierres_diarios: {count} filas — sin cambios")
        return
    to_add = MIN_ROWS - count
    base = datetime.now(timezone.utc)
    choferes = ["Juan Pérez", "María García", "Carlos López"]
    for i in range(to_add):
        db.add(CierreDiario(
            chofer_nombre=choferes[i % len(choferes)],
            fecha=base - timedelta(days=i),
            efectivo_rendido=50000 + i * 500,
            vouchers_transbank=10000,
            descuentos=0,
            total_ventas_calc=60000 + i * 500,
            is_closed=False,
            usuario_id=user.id,
        ))
    print(f"  cierres_diarios: agregados {to_add} registros")


def seed_ventas_revendedor(db, user: Usuario, producto: ProductoMaestro):
    count = db.query(VentaRevendedor).count()
    if count >= MIN_ROWS:
        print(f"  ventas_revendedor: {count} filas — sin cambios")
        return
    to_add = MIN_ROWS - count
    base = datetime.now(timezone.utc)
    for i in range(to_add):
        rut = f"1234567{i % 10}-{(i % 9) + 1}"
        venta = VentaRevendedor(
            rut_cliente=rut,
            nombre_cliente=f"Revendedor Seed {i + 1}",
            fecha=base - timedelta(days=i),
            total_neto=84034,
            descuento_pesos_por_kilo=500,
            monto_descuento_total=5500,
            total_final=78534,
            total_iva=14921,
            total_bruto=93455,
            kilos_totales=11.0,
            usuario_id=user.id,
        )
        db.add(venta)
        db.flush()
        db.add(VentaRevendedorLinea(
            venta_id=venta.id,
            producto_id=producto.id,
            cantidad=1,
            precio_unitario_factura=84034,
            kilos_linea=11.0,
            descuento_aplicado=5500,
            subtotal_neto=78534,
            precio_tipo="revendedor",
        ))
    print(f"  ventas_revendedor: agregados {to_add} registros")


def seed_usuarios(db):
    count = db.query(Usuario).count()
    if count >= MIN_ROWS:
        print(f"  usuarios: {count} filas — sin cambios")
        return
    to_add = MIN_ROWS - count
    for i in range(to_add):
        email = f"operador_seed_{i + 1}@progas.local"
        if db.query(Usuario).filter(Usuario.email == email).first():
            continue
        db.add(Usuario(
            nombre=f"Operador Seed {i + 1}",
            email=email,
            password_hash=hash_password("seed1234"),
            rol="operador",
            estado=True,
        ))
    print(f"  usuarios: agregados hasta {to_add} registros")


def main():
    db = SessionLocal()
    try:
        print("Seeding datos de paginación (solo BD local)...")
        user = _ensure_user(db)
        producto = _ensure_producto(db)
        seed_bitacora(db, user)
        seed_medias_cargas(db, user, producto)
        seed_cierres_diarios(db, user)
        seed_ventas_revendedor(db, user, producto)
        seed_usuarios(db)
        db.commit()
        print("Seed completado.")
    except Exception as e:
        db.rollback()
        print(f"ERROR durante seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
