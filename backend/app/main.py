"""Punto de entrada de la API: FastAPI, ciclo de vida, CORS, salud y WebSocket."""

from __future__ import annotations

import json
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any

from bson import ObjectId
from fastapi import FastAPI, Request
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse as JSONResponseBase

from app.api.router import api
from app.core.config import settings
from app.core.db import close_connections, get_db, ping_mongo, ping_redis
from app.core.errors import registrar_handlers
from app.core.logging_config import configurar_logging

configurar_logging(settings.log_level)
logger = logging.getLogger("app")

# FastAPI usa este mapa para serializar; sin esta linea un ObjectId en una
# respuesta cruda provocaria un error 500.
ENCODERS_BY_TYPE[ObjectId] = str
ENCODERS_BY_TYPE[bytes] = lambda valor: valor.decode("utf-8", "replace")


def _json_default(valor: Any) -> Any:
    """Serializa lo que Python no sabe convertir solo (ObjectId, fechas, modelos)."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (set, frozenset, tuple)):
        return list(valor)
    if hasattr(valor, "model_dump"):
        return valor.model_dump(mode="json")
    return str(valor)


class JSONApiResponse(JSONResponseBase):
    """Respuesta JSON con conversores para los tipos propios del dominio."""

    def render(self, content: Any) -> bytes:
        return json.dumps(content, ensure_ascii=False, default=_json_default).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando %s (%s)", settings.app_name, settings.app_env)
    from app.migrations import runner

    try:
        aplicadas = await runner.ejecutar()
        if aplicadas:
            logger.info("Migraciones aplicadas: %s", ", ".join(aplicadas))
    except Exception as exc:  # pragma: no cover
        logger.error("No se pudieron aplicar las migraciones: %s", exc)
        raise
    from app.services.sincronizacion_service import vigilar_cambios
    sincronizacion = asyncio.create_task(vigilar_cambios())
    try:
        yield
    finally:
        sincronizacion.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sincronizacion
        await close_connections()
    logger.info("Apagando %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API de la mesa de ayuda TI para municipalidades: jerarquia Zona > Oficina > Usuario, "
        "inventario de equipos con estado por campo, campanas de inventario anual, SLA con "
        "calendario laboral y analitica con IA que propone y la persona decide."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    default_response_class=JSONApiResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    max_age=600,
)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    try:
        respuesta = await call_next(request)
    except Exception:
        # Nunca dejamos la conexion colgada: el cliente recibe un error claro.
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        respuesta = JSONApiResponse(
            status_code=500,
            content={
                "codigo": "error_interno",
                "mensaje": "Ocurrio un error inesperado. Intenta de nuevo o contacta al administrador.",
            },
        )
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    respuesta.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return respuesta


registrar_handlers(app)
app.include_router(api, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health", tags=["sistema"])
async def health() -> dict[str, Any]:
    mongo_ok = await ping_mongo()
    redis_ok = await ping_redis()
    estado = "ok" if mongo_ok and redis_ok else "degradado"
    return {
        "estado": estado,
        "mongo": mongo_ok,
        "redis": redis_ok,
        "version": "1.0.0",
        "entorno": settings.app_env,
        "detalle": settings.public_summary(),
    }


@app.get("/", include_in_schema=False)
async def raiz() -> dict[str, str]:
    return {"servicio": settings.app_name, "api": settings.api_prefix, "documentacion": f"{settings.api_prefix}/docs"}
