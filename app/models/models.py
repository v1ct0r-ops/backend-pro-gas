from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    rol: Mapped[str] = mapped_column(nullable=False)  # "operador" | "super_admin"
    estado: Mapped[bool] = mapped_column(nullable=False, default=True)

    bitacora_llamadas: Mapped[list["BitacoraLlamada"]] = relationship(back_populates="usuario")
    medias_cargas: Mapped[list["MediaCarga"]] = relationship(back_populates="usuario")
    cierres_diarios: Mapped[list["CierreDiario"]] = relationship(
        back_populates="usuario", foreign_keys="[CierreDiario.usuario_id]"
    )
    ventas_revendedor: Mapped[list["VentaRevendedor"]] = relationship(back_populates="usuario")


class ProductoMaestro(Base):
    __tablename__ = "productos_maestro"
    __table_args__ = (
        CheckConstraint("stock_llenos >= 0", name="ck_stock_llenos_non_negative"),
        CheckConstraint("stock_vacios >= 0", name="ck_stock_vacios_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    formato: Mapped[str] = mapped_column(nullable=False)  # "5kg", "11kg", etc.
    peso_kg: Mapped[float] = mapped_column(nullable=False)
    precio_publico_base: Mapped[int] = mapped_column(nullable=False)
    stock_llenos: Mapped[int] = mapped_column(nullable=False, default=0)
    stock_vacios: Mapped[int] = mapped_column(nullable=False, default=0)

    @validates("stock_llenos")
    def validate_stock_llenos(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError(f"stock_llenos no puede ser negativo (recibido: {value})")
        return value

    @validates("stock_vacios")
    def validate_stock_vacios(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError(f"stock_vacios no puede ser negativo (recibido: {value})")
        return value


class BitacoraLlamada(Base):
    __tablename__ = "bitacora_llamadas"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_nombre: Mapped[str] = mapped_column(nullable=False)
    telefono: Mapped[str] = mapped_column(nullable=False)
    direccion: Mapped[str] = mapped_column(nullable=False)
    detalle_pedido: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="bitacora_llamadas")


class MediaCarga(Base):
    __tablename__ = "medias_cargas"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero_guia: Mapped[str] = mapped_column(nullable=False)
    proveedor: Mapped[Optional[str]] = mapped_column(nullable=True)  # nullable para filas previas a esta migración
    total_neto: Mapped[int] = mapped_column(nullable=False)
    total_iva: Mapped[int] = mapped_column(nullable=False)
    total_bruto: Mapped[int] = mapped_column(nullable=False)
    kilos_totales: Mapped[float] = mapped_column(nullable=False)
    fecha: Mapped[datetime] = mapped_column(nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="medias_cargas")
    lineas: Mapped[list["MediaCargaLinea"]] = relationship(back_populates="media_carga", cascade="all, delete-orphan")


class MediaCargaLinea(Base):
    __tablename__ = "medias_cargas_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_carga_id: Mapped[int] = mapped_column(ForeignKey("medias_cargas.id"), nullable=False)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_maestro.id"), nullable=False)
    cantidad_llenos: Mapped[int] = mapped_column(nullable=False)
    precio_unitario_neto: Mapped[int] = mapped_column(nullable=False)
    subtotal_neto: Mapped[int] = mapped_column(nullable=False)

    media_carga: Mapped["MediaCarga"] = relationship(back_populates="lineas")
    producto: Mapped["ProductoMaestro"] = relationship()


class CierreDiario(Base):
    __tablename__ = "cierres_diarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    chofer_nombre: Mapped[str] = mapped_column(nullable=False)
    fecha: Mapped[datetime] = mapped_column(nullable=False)
    efectivo_rendido: Mapped[int] = mapped_column(nullable=False, default=0)
    vouchers_transbank: Mapped[int] = mapped_column(nullable=False, default=0)
    descuentos: Mapped[int] = mapped_column(nullable=False, default=0)
    total_ventas_calc: Mapped[int] = mapped_column(nullable=False, default=0)
    is_closed: Mapped[bool] = mapped_column(nullable=False, default=False)
    diferencia: Mapped[Optional[int]] = mapped_column(nullable=True, default=None)
    estado_cuadre: Mapped[Optional[str]] = mapped_column(nullable=True, default=None)
    stock_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)
    lineas_movimiento: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=None)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    # Auditoría — nullable=True para no romper filas existentes en la migración
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    cerrado_por_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True, default=None
    )

    # foreign_keys requerido porque hay dos FK a la misma tabla usuarios
    usuario: Mapped["Usuario"] = relationship(
        back_populates="cierres_diarios", foreign_keys=[usuario_id]
    )
    cerrado_por: Mapped[Optional["Usuario"]] = relationship(foreign_keys=[cerrado_por_id])


class VentaRevendedor(Base):
    __tablename__ = "ventas_revendedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    rut_cliente: Mapped[str] = mapped_column(nullable=False, index=True)
    nombre_cliente: Mapped[str] = mapped_column(nullable=False)
    fecha: Mapped[datetime] = mapped_column(nullable=False)
    total_neto: Mapped[int] = mapped_column(nullable=False)
    descuento_pesos_por_kilo: Mapped[int] = mapped_column(nullable=False, default=0)
    monto_descuento_total: Mapped[int] = mapped_column(nullable=False, default=0)
    total_final: Mapped[int] = mapped_column(nullable=False, default=0)
    total_iva: Mapped[int] = mapped_column(nullable=False)
    total_bruto: Mapped[int] = mapped_column(nullable=False)
    kilos_totales: Mapped[float] = mapped_column(nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="ventas_revendedor")
    lineas: Mapped[list["VentaRevendedorLinea"]] = relationship(back_populates="venta", cascade="all, delete-orphan")


class VentaRevendedorLinea(Base):
    __tablename__ = "ventas_revendedor_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas_revendedor.id"), nullable=False)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_maestro.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(nullable=False)
    precio_unitario_factura: Mapped[int] = mapped_column(nullable=False)
    kilos_linea: Mapped[float] = mapped_column(nullable=False)
    descuento_aplicado: Mapped[Optional[int]] = mapped_column(nullable=True, default=None)
    subtotal_neto: Mapped[int] = mapped_column(nullable=False)
    precio_tipo: Mapped[str] = mapped_column(nullable=False)  # "revendedor" | "publico"

    venta: Mapped["VentaRevendedor"] = relationship(back_populates="lineas")
    producto: Mapped["ProductoMaestro"] = relationship()


class MediaCargaHistorial(Base):
    """Snapshot inmutable de cada ingreso de galones. Nunca se modifica tras su creación."""

    __tablename__ = "medias_cargas_historial"
    __table_args__ = (
        # Índice compuesto para el reporte más frecuente: proveedor + rango de fecha
        Index("ix_mc_hist_proveedor_fecha", "proveedor", "fecha_registro"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # FK nullable con SET NULL: el historial sobrevive si se elimina la media carga origen
    media_carga_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medias_cargas.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Snapshot del documento (desnormalizado, inmutable) ---
    numero_guia: Mapped[str] = mapped_column(nullable=False, index=True)
    proveedor: Mapped[str] = mapped_column(nullable=False)
    fecha_documento: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    # --- Montos en CLP: Integer elimina error de punto flotante (regla del proyecto) ---
    total_neto: Mapped[int] = mapped_column(nullable=False)
    total_iva: Mapped[int] = mapped_column(nullable=False)   # siempre round(neto * 0.19)
    total_bruto: Mapped[int] = mapped_column(nullable=False)  # neto + iva

    # --- Kilos con Numeric(10,3): exactitud decimal sin IEEE-754 ---
    kilos_totales: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    # --- Auditoría ---
    # server_default=func.now() → la DB fija el timestamp atómicamente, sin depender del reloj de la app
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # RESTRICT: un usuario con historial no puede eliminarse (integridad de auditoría)
    registrado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    registrado_por: Mapped["Usuario"] = relationship()
    lineas: Mapped[list["MediaCargaHistorialLinea"]] = relationship(
        back_populates="historial", cascade="all, delete-orphan"
    )


class MediaCargaHistorialLinea(Base):
    """Línea de detalle del historial. Snapshot del producto al momento del ingreso."""

    __tablename__ = "medias_cargas_historial_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    historial_id: Mapped[int] = mapped_column(
        ForeignKey("medias_cargas_historial.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Snapshot desnormalizado: refleja el estado del producto en el momento exacto del ingreso
    formato_producto: Mapped[str] = mapped_column(nullable=False)         # ej. "11kg"
    cantidad_llenos: Mapped[int] = mapped_column(nullable=False)
    cantidad_vacios: Mapped[int] = mapped_column(nullable=False, default=0)
    precio_unitario_neto: Mapped[int] = mapped_column(nullable=False)     # CLP, sin IVA
    kilos_linea: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    subtotal_neto: Mapped[int] = mapped_column(nullable=False)            # cantidad_llenos * precio_unitario_neto

    historial: Mapped["MediaCargaHistorial"] = relationship(back_populates="lineas")


class Cliente(Base):
    """Maestro de clientes revendedor. Snapshot: la venta copia los valores al registrarse."""

    __tablename__ = "clientes"
    __table_args__ = (
        CheckConstraint("descuento_pesos_por_kilo >= 0", name="ck_cliente_descuento_non_negative"),
        Index("ix_clientes_nombre", "nombre"),
        Index("ix_clientes_estado", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rut: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    descuento_pesos_por_kilo: Mapped[int] = mapped_column(nullable=False, default=0)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, onupdate=func.now()
    )

    @validates("descuento_pesos_por_kilo")
    def validate_descuento(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError(f"descuento_pesos_por_kilo no puede ser negativo (recibido: {value})")
        return value
