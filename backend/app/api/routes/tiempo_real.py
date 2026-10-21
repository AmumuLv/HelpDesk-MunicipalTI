"""Notificaciones y WebSocket (chat del ticket y avisos en tiempo real)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.deps import DependeUsuario, SesionActual, exigir_csrf
from app.core.db import get_redis
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

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
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


async def _autenticar(websocket: WebSocket, token: str | None) -> dict[str, Any] | None:
    if not token:
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
    return payload["usuario"]


@router.websocket("/ws/ticket/{ticket_id}")
async def websocket_ticket(websocket: WebSocket, ticket_id: str, token: str | None = Query(default=None)) -> None:
    """Canal del chat de un ticket. Si el ticket no tiene chat, se cierra con el motivo."""
    await websocket.accept()
    usuario = await _autenticar(websocket, token)
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
    conexion = ConexionSocket(websocket)
    canales = [
        notificaciones_service.CANAL_TICKET.format(ticket_id=objetivo),
        notificaciones_service.CANAL_USUARIO.format(usuario_id=usuario["_id"]),
    ]
    await conexion.run(canales)


@router.websocket("/ws/notificaciones")
async def websocket_notificaciones(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    await websocket.accept()
    usuario = await _autenticar(websocket, token)
    if usuario is None:
        return
    conexion = ConexionSocket(websocket)
    from app.services.sincronizacion_service import CANAL
    await conexion.run([notificaciones_service.CANAL_USUARIO.format(usuario_id=usuario["_id"]), notificaciones_service.CANAL_CONFIG_IA, CANAL])
