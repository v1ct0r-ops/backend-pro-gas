# Guía QA — Pro-Gas ERP Backend

Documento de referencia para replicar la infraestructura de testing en nuevos módulos.

---

## Infraestructura instalada

| Paquete | Versión | Rol |
|---|---|---|
| `pytest` | 9.0.1 | Framework de testing |
| `httpx` | 0.27.0 | Cliente HTTP async para tests de integración |
| `pytest-cov` | 6.1.0 | Reporte de cobertura de código |

Todos declarados en `requirements.txt`.

---

## Estructura de archivos

```
tests/
├── conftest.py            ← Fixtures compartidas (TestClient, app lazy)
├── test_cierres.py        ← Tests unitarios: cierre_diario_service.py
├── test_ventas_acidas.py  ← Tests ACID: ventas_revendedor (requiere Docker)
└── QA_GUIDE.md            ← Este archivo
pytest.ini                 ← Configuración global de pytest + cobertura automática
```

---

## Dos tipos de tests en este proyecto

### Tipo A — Tests unitarios (sin base de datos)

**Cuándo usarlos:** lógica de negocio pura — cálculos, validaciones, reglas de estado.

**Herramienta:** `unittest.mock.MagicMock` para reemplazar la sesión SQLAlchemy y los modelos ORM.

**Ventaja:** corren en ~1 segundo, sin Docker, sin Neon.tech. Aptos para CI sin infraestructura adicional.

**Ejemplo:** `tests/test_cierres.py` → valida la aritmética de `cerrar_cierre()`.

### Tipo B — Tests ACID (con base de datos real)

**Cuándo usarlos:** flujos que dependen de transacciones, locks, rollbacks o constraints de la BD.

**Herramienta:** `httpx.AsyncClient` con `ASGITransport` contra PostgreSQL local (Docker puerto 5433).

**Ventaja:** prueban el comportamiento real incluyendo `SELECT FOR UPDATE`, `CHECK CONSTRAINT`, rollbacks.

**Ejemplo:** `tests/test_ventas_acidas.py` → atomicidad, concurrencia, stock negativo.

---

## Resultado de la sesión — Módulo: Cierres Diarios

### Tests creados (`tests/test_cierres.py`)

| Test | Escenario | Resultado |
|---|---|---|
| `test_cuadre_exacto` | ventas=10000, desc=2000, efectivo=8000, vouchers=0 → diferencia=0 | PASSED |
| `test_cuadre_faltante` | efectivo=5000, ventas netas=8000 → diferencia=3000 | PASSED |
| `test_cuadre_sobrante` | efectivo=9000, ventas netas=8000 → diferencia=-1000 | PASSED |
| `test_cuadre_exacto_con_vouchers` | efectivo=6000 + vouchers=4000 = ventas netas=10000 | PASSED |
| `test_descuentos_none_tratados_como_cero` | descuentos=None en BD no rompe la aritmética | PASSED |
| `test_cierre_ya_cerrado_lanza_http_403` | is_closed=True debe rechazar con HTTP 403 | PASSED |
| `test_cierre_inexistente_lanza_http_404` | db.get() retorna None → HTTP 404 | PASSED |

**Total: 7/7 PASSED — 0 fallos — Tiempo: ~1.4s**

### Cobertura alcanzada (`app/services/cierre_diario_service.py`)

```
Stmts: 97   Miss: 54   Cover: 44%
```

**Líneas pendientes de cubrir:**

| Líneas | Función | Para cubrirlas necesitas |
|---|---|---|
| 13–31 | `crear_cierre()` | Test de creación exitosa + test de error DB |
| 58–77 | Actualización de inventario al cerrar | Mock con `lineas_movimiento` con datos reales |
| 112–130 | `actualizar_cierre()` | Test de update exitoso + test de cierre inmutable |
| 134–148 | `eliminar_cierre()` | Test de delete exitoso + test de cierre inmutable |

---

## Comandos de referencia

```bash
# Correr tests de un módulo (cobertura incluida automáticamente por pytest.ini)
pytest tests/test_cierres.py -v

# Correr todos los tests
pytest -v

# Generar reporte HTML navegable
pytest tests/test_cierres.py --cov-report=html
start htmlcov/index.html        # abrir en Git Bash
```

---

## Plantilla para un nuevo módulo

Al agregar tests para otro servicio (ej: `venta_revendedor_service.py`):

### Paso 1 — Leer el servicio

Abrir `app/services/<nombre>_service.py` e identificar:
- Cálculos matemáticos (totales, precios, diferencias)
- Condiciones de estado (`if is_closed`, `if stock < qty`)
- Reglas de negocio críticas documentadas en `CLAUDE.md`

### Paso 2 — Crear `tests/test_<nombre>.py`

```python
from unittest.mock import MagicMock
import pytest


def _make_mock(**kwargs) -> MagicMock:
    obj = MagicMock()
    obj.campo = kwargs.get("campo", valor_default)
    # ... resto de campos
    return obj


def _make_db(obj: MagicMock) -> MagicMock:
    db = MagicMock()
    db.get.return_value = obj
    db.query.return_value.all.return_value = []
    return db


class TestLogica<Nombre>:

    def test_escenario_feliz(self):
        from app.services.<nombre>_service import <funcion>
        obj = _make_mock(campo=valor)
        db = _make_db(obj)

        <funcion>(db, ...)

        assert obj.campo_resultado == valor_esperado

    def test_regla_critica_lanza_excepcion(self):
        from fastapi import HTTPException
        from app.services.<nombre>_service import <funcion>

        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            <funcion>(db, ...)

        assert exc.value.status_code == 404  # o 403, 400
```

### Paso 3 — Verificar cobertura

```bash
pytest tests/test_<nombre>.py -v
```

Revisar la columna `Missing` y agregar tests para las líneas de lógica crítica sin cubrir.

### Paso 4 — Commit

```bash
git add tests/test_<nombre>.py
git commit -m "test(<nombre>): add unit tests for <descripcion>"
```

---

## Convención de commits para QA

| Prefijo | Cuándo usarlo |
|---|---|
| `chore(qa):` | Infraestructura de testing (conftest, pytest.ini, dependencias) |
| `test(<modulo>):` | Nuevos tests para un módulo específico |
| `fix(test):` | Corrección de un test roto |
