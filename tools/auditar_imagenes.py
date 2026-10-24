"""Audita imágenes locales con Docker Scout sin subirlas ni guardar informes."""
import argparse
import json
import subprocess


def revisar(imagen):
    if imagen.startswith('-') or '://' in imagen:
        raise ValueError('Indica un nombre de imagen local.')
    inspeccion = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', imagen], capture_output=True, text=True)
    if inspeccion.returncode:
        return {'imagen': imagen, 'sin_verificar': True, 'motivo': 'La imagen no existe localmente.'}
    identificador = inspeccion.stdout.strip()
    proceso = subprocess.run(
        ['docker', 'scout', 'cves', 'local://' + identificador, '--only-severity', 'critical,high', '--format', 'sarif'],
        capture_output=True, text=True, encoding='utf-8',
    )
    if proceso.returncode != 0:
        return {'imagen': imagen, 'sin_verificar': True, 'estado': proceso.returncode, 'motivo': proceso.stderr[-500:]}
    informe = json.loads(proceso.stdout)
    avisos = []
    for ejecucion in informe.get('runs', []):
        reglas = {r['id']: r for r in ejecucion['tool']['driver'].get('rules', [])}
        for resultado in ejecucion.get('results', []):
            regla = reglas.get(resultado['ruleId'], {})
            propiedades = regla.get('properties', {})
            avisos.append({
                'id': resultado['ruleId'], 'severidad': propiedades.get('cvssV3_severity'),
                'paquetes': propiedades.get('purls', []), 'correccion': propiedades.get('fixed_version'),
            })
    # Un mismo CVE puede afectar a varios paquetes; se conservan ambos avisos.
    return {'imagen': imagen, 'identificador': identificador, 'avisos': avisos, 'total': len(avisos)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('imagenes', nargs='+')
    args = parser.parse_args()
    fallos = False
    for imagen in args.imagenes:
        dato = revisar(imagen)
        print(json.dumps(dato, ensure_ascii=True), flush=True)
        fallos |= bool(dato.get('sin_verificar') or dato.get('total'))
    raise SystemExit(1 if fallos else 0)
