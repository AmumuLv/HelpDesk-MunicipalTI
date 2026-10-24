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
