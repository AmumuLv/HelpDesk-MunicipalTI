"""HTTPS, cookies, CSP y revocación WebSocket en el perfil aislado seguridad."""
import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from verificar_resiliencia import compose, RAIZ


PREPARAR_CUENTA_SEGURIDAD = """import asyncio
from app.core.db import get_db,close_connections
from app.services import usuario_service
async def main():
 try:
  db=get_db(); assert db.name=='helpdesk_test_navegador'
  if not await db.usuarios.find_one({'email':'seguridad.admin@demo.local'}):
   principal=await db.usuarios.find_one({'rol':'administrador','administrador_principal':True,'activo':True,'archivado':{'$ne':True}})
   if principal is None:
    raise RuntimeError('Falta el administrador principal de la instalación ficticia. Prepara primero la base de navegador.')
   await usuario_service.crear({'nombre':'Administrador ficticio de seguridad','email':'seguridad.admin@demo.local','rol':'administrador','password':'Demo12345'},usuario=principal)
 finally:
  await close_connections()
asyncio.run(main())"""


def ejecutar():
    api = json.loads(compose('--profile', 'seguridad', 'config', '--format', 'json', salida=True))['services']['api-seguridad']
    assert api['environment']['MONGO_DB'] == 'helpdesk_test_navegador'
    compose('exec', '-T', 'api-seguridad', 'python', '-c', PREPARAR_CUENTA_SEGURIDAD)
    contenedor = compose('ps', '-q', 'proxy-seguridad', salida=True)
    assert contenedor
    with tempfile.TemporaryDirectory(prefix='helpdesk-tls-ficticio-') as carpeta:
        ca = Path(carpeta) / 'ca.crt'
        for _ in range(30):
            certificado_ca = subprocess.run(['docker', 'compose', '-f', str(RAIZ/'compose.pruebas.yml'), 'exec', '-T', 'proxy-seguridad', 'cat', '/data/caddy/pki/authorities/local/root.crt'], capture_output=True)
            if certificado_ca.returncode == 0:
                ca.write_bytes(certificado_ca.stdout)
                break
            time.sleep(1)
        else:
            raise RuntimeError('La CA de pruebas no está disponible')
        contexto = ssl.create_default_context(cafile=str(ca))
        assert contexto.check_hostname and contexto.verify_mode == ssl.CERT_REQUIRED
        cookies = http.cookiejar.CookieJar()
        cliente = urllib.request.build_opener(urllib.request.HTTPSHandler(context=contexto), urllib.request.HTTPCookieProcessor(cookies))
        base = 'https://localhost:18111'

        def pedir(ruta, cuerpo=None, headers=None, metodo=None):
            cabeceras = dict(headers or {})
            if cuerpo is not None:
                cuerpo = json.dumps(cuerpo).encode()
                cabeceras['Content-Type'] = 'application/json'
            req = urllib.request.Request(base+ruta, data=cuerpo, headers=cabeceras, method=metodo)
            try:
                r = cliente.open(req, timeout=25)
            except urllib.error.HTTPError as e:
                r = e
            with r:
                return r.status, r.headers, r.read()

        estado, h, html = pedir('/')
        assert estado == 200 and h['X-Frame-Options'] == 'DENY' and h['X-Content-Type-Options'] == 'nosniff'
        assert "script-src 'self'" in h['Content-Security-Policy'] and "object-src 'none'" in h['Content-Security-Policy']
        assert h['Strict-Transport-Security'].startswith('max-age=31536000')
        assert b'/tema-inicial.js' in html and not re.search(rb'<script>(.*?)</script>', html, re.S)
        recurso = re.search(rb'src="(/assets/[^" ]+\.js)"', html).group(1).decode()
        assert pedir(recurso)[1]['X-Content-Type-Options'] == 'nosniff'
        for ruta in ('/.env', '/.git/config', '/api/docs', '/api/redoc', '/api/openapi.json'):
            assert pedir(ruta)[0] == 404, ruta
        assert pedir('/api/tickets')[0] == 401
        estado, cors, _ = pedir('/api/tickets', headers={'Origin': 'https://sitio-ajeno.invalid', 'Access-Control-Request-Method': 'POST'}, metodo='OPTIONS')
        assert estado == 400 and not cors.get('Access-Control-Allow-Origin')
        estado, h, datos = pedir('/api/auth/login', {'correo': 'seguridad.admin@demo.local', 'password': 'Demo12345', 'acceso': 'ti'})
        assert estado == 200
        sesion = json.loads(datos)
        refresco = next(c for c in cookies if c.name == 'ma_refresh')
        assert refresco.secure and refresco.has_nonstandard_attr('HttpOnly')
        assert next(c for c in cookies if c.name == 'ma_csrf').secure
        bearer = {'Authorization': f"Bearer {sesion['access_token']}"}
        assert pedir('/api/tickets', {'descripcion': 'No debe guardarse sin CSRF'}, headers=bearer)[0] == 403
        _, _, directorio = pedir('/api/usuarios', headers=bearer)
        assert 'password_hash' not in json.loads(directorio).get('items', [{}])[0]
        with cliente.open(base+'/healthz') as r:
            certificado = r.fp.raw._sock.getpeercert(binary_form=True)
        datos_navegador = {'token': sesion['access_token'], 'certificado': base64.b64encode(certificado).decode(), 'cookies': [{'name': c.name, 'value': c.value, 'domain': 'localhost', 'path': '/', 'secure': True, 'httpOnly': c.has_nonstandard_attr('HttpOnly'), 'sameSite': 'Lax'} for c in cookies]}
        try:
            subprocess.run(['node', str(RAIZ/'tools/probar_interfaz_segura.cjs')], input=json.dumps(datos_navegador).encode(), cwd=RAIZ, check=True)
        except subprocess.CalledProcessError:
            pedir('/api/auth/logout', {}, headers=bearer)
            raise
        codigo = """require('node:dns').setDefaultResultOrder('ipv4first');const rl=require('node:readline').createInterface({input:process.stdin});rl.once('line',l=>{const d=JSON.parse(l);const w=new WebSocket('wss://localhost:18111/api/ws/notificaciones');let listo=false;const t=setTimeout(()=>{console.log('timeout');process.exit(1)},25000);w.onopen=()=>w.send(JSON.stringify({tipo:'autenticar',token:d.token}));w.onmessage=e=>{if(JSON.parse(e.data).tipo==='sincronizacion'&&!listo){listo=true;console.log('conectado')}};w.onclose=e=>{clearTimeout(t);console.log(e.code);process.exit(listo&&e.code===4401?0:1)};w.onerror=e=>{clearTimeout(t);console.log('error_socket:'+String(e.error?.message||e.message||'sin_detalle'));process.exit(1)}})"""
        proceso = subprocess.Popen(['node', '--experimental-websocket', '-e', codigo], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env={**os.environ, 'NODE_EXTRA_CA_CERTS': str(ca)})
        try:
            proceso.stdin.write(json.dumps({'token': sesion['access_token']})+'\n')
            proceso.stdin.flush()
            saludo = proceso.stdout.readline().strip()
            if not saludo:
                proceso.wait(timeout=5)
                detalle = proceso.stderr.read().replace(sesion['access_token'], '[reservado]')
                raise RuntimeError('Fallo del cliente WebSocket de prueba: ' + detalle[:1500])
            assert saludo == 'conectado', saludo
            assert pedir('/api/auth/logout', {}, headers=bearer)[0] == 200
            salida = proceso.stdout.readline().strip()
            assert proceso.wait(timeout=30) == 0 and salida == '4401'
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait()
            proceso.stdin.close()
            proceso.stdout.close()
            proceso.stderr.close()
        assert pedir('/api/auth/sesion', headers=bearer)[0] == 401
        assert pedir('/healthz?token=FICTICIO_NO_DEBE_REGISTRARSE')[0] == 200
        time.sleep(1)
        logs = compose('exec', '-T', 'proxy-seguridad', 'cat', '/data/access.log', salida=True)
        assert 'FICTICIO_NO_DEBE_REGISTRARSE' not in logs and sesion['access_token'] not in logs
        print(json.dumps({'https': 'cadena y nombre verificados con CA local de prueba', 'cookies_secure_httponly': True, 'csp': True, 'cors_ajeno': 'rechazado', 'documentacion_publica': 'cerrada', 'archivos_privados': 'inaccesibles', 'csrf': 'exigido', 'logout_http': 'invalida token', 'logout_websocket': 'cierra antes de entregar eventos', 'tokens_en_log_proxy': False}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ejecutar', action='store_true', required=True)
    p.parse_args()
    ejecutar()
