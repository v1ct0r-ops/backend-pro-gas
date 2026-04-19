# Pro-Gas ERP — API Backend

ERP interno para una empresa distribuidora de gas en cilindros. Gestiona inventario (llenos/vacíos), acuerdos de precio mayorista, cierre de caja diario y bitácora de llamadas. Construido con **FastAPI + PostgreSQL**, desplegado en **Render** con **Neon.tech** como base de datos en la nube.

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.111 |
| ORM | SQLAlchemy 2.0 (sync) |
| Migraciones | Alembic 1.13 |
| Driver DB | psycopg2-binary |
| Validación | Pydantic v2 |
| Panel admin | SQLAdmin |
| Autenticación | JWT (python-jose) + bcrypt |
| Base de datos cloud | Neon.tech (PostgreSQL 15) |
| Despliegue | Render |

---

## Requisitos Previos

- Python **3.11+**
- **Docker Desktop** (para la base de datos local)

---

## Configuración Local

### 1. Clonar y crear entorno virtual

```bash
git clone <repo-url>
cd erp-backend

python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

### 2. Variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```env
# ── Base de datos ──────────────────────────────────────────────────────────────
# Docker local (por defecto para desarrollo)
DATABASE_URL=postgresql+psycopg2://victo:local_password@localhost:5433/pro_gas_erp


# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ── Correo electrónico (opcional) ─────────────────────────────────────────────
# Si no se configura, las funciones de correo se omiten silenciosamente.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SUPER_ADMIN_EMAIL=
```

---

### 3. Iniciar la base de datos local

```bash
docker compose up -d
```

| Configuración | Valor |
|---------------|-------|
| Puerto del host | **5433** (evita conflicto con el 5432 local) |
| Base de datos | `pro_gas_erp` |
| Usuario | `victo` |
| Contraseña | `local_password` |

Para detenerla: `docker compose down`

---

### 4. Ejecutar el servidor de desarrollo

```bash
uvicorn main:app --reload
```

| URL | Descripción |
|-----|-------------|
| `http://localhost:8000/` | Info raíz |
| `http://localhost:8000/api/docs` | Swagger UI (interactivo) |
| `http://localhost:8000/api/redoc` | ReDoc |
| `http://localhost:8000/api/health` | Health check (ping a la DB) |
| `http://localhost:8000/admin` | Panel SQLAdmin |

Las tablas se crean automáticamente al iniciar vía `Base.metadata.create_all()`. Para cambios en producción usar Alembic.

---

## Migraciones de Base de Datos (Alembic)

```bash
# Generar migración a partir de cambios en los modelos
alembic revision --autogenerate -m "descripción del cambio"

# Aplicar todas las migraciones pendientes
alembic upgrade head

# Revertir un paso
alembic downgrade -1
```

---

## Estructura del Proyecto

```
erp-backend/
├── main.py                          # App factory, middleware, SQLAdmin, routers
├── database.py                      # Engine (pooling para Neon.tech), SessionLocal, get_db()
├── requirements.txt
├── docker-compose.yml               # Postgres local en puerto 5433
├── render.yaml                      # Configuración de despliegue en Render
├── alembic.ini
├── alembic/                         # Scripts de migración
└── app/
    ├── core/
    │   ├── config.py                # Singleton de settings (pydantic-settings, lee .env)
    │   ├── security.py              # Hashing bcrypt, encode/decode JWT
    │   └── dependencies.py          # get_current_user, dependencia RBAC require_role
    ├── models/
    │   └── models.py                # Modelos ORM SQLAlchemy (todas las tablas)
    ├── schemas/                     # Schemas Pydantic v2 de request/response
    │   ├── auth.py
    │   ├── usuarios.py
    │   ├── inventario.py
    │   ├── bitacora.py
    │   ├── medias_cargas.py
    │   ├── cierres_diarios.py
    │   └── tratados_comerciales.py
    ├── services/                    # Lógica de negocio (las rutas llaman a los servicios)
    │   ├── stock_service.py         # Validación de inventario, calculadora de precios
    │   ├── media_carga_service.py   # Procesamiento atómico de entregas, cálculo IVA
    │   ├── cierre_diario_service.py # Cierre diario, conciliación, email
    │   ├── logger_service.py        # Registro de llamadas
    │   └── email_service.py         # SMTP / correo HTML
    └── api/
        └── v1/                      # Routers FastAPI
            ├── auth.py
            ├── usuarios.py
            ├── inventario.py
            ├── bitacora.py
            ├── medias_cargas.py
            ├── cierres_diarios.py
            └── tratados_comerciales.py
```

---

## Referencia de la API

> Todas las rutas protegidas requieren el header `Authorization: Bearer <token>`.  
> Roles: `operador` (personal) · `super_admin` (acceso completo).

### Autenticación

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/api/v1/login` | Pública | Iniciar sesión, obtener JWT |

---

### Usuarios (`/api/v1/usuarios`)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| `GET` | `/usuarios/` | super_admin | Listar todos los usuarios |
| `GET` | `/usuarios/{id}` | super_admin | Obtener usuario por ID |
| `POST` | `/usuarios/` | super_admin | Crear usuario |
| `PATCH` | `/usuarios/{id}` | super_admin | Actualizar usuario (parcial) |

---

### Inventario (`/api/v1/inventario`)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| `GET` | `/inventario/` | Cualquier auth | Listar productos con stock actual |
| `PATCH` | `/inventario/{id}/ajuste` | super_admin | Ajuste manual de stock |

---

### Bitácora de Llamadas (`/api/v1/bitacora`)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| `POST` | `/bitacora/` | Cualquier auth | Registrar llamada/pedido entrante |
| `GET` | `/bitacora/` | Cualquier auth | Listar todas las llamadas (más recientes primero) |

---

### Medias Cargas (`/api/v1/medias-cargas`)

Representa una entrega del proveedor. El procesamiento es **atómico** — todas las líneas se confirman o la operación completa se revierte.

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| `POST` | `/medias-cargas/` | Cualquier auth | Registrar entrega (incrementa stock) |
| `GET` | `/medias-cargas/` | Cualquier auth | Listar entregas (más recientes primero) |
| `GET` | `/medias-cargas/{id}` | Cualquier auth | Obtener entrega por ID |

---

### Cierres Diarios (`/api/v1/cierres-diarios`)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| `POST` | `/cierres-diarios/` | Cualquier auth | Abrir nuevo registro de cierre |
| `GET` | `/cierres-diarios/` | Cualquier auth | Listar cierres (más recientes primero) |
| `GET` | `/cierres-diarios/{id}` | Cualquier auth | Obtener cierre por ID |
| `PATCH` | `/cierres-diarios/{id}/cerrar` | Cualquier auth | Cerrar y conciliar |

---

### Tratados Comerciales (`/api/v1/tratados-comerciales`)

Contratos de precio mayorista por RUT de cliente y formato de producto.

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| `GET` | `/tratados-comerciales/` | Cualquier auth | Listar todos los tratados |
| `GET` | `/tratados-comerciales/{id}` | Cualquier auth | Obtener tratado por ID |
| `POST` | `/tratados-comerciales/` | super_admin | Crear nuevo tratado |
| `PATCH` | `/tratados-comerciales/{id}` | super_admin | Actualizar descuento o estado |
| `DELETE` | `/tratados-comerciales/{id}` | super_admin | Eliminar tratado |
| `POST` | `/tratados-comerciales/calcular-precio` | Cualquier auth | Calcular precio para un cliente |


**Fórmulas de precio:**

| Tipo de cliente | Precio neto | IVA | Total |
|-----------------|-------------|-----|-------|
| Revendedor | `precio_factura - (kilos × descuento_por_kilo)` | `neto × 19%` | `neto × 1.19` |
| Público | `precio_publico_base` del maestro de productos | `neto × 19%` | `neto × 1.19` |

---

## CI / CD

**CI:** GitHub Actions (`.github/workflows/ci-backend.yml`) — se ejecuta en PRs hacia `main` o `qa`. Instala dependencias y valida sintaxis con `python -m compileall .`.

**CD:** Despliegue automático a **Render** vía `render.yaml`.  
Comando de inicio: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Configurar las siguientes variables en el panel de Render (nunca hardcodear):

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Cadena de conexión de Neon.tech |
| `SECRET_KEY` | Cadena aleatoria de 256 bits |
| `CORS_ORIGINS` | Dominio de producción en Vercel |
| `SUPER_ADMIN_EMAIL` | Correo del admin para notificaciones de cierre |
| `SMTP_*` | Credenciales SMTP para el envío de correos |
