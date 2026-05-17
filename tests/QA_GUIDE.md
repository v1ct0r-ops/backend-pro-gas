# Guía QA — Pro-Gas ERP Backend

---

## Resumen Ejecutivo

| Métrica | Resultado |
|---|---|
| Tests unitarios creados | **65** |
| Tests pasando | **65 / 65 (100%)** |
| Cobertura total `app/services/` | **100%** |
| Tiempo de ejecución | **~2.1 segundos** |
| Conexiones a base de datos | **0** (tests unitarios aislados) |
| Fallos | **0** |

---

## Infraestructura instalada

| Paquete | Versión | Rol |
|---|---|---|
| `pytest` | 9.0.1 | Framework de testing |
| `httpx` | 0.27.0 | Cliente HTTP async para tests ACID |
| `pytest-cov` | 6.1.0 | Reporte de cobertura de código |

---

## Archivos creados / modificados

| Archivo | Acción | Descripción |
|---|---|---|
| `requirements.txt` | Modificado | Agregado `pytest-cov==6.1.0` |
| `pytest.ini` | Modificado | `addopts` con cobertura automática (terminal + HTML) |
| `tests/conftest.py` | Creado | Fixtures compartidas: `app` (lazy) y `client` (TestClient) |
| `tests/test_cierres.py` | Creado | 22 tests — `cierre_diario_service.py` |
| `tests/test_ventas_revendedor.py` | Creado | 9 tests — `venta_revendedor_service.py` |
| `tests/test_media_carga.py` | Creado | 7 tests — `media_carga_service.py` |
| `tests/test_dashboard.py` | Creado | 10 tests — `dashboard_service.py` |
| `tests/test_logger.py` | Creado | 2 tests — `logger_service.py` |
| `tests/test_email.py` | Creado | 12 tests — `email_service.py` |
| `tests/QA_GUIDE.md` | Creado | Este documento |

---

## Configuración final (`pytest.ini`)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=app/services --cov-report=term-missing --cov-report=html --tb=short
```

**Por qué `--cov=app/services` y no `--cov=app`:**
Enfocar la cobertura solo en `app/services/` elimina el ruido de routers, modelos y schemas que no contienen lógica de negocio. El número resultante es honesto y accionable.

---

## Resultado de cobertura por módulo

```
Name                                       Stmts   Miss  Cover
--------------------------------------------------------------
app\services\__init__.py                       0      0   100%
app\services\cierre_diario_service.py         97      0   100%
app\services\dashboard_service.py             38      0   100%
app\services\email_service.py                 67      0   100%
app\services\logger_service.py                10      0   100%
app\services\media_carga_service.py           46      0   100%
app\services\venta_revendedor_service.py      46      0   100%
--------------------------------------------------------------
TOTAL                                        304      0   100%
```

---

## Detalle de tests por módulo

### `test_cierres.py` — 22 tests

| Suite | Test | Qué valida |
|---|---|---|
| `TestMatematicaCierreDiario` | `test_cuadre_exacto` | ventas=10000, desc=2000, efectivo=8000 → diferencia=0, estado='exacto' |
| | `test_cuadre_faltante` | efectivo insuficiente → diferencia>0, estado='faltante' |
| | `test_cuadre_sobrante` | efectivo excesivo → diferencia<0, estado='sobrante' |
| | `test_cuadre_exacto_con_vouchers` | efectivo + vouchers Transbank cubren el total |
| | `test_descuentos_none_tratados_como_cero` | `descuentos=None` en BD no rompe la aritmética |
| `TestReglasNegocioCierre` | `test_cierre_ya_cerrado_lanza_http_403` | Inmutabilidad: `is_closed=True` → HTTP 403 |
| | `test_cierre_inexistente_lanza_http_404` | `db.get()=None` → HTTP 404 |
| `TestCrearCierre` | `test_crear_cierre_exitoso` | Persiste objeto y llama add/commit/refresh |
| | `test_crear_cierre_error_db_lanza_http_500` | Fallo BD → HTTP 500 + rollback |
| `TestCerrarCierreInventario` | `test_cierre_con_lineas_actualiza_stock` | `galones_vendidos` descuenta `stock_llenos`; `vacios_devueltos` suma `stock_vacios` |
| | `test_cierre_stock_insuficiente_en_linea_lanza_400` | Stock < vendidos → HTTP 400 |
| | `test_cierre_producto_no_encontrado_en_linea_lanza_404` | Producto de línea no existe → HTTP 404 |
| | `test_cierre_error_generico_lanza_http_500` | `db.commit()` falla → HTTP 500 + rollback |
| `TestActualizarCierre` | `test_actualizar_cierre_exitoso` | Campo actualizado correctamente |
| | `test_actualizar_cierre_inmutable_lanza_403` | `is_closed=True` → HTTP 403 |
| | `test_actualizar_cierre_no_encontrado_lanza_404` | Cierre inexistente → HTTP 404 |
| | `test_actualizar_cierre_error_db_lanza_500` | Fallo BD → HTTP 500 + rollback |
| `TestEliminarCierre` | `test_eliminar_cierre_exitoso` | Llama `db.delete()` y `db.commit()` |
| | `test_eliminar_cierre_inmutable_lanza_403` | `is_closed=True` → HTTP 403 |
| | `test_eliminar_cierre_no_encontrado_lanza_404` | Cierre inexistente → HTTP 404 |
| | `test_eliminar_cierre_error_db_lanza_500` | Fallo BD → HTTP 500 + rollback |
| `TestTareaEmailCierre` | `test_tarea_email_cierre_llama_enviar_resumen` | Delega en `enviar_resumen_cierre` con los datos exactos |

---

### `test_ventas_revendedor.py` — 9 tests

| Suite | Test | Qué valida |
|---|---|---|
| `TestCalculosVentaRevendedor` | `test_iva_y_totales_correctos` | IVA=19%, total_bruto = total_final + IVA |
| | `test_kilos_calculados_por_peso_kg` | `kilos_linea = round(cantidad * peso_kg, 4)` |
| | `test_descuento_por_kilo_reduce_total_final` | `monto_descuento = round(kilos_totales * descuento/kg)` |
| | `test_stock_decrementado_tras_venta` | `stock_llenos` se reduce en la cantidad vendida |
| `TestValidacionesVentaRevendedor` | `test_producto_no_encontrado_lanza_404` | Producto inexistente → HTTP 404 |
| | `test_stock_insuficiente_lanza_400` | `stock < cantidad` → HTTP 400 con mensaje "Stock insuficiente" |
| | `test_descuento_supera_total_neto_lanza_400` | `total_final < 0` → HTTP 400 |
| | `test_value_error_capturado_como_400` | `@validates` lanza `ValueError` → HTTP 400 |
| | `test_error_generico_lanza_500_con_rollback` | `db.commit()` falla → HTTP 500 + rollback |

---

### `test_media_carga.py` — 7 tests

| Suite | Test | Qué valida |
|---|---|---|
| `TestCalculosMediaCarga` | `test_iva_y_totales_correctos` | IVA=19% sobre `total_neto` |
| | `test_kilos_totales_calculados` | `kilos = cantidad_llenos * peso_kg` |
| | `test_stock_llenos_incrementado` | Ingreso suma `cantidad_llenos` al `stock_llenos` del producto |
| `TestValidacionesMediaCarga` | `test_producto_no_encontrado_lanza_404` | Producto inexistente → HTTP 404 |
| | `test_cantidad_llenos_cero_lanza_400` | `cantidad_llenos < 1` → HTTP 400 |
| | `test_value_error_capturado_como_400` | `@validates` lanza `ValueError` → HTTP 400 |
| | `test_error_generico_lanza_500_con_rollback` | `db.commit()` falla → HTTP 500 + rollback |

---

### `test_dashboard.py` — 10 tests

| Suite | Test | Qué valida |
|---|---|---|
| `TestCajaHoy` | `test_sin_cierre_hoy_retorna_existe_false` | Sin registro del día → `{"existe": False}` |
| | `test_con_cierre_admin_muestra_datos_financieros` | `es_admin=True` expone `total_ventas_calc` y `efectivo_rendido` |
| | `test_con_cierre_operador_oculta_datos_financieros` | `es_admin=False` devuelve `None` en campos financieros |
| `TestVentasMes` | `test_sin_ventas_total_es_none_para_admin` | Sin ventas en el mes → `total_clp=None` |
| | `test_con_ventas_admin_retorna_totales` | Totales de ventas y kilos del mes |
| | `test_operador_no_ve_total_clp` | `es_admin=False` → `total_clp=None` siempre |
| `TestSaludCuadres` | `test_sin_faltantes_retorna_cero` | Sin faltantes en 7 días → `{"cierres_con_faltante": 0}` |
| | `test_con_faltantes_retorna_conteo` | N cierres con faltante en últimos 7 días |
| | `test_scalar_none_tratado_como_cero` | `scalar()=None` de BD se trata como 0 |
| `TestGrafico7Dias` | `test_retorna_exactamente_7_dias` | El array siempre tiene exactamente 7 entradas |
| | `test_dias_con_ventas_tienen_kilos_correctos` | Los kilos del día mapean correctamente desde la BD |
| | `test_dias_sin_datos_tienen_kilos_cero` | Días sin movimiento → `kilos_vendidos=0, kilos_ingresados=0` |
| `TestGetDashboardResumen` | `test_resumen_combina_todas_las_secciones` | Las 4 secciones del dashboard están presentes |

---

### `test_logger.py` — 2 tests

| Test | Qué valida |
|---|---|
| `test_registrar_llamada_persiste_y_retorna` | Llama `db.add`, `db.commit`, `db.refresh` |
| `test_registrar_llamada_usa_datos_del_payload` | Los campos del payload se transfieren correctamente al modelo |

---

### `test_email.py` — 12 tests

| Suite | Test | Qué valida |
|---|---|---|
| `TestFmtClp` | `test_formato_miles` | `1250000` → `"$ 1.250.000"` |
| | `test_formato_cero` | `0` → `"$ 0"` |
| | `test_formato_sin_miles` | `500` → `"$ 500"` |
| `TestConstruirHtmlReporte` | `test_sin_faltantes_muestra_seccion_ok` | HTML incluye sección "Sin alertas" |
| | `test_con_faltantes_muestra_tabla_de_alertas` | HTML incluye tabla con chofer y monto |
| | `test_html_contiene_datos_de_operacion` | Fecha y kilos presentes en el HTML |
| `TestEnviarResumenCierre` | `test_sin_smtp_configurado_no_envia` | Sin `SMTP_HOST` → retorna sin llamar SMTP |
| | `test_smtp_configurado_envia_email` | Con SMTP → llama `sendmail` una vez |
| | `test_smtp_error_no_propaga_excepcion` | Error de conexión SMTP → se loguea, no se propaga |
| `TestEnviarReporteDiario` | `test_sin_api_key_no_envia` | Sin `RESEND_API_KEY` → retorna sin llamar Resend |
| | `test_con_api_key_llama_resend` | Con API key → llama `resend.Emails.send` |
| | `test_error_resend_no_propaga_excepcion` | Error de Resend → se loguea, no se propaga |

---

## Estrategia de testing utilizada

### Tipo A — Tests unitarios (este documento)
Todos los tests de esta sesión son **unitarios puros**:
- Usan `unittest.mock.MagicMock` para reemplazar la sesión SQLAlchemy y los modelos ORM
- Servicios externos (SMTP, Resend) se mockean con `unittest.mock.patch`
- Cero conexiones a PostgreSQL ni a Internet
- Corren en ~2 segundos en cualquier máquina

### Tipo B — Tests ACID (`test_ventas_acidas.py`)
Tests de integración que **sí requieren** Docker + PostgreSQL local:
- Validan atomicidad, bloqueo pesimista (`SELECT FOR UPDATE`) y concurrencia real
- Correr con `docker compose up -d` activo antes de ejecutar

---

## Comandos de referencia

```bash
# Ejecutar todos los tests unitarios (sin BD)
pytest tests/ --ignore=tests/test_ventas_acidas.py -v

# Ejecutar un módulo específico
pytest tests/test_cierres.py -v

# Ver reporte en terminal
pytest tests/ --ignore=tests/test_ventas_acidas.py

# Abrir reporte HTML (se regenera automáticamente en cada ejecución)
start htmlcov/index.html          # Git Bash
Invoke-Item .\htmlcov\index.html  # PowerShell

# Guardar reporte como archivo de texto
pytest tests/ --ignore=tests/test_ventas_acidas.py > reporte_cobertura.txt 2>&1

# Commit estándar al agregar tests nuevos
git add tests/test_<modulo>.py
git commit -m "test(<modulo>): add unit tests for <descripcion>"
```

---

## Plantilla para un nuevo módulo

Al cubrir un nuevo servicio en `app/services/<nombre>_service.py`:

**Paso 1** — Identificar en el servicio:
- Cálculos matemáticos (totales, IVA, kilos, diferencias)
- Condiciones de estado (`is_closed`, `stock < qty`, `total < 0`)
- Rutas de error (`HTTPException` 400, 403, 404, 500)
- Llamadas a servicios externos (email, APIs)

**Paso 2** — Crear `tests/test_<nombre>.py` con esta estructura:

```python
from unittest.mock import MagicMock, patch
import pytest


def _make_mock(**kwargs) -> MagicMock:
    obj = MagicMock()
    obj.campo = kwargs.get("campo", valor_default)
    return obj


def _make_db(obj: MagicMock) -> MagicMock:
    db = MagicMock()
    db.get.return_value = obj          # para db.get(Modelo, id)
    db.query.return_value.filter.return_value.first.return_value = obj  # para queries
    db.query.return_value.all.return_value = []
    return db


class TestCalculos<Nombre>:
    def test_calculo_principal(self):
        from app.services.<nombre>_service import <funcion>
        # Arrange → Act → Assert

class TestValidaciones<Nombre>:
    def test_no_encontrado_lanza_404(self):
        from fastapi import HTTPException
        from app.services.<nombre>_service import <funcion>
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            <funcion>(db, ...)
        assert exc.value.status_code == 404
```

**Paso 3** — Verificar cobertura y cerrar líneas faltantes:

```bash
pytest tests/test_<nombre>.py -v
# Revisar columna Missing y agregar tests para las líneas críticas
```

**Paso 4** — Commit:

```bash
git add tests/test_<nombre>.py
git commit -m "test(<nombre>): add unit tests for <descripcion>"
```

---

## Convención de commits para QA

| Prefijo | Cuándo usarlo |
|---|---|
| `chore(qa):` | Infraestructura (conftest, pytest.ini, dependencias) |
| `test(<modulo>):` | Tests nuevos para un módulo específico |
| `fix(test):` | Corrección de un test roto |
