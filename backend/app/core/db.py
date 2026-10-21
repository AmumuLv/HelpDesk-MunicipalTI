"""Conexion a MongoDB (PyMongo Async) y Redis.

Se usa ``AsyncMongoClient`` de PyMongo >= 4.13, sucesor oficial de Motor.
Las transacciones multi-documento requieren replica set, por eso
``docker-compose.yml`` inicializa un replica set de un nodo.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None
_redis: Redis | None = None


def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(
            settings.mongo_uri,
            tz_aware=True,
            tzinfo=settings.tz,
            appname=settings.app_name,
            maxPoolSize=50,
            retryWrites=True,
            serverSelectionTimeoutMS=15000,
        )
    return _client


def get_db() -> AsyncDatabase:
    return get_client()[settings.mongo_db]


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis


async def close_connections() -> None:
    global _client, _redis
    if _client is not None:
        await _client.close()
        _client = None
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def ping_mongo() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception as exc:  # pragma: no cover - depende del entorno
        logger.warning("MongoDB no responde: %s", exc)
        return False


async def ping_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception as exc:  # pragma: no cover - depende del entorno
        logger.warning("Redis no responde: %s", exc)
        return False


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncDatabase]:
    """Sesion transaccional (requiere replica set).

    En el driver asincrono ``start_session`` no es corrutina y ``start_transaction`` si.
    """
    async with get_client().start_session() as sesion:
        async with await sesion.start_transaction():
            yield get_db()


async def agregar(coleccion: str, pipeline: list[dict], **opciones: Any) -> list:
    """Ejecuta una agregacion y devuelve la lista de documentos.

    En el driver asincrono ``aggregate`` es una corrutina que hay que esperar
    antes de invocar ``to_list``; este helper evita repetir ese dance.
    """
    cursor = await get_db()[coleccion].aggregate(pipeline, **opciones)
    return await cursor.to_list(None)