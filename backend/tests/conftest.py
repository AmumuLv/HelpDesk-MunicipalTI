"""Configuracion de pruebas.

Las pruebas usan un replica set efimero de MongoDB arrancado con Docker, de modo que
las transacciones multi-documento funcionan igual que en produccion. Si Docker no esta
disponible, se omite la suite completa con un mensaje claro.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

if os.environ.get("TEST_REDIS_URL"):
    os.environ["REDIS_URL"] = os.environ["TEST_REDIS_URL"]
os.environ.setdefault("CLAMAV_ENABLED", "false")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-no-usar-en-produccion-1234567890")
os.environ.setdefault("MONGO_DB", f"mesa_ayuda_test_{uuid.uuid4().hex[:8]}")
if os.environ["MONGO_DB"] == "helpdesk_test_suite":
    os.environ["MONGO_DB"] += "_" + uuid.uuid4().hex[:8]
os.environ.setdefault("BUSINESS_TIMEZONE", "America/Lima")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "3000")

CONTAINER_MONGO = "mesa-ayuda-test-mongo"
REPLICA_SET = "rs_test"


def _docker(*args: str) -> None:
    import subprocess

    subprocess.run(["docker", *args], check=True, capture_output=True, text=True)


@pytest.fixture(scope="session", autouse=True)
def mongo_replica_set():
    """Replica set para las pruebas.

    Si se define TEST_MONGO_URI se reutiliza (útil en CI y dentro de Docker);
    si no, se arranca un contenedor propio en el host.
    """
    import subprocess
    import time

    externa = os.environ.get("TEST_MONGO_URI")
    if externa:
        import pymongo

        cliente = pymongo.MongoClient(externa, serverSelectionTimeoutMS=3000)
        for _ in range(30):
            try:
                cliente.admin.command("ping")
                break
            except Exception:
                time.sleep(1)
        else:  # pragma: no cover
            pytest.skip(f"TEST_MONGO_URI no responde: {externa}")
        cliente.close()
        os.environ["MONGO_URI"] = externa
        yield externa
        return

    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Docker no disponible, se omiten las pruebas de integracion: {exc}")

    nombre = f"{CONTAINER_MONGO}-{uuid.uuid4().hex[:6]}"
    puerto = 27099
    _docker("run", "-d", "--name", nombre, "-p", f"{puerto}:27017", "mongo:8.0", "mongod", "--replSet", "rs_test", "--bind_ip_all")
    import time

    uri = f"mongodb://localhost:{puerto}/?replicaSet={REPLICA_SET}"
    conectado = False
    for _ in range(60):
        try:
            import pymongo

            cliente = pymongo.MongoClient(uri, serverSelectionTimeoutMS=1000)
            cliente.admin.command("ping")
            conectado = True
            break
        except Exception:
            time.sleep(1)
    if not conectado:  # pragma: no cover
        _docker("rm", "-f", nombre)
        pytest.skip("No se pudo arrancar MongoDB de pruebas")
    import pymongo

    cliente = pymongo.MongoClient(uri, directConnection=True)
    try:
        cliente.admin.command("replSetInitiate", {"_id": REPLICA_SET, "members": [{"_id": 0, "host": f"localhost:{puerto}"}]})
    except Exception:
        pass
    for _ in range(60):
        try:
            if cliente.admin.command("hello").get("isWritablePrimary"):
                break
        except Exception:
            pass
        time.sleep(1)
    cliente.close()
    os.environ["MONGO_URI"] = uri
    os.environ["REDIS_URL"] = os.environ.get("REDIS_URL_TEST", "redis://localhost:6379/15")
    try:
        yield uri
    finally:
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)


@pytest.fixture(scope="session")
def redis_limpio(mongo_replica_set: str):
    """Redis de pruebas: usa uno existente (TEST_REDIS_URL) o arranca un contenedor."""
    import subprocess
    import time

    from redis import Redis

    externa = os.environ.get("TEST_REDIS_URL")
    if externa:
        cliente = Redis.from_url(externa, decode_responses=True, socket_connect_timeout=2)
        cliente.ping()
        os.environ["REDIS_URL"] = externa
        cliente.flushdb()
        yield externa
        return

    url_local = os.environ.get("REDIS_URL_TEST", "redis://localhost:6379/15")
    try:
        cliente = Redis.from_url(url_local, decode_responses=True, socket_connect_timeout=1)
        cliente.ping()
        cliente.flushdb()
        return url_local
    except Exception:
        pass

    nombre = f"mesa-ayuda-test-redis-{uuid.uuid4().hex[:6]}"
    puerto = 63899
    _docker("run", "-d", "--name", nombre, "-p", f"{puerto}:6379", "redis:7-alpine")
    url = f"redis://localhost:{puerto}/0"
    for _ in range(30):
        try:
            cliente = Redis.from_url(url, decode_responses=True, socket_connect_timeout=1)
            cliente.ping()
            break
        except Exception:
            time.sleep(0.5)
    else:  # pragma: no cover
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)
        pytest.skip("No se pudo arrancar Redis de pruebas")
    os.environ["REDIS_URL"] = url
    try:
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)


@pytest_asyncio.fixture
async def db(mongo_replica_set: str, redis_limpio: str) -> AsyncIterator[Any]:
    """Base de datos limpia por prueba, con migraciones aplicadas.

    El nombre lleva un identificador aleatorio (ver `MONGO_DB` arriba), así que
    cada corrida crea la suya. Se borra al terminar: si no, cada `pytest` deja
    detrás una base de unos 2 MB en el Mongo del despliegue y con el tiempo se
    acumulan decenas.
    """
    from app.core.config import reload_settings
    from app.core.db import close_connections, get_db
    from app.migrations import runner

    reload_settings()
    await close_connections()
    base = get_db()
    nombre_pruebas = base.name.lower()
    if nombre_pruebas in {'admin', 'config', 'local', 'mesa_ayuda'} or not (
        'test' in nombre_pruebas or 'prueba' in nombre_pruebas
        or nombre_pruebas.startswith('revision_') or '_verif_' in nombre_pruebas
    ):
        await close_connections()
        raise RuntimeError('Las pruebas requieren una base aislada con nombre de pruebas; se rechazo borrar la base configurada.')
    await base.client.drop_database(base.name)
    await runner.ejecutar()
    try:
        yield base
    finally:
        await base.client.drop_database(base.name)
        await close_connections()


@pytest_asyncio.fixture
async def api(db: Any) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP contra la aplicacion completa (middlewares, deps y rutas)."""
    from app.core.config import reload_settings
    from app.main import app as aplicacion

    reload_settings()
    transporte = ASGITransport(app=aplicacion)
    async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
        yield cliente


# ── Datos de apoyo ──────────────────────────────────────────
PASSWORD = "Prueba12345"


async def equipo_para_persona(api, admin, persona_id, *, tipo="CPU"):
    """Prepara un dispositivo realmente asignado, sin saltarse las reglas de alta."""
    persona = (await api.get(f'/api/usuarios/{persona_id}', headers=admin)).json()
    oficina_id = persona.get('oficina_id')
    if not oficina_id:
        zona = await api.post('/api/zonas', headers=admin, json={'nombre': f'Zona prueba {persona_id}'})
        assert zona.status_code == 201, zona.text
        oficina = await api.post('/api/oficinas', headers=admin, json={'nombre': 'Soporte pruebas', 'zona_id': zona.json()['id']})
        assert oficina.status_code == 201, oficina.text
        oficina_id = oficina.json()['id']
        cambio = await api.patch(f'/api/usuarios/{persona_id}', headers=admin, json={'oficina_id': oficina_id})
        assert cambio.status_code == 200, cambio.text
    equipo = await api.post('/api/activos', headers=admin, json={
        'tipo': tipo, 'oficina_id': oficina_id, 'responsable_id': persona_id,
        'nombre_equipo': f'{tipo} de pruebas',
    })
    assert equipo.status_code == 201, equipo.text
    return equipo.json()['id']


async def crear_admin(db, nombre: str = "Administrador Prueba", email: str = "admin@prueba.local") -> dict[str, Any]:
    from app.services import usuario_service

    return await usuario_service.crear(
        {"nombre": nombre, "email": email, "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Instalador", "rol": "sistema"},
        es_primer_admin=True,
    )


async def crear_tecnico(db, nombre: str = "Tecnico Prueba", email: str = "tec@prueba.local", oficina_id=None) -> dict[str, Any]:
    from app.services import usuario_service

    return await usuario_service.crear(
        {
            "nombre": nombre,
            "email": email,
            "password": PASSWORD,
            "rol": "tecnico",
            "oficina_id": oficina_id,
        },
        usuario={"nombre": "Instalador", "rol": "sistema"},
    )


async def crear_usuario(db, nombre: str, email: str, oficina_id) -> dict[str, Any]:
    from app.services import usuario_service

    return await usuario_service.crear(
        {"nombre": nombre, "email": email, "password": PASSWORD, "rol": "usuario", "oficina_id": oficina_id},
        usuario={"nombre": "Instalador", "rol": "sistema"},
    )


async def estructura(db) -> dict[str, Any]:
    """Zona -> oficina -> usuarios lista para reutilizar."""
    from app.services import org_service

    zona_id = await org_service.crear_zona({"nombre": "Zona Complejo"}, usuario={"nombre": "Test", "rol": "sistema"})
    comuna_id = await org_service.crear_oficina({"nombre": "COMUNA", "zona_id": zona_id}, usuario={"nombre": "Test", "rol": "sistema"})
    atm_id = await org_service.crear_oficina({"nombre": "ATM", "zona_id": zona_id}, usuario={"nombre": "Test", "rol": "sistema"})
    return {"zona_id": zona_id, "oficinas": {"COMUNA": comuna_id, "ATM": atm_id}}


@pytest.fixture
def archivo_muestra() -> str:
    from pathlib import Path

    ruta = Path(__file__).parent / "inventario_muestra.xlsx"
    if not ruta.exists():  # pragma: no cover
        pytest.skip("No se encontro el Excel de muestra")
    return str(ruta)


async def token_de(cliente: AsyncClient, correo: str, password: str = PASSWORD) -> dict[str, Any]:
    respuesta = await cliente.post("/api/auth/login", json={"correo": correo, "password": password})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def cabeceras(estado_sesion: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {estado_sesion['access_token']}", "X-CSRF-Token": estado_sesion["csrf_token"]}
