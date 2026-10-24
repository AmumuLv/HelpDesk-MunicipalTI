"""Notificaciones y WebSocket (chat del ticket y avisos en tiempo real)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.deps import DependeUsuario, SesionActual, exigir_csrf
from app.core.db import get_db, get_redis
from app.core.errors import AppError
from app.core.ids import a_id
from app.services import auth_service, notificaciones_service, ticket_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tiempo-real"])


@router.get("/notificaciones")
async def listar_notificaciones(
    sesion: DependeUsuario,
    limite: int = Query(30, ge=1, le=100),
    solo_no_leidas: bool = False,
):
    items = await notificaciones_service.listar(sesion.id, solo_no_leidas=solo_no_leidas, limite=limite)
    for item in items:
        item["id"] = str(item["id"])
        item["ticket_id"] = str(item["ticket_id"]) if item.get("ticket_id") else None
    return {"items": items, "no_leidas": await notificaciones_service.contar_no_leidas(sesion.id)}


@router.post("/notificaciones/leer")
async def leer_notificaciones(
    sesion: SesionActual = Depends(exigir_csrf),
    ids: list[str] | None = Query(default=None),
):
    from app.core.ids import id_requerido
    objetivo = [id_requerido(i, 'notificación') for i in (ids or [])]
    return {"actualizadas": await notificaciones_service.marcar_leidas(sesion.id, objetivo or None)}


# ── WebSocket ────────────────────────────────────────────────
@router.delete('/notificaciones')
async def vaciar_notificaciones(sesion: SesionActual = Depends(exigir_csrf)):
    return {'eliminadas': await notificaciones_service.eliminar(sesion.id)}


@router.delete('/notificaciones/{notificacion_id}')
async def eliminar_notificacion(notificacion_id: str, sesion: SesionActual = Depends(exigir_csrf)):
    from app.core.ids import id_requerido
    from app.core.errors import NoEncontrado
    eliminadas = await notificaciones_service.eliminar(sesion.id, id_requerido(notificacion_id, 'notificación'))
    if not eliminadas:
        raise NoEncontrado('Notificación no encontrada.')
    return {'eliminadas': eliminadas}


class ConexionSocket:
    """Suscripcion de un cliente a los canales de Redis que le importan."""

    def __init__(self, websocket: WebSocket, acceso: str | None = None, ticket_id=None):
        self.websocket = websocket
        self.acceso = acceso
        self.ticket_id = ticket_id
        self.pubsub = None
        self.cola: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)

    async def run(self, canales: list[str]) -> None:
        self.pubsub = get_redis().pubsub()
        if canales:
            await self.pubsub.subscribe(*canales)
        await self.cola.put({'tipo': 'sincronizacion'})
        consumidor = asyncio.create_task(self._consumir_redis())
        async def enviar():
            while True:
                try:
                    mensaje = await asyncio.wait_for(self.cola.get(), timeout=20)
                except asyncio.TimeoutError:
                    mensaje = {'tipo': 'latido'}
                if not await self.autorizado():
                    return
                await self.websocket.send_json(mensaje)

        async def recibir():
            while True:
                evento = await self.websocket.receive()
                if evento['type'] == 'websocket.disconnect':
                    return

        emisor = asyncio.create_task(enviar())
        receptor = asyncio.create_task(recibir())
        try:
            terminadas, _ = await asyncio.wait([consumidor, emisor, receptor], return_when=asyncio.FIRST_COMPLETED)
            for tarea in terminadas:
                tarea.result()
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            for tarea in (consumidor, emisor, receptor):
                tarea.cancel()
            for tarea in (consumidor, emisor, receptor):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await tarea
            with contextlib.suppress(Exception):
                await self.pubsub.unsubscribe(*canales)
            with contextlib.suppress(Exception):
                await self.pubsub.aclose()

    async def _consumir_redis(self) -> None:
        if self.pubsub is None:
            return
        try:
            async for mensaje in self.pubsub.listen():
                if mensaje.get("type") != "message":
                    continue
                try:
                    await self.cola.put(json.loads(mensaje.get("data") or "{}"))
                except (ValueError, TypeError):
                    continue
        except asyncio.CancelledError:  # pragma: no cover
            return

    async def enviar(self, dato: dict[str, Any]) -> None:
        await self.cola.put(dato)

    async def autorizado(self) -> bool:
        if self.acceso is None:
            return True
        try:
            sesion = await auth_service.payload_sesion(self.acceso)
            if self.ticket_id is not None:
                ticket = await get_db().tickets.find_one({'_id': self.ticket_id, 'eliminado': {'$ne': True}})
                if ticket is None:
                    raise ValueError('Ticket no disponible')
                ticket_service._verificar_acceso(ticket, sesion['usuario'])
        except Exception:
            await self.websocket.close(code=4401, reason='Sesion o acceso no valido')
            return False
        return True


async def _autenticar(websocket: WebSocket) -> dict[str, Any] | None:
    # El token viaja en el primer mensaje, nunca en la URL ni en access logs.
    try:
        dato = await asyncio.wait_for(websocket.receive_json(), timeout=5)
    except (asyncio.TimeoutError, ValueError, KeyError, TypeError, WebSocketDisconnect, RuntimeError):
        await websocket.close(code=4401, reason="Falta autenticacion")
        return None
    token = dato.get('token') if isinstance(dato, dict) and dato.get('tipo') == 'autenticar' else None
    if not isinstance(token, str) or not token or len(token) > 4096:
        await websocket.close(code=4401, reason="Sin token")
        return None
    try:
        payload = await auth_service.payload_sesion(token)
    except AppError:
        await websocket.close(code=4401, reason="Sesion no valida")
        return None
    except Exception:  # pragma: no cover
        await websocket.close(code=4401, reason="Sesion no valida")
        return None
    websocket.state.acceso = token
    return payload["usuario"]


@router.websocket("/ws/ticket/{ticket_id}")
async def websocket_ticket(websocket: WebSocket, ticket_id: str) -> None:
    """Canal del chat de un ticket. Si el ticket no tiene chat, se cierra con el motivo."""
    await websocket.accept()
    usuario = await _autenticar(websocket)
    if usuario is None:
        return
    objetivo = a_id(ticket_id)
    try:
        ticket = await ticket_service.obtener(objetivo, usuario=usuario)
    except AppError:
        await websocket.close(code=4403, reason="Sin acceso")
        return
    if not ticket.get("tiene_chat"):
        await websocket.send_json(
            {
                "tipo": "sin_chat",
                "mensaje": "Este ticket fue registrado por el equipo de soporte, por eso no tiene chat.",
            }
        )
        await websocket.close(code=4400, reason="sin_chat")
        return
    conexion = ConexionSocket(websocket, websocket.state.acceso, objetivo)
    canales = [
        notificaciones_service.CANAL_TICKET.format(ticket_id=objetivo),
        notificaciones_service.CANAL_USUARIO.format(usuario_id=usuario["_id"]),
    ]
    await conexion.run(canales)


@router.websocket("/ws/notificaciones")
async def websocket_notificaciones(websocket: WebSocket) -> None:
    await websocket.accept()
    usuario = await _autenticar(websocket)
    if usuario is None:
        return
    conexion = ConexionSocket(websocket, websocket.state.acceso)
    from app.services.sincronizacion_service import CANAL
    await conexion.run([notificaciones_service.CANAL_USUARIO.format(usuario_id=usuario["_id"]), notificaciones_service.CANAL_CONFIG_IA, CANAL])
