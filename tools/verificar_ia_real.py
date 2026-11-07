"""Usa la clave configurada sin imprimirla ni guardarla en archivos o argumentos."""
import argparse
import json
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ejecutar', action='store_true', required=True)
    p.add_argument('--red-host', action='store_true', help='Diagnóstico alternativo si la red puente de Docker no tiene salida HTTPS')
    p.add_argument('--casos', nargs='+', choices=['orientacion', 'datos_reales', 'sin_escrituras', 'secretos'])
    p.add_argument('--diagnostico', action='store_true', help='Muestra errores del proveedor redactados, solo en la sonda ficticia')
    args = p.parse_args()
    codigo = "import json;from app.core.config import settings as s;print(json.dumps({'proveedor':s.chatbot_provider,'modelo':s.groq_model if s.chatbot_provider=='groq' else s.gemini_model,'clave':s.groq_api_key if s.chatbot_provider=='groq' else s.gemini_api_key}))"
    configuracion = subprocess.run(['docker', 'compose', 'exec', '-T', 'api', 'python', '-c', codigo], cwd=RAIZ, capture_output=True, check=True).stdout
    if not json.loads(configuracion).get('clave'):
        raise SystemExit('Falta configurar la clave del proveedor en el servidor.')
    if args.casos:
        configuracion = json.dumps({**json.loads(configuracion), 'casos': args.casos}).encode()
    if args.diagnostico:
        configuracion = json.dumps({**json.loads(configuracion), 'diagnostico': True}).encode()
    comando = ['docker', 'compose', '-f', 'compose.pruebas.yml', 'exec', '-T', 'api', 'python', '-m', 'app.scripts.verificar_ia_real']
    if args.red_host:
        base = ['docker', 'compose', '-f', 'compose.pruebas.yml']
        def ip(servicio):
            contenedor = subprocess.check_output([*base, 'ps', '-q', servicio], cwd=RAIZ).decode().strip()
            redes = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .NetworkSettings.Networks}}', contenedor]))
            assert set(redes) == {'helpdesk-verificacion_default'}
            return redes['helpdesk-verificacion_default']['IPAddress']
        comando = ['docker', 'run', '--rm', '-i', '--network', 'host', '-e', 'APP_ENV=test', '-e', 'SECRET_KEY=solo-pruebas-aisladas-no-utilizar-en-produccion-1234567890', '-e', 'MONGO_DB=helpdesk_test_navegador', '-e', f'MONGO_URI=mongodb://{ip("mongo")}:27017/?directConnection=true&replicaSet=rs0', '-e', f'REDIS_URL=redis://{ip("redis")}:6379/5', '--mount', f'type=bind,source={RAIZ / "backend"},target=/app,readonly', '--entrypoint', 'python', 'helpdesk-pruebas-api', '-m', 'app.scripts.verificar_ia_real']
        print('Diagnóstico con red del host; no certifica la conectividad de la red puente.', flush=True)
    resultado = subprocess.run(comando, cwd=RAIZ, input=configuracion)
    raise SystemExit(resultado.returncode)
