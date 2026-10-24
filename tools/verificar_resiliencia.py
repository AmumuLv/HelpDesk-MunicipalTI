"""Ensayo real, exclusivamente en compose.pruebas.yml; nunca usa producción.

Con la API de pruebas iniciada: python tools/verificar_resiliencia.py --ejecutar
Genera datos ficticios, mide carga, reinicia y restaura en otra base/volumen.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import http.cookiejar
import io
import json
from pathlib import Path
import statistics
import struct
import subprocess
import tempfile
import time
from unittest.mock import patch
import urllib.error
import urllib.request
import uuid
import zipfile
import zlib

import trasladar

RAIZ = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '-f', str(RAIZ / 'compose.pruebas.yml')]


def compose(*args, salida=False):
    r = subprocess.run([*COMPOSE, *args], cwd=RAIZ, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.stdout.decode('utf-8').strip() if salida else ''


def esperar(puerto):
    limite = time.monotonic() + 120
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{puerto}/api/health', timeout=3) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(1)
    raise RuntimeError(f'La API aislada {puerto} no recuperó su salud')


class Cliente:
    def __init__(self, puerto=18100):
        assert puerto in (18100, 18101)
        self.base = f'http://127.0.0.1:{puerto}/api'
        self.headers = {}
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def pedir(self, ruta, cuerpo=None, metodo=None, cabeceras=None, binario=False):
        headers = {**self.headers, **(cabeceras or {})}
        if isinstance(cuerpo, dict):
            cuerpo = json.dumps(cuerpo).encode()
            headers['Content-Type'] = 'application/json'
        solicitud = urllib.request.Request(self.base + ruta, data=cuerpo, method=metodo or ('POST' if cuerpo is not None else 'GET'), headers=headers)
        inicio = time.perf_counter()
        try:
            r = self.opener.open(solicitud, timeout=180)
        except urllib.error.HTTPError as error:
            r = error
        with r:
            contenido = r.read()
            estado = r.status
        valor = contenido if binario else json.loads(contenido or '{}')
        return estado, valor, round((time.perf_counter() - inicio) * 1000, 2)

    def entrar(self, correo, password='Demo12345'):
        estado, datos, _ = self.pedir('/auth/login', {'correo': correo, 'password': password})
        assert estado == 200, f'Login de prueba: HTTP {estado}'
        self.headers = {'Authorization': f"Bearer {datos['access_token']}", 'X-CSRF-Token': datos['csrf_token']}
        return datos

    def subir(self, ruta, nombre, contenido, mime):
        borde = 'prueba-' + uuid.uuid4().hex
        datos = (f'--{borde}\r\nContent-Disposition: form-data; name="archivo"; filename="{nombre}"\r\nContent-Type: {mime}\r\n\r\n').encode() + contenido + f'\r\n--{borde}--\r\n'.encode()
        return self.pedir(ruta, datos, cabeceras={'Content-Type': f'multipart/form-data; boundary={borde}'})


@contextmanager
def traslado_aislado(servicio):
    assert servicio in ('api', 'api-restauracion')

    def ejecutar(*args, salida=False):
        resultado = compose(*(servicio if a == 'api' else a for a in args), salida=salida)
        if args[:1] == ('ps',) and '--services' in args:
            return 'api\nmongo\nredis'
        return resultado

    with patch.object(trasladar, 'ejecutar', ejecutar), patch('builtins.input', return_value='RESTAURAR'):
        yield


def cuantiles(resultados):
    tiempos = sorted(r[2] for r in resultados)
    return {'solicitudes': len(resultados), 'errores': sum(r[0] >= 400 for r in resultados), 'mediana_ms': round(statistics.median(tiempos), 2), 'p95_ms': tiempos[min(len(tiempos)-1, int(len(tiempos)*.95))], 'max_ms': max(tiempos)}


def medir_carga(admin):
    cargas = []
    rutas = ['/tickets?por_pagina=20', '/activos?por_pagina=25', '/usuarios?por_pagina=20']
    for concurrentes in (5, 15, 30):
        print(f'Midiendo {concurrentes} solicitudes concurrentes.', flush=True)
        with ThreadPoolExecutor(max_workers=concurrentes) as grupo:
            respuestas = list(grupo.map(lambda i: admin.pedir(rutas[i % len(rutas)]), range(concurrentes * 10)))
        cargas.append({'concurrencia': concurrentes, **cuantiles(respuestas), 'por_ruta': {ruta: cuantiles(respuestas[i::len(rutas)]) for i, ruta in enumerate(rutas)}})
        assert all(r[0] == 200 for r in respuestas), 'Error HTTP bajo carga'
    return cargas


def ejecutar(solo_carga=False):
    config = json.loads(compose('--profile', 'navegador', 'config', '--format', 'json', salida=True))
    assert config['name'] == 'helpdesk-verificacion'
    assert config['services']['api']['environment']['MONGO_DB'] == 'helpdesk_test_navegador'
    print('Preparando datos ficticios en la instalación aislada.', flush=True)
    esperar(18100)
    admin, usuario = Cliente(), Cliente()
    admin.entrar('admin@demo.local')
    if solo_carga:
        print(json.dumps({'entorno': 'aislado', 'carga': medir_carga(admin)}, indent=2, ensure_ascii=False))
        return
    persona = usuario.entrar('usuario1@demo.local')
    resultado = {'entorno': 'aislado', 'carga': [], 'comprobaciones': []}
    marca = uuid.uuid4().hex
    cuerpo = {'descripcion': f'Prueba ficticia persistencia {marca}'}
    clave = {'Idempotency-Key': str(uuid.uuid4())}
    estado, creado, _ = usuario.pedir('/tickets', cuerpo, cabeceras=clave)
    assert estado == 201
    ticket = creado['ticket']['id']
    adjunto = usuario.subir('/adjuntos', 'ensayo.txt', b'Adjunto ficticio para comprobar restauracion', 'text/plain')
    assert adjunto[0] == 201
    adjunto_id = adjunto[1]['id']
    assert usuario.pedir(f'/tickets/{ticket}/mensajes', {'cuerpo': 'Archivo para el ensayo', 'adjuntos': [adjunto_id]})[0] == 201
    def bloque_png(tipo, datos):
        return struct.pack('!I', len(datos)) + tipo + datos + struct.pack('!I', zlib.crc32(tipo + datos))
    foto = b'\x89PNG\r\n\x1a\n' + bloque_png(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0)) + bloque_png(b'IDAT', zlib.compress(b'\x00\x20\x80\xff')) + bloque_png(b'IEND', b'')
    assert usuario.subir(f"/usuarios/{persona['id']}/foto", 'foto.png', foto, 'image/png')[0] == 200
    hashes = [hashlib.sha256(usuario.pedir(r, binario=True)[1]).hexdigest() for r in (f'/adjuntos/{adjunto_id}', f"/usuarios/{persona['id']}/foto")]
    # Volumen ficticio grande; usa el mismo validador e índices del sistema.
    codigo = """import asyncio
from bson import ObjectId
from app.core.db import get_db,close_connections
from app.core.time import utcnow
async def main():
 db=get_db(); assert db.name=='helpdesk_test_navegador'
 oficina=await db.oficinas.find_one({}); ahora=utcnow()
 await db.activos.insert_many([{'tipo':'Laptop','tipo_normalizado':'laptop','nombre_equipo':f'Equipo ficticio carga {i}','oficina_id':oficina['_id'],'oficina_nombre':oficina['nombre'],'zona_id':oficina.get('zona_id'),'activo':True,'campos_estado':{},'creado_en':ahora,'actualizado_en':ahora,'clave_natural':f'ensayo-carga-{ahora.timestamp()}-{i}','codigo_patrimonial':f'CARGA-{i}'} for i in range(5000)])
 print(await db.activos.count_documents({})); await close_connections()
asyncio.run(main())"""
    resultado['equipos'] = int(compose('exec', '-T', 'api', 'python', '-c', codigo, salida=True))
    with ThreadPoolExecutor(max_workers=10) as grupo:
        altas = list(grupo.map(lambda i: usuario.pedir('/tickets', {'descripcion': f'Incidencia ficticia de carga {marca} {i}'}, cabeceras={'Idempotency-Key': str(uuid.uuid4())}), range(100)))
    assert all(r[0] == 201 for r in altas)
    assert len({r[1]['ticket']['codigo'] for r in altas}) == 100
    resultado['altas'] = cuantiles(altas)
    resultado['carga'] = medir_carga(admin)
    resultado['recursos_observados'] = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.Name}} {{.CPUPerc}} {{.MemUsage}}', compose('ps', '-q', 'api', salida=True), compose('ps', '-q', 'mongo', salida=True)], check=True, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()
    for tipo, formato, firma in [('tickets', 'pdf', b'%PDF'), ('inventario', 'excel', b'PK')]:
        print(f'Comprobando reporte {tipo}, formato {formato}.', flush=True)
        estado, archivo, ms = admin.pedir('/exportaciones', {'tipo': tipo, 'formato': formato, 'filtros': {}})
        assert estado in (200, 201)
        descarga = admin.pedir(f"/exportaciones/{archivo['id']}/descargar", binario=True)
        assert descarga[0] == 200 and descarga[1].startswith(firma)
        if formato == 'excel':
            with zipfile.ZipFile(io.BytesIO(descarga[1])) as libro:
                filas = sum(libro.read(n).count(b'<row ') for n in libro.namelist() if n.startswith('xl/worksheets/sheet'))
                assert filas >= 5000
        resultado['comprobaciones'].append({'reporte': tipo, 'formato': formato, 'generacion_ms': ms, 'bytes': len(descarga[1])})
    print('Reiniciando únicamente MongoDB, Redis y API de pruebas.', flush=True)
    compose('restart', 'mongo', 'redis', 'api')
    esperar(18100)
    usuario.entrar('usuario1@demo.local')
    assert usuario.pedir(f'/tickets/{ticket}')[0] == 200
    assert usuario.pedir('/tickets', cuerpo, cabeceras=clave)[1]['ticket']['id'] == ticket
    resultado['comprobaciones'].append('Reinicio de MongoDB, Redis y API: registros, sesión nueva y envío único conservados')
    print('Preparando restauración en otra base y otro volumen de pruebas.', flush=True)
    compose('--profile', 'restauracion', 'up', '-d', '--wait', 'api-restauracion')
    esperar(18101)
    estado, instalacion, _ = Cliente(18101).pedir('/instalacion')
    assert estado == 200
    assert any(p['clave'] == 'crear_admin' and not p['hecho'] for p in instalacion['pasos'])
    resultado['comprobaciones'].append('Instalación nueva: migraciones y asistente de primer administrador disponibles')
    with tempfile.TemporaryDirectory(prefix='helpdesk-ensayo-') as temporal:
        respaldo = Path(temporal).resolve() / 'ficticio.helpdesk.zip'
        with traslado_aislado('api'):
            trasladar.respaldar(respaldo)
        with zipfile.ZipFile(respaldo) as archivo:
            assert not any('.env' in nombre or nombre.endswith('.key') for nombre in archivo.namelist())
        with traslado_aislado('api-restauracion'):
            trasladar.restaurar(respaldo)
    esperar(18101)
    restaurado = Cliente(18101)
    restaurado.entrar('usuario1@demo.local')
    assert restaurado.pedir(f'/tickets/{ticket}')[0] == 200
    assert restaurado.pedir('/tickets', cuerpo, cabeceras=clave)[1]['ticket']['id'] == ticket
    for ruta, huella in zip((f'/adjuntos/{adjunto_id}', f"/usuarios/{persona['id']}/foto"), hashes):
        estado, contenido, _ = restaurado.pedir(ruta, binario=True)
        assert estado == 200 and hashlib.sha256(contenido).hexdigest() == huella
    resultado['comprobaciones'].append('Restauración real en otra base y volumen: login, ticket, idempotencia, adjunto y foto idénticos')
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ejecutar', action='store_true', required=True)
    parser.add_argument('--solo-carga', action='store_true', help='Repite solo las lecturas sobre los datos ficticios existentes')
    args = parser.parse_args()
    ejecutar(solo_carga=args.solo_carga)
