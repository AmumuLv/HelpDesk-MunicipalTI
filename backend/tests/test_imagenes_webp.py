from io import BytesIO
from pathlib import Path
import hashlib

import pytest
from bson import ObjectId
from PIL import Image

from app.core.errors import Validacion
from app.services.imagenes_service import optimizar
from tests.test_tickets_horarios import _mundo


def foto(formato, size=(40, 20), exif=None):
    imagen = Image.new('RGB', size, 'red')
    imagen.paste('blue', (size[0] // 2, 0, size[0], size[1]))
    archivo = BytesIO()
    imagen.save(archivo, format=formato, **({'exif': exif} if exif else {}))
    return archivo.getvalue()


@pytest.mark.parametrize('formato,mime', [('JPEG', 'image/jpeg'), ('PNG', 'image/png')])
def test_redimensiona_sin_deformar_y_no_amplia(formato, mime):
    for size, esperado in [((4000, 2000), (1920, 960)), ((40, 20), (40, 20))]:
        original = foto(formato, size)
        contenido, tipo = optimizar(original, mime)
        salida = Image.open(BytesIO(contenido))
        assert tipo == 'image/webp' and salida.format == 'WEBP'
        assert salida.size == esperado
        if size[0] > 1920:
            assert len(contenido) < len(original)


def test_orientacion_y_privacidad_exif():
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = 'Metadatos privados'
    contenido, _ = optimizar(foto('JPEG', (4000, 2000), exif), 'image/jpeg')
    salida = Image.open(BytesIO(contenido))
    assert salida.size == (960, 1920)
    assert not salida.getexif()
    arriba = salida.getpixel((480, 100))
    abajo = salida.getpixel((480, 1820))
    assert arriba[0] > arriba[2] and abajo[2] > abajo[0]


def test_png_con_transparencia():
    imagen = Image.new('RGBA', (20, 10), (20, 80, 120, 0))
    original = BytesIO()
    imagen.save(original, format='PNG')
    contenido, _ = optimizar(original.getvalue(), 'image/png')
    salida = Image.open(BytesIO(contenido))
    assert salida.size == (20, 10)
    assert salida.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize('contenido,mime', [(b'PK\x03\x04excel', 'application/zip'), (b'%PDF-1.7', 'application/pdf'), (b'RIFFaudio', 'audio/wav'), (b'GIF89a', 'image/gif')])
def test_no_modifica_otros_formatos(contenido, mime):
    assert optimizar(contenido, mime) == (contenido, mime)


def test_rechaza_imagen_truncada():
    with pytest.raises(Validacion):
        optimizar(b'\xff\xd8\xffimagen rota', 'image/jpeg')


async def test_subidas_metadatos_descarga_y_fotos_antiguas(db, api):
    from app.services import adjuntos_service, usuario_service
    from app.core.config import settings
    mundo = await _mundo(api, 'webp')
    usuario_id = ObjectId(mundo['usuario_id'])
    usuario = await db.usuarios.find_one({'_id': usuario_id})
    # Los adjuntos de todas las pantallas usan este mismo servicio.
    for formato, ext, mime in [('JPEG', 'jpg', 'image/jpeg'), ('PNG', 'png', 'image/png')]:
        original = foto(formato, (3000, 1500))
        respuesta = await api.post('/api/adjuntos', headers=mundo['usuario'], files={'archivo': (f'celular.{ext}', original, mime)})
        assert respuesta.status_code == 201, respuesta.text
        datos = respuesta.json()
        assert datos['mime'] == 'image/webp' and datos['nombre'].endswith('.webp')
        guardado = await db.adjuntos.find_one({'_id': ObjectId(datos['id'])})
        contenido = Path(guardado['ruta']).read_bytes()
        assert guardado['tamano'] == datos['tamano'] == len(contenido)
        assert guardado['sha256'] == hashlib.sha256(contenido).hexdigest()
        descarga = await api.get(f"/api/adjuntos/{datos['id']}", headers=mundo['usuario'])
        assert descarga.headers['content-type'] == 'image/webp'
        assert descarga.content == contenido
        assert Image.open(BytesIO(contenido)).size == (1920, 960)
        ruta_legacy = Path(guardado['ruta']).with_name(f'antigua.{ext}')
        ruta_legacy.write_bytes(original)
        legacy = {k: v for k, v in guardado.items() if k != '_id'}
        legacy.update(ruta=str(ruta_legacy), nombre_original=ruta_legacy.name, nombre_archivo=ruta_legacy.name, mime=mime, tamano=len(original))
        legacy_id = (await db.adjuntos.insert_one(legacy)).inserted_id
        antigua_adjunto = await api.get(f'/api/adjuntos/{legacy_id}', headers=mundo['usuario'])
        assert antigua_adjunto.status_code == 200 and antigua_adjunto.content == original
        assert antigua_adjunto.headers['content-type'] == mime
        # Una referencia antigua sigue sirviendo exactamente sus bytes y MIME.
        ruta = usuario_service.ruta_foto(usuario_id, mime)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(original)
        await db.usuarios.update_one({'_id': usuario_id}, {'$set': {'foto': {'nombre': ruta.name, 'mime': mime, 'tamano': len(original)}}})
        antigua = await api.get(f'/api/usuarios/{usuario_id}/foto', headers=mundo['usuario'])
        assert antigua.status_code == 200 and antigua.content == original
        assert antigua.headers['content-type'] == mime
    nueva = await api.post(f'/api/usuarios/{usuario_id}/foto', headers=mundo['usuario'], files={'archivo': ('perfil.png', foto('PNG') + bytes(3 * 1024 * 1024), 'image/png')})
    assert nueva.status_code == 200 and nueva.json()['mime'] == 'image/webp'
    perfil = await db.usuarios.find_one({'_id': usuario_id})
    assert perfil['foto']['nombre'].endswith('.webp')
    assert perfil['foto']['tamano'] == (Path(settings.upload_dir) / 'fotos' / perfil['foto']['nombre']).stat().st_size
    anterior = (await api.get(f'/api/usuarios/{usuario_id}/foto', headers=mundo['usuario'])).content
    invalida = await api.post(f'/api/usuarios/{usuario_id}/foto', headers=mundo['usuario'], files={'archivo': ('rota.jpg', b'\xff\xd8\xffrota', 'image/jpeg')})
    assert invalida.status_code == 422
    assert (await api.get(f'/api/usuarios/{usuario_id}/foto', headers=mundo['usuario'])).content == anterior
    for nombre, contenido, mime in [('reporte.pdf', b'%PDF-1.7\ncontenido', 'application/pdf'), ('inventario.xlsx', b'PK\x03\x04contenido excel', 'application/zip')]:
        documento = await adjuntos_service.guardar_archivo(contenido, nombre_original=nombre, mime_declarado=mime, usuario=usuario)
        assert Path(documento['ruta']).read_bytes() == contenido
        assert documento['nombre_original'] == nombre and documento['tamano'] == len(contenido)
