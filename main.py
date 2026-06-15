from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin, ModelView

from app.core.admin_auth import AdminAuth
from app.core.config import settings, engine

# Importamos los modelos y el router
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.inventario import router as inventario_router
from app.api.v1.medias_cargas import router as medias_cargas_router
from app.api.v1.bitacora import router as bitacora_router
from app.api.v1.usuarios import router as usuarios_router
from app.api.v1.cierres_diarios import router as cierres_diarios_router
from app.api.v1.ventas_revendedor import router as ventas_revendedor_router
from app.api.v1.clientes import router as clientes_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.reportes import router as reportes_router
from app.models.models import (
    Base, Cliente, Usuario, ProductoMaestro, BitacoraLlamada, MediaCarga, MediaCargaLinea,
    CierreDiario, VentaRevendedor, VentaRevendedorLinea,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.scheduler import scheduler
    scheduler.start()
    yield
    scheduler.shutdown()


# 1. Definimos la APP UNA SOLA VEZ con toda la info
app = FastAPI(
    title="Pro-Gas ERP API",
    description="ERP interno de inventario y caja — Pro-Gas",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# 2. Creamos las tablas en la DB de Docker
# (Esto es lo que hace que aparezcan en pgAdmin o SQLAdmin)
Base.metadata.create_all(bind=engine)

# 3. Configuración del "Prisma Studio" (SQLAdmin) — con autenticación
admin = Admin(app, engine, authentication_backend=AdminAuth(secret_key=settings.SECRET_KEY))

class UsuarioAdmin(ModelView, model=Usuario):
    name = "Usuario"
    icon = "fa-solid fa-user"
    column_list = [Usuario.id, Usuario.nombre, Usuario.email, Usuario.rol, Usuario.estado]
    column_searchable_list = [Usuario.nombre, Usuario.email]
    column_filters = [Usuario.rol, Usuario.estado]

admin.add_view(UsuarioAdmin)

class ProductoMaestroAdmin(ModelView, model=ProductoMaestro):
    name = "Producto Maestro"
    icon = "fa-solid fa-box"
    column_list = [ProductoMaestro.id, ProductoMaestro.formato, ProductoMaestro.peso_kg,
                   ProductoMaestro.precio_publico_base, ProductoMaestro.stock_llenos, ProductoMaestro.stock_vacios]
    column_searchable_list = [ProductoMaestro.formato]
    column_filters = [ProductoMaestro.formato]

admin.add_view(ProductoMaestroAdmin)

class BitacoraLlamadaAdmin(ModelView, model=BitacoraLlamada):
    name = "Bitácora Llamadas"
    icon = "fa-solid fa-phone"
    column_list = [BitacoraLlamada.id, BitacoraLlamada.cliente_nombre, BitacoraLlamada.telefono,
                   BitacoraLlamada.fecha_hora, BitacoraLlamada.usuario]
    column_searchable_list = [BitacoraLlamada.cliente_nombre, BitacoraLlamada.telefono]

admin.add_view(BitacoraLlamadaAdmin)

class MediaCargaAdmin(ModelView, model=MediaCarga):
    name = "Media Carga"
    icon = "fa-solid fa-truck"
    column_list = [MediaCarga.id, MediaCarga.numero_guia, MediaCarga.fecha, MediaCarga.total_bruto, MediaCarga.usuario]
    column_searchable_list = [MediaCarga.numero_guia]
    column_filters = [MediaCarga.usuario, MediaCarga.fecha]

admin.add_view(MediaCargaAdmin)

class MediaCargaLineaAdmin(ModelView, model=MediaCargaLinea):
    name = "Línea Media Carga"
    icon = "fa-solid fa-list"
    column_list = [MediaCargaLinea.id, MediaCargaLinea.media_carga, MediaCargaLinea.producto,
                   MediaCargaLinea.cantidad_llenos, MediaCargaLinea.subtotal_neto]
    column_filters = [MediaCargaLinea.media_carga, MediaCargaLinea.producto]

admin.add_view(MediaCargaLineaAdmin)

class CierreDiarioAdmin(ModelView, model=CierreDiario):
    name = "Cierre Diario"
    icon = "fa-solid fa-calendar-check"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [CierreDiario.id, CierreDiario.chofer_nombre, CierreDiario.fecha,
                   CierreDiario.total_ventas_calc, CierreDiario.is_closed, CierreDiario.usuario]
    column_searchable_list = [CierreDiario.chofer_nombre]
    column_filters = [CierreDiario.is_closed, CierreDiario.usuario]

admin.add_view(CierreDiarioAdmin)

class VentaRevendedorAdmin(ModelView, model=VentaRevendedor):
    name = "Venta Revendedor"
    icon = "fa-solid fa-shop"
    column_list = [VentaRevendedor.id, VentaRevendedor.rut_cliente, VentaRevendedor.nombre_cliente,
                   VentaRevendedor.fecha, VentaRevendedor.total_bruto, VentaRevendedor.usuario]
    column_searchable_list = [VentaRevendedor.rut_cliente, VentaRevendedor.nombre_cliente]
    column_filters = [VentaRevendedor.usuario, VentaRevendedor.fecha]

admin.add_view(VentaRevendedorAdmin)

class VentaRevendedorLineaAdmin(ModelView, model=VentaRevendedorLinea):
    name = "Línea Venta Revendedor"
    icon = "fa-solid fa-receipt"
    column_list = [VentaRevendedorLinea.id, VentaRevendedorLinea.venta, VentaRevendedorLinea.producto,
                   VentaRevendedorLinea.cantidad, VentaRevendedorLinea.subtotal_neto]
    column_filters = [VentaRevendedorLinea.venta, VentaRevendedorLinea.producto]

admin.add_view(VentaRevendedorLineaAdmin)

class ClienteAdmin(ModelView, model=Cliente):
    name = "Cliente"
    icon = "fa-solid fa-address-book"
    column_list = [Cliente.id, Cliente.rut, Cliente.nombre, Cliente.email,
                   Cliente.descuento_pesos_por_kilo, Cliente.estado]
    column_searchable_list = [Cliente.rut, Cliente.nombre]
    column_filters = [Cliente.estado]

admin.add_view(ClienteAdmin)

# 4. Middleware (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Routers
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(inventario_router, prefix="/api/v1/inventario", tags=["inventario"])
app.include_router(medias_cargas_router, prefix="/api/v1/medias-cargas", tags=["medias-cargas"])
app.include_router(bitacora_router, prefix="/api/v1/bitacora", tags=["bitacora"])
app.include_router(usuarios_router, prefix="/api/v1/usuarios", tags=["usuarios"])
app.include_router(cierres_diarios_router, prefix="/api/v1/cierres-diarios", tags=["cierres-diarios"])
app.include_router(ventas_revendedor_router, prefix="/api/v1/ventas-revendedor", tags=["ventas-revendedor"])
app.include_router(clientes_router, prefix="/api/v1/clientes", tags=["clientes"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(reportes_router, prefix="/api/v1/reportes", tags=["reportes"])

# 6. Ruta Raíz (Consolidada)
@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Pro-Gas ERP API is running.",
        "admin_panel": "/admin",
        "docs": "/api/docs",
        "health": "/api/health",
    }