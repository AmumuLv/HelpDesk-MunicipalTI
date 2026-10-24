"""Barreras de publicación: autenticación del socket y límites no falsificables."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.api import deps
from app.api.routes import auth, tiempo_real
from app.core.errors import NoAutorizado


@pytest.mark.parametrize('dato', [{}, [], {'tipo': 'autenticar', 'token': ''}, {'tipo': 'autenticar', 'token': 'x'*4097}, {'tipo': 'mensaje', 'token': 'ficticio'}])
async def test_socket_rechaza_primer_mensaje_invalido(dato, monkeypatch):
    socket = AsyncMock()
    socket.receive_json.return_value = dato
    validar = AsyncMock()
    monkeypatch.setattr(tiempo_real.auth_service, 'payload_sesion', validar)
    assert await tiempo_real._autenticar(socket) is None
    socket.close.assert_awaited_once()
    validar.assert_not_awaited()


async def test_socket_autentica_en_mensaje_y_no_en_url(monkeypatch):
    socket = AsyncMock()
    socket.receive_json.return_value = {'tipo': 'autenticar', 'token': 'token-ficticio'}
    validar = AsyncMock(return_value={'usuario': {'nombre': 'Prueba'}})
    monkeypatch.setattr(tiempo_real.auth_service, 'payload_sesion', validar)
    assert await tiempo_real._autenticar(socket) == {'nombre': 'Prueba'}
    validar.assert_awaited_once_with('token-ficticio')
    socket.close.assert_not_awaited()


async def test_socket_sin_autenticacion_no_espera_indefinidamente():
    socket = AsyncMock()
    socket.receive_json.side_effect = asyncio.TimeoutError
    assert await tiempo_real._autenticar(socket) is None
    socket.close.assert_awaited_once()


async def test_socket_cierra_antes_de_emitir_si_se_revoca_la_sesion(monkeypatch):
    socket = AsyncMock()
    validar = AsyncMock(side_effect=[{'usuario': {'rol': 'usuario'}}, NoAutorizado('Revocado')])
    monkeypatch.setattr(tiempo_real.auth_service, 'payload_sesion', validar)
    conexion = tiempo_real.ConexionSocket(socket, 'acceso-ficticio')
    assert await conexion.autorizado()
    assert not await conexion.autorizado()
    socket.close.assert_awaited_once_with(code=4401, reason='Sesion o acceso no valido')


def test_cabeceras_del_cliente_no_suplantan_ip_para_limites():
    request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [(b'x-real-ip', b'1.2.3.4'), (b'x-forwarded-for', b'5.6.7.8')], 'client': ('127.0.0.1', 1234)})
    assert deps._ip(request) == auth._ip(request) == '127.0.0.1'


async def test_no_se_elude_limite_login_cambiando_cabeceras(db, api, monkeypatch):
    monkeypatch.setattr(deps.settings, 'rate_limit_per_minute', 120)
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    import uuid
    ip = '2001:db8:' + ':'.join(uuid.uuid4().hex[i:i+4] for i in range(0,24,4))
    estados = []
    async with AsyncClient(transport=ASGITransport(app=app, client=(ip, 1234)), base_url='http://test') as cliente:
        for i in range(21):
            r = await cliente.post('/api/auth/login', headers={'X-Real-IP': f'10.1.0.{i}', 'X-Forwarded-For': f'10.2.0.{i}'}, json={'correo': f'inexistente{i}@prueba.local', 'password': 'PruebaFicticia123'})
            estados.append(r.status_code)
    assert 401 in estados
    assert estados[-1] == 429


@pytest.mark.parametrize('url', ['http://127.0.0.1:9/imagen.png', 'file:///etc/passwd'])
def test_pdf_no_descarga_recursos_ni_abre_archivos_por_url(monkeypatch, url):
    from app.services.pdf_service import _render
    from urllib.request import OpenerDirector
    from unittest.mock import Mock
    acceso = Mock(side_effect=AssertionError('No se debe acceder al recurso'))
    monkeypatch.setattr(OpenerDirector, 'open', acceso)
    pdf = _render(f'<p>Reporte sin recursos externos</p><img src="{url}">')
    assert pdf.startswith(b'%PDF')
    acceso.assert_not_called()
