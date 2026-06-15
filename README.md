# Pro-Gas ERP — Backend API

Sistema ERP interno para una empresa distribuidora de gas en cilindros. Gestiona inventario bidireccional (llenos/vacíos), acuerdos de precio mayorista, conciliación de caja diaria, bitácora de llamadas y reportes operacionales. Construido con **FastAPI + PostgreSQL**, desplegado en **Render** con **Neon.tech** como base de datos en la nube.

---

## Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Framework HTTP | FastAPI | 0.115 |
| ORM | SQLAlchemy (sync) | 2.0 |
| Migraciones de esquema | Alembic | 1.18 |
| Driver de base de datos | psycopg2-binary | 2.9 |
| Validación | Pydantic v2 | 2.11 |
| Autenticación | PyJWT + bcrypt | 2.9 / 4.2 |
| Panel administrativo | SQLAdmin | 0.20 |
| Scheduler de tareas | APScheduler | 3.11 |
| Correo transaccional | Resend | 2.30 |
| Testing | pytest + pytest-cov | 9.0 / 6.1 |
| Base de datos cloud | Neon.tech (PostgreSQL 16) | — |
| Despliegue | Render | — |

---

## Arquitectura

```
main.py                      # App factory: instancia FastAPI, SQLAdmin, CORS, routers
database.py                  # Engine con pooling para Neon.tech, SessionLocal, get_db()
app/
├── core/
│   ├── config.py            # Singleton de settings (pydantic-settings, lee .env); crea el engine
│   ├── security.py          # Hashing bcrypt, encode/decode JWT
│   ├── dependencies.py      # get_current_user(), require_role() como dependencias FastAPI
│   └── scheduler.py         # Instancia APScheduler para jobs en segundo plano
├── models/
│   └── models.py            # Todos los modelos ORM SQLAlchemy (DeclarativeBase)
├── schemas/                 # Schemas Pydantic v2 de request/response por dominio
├── services/                # Capa de lógica de negocio — las rutas delegan completamente aquí
│   ├── stock_service.py
│   ├── media_carga_service.py
│   ├── cierre_diario_service.py
│   ├── ventas_revendedor_service.py
│   ├── logger_service.py
│   ├── email_service.py
│   └── dashboard_service.py
└── api/v1/                  # Routers FastAPI, un archivo por dominio
    ├── auth.py
    ├── usuarios.py
    ├── inventario.py
    ├── bitacora.py
    ├── medias_cargas.py
    ├── cierres_diarios.py
    ├── ventas_revendedor.py
    ├── dashboard.py
    └── reportes.py
```

### Dominios de Negocio

| Dominio | Prefijo del router | Descripción |
|---|---|---|
| Autenticación | `/api/v1/auth` | Login JWT y emisión de tokens |
| Usuarios / RBAC | `/api/v1/usuarios` | Gestión de usuarios; roles: `operador`, `super_admin` |
| Inventario | `/api/v1/inventario` | Catálogo maestro de productos con stock bidireccional (`stock_llenos` / `stock_vacios`) |
| Medias Cargas | `/api/v1/medias-cargas` | Documentos de entrega de proveedor procesados de forma atómica |
| Bitácora | `/api/v1/bitacora` | Registro de llamadas y pedidos entrantes de clientes |
| Cierres Diarios | `/api/v1/cierres-diarios` | Conciliación de caja por chofer; inmutable una vez cerrado |
| Ventas Revendedor | `/api/v1/ventas-revendedor` | Transacciones mayoristas con cálculo dinámico de descuento por kilo |
| Dashboard | `/api/v1/dashboard` | KPIs agregados para la vista operacional |
| Reportes | `/api/v1/reportes` | Generación de reportes históricos y financieros |

---

## Prerrequisitos

- Python **3.11+**
- **Docker Desktop** (instancia local de PostgreSQL)

---

## Configuración Local

### 1. Clonar y crear entorno virtual

```bash
git clone <url-del-repositorio>
cd erp-backend

python -m venv .venv

# Windows
.venv\Scripts\activate
# en caso de ocupar por bash para levantar
source .venv/Scripts/activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```env
# ── Base de datos ──────────────────────────────────────────────────────────────
# Docker local (por defecto para desarrollo)
DATABASE_URL=postgresql+psycopg2://victo:local_password@localhost:5433/pro_gas_erp

# ── Aplicación ─────────────────────────────────────────────────────────────────
APP_ENV=development
APP_DEBUG=False

# ── JWT ────────────────────────────────────────────────────────────────────────
SECRET_KEY=reemplazar-con-cadena-aleatoria-de-256-bits
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# ── CORS ───────────────────────────────────────────────────────────────────────
# Lista de orígenes permitidos separados por coma
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ── Correo SMTP (opcional) ─────────────────────────────────────────────────────
# Si no se configura, el envío de correo se omite silenciosamente
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SUPER_ADMIN_EMAIL=

# ── Resend (correo transaccional para reportes diarios) ────────────────────────
RESEND_API_KEY=
```

### 3. Iniciar la base de datos local

```bash
docker compose up -d
```

| Configuración | Valor |
|---|---|
| Puerto del host | **5433** (evita conflicto con una instancia local en 5432) |
| Base de datos | `pro_gas_erp` |
| Usuario | `victo` |
| Contraseña | `local_password` |

Para detener: `docker compose down`

### 4. Ejecutar el servidor de desarrollo

```bash
uvicorn main:app --reload
```

| URL | Descripción |
|---|---|
| `http://localhost:8000/` | Información raíz (enlaces a docs, admin, health) |
| `http://localhost:8000/api/docs` | Swagger UI |
| `http://localhost:8000/api/redoc` | ReDoc |
| `http://localhost:8000/api/health` | Health check — verifica conectividad con la DB |
| `http://localhost:8000/admin` | Panel SQLAdmin |

> Las tablas se crean automáticamente al iniciar mediante `Base.metadata.create_all()`. Para cambios de esquema en producción, utilizar Alembic.

---

## Referencia de Variables de Entorno

| Variable | Requerida | Valor por defecto | Descripción |
|---|---|---|---|
| `DATABASE_URL` | Sí | — | Cadena de conexión SQLAlchemy (dialecto psycopg2) |
| `SECRET_KEY` | Sí | — | Secreto de firma JWT (mínimo 32 bytes aleatorios) |
| `APP_ENV` | No | `development` | Etiqueta del entorno de ejecución |
| `APP_DEBUG` | No | `False` | Activa el modo debug |
| `ALGORITHM` | No | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `480` | TTL del token en minutos |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Lista de orígenes CORS permitidos, separados por coma |
| `SMTP_HOST` | No | `""` | Hostname del servidor SMTP |
| `SMTP_PORT` | No | `587` | Puerto del servidor SMTP |
| `SMTP_USER` | No | `""` | Usuario de login SMTP |
| `SMTP_PASSWORD` | No | `""` | Contraseña de login SMTP |
| `SMTP_FROM` | No | `""` | Dirección remitente para correos salientes |
| `SUPER_ADMIN_EMAIL` | No | `""` | Destinatario de las notificaciones de cierre diario |
| `RESEND_API_KEY` | No | `""` | API key de Resend para correo transaccional |

---

## Migraciones de Base de Datos (Alembic)

```bash
# Generar una nueva migración a partir de cambios en los modelos
alembic revision --autogenerate -m "descripción breve del cambio"

# Aplicar todas las migraciones pendientes
alembic upgrade head

# Revertir una migración
alembic downgrade -1

# Mostrar el estado actual de las migraciones
alembic current
```

---

## Testing y Calidad

### Ejecutar la suite completa

```bash
pytest
```

La configuración en `pytest.ini` apunta a `tests/` y genera automáticamente un reporte de cobertura sobre `app/services/`:

```
--cov=app/services --cov-report=term-missing --cov-report=html
```

El reporte HTML se escribe en `htmlcov/index.html`.

### Ejecutar un archivo de tests específico

```bash
pytest tests/test_cierres.py -v
```

### Ejecutar solo con reporte de cobertura en terminal

```bash
pytest --cov=app/services --cov-report=term-missing -q
```

### Verificar sintaxis (equivalente al chequeo de CI)

```bash
python -m compileall .
```

### Verificar conexión a la base de datos

```bash
python -c "from database import check_db_connection; check_db_connection(); print('OK')"
```

---

## Referencia de la API

Todas las rutas protegidas requieren el siguiente header:

```
Authorization: Bearer <access_token>
```

Roles: `operador` · `super_admin`

### Autenticación

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Pública | Devuelve un token JWT de acceso |

### Usuarios

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| `GET` | `/api/v1/usuarios/` | `super_admin` | Listar todos los usuarios |
| `GET` | `/api/v1/usuarios/{id}` | `super_admin` | Obtener usuario por ID |
| `POST` | `/api/v1/usuarios/` | `super_admin` | Crear usuario |
| `PATCH` | `/api/v1/usuarios/{id}` | `super_admin` | Actualización parcial |

### Inventario

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| `GET` | `/api/v1/inventario/` | Cualquier auth | Listar todos los productos con stock actual |
| `PATCH` | `/api/v1/inventario/{id}/ajuste` | `super_admin` | Ajuste manual de stock |

### Medias Cargas

Representa una entrega del proveedor. El procesamiento es **atómico** — todas las líneas se confirman o la operación completa se revierte (ROLLBACK).

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/medias-cargas/` | Cualquier auth | Registrar entrega (incrementa stock de llenos) |
| `GET` | `/api/v1/medias-cargas/` | Cualquier auth | Listar entregas |
| `GET` | `/api/v1/medias-cargas/{id}` | Cualquier auth | Obtener entrega por ID |

### Bitácora de Llamadas

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/bitacora/` | Cualquier auth | Registrar llamada/pedido entrante |
| `GET` | `/api/v1/bitacora/` | Cualquier auth | Listar llamadas (más recientes primero) |

### Cierres Diarios

Los registros con `is_closed=True` son **inmutables** — cualquier `PUT`, `PATCH` o `DELETE` sobre un cierre cerrado devuelve `HTTP 403`.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/cierres-diarios/` | Cualquier auth | Abrir nuevo registro de cierre |
| `GET` | `/api/v1/cierres-diarios/` | Cualquier auth | Listar cierres |
| `GET` | `/api/v1/cierres-diarios/{id}` | Cualquier auth | Obtener cierre por ID |
| `PATCH` | `/api/v1/cierres-diarios/{id}/cerrar` | Cualquier auth | Cerrar y conciliar |

### Ventas Revendedor

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/ventas-revendedor/` | Cualquier auth | Registrar transacción mayorista |
| `GET` | `/api/v1/ventas-revendedor/` | Cualquier auth | Listar ventas a revendedores |
| `GET` | `/api/v1/ventas-revendedor/{id}` | Cualquier auth | Obtener venta por ID |

**Reglas de precio:**

| Tipo de cliente | Precio neto | Total |
|---|---|---|
| Revendedor | `precio_factura − (kilos × descuento_por_kilo)` del tratado comercial vigente | `neto × 1.19` |
| Público general | `precio_publico_base` del maestro de productos | `neto × 1.19` |

El sistema resuelve el tipo de cliente automáticamente por RUT antes de cualquier cálculo de precio.

---

## CI / CD

### Integración Continua (GitHub Actions)

Dos workflows se ejecutan ante pushes a `dev`, `qa` y `main`:

| Workflow | Archivo | Disparador | Qué hace |
|---|---|---|---|
| Backend CI | `ci-backend.yml` | push/PR a `dev`, `qa`, `main` | Instala dependencias, ejecuta `compileall`, verifica imports de módulos clave, comprueba que no hay `.env` comprometido |
| Tests Unitarios y API | `backend-tests.yml` | push a `dev`, `qa` | Ejecuta `pytest` con DB mockeada; publica resumen de cobertura |

Los tests se ejecutan contra un `DATABASE_URL` ficticio — `get_db` está completamente mockeado y no se requiere base de datos real en CI.

### Despliegue (Render)

La configuración está declarada en `render.yaml`. El servicio arranca con:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Configurar las siguientes variables manualmente en el panel de Render (nunca committear secretos):

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión de Neon.tech (`?sslmode=require`) |
| `SECRET_KEY` | Secreto de firma aleatorio de 256 bits |
| `CORS_ORIGINS` | Dominio de producción en Vercel |
| `SUPER_ADMIN_EMAIL` | Destinatario de los reportes automáticos de cierre diario |
| `RESEND_API_KEY` | API key de Resend para correo transaccional |
| `SMTP_*` | Credenciales SMTP si se usa correo directo en lugar de Resend |

Ruta de health check: `/api/health`
