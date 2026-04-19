from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _validar_rut_chileno(rut: str) -> str:
    rut = rut.strip().upper().replace(".", "")
    if "-" not in rut:
        raise ValueError("RUT debe incluir dígito verificador separado por '-' (ej: 12345678-9)")
    cuerpo, dv = rut.split("-", 1)
    if not cuerpo.isdigit() or len(cuerpo) < 7:
        raise ValueError("Cuerpo del RUT debe contener al menos 7 dígitos numéricos")

    digits = [int(d) for d in reversed(cuerpo)]
    factors = [2, 3, 4, 5, 6, 7]
    total = sum(d * factors[i % 6] for i, d in enumerate(digits))
    remainder = total % 11
    dv_calc_val = 11 - remainder
    if dv_calc_val == 11:
        dv_calculado = "0"
    elif dv_calc_val == 10:
        dv_calculado = "K"
    else:
        dv_calculado = str(dv_calc_val)

    if dv != dv_calculado:
        raise ValueError(f"Dígito verificador inválido para RUT '{rut}' (esperado: {dv_calculado})")
    return rut


class TratadoComercialIn(BaseModel):
    rut_cliente: str
    nombre_cliente: str
    formato_id: int
    descuento_por_kilo: float

    @field_validator("rut_cliente")
    @classmethod
    def validar_rut(cls, v: str) -> str:
        return _validar_rut_chileno(v)

    @field_validator("descuento_por_kilo")
    @classmethod
    def descuento_no_negativo(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El descuento por kilo no puede ser negativo")
        return v

    @field_validator("nombre_cliente")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del cliente no puede estar vacío")
        return v.strip()


class TratadoComercialUpdate(BaseModel):
    descuento_por_kilo: Optional[float] = None
    vigente: Optional[bool] = None

    @field_validator("descuento_por_kilo")
    @classmethod
    def descuento_no_negativo(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("El descuento por kilo no puede ser negativo")
        return v


class TratadoComercialOut(BaseModel):
    id: int
    rut_cliente: str
    nombre_cliente: str
    formato_id: int
    descuento_por_kilo: float
    vigente: bool
    admin_id: int

    model_config = ConfigDict(from_attributes=True)


class PrecioClienteIn(BaseModel):
    rut_cliente: str
    producto_id: int
    precio_factura_proveedor: int
    kilos_totales: float

    @field_validator("rut_cliente")
    @classmethod
    def validar_rut(cls, v: str) -> str:
        return _validar_rut_chileno(v)

    @field_validator("precio_factura_proveedor")
    @classmethod
    def precio_positivo(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("El precio de factura proveedor debe ser positivo")
        return v

    @field_validator("kilos_totales")
    @classmethod
    def kilos_positivos(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Los kilos totales deben ser positivos")
        return v


class PrecioClienteOut(BaseModel):
    tipo: str  # "revendedor" | "publico"
    neto: int
    iva: int
    total: int
    descuento_aplicado: Optional[float] = None
    tratado_id: Optional[int] = None
