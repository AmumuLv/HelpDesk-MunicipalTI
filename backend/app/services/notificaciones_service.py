"""Notificaciones en el sistema y difusion en tiempo real (Redis pub/sub)."""

from __future__ import annotations

import json
from typing import Any

from bson import ObjectId

from app.core.db import get_redis
from app.core.time import utcnow

CANAL_USUARIO = "notificaciones:{usuario_id}"
CANAL_TICKET = "ticket:{ticket_id}"
CANAL_SISTEMA = "sistema"
CANAL_CONFIG_IA = 'configuracion:ia'


async def avisar_configuracion_ia(configuracion: dict[str, Any]) -> None:
    ia = configuracion.get('ia') or {}
    await _publicar(CANAL_CONFIG_IA, {'tipo': 'ia_actualizada', 'global_activa': bool(ia.get('global_activa', True)), 'recomendaciones_activas': bool(ia.get('recomendaciones_activas', True))})


async def avisar_preferencia_ia(usuario_id: ObjectId, activa: bool) -> None:
    await _publicar(CANAL_USUARIO.format(usuario_id=usuario_id), {'tipo': 'ia_preferencia', 'recomendaciones_ia': activa})


async def crear(
    usuario_id: ObjectId,
    titulo: str,
    mensaje: str,
    *,
    tipo: str = "info",
    enlace: str | None = None,
    ticket_id: ObjectId | None = None,
) -> dict[str, Any]:
    from app.core.db import get_db

    documento = {
        "usuario_id": usuario_id,
        "titulo": titulo,
        "mensaje": mensaje,
        "tipo": tipo,
        "enlace": enlace,
        "ticket_id": ticket_id,
        "leida": False,
        "creado_en": utcnow(),
    }
    resultado = await get_db()["notificaciones"].insert_one(documento)
    documento["id"] = resultado.inserted_id
    await _publicar(
        CANAL_USUARIO.format(usuario_id=usuario_id),
        {"tipo": "notificacion", "datos": await _serializable(documento)},
    )
    return documento


async def _serializable(documento: dict[str, Any]) -> dict[str, Any]:
    salida = dict(documento)
    for clave, valor in list(salida.items()):
        if isinstance(valor, ObjectId):
            salida[clave] = str(valor)
        elif hasattr(valor, "isoformat"):
            salida[clave] = valor.isoformat()
    return salida


async def _publicar(canal: str, mensaje: dict[str, Any]) -> None:
    try:
        await get_redis().publish(canal, json.dumps(mensaje, default=str))
    except Exception:  # pragma: no cover - la app funciona sin pub/sub
        pass


async def publicar_ticket(ticket_id: ObjectId, tipo: str, datos: dict[str, Any]) -> None:
    """Difunde cambios del ticket a quien este suscrito en ese momento."""
    payload = {"tipo": tipo, "ticket_id": str(ticket_id), "datos": datos}
    await _publicar(CANAL_TICKET.format(ticket_id=ticket_id), payload)
    await _publicar(CANAL_SISTEMA, payload)


async def listar(usuario_id: ObjectId, *, solo_no_leidas: bool = False, limite: int = 30) -> list[dict[str, Any]]:
    from app.core.db import get_db

    consulta: dict[str, Any] = {"usuario_id": usuario_id}
    if solo_no_leidas:
        consulta["leida"] = False
    documentos = await (
        get_db()["notificaciones"].find(consulta).sort("creado_en", -1).limit(limite).to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
    return documentos


async def marcar_leidas(usuario_id: ObjectId, ids: list[ObjectId] | None = None) -> int:
    from app.core.db import get_db

    consulta: dict[str, Any] = {"usuario_id": usuario_id, "leida": False}
    if ids:
        consulta["_id"] = {"$in": ids}
    resultado = await get_db()["notificaciones"].update_many(consulta, {"$set": {"leida": True, "leida_en": utcnow()}})
    return resultado.modified_count


async def contar_no_leidas(usuario_id: ObjectId) -> int:
    from app.core.db import get_db

    return await get_db()["notificaciones"].count_documents({"usuario_id": usuario_id, "leida": False})


async def eliminar(usuario_id: ObjectId, notificacion_id: ObjectId | None = None) -> int:
    from app.core.db import get_db
    consulta = {'usuario_id': usuario_id}
    if notificacion_id is not None:
        consulta['_id'] = notificacion_id
    resultado = await get_db()['notificaciones'].delete_many(consulta)
    if resultado.deleted_count:
        await _publicar(CANAL_USUARIO.format(usuario_id=usuario_id), {'tipo': 'notificaciones_eliminadas'})
    return resultado.deleted_count


async def avisar_participantes(
    ticket: dict[str, Any],
    *,
    titulo: str,
    mensaje: str,
    excluir: ObjectId | None = None,
    enlace: str | None = None,
    tipo: str = "info",
) -> None:
    """Notifica al reportante, al afectado y al tecnico asignado (sin duplicar)."""
    from app.core.db import get_db

    from app.services import config_service
    preferencias = await config_service.seccion("notificaciones")
    destinos: list[ObjectId] = []
    for campo in ("reportante_id", "afectado_id", "tecnico_id"):
        if campo == "reportante_id" and not preferencias.get("avisar_al_reportante", True):
            continue
        if campo == "afectado_id" and not preferencias.get("avisar_al_afectado", True):
            continue
        valor = ticket.get(campo)
        if valor and valor != excluir and valor not in destinos:
            destinos.append(valor)
    for usuario_id in destinos:
        usuario = await get_db()["usuarios"].find_one({"_id": usuario_id}, {"activo": 1, "preferencias": 1})
        if usuario is None or not usuario.get("activo", True):
            continue
        await crear(usuario_id, titulo, mensaje, tipo=tipo, enlace=enlace or f"/tickets/{ticket['_id']}", ticket_id=ticket["_id"])
