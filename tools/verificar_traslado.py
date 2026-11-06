"""Prueba Windows: instalación vacía y traslado real, solo con datos ficticios.

Requiere Docker e imágenes locales de compose.pruebas.yml y mesa-ayuda-web.
No lee ni cambia .env operativo. No descarga modelos ni llama proveedores de IA.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile

from verificar_resiliencia import Cliente

RAIZ = Path(__file__).resolve().parents[1]
PROYECTOS = ('helpdesk-traslado-origen', 'helpdesk-traslado-destino')


class CuentaPrueba(Cliente):
    def __init__(self, puerto):
        # La implementación de solicitudes no cambia; solo estos dos puertos
        # adicionales pertenecen al ensayo, nunca a los servicios operativos.
        super().__init__()
        assert puerto in (18220, 18221)
        self.base = f'http://127.0.0.1:{puerto}/api'


def dc(archivo, *args):
    return subprocess.run(['docker', 'compose', '-f', str(archivo), *args],
                          cwd=archivo.parent, capture_output=True, check=True,
                          encoding='utf-8').stdout.strip()


def esperar(cliente):
    fin = time.monotonic() + 90
    while time.monotonic() < fin:
        try:
            estado, salud, _ = cliente.pedir('/health')
            if estado == 200 and salud.get('estado') == 'ok' and salud.get('mongo') is True and salud.get('redis') is True:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError('La API ficticia no recuperó su estado saludable.')


def entorno(carpeta, proyecto, puerto, plantilla):
    assert proyecto in PROYECTOS
    carpeta.mkdir()
    (carpeta / 'tools').mkdir()
    shutil.copy2(RAIZ / 'tools/trasladar.ps1', carpeta / 'tools/trasladar.ps1')
    shutil.copy2(RAIZ / '.env.example', carpeta / '.env.example')
    cfg = copy.deepcopy(plantilla)
    cfg['name'] = proyecto
    cfg['services'] = {k: v for k, v in cfg['services'].items()
                       if k in {'mongo', 'mongo-init', 'redis', 'api'}}
    usados = set()
    for servicio in cfg['services'].values():
        servicio.pop('build', None)
        servicio.pop('profiles', None)
        for volumen in servicio.get('volumes', []):
            if volumen.get('type') == 'volume':
                usados.add(volumen['source'])
    cfg['volumes'] = {k: {'name': f'{proyecto}_{k}'} for k in usados}
    cfg['networks'] = {k: {'name': f'{proyecto}_{k}'} for k in cfg.get('networks', {'default': {}})}
    api = cfg['services']['api']
    api['ports'] = [{'host_ip': '127.0.0.1', 'published': str(puerto),
                     'target': 8000, 'protocol': 'tcp'}]
    api['environment']['MONGO_DB'] = proyecto.replace('-', '_')
    api['environment']['SECRET_KEY'] = '${SECRET_KEY:?falta clave de prueba}'
    api['command'] = ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000']
    api['healthcheck'] = {'test': ['CMD', 'curl', '-fsS', 'http://localhost:8000/api/health'],
                          'interval': '2s', 'start_period': '2s', 'timeout': '3s', 'retries': 50}
    # Un navegador puede abrir la interfaz a través del mismo origen que la API.
    cfg['services']['web'] = {
        'image': 'mesa-ayuda-web',
        'depends_on': {'api': {'condition': 'service_healthy'}},
        'ports': [{'host_ip': '127.0.0.1', 'published': str(puerto + 2),
                   'target': 80, 'protocol': 'tcp'}],
    }
    archivo = carpeta / 'compose-prueba.json'
    archivo.write_text(json.dumps(cfg), encoding='utf-8')
    return archivo


def powershell(archivo, accion, *args, correcto=True):
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(archivo.parent / 'tools/trasladar.ps1'),
                        accion, *map(str, args), '-ComposeFile', str(archivo)],
                       cwd=RAIZ.parent, capture_output=True)
    # No imprimir respuestas de login, entornos ni logs completos ante fallos.
    if correcto and r.returncode:
        mensaje = r.stderr.decode('utf-8', errors='replace')[-2500:]
        raise RuntimeError(f'Falló el script de traslado de prueba: {mensaje}')
    return r


def ejecutar():
    if os.name != 'nt':
        raise RuntimeError('Este recorrido comprueba el iniciador de Windows.')
    plantilla = json.loads(subprocess.check_output(
        ['docker', 'compose', '-f', str(RAIZ / 'compose.pruebas.yml'),
         '--profile', 'navegador', 'config', '--format', 'json'], cwd=RAIZ))
    assert plantilla['name'] == 'helpdesk-verificacion'
    assert plantilla['services']['api']['environment']['APP_ENV'] == 'test'
    for nombre in PROYECTOS:
        existentes = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                                              f'label=com.docker.compose.project={nombre}'])
        volumenes = subprocess.check_output(['docker', 'volume', 'ls', '-q', '--filter',
                                             f'label=com.docker.compose.project={nombre}'])
        if existentes.strip() or volumenes.strip():
            raise RuntimeError('Ya existe un ensayo de traslado; no se reutiliza ni elimina.')
    comprobaciones = []
    with tempfile.TemporaryDirectory(prefix='helpdesk-ensayo-traslado-') as temporal:
        base = Path(temporal)
        archivos = []
        try:
            for indice, proyecto in enumerate(PROYECTOS):
                archivo = entorno(base / ('PC origen con espacios' if indice == 0 else 'PC destino con espacios'),
                                  proyecto, 18220 + indice, plantilla)
                archivos.append(archivo)
                powershell(archivo, 'iniciar')
                assert (archivo.parent / '.env').is_file()
            origen, destino = CuentaPrueba(18220), CuentaPrueba(18221)
            esperar(origen); esperar(destino)
            for cliente in (origen, destino):
                estado, vacio, _ = cliente.pedir('/instalacion')
                assert estado == 200 and not vacio['hay_admin']
            comprobaciones.append('Dos instalaciones vacías, sin Git, desde carpetas con espacios y otra ubicación de trabajo')
            clave = 'SoloEnsayo' + uuid.uuid4().hex + '!'
            estado, titular, _ = origen.pedir('/instalacion/administrador', {
                'nombre': 'Titular ficticio traslado', 'email': 'titular@ensayo.local', 'password': clave})
            assert estado == 200 and titular['administrador_principal']
            origen.entrar('titular@ensayo.local', clave)
            comprobaciones.append('Creación del primer administrador protegido e inicio de sesión sin cuenta predeterminada')
            estado, zona, _ = origen.pedir('/zonas', {'nombre': 'Zona ficticia traslado'})
            assert estado == 201, f'Zona ficticia: HTTP {estado}'
            estado, oficina, _ = origen.pedir('/oficinas', {'nombre': 'Oficina ficticia traslado', 'zona_id': zona['id']})
            assert estado == 201, f'Oficina ficticia: HTTP {estado}'
            assert origen.pedir(f"/usuarios/{titular['id']}", {'oficina_id': oficina['id']}, metodo='PATCH')[0] == 200
            estado, equipo, _ = origen.pedir('/activos', {'tipo': 'Laptop', 'nombre_equipo': 'Laptop ficticia traslado',
                'oficina_id': oficina['id'], 'responsable_id': titular['id']})
            assert estado == 201, f'Equipo ficticio: HTTP {estado}'
            estado, creado, _ = origen.pedir('/tickets', {'descripcion': 'Ticket ficticio para traslado', 'activo_id': equipo['id']})
            assert estado == 201, f"Ticket ficticio: HTTP {estado}, {creado.get('mensaje', creado.get('codigo', 'respuesta inesperada'))}"
            ticket = creado['ticket']['id']
            adjunto = origen.subir('/adjuntos', 'ensayo.txt', b'Datos ficticios de traslado', 'text/plain')
            assert adjunto[0] == 201
            adjunto_id = adjunto[1]['id']
            assert origen.pedir(f'/tickets/{ticket}/mensajes', {'cuerpo': 'Adjunto de ensayo', 'adjuntos': [adjunto_id]})[0] == 201
            # PNG válido de un píxel, sin información personal.
            import struct
            import zlib
            def bloque(tipo, contenido):
                return struct.pack('!I', len(contenido)) + tipo + contenido + struct.pack('!I', zlib.crc32(tipo + contenido))
            png = b'\x89PNG\r\n\x1a\n' + bloque(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0)) + bloque(b'IDAT', zlib.compress(b'\x00\x20\x80\xff')) + bloque(b'IEND', b'')
            assert origen.subir(f"/usuarios/{titular['id']}/foto", 'foto.png', png, 'image/png')[0] == 200
            rutas = [f'/adjuntos/{adjunto_id}', f"/usuarios/{titular['id']}/foto"]
            hashes = [hashlib.sha256(origen.pedir(r, binario=True)[1]).hexdigest() for r in rutas]
            respaldo = base / 'datos-ficticios.helpdesk.zip'
            powershell(archivos[0], 'respaldar', respaldo)
            with zipfile.ZipFile(respaldo) as z:
                assert 'mongo.gz' in z.namelist()
                assert not any(n.endswith('.env') or n.endswith('.key') for n in z.namelist())
            comprobaciones.append('Copia privada ficticia con base, foto y adjunto, sin archivo de entorno')
            # Prueba el rechazo antes de escribir y después la recuperación completa.
            corrupto = base / 'corrupto.helpdesk.zip'
            with zipfile.ZipFile(respaldo) as z, zipfile.ZipFile(corrupto, 'w') as salida:
                for n in z.namelist():
                    salida.writestr(n, b'alterado' if n == 'mongo.gz' else z.read(n))
            rechazo = powershell(archivos[1], 'restaurar', corrupto, '-ConfirmarRestauracion', correcto=False)
            assert rechazo.returncode != 0
            assert not destino.pedir('/instalacion')[1]['hay_admin']
            powershell(archivos[1], 'restaurar', respaldo, '-ConfirmarRestauracion')
            esperar(destino)
            destino.entrar('titular@ensayo.local', clave)
            assert destino.pedir('/auth/sesion')[1]['administrador_principal']
            assert destino.pedir(f'/tickets/{ticket}')[0] == 200
            assert destino.pedir(f"/activos/{equipo['id']}")[0] == 200
            assert destino.pedir(f"/oficinas/{oficina['id']}")[0] == 200
            for ruta, huella in zip(rutas, hashes):
                estado, contenido, _ = destino.pedir(ruta, binario=True)
                assert estado == 200 and hashlib.sha256(contenido).hexdigest() == huella
            comprobaciones.append('Rechazo de archivo alterado; restauración con login, rol principal, ticket, foto y adjunto idénticos')
            ocupado = powershell(archivos[1], 'restaurar', respaldo, '-ConfirmarRestauracion', correcto=False)
            assert ocupado.returncode != 0
            comprobaciones.append('Rechazo de restauración sobre una instalación que ya contiene datos')
            antes = hashlib.sha256((archivos[1].parent / '.env').read_bytes()).digest()
            powershell(archivos[1], 'iniciar')
            assert hashlib.sha256((archivos[1].parent / '.env').read_bytes()).digest() == antes
            esperar(destino)
            destino.entrar('titular@ensayo.local', clave)
            assert destino.pedir(f'/tickets/{ticket}')[0] == 200
            comprobaciones.append('Segundo arranque conserva entorno y datos; destino separado del origen')
            for punto in comprobaciones:
                print('OK:', punto, flush=True)
        finally:
            errores_limpieza = []
            for archivo in archivos:
                cfg = json.loads(archivo.read_text(encoding='utf-8'))
                assert cfg['name'] in PROYECTOS
                assert all(not v.get('external') and v['name'].startswith(cfg['name'] + '_')
                           for v in cfg['volumes'].values())
                assert all(not v.get('external') and v['name'].startswith(cfg['name'] + '_')
                           for v in cfg['networks'].values())
                try:
                    dc(archivo, 'down', '-v')
                except subprocess.CalledProcessError:
                    errores_limpieza.append(cfg['name'])
            if errores_limpieza:
                raise RuntimeError('No se pudo limpiar el ensayo: ' + ', '.join(errores_limpieza))
    print('Ensayo finalizado: contenedores, volúmenes y archivos ficticios retirados.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ejecutar', action='store_true', required=True)
    parser.parse_args()
    ejecutar()
