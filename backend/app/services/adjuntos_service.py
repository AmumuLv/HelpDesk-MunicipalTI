"""Adjuntos: validacion de tipo real, tamano, nombre saneado y antivirus opcional."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import secrets
from pathlib import Path
from typing import Any

from bson import ObjectId
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import Prohibido, Validacion
from app.core.ids import normalizar_texto
from app.core.time import utcnow

EXTENSIONES_PERMITIDAS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic",
    ".pdf", ".txt", ".csv", ".log", ".md",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".7z", ".rar",
    ".msg", ".eml",
    ".webm", ".ogg", ".oga", ".wav", ".mp3", ".m4a",
}
# Firmas binarias aceptadas (se comparan con los primeros bytes del archivo)
FIRMAS: dict[str, bytes] = {
    ".pdf": b"%PDF-",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".gif": b"GIF8",
    ".zip": b"PK\x03\x04",
    ".webp": b"RIFF",
    ".bmp": b"BM",
}
NOMBRE_SEGURO = re.compile(r"[^A-Za-z0-9._-]+")


def nombre_saneado(nombre_original: str) -> str:
    base = os.path.basename(normalizar_texto(nombre_original).replace("\\", "/"))
    base = NOMBRE_SEGURO.sub("_", base).strip("._") or "archivo"
    extension = Path(base).suffix.lower()[:10]
    sin_extension = Path(base).stem[:60] or "archivo"
    return f"{sin_extension}{extension}"


def extension(nombre: str) -> str:
    return Path(nombre).suffix.lower()


def validar(nombre_original: str, mime: str, tamano: int, contenido: bytes | None = None) -> tuple[str, str]:
    """Devuelve (nombre saneado, mime normalizado). Lanza si no es aceptable."""
    if tamano <= 0:
        raise Validacion("El archivo esta vacio.")
    if tamano > settings.max_upload_bytes:
        raise Validacion(
            f"El archivo supera el limite de {settings.max_upload_mb} MB.",
            detalles={"limite_mb": settings.max_upload_mb, "tamano_mb": round(tamano / 1048576, 2)},
        )
    nombre = nombre_saneado(nombre_original)
    ext = extension(nombre)
    if ext not in EXTENSIONES_PERMITIDAS:
        raise Validacion(
            f"El tipo de archivo '{ext or 'desconocido'}' no esta permitido.",
            detalles={"permitidos": sorted(EXTENSIONES_PERMITIDAS)},
        )
    mime_detectado = _detectar_mime(contenido, nombre)
    if mime_detectado is None:
        raise Validacion("No se pudo verificar el contenido del archivo.")
    if not _coincide_tipo(ext, mime_detectado):
        raise Validacion(
            "El contenido del archivo no corresponde a su extension.",
            detalles={"extension": ext, "contenido_detectado": mime_detectado},
        )
    return nombre, mime_detectado


def _detectar_mime(contenido: bytes | None, nombre: str) -> str | None:
    ext = extension(nombre)
    if contenido:
        if contenido.startswith(b"RIFF") and contenido[8:12] == b"WAVE":
            return "audio/wav"
        if contenido.startswith(b"OggS") and (b"OpusHead" in contenido[:65536] or b"vorbis" in contenido[:65536]):
            return "audio/ogg"
        if contenido.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in contenido[:1024] and (b"A_OPUS" in contenido[:65536] or b"A_VORBIS" in contenido[:65536]):
            return "audio/webm"
        if contenido.startswith(b"ID3") or (len(contenido) > 2 and contenido[0] == 255 and contenido[1] & 0xE0 == 0xE0):
            return "audio/mpeg"
        if contenido[4:8] == b"ftyp" and b"soun" in contenido:
            return "audio/mp4"
        for firma_ext, firma in FIRMAS.items():
            if contenido.startswith(firma):
                return {
                    ".pdf": "application/pdf",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".zip": "application/zip",
                    ".webp": "image/webp",
                    ".bmp": "image/bmp",
                }[firma_ext]
        if contenido[:2] == b"\xd0\xcf":  # formatos OLE: doc/xls/ppt antiguos
            return {
                ".doc": "application/msword",
                ".xls": "application/vnd.ms-excel",
                ".ppt": "application/vnd.ms-powerpoint",
            }.get(ext, "application/octet-stream")
        try:
            texto = contenido[:2048].decode("utf-8")
        except UnicodeDecodeError:
            return "application/octet-stream" if ext in {".zip", ".7z", ".rar"} else None
        if texto.strip().startswith("<") or "<?xml" in texto[:200]:
            return {
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }.get(ext, "application/xml")
        if "," in texto.splitlines()[:2][0] if texto.splitlines() else False:
            return "text/csv"
        return "text/plain"
    mime, _ = mimetypes.guess_type(nombre)
    return mime


def _coincide_tipo(ext: str, mime_detectado: str) -> bool:
    permitidos = {
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".png": {"image/png"},
        ".gif": {"image/gif"},
        ".webp": {"image/webp", "image/x-webp"},
        ".bmp": {"image/bmp"},
        ".heic": {"image/heic", "image/heif"},
        ".pdf": {"application/pdf"},
        ".txt": {"text/plain"},
        ".log": {"text/plain"},
        ".md": {"text/plain", "text/markdown"},
        ".csv": {"text/csv", "text/plain", "application/csv"},
        ".doc": {"application/msword"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
        ".xls": {"application/vnd.ms-excel"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"},
        ".ppt": {"application/vnd.ms-powerpoint"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip"},
        ".zip": {"application/zip", "application/x-zip-compressed"},
        ".7z": {"application/x-7z-compressed"},
        ".rar": {"application/vnd.rar", "application/x-rar-compressed"},
        ".msg": {"application/vnd.ms-outlook"},
        ".eml": {"message/rfc822", "text/plain"},
        ".wav": {"audio/wav"},
        ".ogg": {"audio/ogg"},
        ".oga": {"audio/ogg"},
        ".webm": {"audio/webm"},
        ".mp3": {"audio/mpeg"},
        ".m4a": {"audio/mp4"},
    }
    return mime_detectado in permitidos.get(ext, {mime_detectado})


def ruta_destino(usuario_id: ObjectId, nombre_archivo: str) -> Path:
    carpeta = Path(settings.upload_dir) / str(usuario_id) / utcnow().strftime("%Y-%m")
    carpeta.mkdir(parents=True, exist_ok=True)
    sufijo = secrets.token_hex(6)
    return carpeta / f"{sufijo}_{nombre_archivo}"


async def guardar_archivo(
    contenido: bytes,
    *,
    nombre_original: str,
    mime_declarado: str,
    usuario: dict[str, Any],
    ticket_id: ObjectId | None = None,
    mensaje_id: ObjectId | None = None,
    nota_id: ObjectId | None = None,
    ambito: str = "ticket",
) -> dict[str, Any]:
    nombre, mime = validar(nombre_original, mime_declarado, len(contenido), contenido)
    duracion_audio = None
    if mime.startswith('audio/'):
        from app.services.audio_service import validar_audio
        duracion_audio = await run_in_threadpool(validar_audio, contenido)
    if settings.clamav_enabled:
        await _escanear_con_clamav(contenido)
    from app.services.imagenes_service import optimizar
    if mime in {'image/jpeg', 'image/png'}:
        contenido, mime_guardado = await run_in_threadpool(optimizar, contenido, mime)
    else:
        mime_guardado = mime
    nombre_subido = nombre_original
    if mime_guardado != mime:
        nombre = str(Path(nombre).with_suffix('.webp'))
        nombre_original = nombre
    mime = mime_guardado
    destino = ruta_destino(usuario["_id"], nombre)
    destino.write_bytes(contenido)
    huella = hashlib.sha256(contenido).hexdigest()
    documento = {
        "nombre_original": nombre_original[:255],
        "nombre_subido": nombre_subido[:255],
        "nombre_archivo": destino.name,
        "ruta": str(destino),
        "mime": mime,
        "tamano": len(contenido),
        "sha256": huella,
        "ambito": ambito,
        "ticket_id": ticket_id,
        "mensaje_id": mensaje_id,
        "nota_id": nota_id,
        "subido_por": usuario.get("_id"),
        "subido_por_nombre": usuario.get("nombre", ""),
        "creado_en": utcnow(),
    }
    if duracion_audio is not None:
        documento['duracion_segundos'] = duracion_audio
    resultado = await get_db()["adjuntos"].insert_one(documento)
    documento["id"] = resultado.inserted_id
    return documento


async def _escanear_con_clamav(contenido: bytes) -> None:
    """Usa el protocolo INSTREAM de clamd. Si no responde, no bloquea el flujo."""
    import logging
    import socket

    try:
        with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=10) as sock:
            sock.sendall(b"zINSTREAM\0")
            bloque = 32768
            for inicio in range(0, len(contenido), bloque):
                trozo = contenido[inicio : inicio + bloque]
                sock.sendall(len(trozo).to_bytes(4, "big") + trozo)
            sock.sendall((0).to_bytes(4, "big"))
            respuesta = sock.recv(1024).decode("utf-8", "replace")
    except Exception as exc:
        logging.getLogger(__name__).warning("ClamAV no disponible (%s); se continua sin escaneo", exc)
        return
    if "FOUND" in respuesta:
        raise Prohibido("El archivo fue bloqueado por el antivirus.", codigo="archivo_bloqueado")


async def obtener(adjunto_id: ObjectId) -> dict[str, Any]:
    documento = await get_db()["adjuntos"].find_one({"_id": adjunto_id})
    if documento is None:
        raise Prohibido("El archivo no existe.")
    return documento


async def listar_por_ticket(ticket_id: ObjectId) -> list[dict[str, Any]]:
    documentos = await (get_db()["adjuntos"].find({"ticket_id": ticket_id}).sort("creado_en", 1).to_list(None))
    for documento in documentos:
        documento["id"] = documento.pop("_id")
        documento.pop("ruta", None)
    return documentos
