"""Carga sostenida exclusivamente contra la instalación ficticia de pruebas."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import threading
import time
import uuid

from verificar_resiliencia import Cliente, compose, esperar


def ejecutar(minutos, clientes):
    config = json.loads(compose('--profile', 'navegador', 'config', '--format', 'json', salida=True))
    assert config['name'] == 'helpdesk-verificacion'
    assert config['services']['api']['environment']['MONGO_DB'] == 'helpdesk_test_navegador'
    esperar(18100)
    inicio = time.monotonic()
    fin = inicio + minutos * 60
    bloqueo = threading.Lock()
    tiempos, fallos, muestras = [], [], []
    renovaciones = 0
    altas = 0

    def trabajador(indice):
        nonlocal renovaciones, altas
        cliente = Cliente()
        correo = ['admin@demo.local', 'jorge.castillo@municipalidad.gob.pe', 'usuario1@demo.local'][indice % 3]
        cliente.entrar(correo)
        renovar = time.monotonic() + 600
        siguiente_alta = time.monotonic() + 60
        contador = 0
        rutas = ['/tickets?por_pagina=20', '/auth/sesion'] if indice % 3 == 2 else ['/tickets?por_pagina=20', '/activos?por_pagina=25', '/usuarios?por_pagina=20', '/auth/sesion']
        while time.monotonic() < fin:
            try:
                if time.monotonic() >= renovar:
                    estado, datos, ms = cliente.pedir('/auth/refresh', {}, metodo='POST')
                    if estado != 200:
                        raise RuntimeError(f'Renovación HTTP {estado}')
                    cliente.headers = {'Authorization': f"Bearer {datos['access_token']}", 'X-CSRF-Token': datos['csrf_token']}
                    renovar = time.monotonic() + 600
                    with bloqueo:
                        renovaciones += 1
                ruta = rutas[contador % len(rutas)]
                estado, _, ms = cliente.pedir(ruta)
                with bloqueo:
                    tiempos.append(ms)
                    if estado != 200:
                        fallos.append({'cliente': indice, 'ruta': ruta, 'estado': estado})
                if indice == 2 and time.monotonic() >= siguiente_alta:
                    estado, _, ms = cliente.pedir('/tickets', {'descripcion': 'Incidencia ficticia de carga sostenida ' + uuid.uuid4().hex}, cabeceras={'Idempotency-Key': str(uuid.uuid4())})
                    with bloqueo:
                        tiempos.append(ms)
                        if estado == 201:
                            altas += 1
                        else:
                            fallos.append({'ruta': '/tickets', 'estado': estado})
                    siguiente_alta = time.monotonic() + 60
            except Exception as error:
                with bloqueo:
                    fallos.append({'cliente': indice, 'tipo': type(error).__name__})
            contador += 1
            time.sleep(1)

    def resumen():
        with bloqueo:
            ordenados = sorted(tiempos)
            return {'minutos': round((time.monotonic() - inicio) / 60, 2), 'solicitudes': len(ordenados), 'errores': len(fallos), 'p95_ms': ordenados[min(len(ordenados)-1, int(len(ordenados)*.95))] if ordenados else None, 'altas': altas, 'renovaciones': renovaciones}

    with ThreadPoolExecutor(max_workers=clientes) as grupo:
        tareas = [grupo.submit(trabajador, i) for i in range(clientes)]
        while not all(t.done() for t in tareas):
            time.sleep(min(30, max(1, fin - time.monotonic())))
            recursos = compose('ps', '-q', 'api', salida=True)
            salida = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', recursos], check=True, capture_output=True, text=True)
            dato = json.loads(salida.stdout)
            muestra = {**resumen(), 'memoria_api': dato['MemUsage'], 'cpu_api': dato['CPUPerc']}
            muestras.append(muestra)
            print(json.dumps(muestra), flush=True)
        for tarea in tareas:
            tarea.result()
    print(json.dumps({'resultado': resumen(), 'fallos': fallos[:20], 'muestras': muestras}, indent=2), flush=True)
    return not fallos


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ejecutar', action='store_true', required=True)
    p.add_argument('--minutos', type=int, default=30, choices=range(1, 121))
    p.add_argument('--clientes', type=int, default=6, choices=range(3, 10))
    a = p.parse_args()
    raise SystemExit(0 if ejecutar(a.minutos, a.clientes) else 1)
