"""Revisa únicamente archivos publicables; nunca muestra valores de secretos."""
from pathlib import Path
import re
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[1]


def revisar():
    resultado = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=RAIZ, check=True, stdout=subprocess.PIPE)
    archivos = sorted(set(p.decode('utf-8') for p in resultado.stdout.split(b'\0') if p))
    secretos = []
    entorno = RAIZ / '.env'
    if entorno.exists():
        for linea in entorno.read_text(encoding='utf-8-sig').splitlines():
            clave, separador, valor = linea.partition('=')
            if separador and not clave.lstrip().startswith('#') and re.search(r'KEY|TOKEN|PASSWORD|SECRET', clave, re.I):
                valor = valor.strip().split(' #', 1)[0].strip().strip('\"\'')
                if len(valor) >= 16 and not valor.startswith('cambia-'):
                    secretos.append(valor.encode())
    patron = re.compile(rb'(?:gsk_[A-Za-z0-9]{32,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    problemas = []
    for nombre in archivos:
        ruta = RAIZ / nombre
        if not ruta.is_file():
            continue
        if (ruta.name.startswith('.env') and ruta.name != '.env.example') or ruta.suffix in {'.pem', '.key', '.p12', '.pfx', '.bson', '.dump'}:
            problemas.append(f'{nombre}: archivo privado')
        if ruta.stat().st_size > 50 * 1024 * 1024:
            problemas.append(f'{nombre}: archivo superior a 50 MB')
            continue
        contenido = ruta.read_bytes()
        if any(secreto in contenido for secreto in secretos):
            problemas.append(f'{nombre}: contiene un secreto del entorno local')
        if patron.search(contenido):
            problemas.append(f'{nombre}: posible credencial o clave privada')
    for problema in problemas:
        print(problema)
    print(f'{len(archivos)} archivos revisados; {len(problemas)} problemas de publicación.')
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(revisar())
