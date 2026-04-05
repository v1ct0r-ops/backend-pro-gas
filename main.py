from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.health import router as health_router


app = FastAPI(
    title="Pro-Gas ERP API",
    description="Internal inventory and cash management ERP - Backend API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS Middleware
# In production, CORS_ORIGINS must be set to your Vercel deployment domain,
# e.g.: https://pro-gas-erp.vercel.app
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health_router, prefix="/api")

# ---------------------------------------------------------------------------
# Root (convenience redirect for browser/health check services)
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Pro-Gas ERP API is running.",
        "docs": "/api/docs",
        "health": "/api/health",
    }
