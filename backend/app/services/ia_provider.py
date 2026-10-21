"""Capa de abstraccion del proveedor de modelo de lenguaje.

Una sola interfaz (`ProveedorIA`) con implementaciones intercambiables por variable
de entorno. Si el proveedor no esta disponible NO se inventa nada: las funciones
que dependen del modelo devuelven ``disponible=False`` y la interfaz lo muestra
como "no disponible en este momento". La clasificacion, la asignacion y la
prioridad NO dependen del LLM: usan reglas y modelos entrenados con datos reales.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SIN_DATOS_SUFICIENTES = "datos_insuficientes"


@dataclass
class RespuestaIA:
    texto: str = ""
    disponible: bool = False
    motivo: str | None = None
    datos: dict[str, Any] = field(default_factory=dict)
    llamadas: list[dict[str, Any]] = field(default_factory=list)


class ProveedorIA:
    """Interfaz comun. Las implementaciones reales heredan de esta clase."""

    nombre: str = "generico"

    async def disponible(self) -> bool:
        raise NotImplementedError

    async def completar(
        self,
        mensajes: list[dict[str, Any]],
        *,
        herramientas: list[dict[str, Any]] | None = None,
        temperatura: float = 0.1,
        max_tokens: int | None = None,
    ) -> RespuestaIA:
        raise NotImplementedError


class ProveedorDesactivado(ProveedorIA):
    nombre = "desactivado"

    async def disponible(self) -> bool:
        return False

    async def completar(self, mensajes, *, herramientas=None, temperatura=0.1, max_tokens=None) -> RespuestaIA:
        return RespuestaIA(
            disponible=False,
            motivo="El servicio de inteligencia artificial no esta configurado en esta instalacion.",
        )


class ProveedorOpenAICompatible(ProveedorIA):
    """Compatible con OpenAI, Ollama (/v1), LM Studio, vLLM y gateways corporativos."""

    nombre = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, modelo: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.modelo = modelo
        self.timeout = timeout
        self._cache_disponible: tuple[float, bool] | None = None

    def _cabeceras(self) -> dict[str, str]:
        cabeceras = {"Content-Type": "application/json"}
        if self.api_key and self.api_key.lower() != "local":
            cabeceras["Authorization"] = f"Bearer {self.api_key}"
        return cabeceras

    async def _probe(self) -> bool:
        import time

        ahora = time.monotonic()
        if self._cache_disponible and ahora - self._cache_disponible[0] < 60:
            return self._cache_disponible[1]
        try:
            async with httpx.AsyncClient(timeout=5) as cliente:
                respuesta = await cliente.get(f"{self.base_url}/models", headers=self._cabeceras())
                disponible = 200 <= respuesta.status_code < 300
        except Exception:
            disponible = False
        self._cache_disponible = (ahora, disponible)
        return disponible

    async def disponible(self) -> bool:  # type: ignore[override]
        return await self._probe()

    async def completar(
        self,
        mensajes: list[dict[str, Any]],
        *,
        herramientas: list[dict[str, Any]] | None = None,
        temperatura: float = 0.1,
        max_tokens: int | None = None,
    ) -> RespuestaIA:
        cuerpo: dict[str, Any] = {
            "model": self.modelo,
            "messages": mensajes,
            "temperature": temperatura,
            "stream": False,
            "max_tokens": max_tokens or settings.ai_max_tokens,
        }
        if herramientas:
            cuerpo["tools"] = herramientas
            cuerpo["tool_choice"] = "auto"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as cliente:
                respuesta = await cliente.post(
                    f"{self.base_url}/chat/completions", headers=self._cabeceras(), json=cuerpo
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
        except Exception as exc:
            logger.warning("Proveedor IA no disponible: %s", exc)
            return RespuestaIA(disponible=False, motivo=f"El modelo de lenguaje no respondio ({type(exc).__name__}).")
        elegir = datos.get("choices") or []
        if not elegir:
            return RespuestaIA(disponible=False, motivo="El modelo no devolvio ninguna respuesta.")
        mensaje = elegir[0].get("message") or {}
        llamadas = mensaje.get("tool_calls") or []
        return RespuestaIA(
            texto=(mensaje.get("content") or "").strip(),
            disponible=True,
            llamadas=[
                {
                    "nombre": c.get("function", {}).get("name"),
                    "argumentos": _json_seguro(c.get("function", {}).get("arguments")),
                    "id": c.get("id"),
                }
                for c in llamadas
            ],
            datos={"uso": datos.get("usage") or {}},
        )


def _json_seguro(texto: Any) -> dict[str, Any]:
    if isinstance(texto, dict):
        return texto
    try:
        return json.loads(texto or "{}")
    except (TypeError, ValueError):
        return {}


_proveedor: ProveedorIA | None = None


def obtener_proveedor() -> ProveedorIA:
    global _proveedor
    if _proveedor is None:
        if settings.ai_provider in {"desactivado", "none", "off"}:
            _proveedor = ProveedorDesactivado()
        else:
            _proveedor = ProveedorOpenAICompatible(
                settings.ai_base_url, settings.ai_api_key, settings.ai_model, settings.ai_timeout_seconds
            )
    return _proveedor


def reiniciar_proveedor() -> None:
    global _proveedor
    _proveedor = None


async def estado() -> dict[str, Any]:
    proveedor = obtener_proveedor()
    disponible = await proveedor.disponible()
    return {
        "proveedor": proveedor.nombre,
        "modelo": settings.ai_model if disponible else None,
        "base_url": settings.ai_base_url if disponible else None,
        "disponible": disponible,
        "motivo": None if disponible else "No se pudo contactar con el modelo de lenguaje.",
        "funcionalidad": "clasificacion_y_asignacion",
    }
