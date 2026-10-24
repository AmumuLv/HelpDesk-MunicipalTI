"""Contrasta versiones Python instaladas con los avisos públicos de PyPI."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import subprocess
import urllib.request


def revisar(paquete):
    nombre, version = paquete['name'], paquete['version']
    try:
        with urllib.request.urlopen(f'https://pypi.org/pypi/{nombre}/{version}/json', timeout=12) as r:
            datos = json.load(r)
        return {'paquete': nombre, 'version': version, 'avisos': [{k: v for k, v in aviso.items() if k in {'id', 'aliases', 'fixed_in', 'link', 'withdrawn'}} for aviso in datos.get('vulnerabilities', []) if not aviso.get('withdrawn')]}
    except Exception as error:
        return {'paquete': nombre, 'version': version, 'sin_verificar': type(error).__name__}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--imagen', help='Verifica una imagen reconstruida antes de desplegarla')
    args = parser.parse_args()
    comando = ['docker', 'run', '--rm', '--entrypoint', 'python', args.imagen] if args.imagen else ['docker', 'compose', 'exec', '-T', 'api', 'python']
    codigo = "import importlib.metadata as m,json; print(json.dumps([{'name':d.metadata['Name'],'version':d.version} for d in m.distributions()]))"
    paquetes = json.loads(subprocess.check_output([*comando, '-c', codigo]))
    with ThreadPoolExecutor(max_workers=6) as grupo:
        resultados = list(grupo.map(revisar, paquetes))
    problemas = [r for r in resultados if r.get('avisos')]
    incompletos = [r for r in resultados if r.get('sin_verificar')]
    print(json.dumps({'revisados': len(paquetes)-len(incompletos), 'sin_verificar': incompletos, 'vulnerabilidades': problemas}, indent=2))
    raise SystemExit(1 if problemas or incompletos else 0)
