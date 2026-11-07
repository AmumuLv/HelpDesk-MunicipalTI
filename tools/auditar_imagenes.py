"""Audita imágenes locales con Docker Scout sin subirlas ni guardar informes."""
import argparse
import json
import os
import signal
import subprocess


def _ejecutar(comando, *, timeout):
    """Acota también los plugins descendientes de Docker en Windows."""
    opciones = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    proceso = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8', **opciones)
    try:
        salida, errores = proceso.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # run(timeout=...) solo mata docker.exe; Scout puede quedar vivo con las
        # tuberías abiertas y mantener bloqueado communicate indefinidamente.
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proceso.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            else:
                os.killpg(proceso.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if proceso.poll() is None:
            proceso.kill()
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        try:
            proceso.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(comando, proceso.returncode, salida, errores)


def revisar(imagen, *, ejecutable=None, tiempo_maximo=300):
    if imagen.startswith('-') or '://' in imagen:
        raise ValueError('Indica un nombre de imagen local.')
    try:
        inspeccion = _ejecutar(['docker', 'image', 'inspect', '--format', '{{.Id}}', imagen], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {'imagen': imagen, 'sin_verificar': True, 'motivo': 'Docker no responde o no está disponible.'}
    if inspeccion.returncode:
        return {'imagen': imagen, 'sin_verificar': True, 'motivo': 'La imagen no existe localmente.'}
    identificador = inspeccion.stdout.strip()
    try:
        proceso = _ejecutar(
            ([str(ejecutable)] if ejecutable else ['docker', 'scout']) +
            ['cves', 'local://' + identificador, '--only-severity', 'critical,high', '--format', 'sarif'],
            timeout=tiempo_maximo,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {'imagen': imagen, 'identificador': identificador, 'sin_verificar': True,
                'motivo': 'El analizador no terminó o no está disponible.'}
    if proceso.returncode != 0:
        return {'imagen': imagen, 'sin_verificar': True, 'estado': proceso.returncode, 'motivo': proceso.stderr[-500:]}
    try:
        informe = json.loads(proceso.stdout)
        ejecuciones = informe['runs']
        if not isinstance(ejecuciones, list) or not ejecuciones:
            raise ValueError('No hay ejecuciones verificables.')
        avisos = []
        for ejecucion in ejecuciones:
            driver = ejecucion['tool']['driver']
            resultados = ejecucion['results']
            if not isinstance(driver, dict) or not driver.get('name') or not isinstance(resultados, list):
                raise ValueError('Informe incompleto.')
            if any(i.get('executionSuccessful') is False for i in ejecucion.get('invocations', [])):
                raise ValueError('La ejecución del analizador falló.')
            reglas = {r['id']: r for r in driver.get('rules', [])}
            for resultado in resultados:
                regla = reglas.get(resultado['ruleId'], {})
                propiedades = regla.get('properties', {})
                avisos.append({
                    'id': resultado['ruleId'], 'severidad': propiedades.get('cvssV3_severity'),
                    'paquetes': propiedades.get('purls', []), 'correccion': propiedades.get('fixed_version'),
                })
    except (ValueError, KeyError, TypeError, AttributeError):
        return {'imagen': imagen, 'identificador': identificador, 'sin_verificar': True,
                'motivo': 'El analizador devolvió un informe inválido, incompleto o fallido.'}
    # Un mismo CVE puede afectar a varios paquetes; se conservan ambos avisos.
    return {'imagen': imagen, 'identificador': identificador, 'avisos': avisos, 'total': len(avisos)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('imagenes', nargs='+')
    parser.add_argument('--scout-ejecutable', type=str, help='Copia local de Scout verificada; por defecto usa el plugin Docker instalado')
    parser.add_argument('--tiempo-maximo', type=int, default=300, help='Segundos por imagen, entre 30 y 1800; predeterminado: 300')
    args = parser.parse_args()
    if not 30 <= args.tiempo_maximo <= 1800:
        parser.error('--tiempo-maximo debe estar entre 30 y 1800 segundos.')
    if args.scout_ejecutable:
        from pathlib import Path
        args.scout_ejecutable = Path(args.scout_ejecutable).resolve()
        if not args.scout_ejecutable.is_file():
            parser.error('No existe el ejecutable de Scout indicado.')
    fallos = False
    for imagen in args.imagenes:
        dato = revisar(imagen, ejecutable=args.scout_ejecutable, tiempo_maximo=args.tiempo_maximo)
        print(json.dumps(dato, ensure_ascii=True), flush=True)
        fallos |= bool(dato.get('sin_verificar') or dato.get('total'))
    raise SystemExit(1 if fallos else 0)
