"""Tareas en segundo plano con ARQ: SLA, exportaciones, limpieza y modelos."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.db import close_connections, get_db
from app.core.logging_config import configurar_logging
from app.services import campana_service, catalogo_service, export_service, horario_service, inventario_service, ml_service, sla_service

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    configurar_logging(settings.log_level)
    logger.info("Worker ARQ iniciado")
    await ml_service.invalidar_cache()


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Worker ARQ detenido")
    await close_connections()


# ── Tareas periodicas ────────────────────────────────────────
async def resumir_ticket(ctx: dict[str, Any], ticket_id: str) -> bool:
    from app.services.resumen_ticket_service import resumir
    return await resumir(ticket_id)


async def revisar_sla(ctx: dict[str, Any]) -> dict[str, Any]:
    """Recalcula riesgos de SLA y marca incumplimientos. Corre cada 5 minutos."""
    resultado = await sla_service.recalcular_todos_abiertos()
    logger.info("SLA: %s", resultado)
    return resultado


async def refrescar_sugerencias(ctx: dict[str, Any]) -> dict[str, Any]:
    """Rehace el conteo de valores usados para las sugerencias de inventario."""
    db = get_db()
    activos = await (db["activos"].find({"activo": {"$ne": False}}).to_list(None))
    valores = []
    for activo in activos:
        for campo in ("marca", "modelo", "procesador", "memoria_ram", "almacenamiento", "tamano_pantalla", "propiedad", "estado"):
            if activo.get(campo):
                valores.append((campo, activo[campo], activo.get("tipo"), activo.get("marca")))
    if valores:
        await catalogo_service.registrar_lote(valores)
    logger.info("Sugerencias de inventario refrescadas (%s equipos)", len(activos))
    return {"activos": len(activos), "valores": len(valores)}


async def refrescar_modelos(ctx: dict[str, Any]) -> dict[str, Any]:
    await ml_service.invalidar_cache()
    familias = await ml_service.predecir_familias()
    logger.info("Modelo de fallas recalculado (%s familias)", len(familias))
    return {"familias": len(familias), "suficiente_datos": familias[0]["suficiente_datos"] if familias else False}


async def limpiar_exportaciones(ctx: dict[str, Any]) -> dict[str, Any]:
    return await export_service.limpiar_antiguos(dias=7)


async def limpiar_sesiones(ctx: dict[str, Any]) -> dict[str, Any]:
    from app.core.time import utcnow

    db = get_db()
    resultado = await db["sesiones"].delete_many({"expira": {"$lt": utcnow()}})
    return {"sesiones_eliminadas": resultado.deleted_count}


async def limpiar_auditoria(ctx: dict[str, Any]) -> dict[str, Any]:
    from datetime import timedelta
    from app.core.time import utcnow
    resultado = await get_db()['auditoria'].delete_many({'fecha': {'$lt': utcnow() - timedelta(days=15)}})
    return {'eliminados': resultado.deleted_count}


from arq import cron  # noqa: E402
from arq.connections import RedisSettings  # noqa: E402


def redis_settings_from_url(url: str) -> RedisSettings:
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    functions = [
        resumir_ticket,
        revisar_sla,
        refrescar_sugerencias,
        refrescar_modelos,
        limpiar_exportaciones,
        limpiar_sesiones,
        limpiar_auditoria,
    ]
    cron_jobs = [
        # SLA cada 5 minutos
        cron(revisar_sla, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        # Sugerencias y modelos una vez por noche
        cron(refrescar_sugerencias, hour={3}, minute=10),
        cron(refrescar_modelos, hour={3}, minute=40),
        # Limpieza diaria
        cron(limpiar_exportaciones, hour={4}, minute=0),
        cron(limpiar_sesiones, hour={4}, minute=30),
        cron(limpiar_auditoria, hour={4}, minute=45),
    ]
    redis_settings = redis_settings_from_url(settings.redis_url)
    max_jobs = 10
    job_timeout = 600
    keep_result = 3600
    on_startup = startup
    on_shutdown = shutdown
