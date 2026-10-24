"""Archivos inválidos y nombres hostiles, sin crear archivos en disco."""
import pytest

from app.core.config import settings
from app.core.errors import Validacion
from app.services import adjuntos_service


@pytest.mark.parametrize('nombre', ['programa.exe', 'comando.ps1', 'inicio.bat', 'pagina.html', 'vector.svg', 'archivo.js'])
def test_extensiones_ejecutables_o_activas_se_rechazan(nombre):
    with pytest.raises(Validacion):
        adjuntos_service.validar(nombre, 'text/plain', 10, b'contenido')


@pytest.mark.parametrize('nombre', ['../../prueba.txt', r'C:\Users\otra\prueba.txt', '/tmp/prueba.txt'])
def test_nombre_no_contiene_rutas_del_cliente(nombre):
    assert adjuntos_service.nombre_saneado(nombre) == 'prueba.txt'


@pytest.mark.parametrize('nombre,contenido', [
    ('foto.png', b'No es una imagen'),
    ('informe.pdf', b'No es un PDF'),
    ('nota.txt', b'<script>alert(1)</script>'),
])
def test_formato_falso_no_pasa_por_su_extension(nombre, contenido):
    with pytest.raises(Validacion):
        adjuntos_service.validar(nombre, 'text/plain', len(contenido), contenido)


@pytest.mark.parametrize('tamano', [0, -1])
def test_archivo_vacio_o_tamano_invalido(tamano):
    with pytest.raises(Validacion):
        adjuntos_service.validar('nota.txt', 'text/plain', tamano, b'')


def test_tamano_excesivo_se_rechaza_sin_reservar_el_archivo():
    with pytest.raises(Validacion):
        adjuntos_service.validar('nota.txt', 'text/plain', settings.max_upload_bytes + 1, b'x')


@pytest.mark.asyncio
@pytest.mark.parametrize('respuesta', [b'stream: OK\0', b'stream: OK\n'])
async def test_antivirus_exige_confirmacion_limpia(monkeypatch, respuesta):
    _socket_antivirus(monkeypatch, respuesta)
    await adjuntos_service._escanear_con_clamav(b'contenido')


def _socket_antivirus(monkeypatch, respuesta):
    import socket
    class Conexion:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def sendall(self, contenido): pass
        def recv(self, tamano):
            nonlocal respuesta
            parte, respuesta = respuesta, b''
            return parte
    monkeypatch.setattr(socket, 'create_connection', lambda *args, **kwargs: Conexion())


@pytest.mark.asyncio
async def test_antivirus_bloquea_deteccion(monkeypatch):
    from app.core.errors import Prohibido
    _socket_antivirus(monkeypatch, b'stream: firma FOUND\0')
    with pytest.raises(Prohibido, match='antivirus'):
        await adjuntos_service._escanear_con_clamav(b'contenido')


@pytest.mark.asyncio
@pytest.mark.parametrize('respuesta', [b'', b'stream: error ERROR\0', b'OK\0'])
async def test_antivirus_no_acepta_errores_o_respuestas_desconocidas(monkeypatch, respuesta):
    from app.core.errors import DependenciaNoDisponible
    _socket_antivirus(monkeypatch, respuesta)
    with pytest.raises(DependenciaNoDisponible):
        await adjuntos_service._escanear_con_clamav(b'contenido')


@pytest.mark.asyncio
async def test_antivirus_caido_no_deja_subir_sin_revision(monkeypatch):
    import socket
    from app.core.errors import DependenciaNoDisponible
    def caido(*args, **kwargs): raise ConnectionRefusedError()
    monkeypatch.setattr(socket, 'create_connection', caido)
    with pytest.raises(DependenciaNoDisponible):
        await adjuntos_service._escanear_con_clamav(b'contenido')


@pytest.mark.parametrize('objetivo', ['adjunto', 'foto'])
@pytest.mark.parametrize('estado,esperado', [('caido', 503), ('infectado', 403)])
async def test_subidas_no_guardan_archivos_sin_aprobacion_antivirus(db, api, monkeypatch, objetivo, estado, esperado):
    from app.core.errors import DependenciaNoDisponible, Prohibido
    from tests.test_tickets_horarios import _mundo
    from tests.test_usuarios_foto import PNG_REAL
    mundo = await _mundo(api, f'av-{objetivo}-{estado}')
    from app.services import usuario_service
    monkeypatch.setattr(adjuntos_service.settings, 'clamav_enabled', True)
    monkeypatch.setattr(usuario_service.settings, 'clamav_enabled', True)
    async def rechazar(contenido):
        if estado == 'caido': raise DependenciaNoDisponible('Antivirus temporalmente no disponible')
        raise Prohibido('Archivo bloqueado')
    monkeypatch.setattr(adjuntos_service, '_escanear_con_clamav', rechazar)
    usuario_id = mundo['companero_id']
    ruta = '/api/adjuntos' if objetivo == 'adjunto' else f'/api/usuarios/{usuario_id}/foto'
    respuesta = await api.post(ruta, headers=mundo['admin'], files={'archivo': ('foto.png', PNG_REAL, 'image/png')})
    assert respuesta.status_code == esperado, respuesta.text
    assert await db.adjuntos.count_documents({}) == 0
    perfil = await api.get(f'/api/usuarios/{usuario_id}', headers=mundo['admin'])
    assert perfil.json()['tiene_foto'] is False
