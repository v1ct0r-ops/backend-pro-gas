from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin, ModelView # Agregamos ModelView

# Importamos la configuración y el engine
from app.core.config import settings, engine 

# Importamos los modelos y el router
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.inventario import router as inventario_router
from app.api.v1.medias_cargas import router as medias_cargas_router
from app.api.v1.bitacora import router as bitacora_router
from app.api.v1.usuarios import router as usuarios_router
from app.api.v1.cierres_diarios import router as cierres_diarios_router
from app.api.v1.tratados_comerciales import router as tratados_comerciales_router
from app.models.models import Base, Usuario # Asegúrate de que esta ruta sea correcta

# 1. Definimos la APP UNA SOLA VEZ con toda la info
app = FastAPI(
    title="Pro-Gas ERP API",
    description="ERP interno de inventario y caja — Pro-Gas",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# 2. Creamos las tablas en la DB de Docker
# (Esto es lo que hace que aparezcan en pgAdmin o SQLAdmin)
Base.metadata.create_all(bind=engine)

# 3. Configuración del "Prisma Studio" (SQLAdmin)
admin = Admin(app, engine)

class UsuarioAdmin(ModelView, model=Usuario):
    column_list = [Usuario.id, Usuario.nombre, Usuario.email]
    icon = "fa-solid fa-user"
    name = "Usuario"

admin.add_view(UsuarioAdmin)

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
app.include_router(tratados_comerciales_router, prefix="/api/v1/tratados-comerciales", tags=["tratados-comerciales"])

# 6. Ruta Raíz (Consolidada)
@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Pro-Gas ERP API is running.",
        "admin_panel": "/admin",
        "docs": "/api/docs",
        "health": "/api/health",
    }