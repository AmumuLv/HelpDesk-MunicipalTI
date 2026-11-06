"""Inicio y traslado local entre equipos. Requiere Python 3.10+ y Docker Compose."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import zipfile

RAIZ = Path(__file__).resolve().parents[1]


def ejecutar(*args, salida=False):
    resultado = subprocess.run(['docker', 'compose', *args], cwd=RAIZ, stdout=subprocess.PIPE if salida else None, check=True)
    return resultado.stdout.decode().strip() if salida else ''


def preparar_entorno():
    entorno = RAIZ / '.env'
    if not entorno.exists():
        texto = (RAIZ / '.env.example').read_text(encoding='utf-8-sig')
        lineas = [f'SECRET_KEY={secrets.token_urlsafe(48)}' if l.startswith('SECRET_KEY=') else l for l in texto.splitlines()]
        with entorno.open('x', encoding='utf-8', newline='\n') as archivo:
            archivo.write('\n'.join(lineas) + '\n')
        print('.env creado con una clave aleatoria. Las claves del chatbot se configuran aparte.')


def identificadores():
    api = ejecutar('ps', '-q', 'api', salida=True)
    mongo = ejecutar('ps', '-q', 'mongo', salida=True)
    if not api or not mongo:
        raise ValueError('Primero inicia el sistema; API y MongoDB deben estar saludables.')
    datos = ejecutar('exec', '-T', 'api', 'python', '-c',
        "import json; from urllib.parse import urlparse; from app.core.config import settings; print(json.dumps({'db':settings.mongo_db,'local':urlparse(settings.mongo_uri).hostname=='mongo','uploads':settings.upload_dir}))", salida=True)
    config = json.loads(datos)
    if not config['local']:
        raise ValueError('Esta herramienta requiere el MongoDB incluido en Compose; una base externa requiere su propio respaldo.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', config['db']) or not config['uploads'].startswith('/data/') or '..' in config['uploads'].split('/'):
        raise ValueError('La base o el directorio de adjuntos no son compatibles con el traslado seguro.')
    return api, mongo, config


@contextmanager
def sin_escrituras():
    activos = ejecutar('ps', '--status', 'running', '--services', salida=True).splitlines()
    pausar = [s for s in ('api', 'worker') if s in activos]
    try:
        if pausar:
            ejecutar('stop', *pausar)
        yield
    finally:
        if pausar:
            ejecutar('start', *pausar)


def docker(*args):
    subprocess.run(['docker', *args], cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)


def huella(ruta):
    digest = hashlib.sha256()
    with ruta.open('rb') as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
            digest.update(bloque)
    return digest.hexdigest()


def respaldar(destino):
    api, mongo, config = identificadores()
    destino = Path(destino).resolve()
    if not destino.name.lower().endswith('.helpdesk.zip'):
        raise ValueError('Usa la extensión .helpdesk.zip para excluir el respaldo de Git.')
    if destino.exists():
        raise ValueError('El archivo de destino ya existe; elige otro nombre.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal_mongo = '/tmp/traslado-' + secrets.token_hex(8) + '.gz'
    with tempfile.TemporaryDirectory(prefix='helpdesk-') as carpeta:
        base = Path(carpeta).resolve()
        with sin_escrituras():
            try:
                docker('exec', mongo, 'mongodump', '--quiet', '--host=127.0.0.1:27017', '--db=' + config['db'], '--gzip', '--archive=' + temporal_mongo)
                docker('cp', f'{mongo}:{temporal_mongo}', str(base / 'mongo.gz'))
                (base / 'uploads').mkdir()
                docker('cp', f"{api}:{config['uploads']}/.", str(base / 'uploads'))
            finally:
                docker('exec', mongo, 'rm', '-f', temporal_mongo)
        archivos = [p for p in base.rglob('*') if p.is_file()]
        manifiesto = {'formato': 1, 'base': config['db'], 'creado_utc': datetime.now(timezone.utc).isoformat(),
                     'archivos': {p.relative_to(base).as_posix(): huella(p) for p in archivos}}
        # La configuración y sus claves nunca se meten en el archivo trasladable.
        try:
            with zipfile.ZipFile(destino, 'x', zipfile.ZIP_DEFLATED) as zip_out:
                for ruta in archivos:
                    zip_out.write(ruta, ruta.relative_to(base).as_posix())
                zip_out.writestr('manifiesto.json', json.dumps(manifiesto, indent=2))
        except FileExistsError:
            raise
        except Exception:
            destino.unlink(missing_ok=True)
            raise
    print(f'Respaldo creado: {destino}. Contiene datos privados; no lo subas a GitHub.')


def restaurar(origen):
    api, mongo, config = identificadores()
    ocupado = ejecutar('exec', '-T', 'api', 'python', '-c',
        "import asyncio; from app.core.db import get_db,close_connections\nasync def main():\n db=get_db(); total=0\n for coleccion in await db.list_collection_names():\n  if coleccion not in {'_migraciones','catalogos','esquemas_tipos','configuracion','contadores'}: total+=await db[coleccion].count_documents({})\n print(total); await close_connections()\nasyncio.run(main())", salida=True)
    if int(ocupado):
        raise ValueError('La instalación de destino ya contiene datos. La restauración solo admite una instalación nueva y vacía.')
    temporal_mongo = '/tmp/traslado-' + secrets.token_hex(8) + '.gz'
    with tempfile.TemporaryDirectory(prefix='helpdesk-') as carpeta:
        # Windows puede devolver el temporal con un nombre corto (8.3).
        # Comparar ambas rutas resueltas conserva la validación del directorio.
        base = Path(carpeta).resolve()
        with zipfile.ZipFile(origen) as zip_in:
            manifiesto = json.loads(zip_in.read('manifiesto.json'))
            if manifiesto.get('formato') != 1 or 'mongo.gz' not in manifiesto.get('archivos', {}):
                raise ValueError('El archivo no es un respaldo compatible.')
            if not re.fullmatch(r'[A-Za-z0-9_-]+', manifiesto.get('base', '')):
                raise ValueError('El nombre de la base del respaldo no es válido.')
            for nombre, esperada in manifiesto['archivos'].items():
                ruta = (base / nombre).resolve()
                if not ruta.is_relative_to(base) or not (nombre == 'mongo.gz' or nombre.startswith('uploads/')):
                    raise ValueError('El respaldo contiene una ruta no permitida.')
                ruta.parent.mkdir(parents=True, exist_ok=True)
                with zip_in.open(nombre) as entrada, ruta.open('xb') as salida:
                    import shutil
                    shutil.copyfileobj(entrada, salida)
                if huella(ruta) != esperada:
                    raise ValueError('La integridad del respaldo no coincide; no se restauró ningún dato.')
        if input('Se restaurarán datos privados en esta instalación vacía. Escribe RESTAURAR: ').strip() != 'RESTAURAR':
            print('Restauración cancelada.')
            return
        with sin_escrituras():
            try:
                docker('cp', str(base / 'mongo.gz'), f'{mongo}:{temporal_mongo}')
                docker('exec', mongo, 'mongorestore', '--quiet', '--host=127.0.0.1:27017', '--gzip', '--archive=' + temporal_mongo,
                       '--nsFrom=' + manifiesto['base'] + '.*', '--nsTo=' + config['db'] + '.*', '--drop')
                # docker cp works on the stopped API container as well.
                if (base / 'uploads').exists():
                    docker('cp', str(base / 'uploads') + '/.', f"{api}:{config['uploads']}")
                imagen = subprocess.run(['docker', 'inspect', '--format', '{{.Image}}', api], check=True, stdout=subprocess.PIPE).stdout.decode().strip()
                docker('run', '--rm', '--user', 'root', '--volumes-from', api, '--entrypoint', 'chown', imagen, '-R', '10001:10001', config['uploads'])
            finally:
                docker('exec', mongo, 'rm', '-f', temporal_mongo)
    print('Datos restaurados. Inicia sesión de nuevo y comprueba los adjuntos.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='accion', required=True)
    sub.add_parser('iniciar')
    sub.add_parser('respaldar').add_argument('archivo')
    sub.add_parser('restaurar').add_argument('archivo')
    args = parser.parse_args()
    try:
        if args.accion == 'iniciar':
            preparar_entorno()
            ejecutar('up', '-d', '--build', '--wait', '--wait-timeout', '600')
            print('Sistema iniciado. Abre http://localhost o el puerto configurado en .env.')
        elif args.accion == 'respaldar':
            respaldar(args.archivo)
        else:
            restaurar(args.archivo)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f'No se completó la operación: {error}\n')


if __name__ == '__main__':
    main()
