"""Foto de perfil: subida, contenido real y permisos.

La foto se valida mirando los **primeros bytes**, no la extensiÃ³n ni el `content-type`
que declara el navegador. Eso es lo que distingue esto de un campo de archivo cualquiera:
sin esa comprobaciÃ³n, cualquiera con `usuarios.editar` podrÃ­a dejar en el servidor un
script disfrazado de foto, y el navegador lo pedirÃ­a desde el mismo origen de la
aplicaciÃ³n.
"""

from __future__ import annotations

import io
from PIL import Image

from tests.test_tickets_horarios import _mundo

# Un PNG de 1x1 real: la validaciÃ³n no mira el nombre, mira los bytes.
def imagen_real(formato='PNG'):
    salida = io.BytesIO()
    Image.new('RGB', (16, 16), 'blue').save(salida, format=formato)
    return salida.getvalue()

PNG_REAL = imagen_real()

PDF_REAL = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


def _subida(nombre: str, contenido: bytes, tipo: str = "image/png"):
    return {"archivo": (nombre, io.BytesIO(contenido), tipo)}


async def test_la_foto_se_guarda_y_se_sirve(db, api):
    """Subir una imagen real la deja puesta y se vuelve a servir tal cual."""
    mundo = await _mundo(api, "foto-guardar")
    objetivo = mundo["companero_id"]

    subida = await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("mi-foto.png", PNG_REAL),
        headers=mundo["admin"],
    )
    assert subida.status_code == 200, subida.text
    assert subida.json()["foto"] is True

    # El perfil lo dice, para que el avatar sepa pintar la imagen.
    perfil = await api.get(f"/api/usuarios/{objetivo}", headers=mundo["admin"])
    assert perfil.json()["tiene_foto"] is True

    # Y la imagen se sirve con su tipo real.
    descarga = await api.get(f"/api/usuarios/{objetivo}/foto", headers=mundo["admin"])
    assert descarga.status_code == 200, descarga.text
    assert Image.open(io.BytesIO(descarga.content)).format == 'WEBP'
    assert descarga.headers["content-type"] == "image/webp"


async def test_una_foto_renombrada_no_pasa(db, api):
    """Un PDF con extensiÃ³n .png se rechaza: se mira el contenido, no el nombre.

    Es el caso que justifica el mÃ³dulo entero. Sin la comprobaciÃ³n de bytes, esto
    devolverÃ­a 200 y el archivo quedarÃ­a servido desde el mismo origen que la app.
    """
    mundo = await _mundo(api, "foto-renombrada")
    objetivo = mundo["companero_id"]

    subida = await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("disfrazada.png", PDF_REAL, "image/png"),
        headers=mundo["admin"],
    )
    assert subida.status_code == 422, f"un PDF disfrazado de PNG se guardÃ³: {subida.text[:200]}"
    assert not (await api.get(f"/api/usuarios/{objetivo}/foto", headers=mundo["admin"])).status_code == 200


async def test_un_documento_no_es_una_foto(db, api):
    """Aunque el contenido sea vÃ¡lido, tiene que ser una imagen."""
    mundo = await _mundo(api, "foto-documento")
    objetivo = mundo["companero_id"]

    subida = await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("curriculum.pdf", PDF_REAL, "application/pdf"),
        headers=mundo["admin"],
    )
    assert subida.status_code == 422, subida.text


async def test_cualquiera_cambia_la_foto_de_otro(db, api):
    """Una cuenta normal no puede tocar la foto de otra persona."""
    mundo = await _mundo(api, "foto-ajena")
    objetivo = mundo["companero_id"]

    subida = await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("mia.png", PNG_REAL),
        headers=mundo["usuario"],
    )
    assert subida.status_code == 403, f"cambiÃ³ la foto de otro: {subida.text[:200]}"

    borrado = await api.delete(f"/api/usuarios/{objetivo}/foto", headers=mundo["usuario"])
    assert borrado.status_code == 403, borrado.text


async def test_uno_mismo_si_puede_subir_su_foto(db, api):
    """La propia foto no exige permiso: es tan personal como el nombre."""
    mundo = await _mundo(api, "foto-propia")

    subida = await api.post(
        f"/api/usuarios/{mundo['usuario_id']}/foto",
        files=_subida("mia.png", PNG_REAL),
        headers=mundo["usuario"],
    )
    assert subida.status_code == 200, subida.text

    perfil = await api.get(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo["usuario"])
    assert perfil.json()["tiene_foto"] is True


async def test_una_cuenta_normal_no_ve_la_foto_de_otro(db, api):
    """La foto respeta el mismo lÃ­mite que el perfil: la tuya y la de tu equipo."""
    mundo = await _mundo(api, "foto-ver-ajena")
    objetivo = mundo["companero_id"]
    await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("foto.png", PNG_REAL),
        headers=mundo["admin"],
    )

    ajena = await api.get(f"/api/usuarios/{objetivo}/foto", headers=mundo["usuario"])
    assert ajena.status_code == 403, f"una cuenta normal se descargÃ³ la foto de otro: {ajena.text[:200]}"

    propia = await api.get(f"/api/usuarios/{mundo['usuario_id']}/foto", headers=mundo["usuario"])
    assert propia.status_code == 404, "sin foto propia, la ruta debe decir 404 y no 403"


async def test_quitar_la_foto(db, api):
    """Quitarla borra el archivo del disco, no solo la referencia."""
    from pathlib import Path

    from app.core.config import settings

    mundo = await _mundo(api, "foto-quitar")
    objetivo = mundo["companero_id"]
    await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("foto.png", PNG_REAL),
        headers=mundo["admin"],
    )
    assert list((Path(settings.upload_dir) / "fotos").glob(f"{objetivo}.*")), "no se escribiÃ³ el archivo"

    borrado = await api.delete(f"/api/usuarios/{objetivo}/foto", headers=mundo["admin"])
    assert borrado.status_code == 200, borrado.text
    assert borrado.json()["foto"] is False

    perfil = await api.get(f"/api/usuarios/{objetivo}", headers=mundo["admin"])
    assert perfil.json()["tiene_foto"] is False
    assert not list((Path(settings.upload_dir) / "fotos").glob(f"{objetivo}.*")), "el archivo se quedÃ³ en disco"


async def test_subir_dos_veces_no_deja_archivos_sueltos(db, api):
    """Cambiar de formato borra el archivo anterior."""
    from pathlib import Path

    from app.core.config import settings

    mundo = await _mundo(api, "foto-reemplazo")
    objetivo = mundo["companero_id"]
    await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("una.png", PNG_REAL),
        headers=mundo["admin"],
    )
    await api.post(
        f"/api/usuarios/{objetivo}/foto",
        files=_subida("otra.jpg", imagen_real('JPEG'), "image/jpeg"),
        headers=mundo["admin"],
    )
    sobrantes = list((Path(settings.upload_dir) / "fotos").glob(f"{objetivo}.*"))
    assert len(sobrantes) == 1, f"quedaron {sobrantes} archivos para la misma cuenta"
