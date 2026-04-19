from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates


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
    cierres_diarios: Mapped[list["CierreDiario"]] = relationship(back_populates="usuario")
    tratados_comerciales: Mapped[list["TratadoComercial"]] = relationship(back_populates="admin")


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

    tratados_comerciales: Mapped[list["TratadoComercial"]] = relationship(back_populates="formato")

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
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="cierres_diarios")


class TratadoComercial(Base):
    __tablename__ = "tratados_comerciales"
    __table_args__ = (
        CheckConstraint("descuento_por_kilo >= 0", name="ck_descuento_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rut_cliente: Mapped[str] = mapped_column(nullable=False, index=True)
    nombre_cliente: Mapped[str] = mapped_column(nullable=False)
    formato_id: Mapped[int] = mapped_column(ForeignKey("productos_maestro.id"), nullable=False)
    descuento_por_kilo: Mapped[float] = mapped_column(nullable=False)
    vigente: Mapped[bool] = mapped_column(nullable=False, default=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    formato: Mapped["ProductoMaestro"] = relationship(back_populates="tratados_comerciales")
    admin: Mapped["Usuario"] = relationship(back_populates="tratados_comerciales")
