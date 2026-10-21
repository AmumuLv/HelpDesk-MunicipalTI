"""Ejecuta las comprobaciones reales contra una API y base aisladas."""
import asyncio
import os
import subprocess
import sys
import time
import uuid

os.environ['MONGO_DB'] = 'mesa_ayuda_revision_' + uuid.uuid4().hex[:10]
os.environ['APP_ENV'] = 'test'
os.environ['VERIFICAR_API'] = 'http://127.0.0.1:8100/api'
os.environ['VERIFICAR_HOST'] = 'host.docker.internal'

async def preparar():
    from app.migrations.runner import ejecutar
    from app.services.usuario_service import crear
    from app.core.db import close_connections
    await ejecutar()
    await crear({'nombre': 'Administrador verificación', 'email': 'admin@demo.local', 'password': 'Demo12345', 'rol': 'administrador'}, usuario={'nombre': 'Instalador', 'rol': 'sistema'}, es_primer_admin=True)
    await close_connections()

asyncio.run(preparar())
proceso = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8100'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
try:
    import httpx
    for _ in range(60):
        try:
            if httpx.get(os.environ['VERIFICAR_API'] + '/health', timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('La API aislada no arrancó')
    errores = []
    for modulo in ('humo', 'verificar_web', 'verificar_contratos'):
        resultado = subprocess.run([sys.executable, '-m', 'app.scripts.' + modulo])
        if resultado.returncode:
            errores.append(modulo)
    if errores:
        raise RuntimeError('Fallaron: ' + ', '.join(errores))
finally:
    proceso.terminate()
    proceso.wait(timeout=20)
    async def limpiar():
        from app.core.db import get_db, close_connections
        db = get_db()
        await db.client.drop_database(db.name)
        await close_connections()
    asyncio.run(limpiar())
