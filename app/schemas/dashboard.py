from datetime import date
from typing import Optional

from pydantic import BaseModel


class CajaHoy(BaseModel):
    existe: bool
    is_closed: Optional[bool] = None
    estado_cuadre: Optional[str] = None
    total_ventas_calc: Optional[int] = None
    efectivo_rendido: Optional[int] = None


class VentasMesActual(BaseModel):
    total_clp: Optional[int] = None
    kilos_totales: float


class SaludCuadres(BaseModel):
    cierres_con_faltante: int


class DiaGrafico(BaseModel):
    fecha: date
    kilos_vendidos: float
    kilos_ingresados: float


class DashboardResumen(BaseModel):
    caja_hoy: CajaHoy
    ventas_mes_actual: VentasMesActual
    salud_cuadres: SaludCuadres
    grafico_7_dias: list[DiaGrafico]
