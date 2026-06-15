"""
Pruebas ACID para POST /api/v1/ventas-revendedor/

Requisitos previos:
    pip install pytest
    docker compose up -d        # Postgres local en puerto 5433

Ejecutar:
    pytest tests/test_ventas_acidas.py -v

IMPORTANTE — por qué los imports pesados están en fixtures y no en el módulo:
    `from main import app` provoca que main.py llame a
    `Base.metadata.create_all(bind=engine)` en el momento de la importación.
    Si pytest importa el módulo durante la fase de recolección (collection) y la
    DB no está disponible, el proceso se bloquea indefinidamente.
    Al ponerlo dentro de un fixture `scope="session"`, la importación ocurre
    durante la FASE DE EJECUCIÓN (cuando la DB ya debe estar activa), no durante
    la recolección.
"""
import asyncio
import os
import time
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ✅ Estos imports son seguros: solo definen clases, no abren conexiones a la DB.
from app.core.security import create_access_token, hash_password
from app.models.models import (
    ProductoMaestro,
    Usuario,
    VentaRevendedor,
    VentaRevendedorLinea,
)

# RUT chileno válido — dígito verificador = 5 (calculado algorítmicamente)
_RUT = "12345678-5"

_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://victo:local_password@localhost:5433/pro_gas_erp",
)


# ===========================================================================
# Fixtures de sesión (se instancian UNA vez; compartidas entre todos los tests)
# ===========================================================================

@pytest.fixture(scope="session")
def fastapi_app():
    """
    Importa la app FastAPI de forma LAZY (dentro del fixture, no a nivel módulo).

    De esta manera `Base.metadata.create_all(bind=engine)` en main.py se ejecuta
    en la FASE DE EJECUCIÓN de pytest, no durante la recolección de tests.
    Esto evita el hang cuando Docker no ha terminado de iniciar.
    """
    from main import app  # noqa: PLC0415  — import intencional fuera del top-level
    return app


@pytest.fixture(scope="session")
def db_engine():
    """
    Crea el SQLAlchemy engine UNA vez por sesión de pytest.
    `create_engine` es lazy: no abre conexiones hasta el primer uso.
    """
    engine = create_engine(
        _DB_URL,
        pool_pre_ping=True,
        pool_size=15,
        max_overflow=25,
        connect_args={"connect_timeout": 10},
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine):
    """Fábrica de sesiones SQLAlchemy reutilizable entre tests."""
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


# ===========================================================================
# Helpers internos (funciones puras, sin estado global)
# ===========================================================================

def _make_user(session: Session, tag: str) -> Usuario:
    """Crea y persiste un Usuario de prueba con email único (timestamp)."""
    user = Usuario(
        nombre=f"Test {tag}",
        email=f"acid_{tag}_{int(time.time() * 1000)}@progas.test",
        password_hash=hash_password("test1234"),
        rol="operador",
        estado=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _purge_ventas(session: Session, usuario_id: int) -> None:
    """Elimina en bulk las ventas y sus líneas de un usuario de prueba."""
    venta_ids = [
        row[0]
        for row in session.query(VentaRevendedor.id).filter_by(usuario_id=usuario_id)
    ]
    if venta_ids:
        session.query(VentaRevendedorLinea).filter(
            VentaRevendedorLinea.venta_id.in_(venta_ids)
        ).delete(synchronize_session=False)
        session.query(VentaRevendedor).filter(
            VentaRevendedor.id.in_(venta_ids)
        ).delete(synchronize_session=False)
        session.commit()


def _delete_obj(session: Session, obj) -> None:
    """Recarga el objeto desde la DB y lo elimina si aún existe."""
    if obj is None:
        return
    fresh = session.get(type(obj), obj.id)
    if fresh:
        session.delete(fresh)


def _bearer(usuario_id: int) -> dict:
    token = create_access_token({"sub": str(usuario_id)})
    return {"Authorization": f"Bearer {token}"}


def _payload(lineas: list[dict], descuento: int = 0) -> dict:
    return {
        "rut_cliente": _RUT,
        "nombre_cliente": "Distribuidora Test LTDA",
        "fecha": datetime.now(timezone.utc).isoformat(),
        "descuento_pesos_por_kilo": descuento,
        "lineas": lineas,
    }


# ===========================================================================
# TEST 1 — Atomicidad: rollback completo cuando un producto excede el stock
# ===========================================================================

def test_rollback_atomicidad_completa(fastapi_app, session_factory):
    """
    Escenario:
        - Producto A tiene 10 unidades (qty solicitada: 5 → OK).
        - Producto B tiene 2 unidades  (qty solicitada: 5 → FALLA: 5 > 2).

    El servicio valida TODOS los productos antes de escribir en la DB.
    Cuando B falla levanta HTTPException(400) y llama db.rollback().
    Stock de A jamás se tocó; ninguna VentaRevendedor debe existir.

    Aserciones:
        1. HTTP 400 con mensaje "Stock insuficiente".
        2. stock_llenos de A intacto (= 10).
        3. Ningún registro en ventas_revendedor.
    """
    session = session_factory()
    user = producto_a = producto_b = None

    try:
        user = _make_user(session, "atomicidad")

        producto_a = ProductoMaestro(
            formato="11kg-ACID-A", peso_kg=11.0,
            precio_publico_base=15_000, stock_llenos=10, stock_vacios=0,
        )
        producto_b = ProductoMaestro(
            formato="5kg-ACID-B", peso_kg=5.0,
            precio_publico_base=8_000, stock_llenos=2, stock_vacios=0,
        )
        session.add_all([producto_a, producto_b])
        session.commit()
        session.refresh(producto_a)
        session.refresh(producto_b)

        stock_a_antes = producto_a.stock_llenos  # 10

        async def _run():
            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(
                    "/api/v1/ventas-revendedor/",
                    json=_payload(lineas=[
                        # A: stock(10) >= qty(5) → pasa validación
                        {"producto_id": producto_a.id, "cantidad": 5, "precio_unitario_factura": 12_000},
                        # B: stock(2) < qty(5)  → levanta HTTPException(400)
                        {"producto_id": producto_b.id, "cantidad": 5, "precio_unitario_factura": 6_000},
                    ]),
                    headers=_bearer(user.id),
                )

        resp = asyncio.run(_run())

        # Aserción 1 — error de negocio
        assert resp.status_code == 400, (
            f"Esperado HTTP 400, recibido {resp.status_code}.\nBody: {resp.text}"
        )
        assert "Stock insuficiente" in resp.json().get("detail", ""), (
            f"Mensaje inesperado: {resp.json()}"
        )

        # Aserción 2 — stock de A intacto (rollback verificado contra la DB)
        session.expire(producto_a)
        session.refresh(producto_a)
        assert producto_a.stock_llenos == stock_a_antes, (
            f"ROLLBACK FALLÓ: stock_llenos de A era {stock_a_antes}, ahora es {producto_a.stock_llenos}"
        )

        # Aserción 3 — ninguna VentaRevendedor creada
        venta = session.query(VentaRevendedor).filter_by(usuario_id=user.id).first()
        assert venta is None, (
            f"Se creó VentaRevendedor id={venta.id} cuando debía hacerse rollback"
        )

    finally:
        if user:
            _purge_ventas(session, user.id)
        _delete_obj(session, producto_a)
        _delete_obj(session, producto_b)
        _delete_obj(session, user)
        session.commit()
        session.close()


# ===========================================================================
# TEST 2 — Consistencia: Pydantic rechaza descuento negativo (HTTP 422)
# ===========================================================================

def test_validacion_descuento_negativo(fastapi_app, session_factory):
    """
    Escenario:
        - Payload con `descuento_pesos_por_kilo = -100`.

    El @field_validator de Pydantic en VentaRevendedorIn debe rechazar el
    payload ANTES de que el request llegue al servicio (capa de schema, HTTP 422).
    El servicio nunca se ejecuta: la DB queda intacta.

    Aserciones:
        1. HTTP 422 (Unprocessable Entity).
        2. El campo "descuento_pesos_por_kilo" aparece en el detalle del error.
        3. stock_llenos del producto sin cambios.
        4. Ningún registro en ventas_revendedor.
    """
    session = session_factory()
    user = producto = None

    try:
        user = _make_user(session, "consistencia")
        producto = ProductoMaestro(
            formato="11kg-VALID-TEST", peso_kg=11.0,
            precio_publico_base=15_000, stock_llenos=50, stock_vacios=0,
        )
        session.add(producto)
        session.commit()
        session.refresh(producto)

        stock_antes = producto.stock_llenos  # 50

        async def _run():
            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(
                    "/api/v1/ventas-revendedor/",
                    json=_payload(
                        lineas=[{"producto_id": producto.id, "cantidad": 1, "precio_unitario_factura": 12_000}],
                        descuento=-100,  # INVÁLIDO: viola @field_validator("descuento_pesos_por_kilo")
                    ),
                    headers=_bearer(user.id),
                )

        resp = asyncio.run(_run())

        # Aserción 1 — Pydantic rechaza antes del servicio
        assert resp.status_code == 422, (
            f"Esperado HTTP 422, recibido {resp.status_code}.\nBody: {resp.text}"
        )

        # Aserción 2 — el error identifica el campo correcto
        body_str = str(resp.json().get("detail", ""))
        assert "descuento_pesos_por_kilo" in body_str, (
            f"El 422 no menciona el campo. Detail: {body_str}"
        )

        # Aserción 3 — stock sin cambios
        session.expire(producto)
        session.refresh(producto)
        assert producto.stock_llenos == stock_antes, (
            f"Stock cambió de {stock_antes} → {producto.stock_llenos} con payload inválido"
        )

        # Aserción 4 — ninguna venta guardada
        assert session.query(VentaRevendedor).filter_by(usuario_id=user.id).first() is None

    finally:
        if user:
            _purge_ventas(session, user.id)
        _delete_obj(session, producto)
        _delete_obj(session, user)
        session.commit()
        session.close()


# ===========================================================================
# TEST 3 — Aislamiento: 50 requests concurrentes, stock nunca negativo
# ===========================================================================

def test_concurrencia_sin_stock_negativo(fastapi_app, session_factory):
    """
    Escenario:
        - 12 corrutinas lanzan simultáneamente una venta de 1 unidad al mismo
          producto que tiene exactamente 5 unidades (asyncio.gather).

    NOTA: la concurrencia (12) se mantiene <= al pool de conexiones del engine
    (pool_size 5 + max_overflow 10 = 15). Superar 15 provoca QueuePool timeout
    —un límite de infraestructura, no un fallo de negocio— y deja datos huérfanos
    en la BD al abortar antes del cleanup.

    El bloqueo pesimista `.with_for_update()` serializa el acceso al inventario
    en PostgreSQL. Se espera que solo 5 transacciones ganen el lock con stock
    disponible; las otras 7 encuentren stock=0 y reciban HTTP 400.

    Aserciones:
        1. stock_llenos final >= 0 (invariante crítica de negocio).
        2. Exactamente 5 respuestas HTTP 201 (ventas exitosas).
        3. Exactamente 7 respuestas HTTP 400 (stock agotado).
        4. stock_llenos final == 0 (todas las unidades vendidas sin sobreventa).
        5. Ningún request individual supera 1.5 s de tiempo de respuesta.
    """
    N_CONCURRENT = 12   # <= pool (5 + overflow 10 = 15) para no agotar conexiones
    STOCK_INICIAL = 5

    session = session_factory()
    user = producto = None

    try:
        user = _make_user(session, "concurrencia")
        producto = ProductoMaestro(
            formato="11kg-CONCURRENT",
            peso_kg=11.0,
            precio_publico_base=15_000,
            stock_llenos=STOCK_INICIAL,  # unidades disponibles
            stock_vacios=0,
        )
        session.add(producto)
        session.commit()
        session.refresh(producto)

        headers     = _bearer(user.id)
        producto_id = producto.id
        endpoint    = "/api/v1/ventas-revendedor/"

        async def _disparar_concurrente() -> list[tuple[int, float]]:
            """Dispara N_CONCURRENT requests concurrentes vía asyncio.gather."""
            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                timeout=10.0,
            ) as client:

                async def _una(_: int) -> tuple[int, float]:
                    payload = _payload(lineas=[{
                        "producto_id": producto_id,
                        "cantidad": 1,
                        "precio_unitario_factura": 12_000,
                    }])
                    t0   = time.monotonic()
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    return resp.status_code, time.monotonic() - t0

                # asyncio.gather lanza las N_CONCURRENT corrutinas simultáneamente.
                # FastAPI ejecuta cada handler síncrono en un thread del pool,
                # por lo que los with_for_update() en PostgreSQL compiten en paralelo.
                return list(await asyncio.gather(*[_una(i) for i in range(N_CONCURRENT)]))

        resultados = asyncio.run(_disparar_concurrente())

        codigos  = [r[0] for r in resultados]
        tiempos  = [r[1] for r in resultados]
        exitosas = codigos.count(201)
        fallidas = codigos.count(400)

        # Leer stock final con sesión fresca (sin caché ORM)
        session.expire(producto)
        session.refresh(producto)
        stock_final = producto.stock_llenos

        # Aserción 1 — invariante de negocio: stock no negativo
        assert stock_final >= 0, (
            f"VIOLACIÓN CRÍTICA: stock_llenos = {stock_final} (negativo)"
        )

        # Aserción 2 — exactamente STOCK_INICIAL ventas exitosas
        assert exitosas == STOCK_INICIAL, (
            f"Esperadas {STOCK_INICIAL} ventas exitosas, se registraron {exitosas}.\n"
            f"201={exitosas}, 400={fallidas}, otros={[c for c in codigos if c not in (201, 400)]}"
        )

        # Aserción 3 — el resto son rechazos por stock insuficiente
        assert exitosas + fallidas == N_CONCURRENT, (
            f"Códigos inesperados: {sorted(set(codigos) - {201, 400})}"
        )

        # Aserción 4 — sin sobreventa: stock final = 0
        assert stock_final == 0, (
            f"Stock final debería ser 0 tras 10 ventas exitosas, es {stock_final}"
        )

        # Aserción 5 — rendimiento: ningún request supera 1.5 s
        tiempo_max = max(tiempos)
        tiempos_ord = sorted(tiempos)
        p50 = tiempos_ord[len(tiempos_ord) // 2]
        p95 = tiempos_ord[min(len(tiempos_ord) - 1, int(len(tiempos_ord) * 0.95))]
        assert tiempo_max < 1.5, (
            f"Request más lento: {tiempo_max:.3f}s (límite 1.5s).\n"
            f"p50={p50:.3f}s  p95={p95:.3f}s  max={tiempo_max:.3f}s"
        )

    finally:
        if user:
            _purge_ventas(session, user.id)
        _delete_obj(session, producto)
        _delete_obj(session, user)
        session.commit()
        session.close()
