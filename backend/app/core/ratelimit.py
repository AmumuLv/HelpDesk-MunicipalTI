"""Rate limiting y bloqueo por intentos fallidos (Redis)."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.db import get_redis
from app.core.errors import DemasiadasPeticiones

logger = logging.getLogger(__name__)

_LLAVE_INTENTOS = "login:intentos:{clave}"
_LLAVE_BLOQUEO = "login:bloqueo:{clave}"


async def comprobar_limite(clave: str, limite: int | None = None) -> None:
    """Ventana fija de 60 s. Lanza 429 si se excede."""
    maximo = limite or settings.rate_limit_per_minute
    if maximo <= 0:
        return
    redis = get_redis()
    ventana = f"rate:{clave}"
    try:
        actual = await redis.incr(ventana)
        if actual == 1:
            await redis.expire(ventana, 60)
        if actual > maximo:
            ttl = await redis.ttl(ventana)
            raise DemasiadasPeticiones(
                "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
                detalles={"reintenta_en_segundos": max(ttl, 1)},
            )
    except DemasiadasPeticiones:
        raise
    except Exception as exc:  # pragma: no cover - Redis no disponible
        logger.warning("No se pudo aplicar el rate limit: %s", exc)


async def registrar_intento_fallido(clave: str) -> int:
    """Suma un intento fallido y bloquea al superar el maximo."""
    redis = get_redis()
    llave = _LLAVE_INTENTOS.format(clave=clave)
    try:
        intentos = await redis.incr(llave)
        if intentos == 1:
            await redis.expire(llave, settings.login_lock_minutes * 60)
        if intentos >= settings.login_max_attempts:
            await redis.set(
                _LLAVE_BLOQUEO.format(clave=clave), "1", ex=settings.login_lock_minutes * 60
            )
        return intentos
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudo registrar el intento fallido: %s", exc)
        return 0


async def limpiar_intentos(clave: str) -> None:
    try:
        redis = get_redis()
        await redis.delete(_LLAVE_INTENTOS.format(clave=clave), _LLAVE_BLOQUEO.format(clave=clave))
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudieron limpiar los intentos: %s", exc)


async def esta_bloqueado(clave: str) -> int:
    """Devuelve los segundos restantes de bloqueo (0 si no esta bloqueado)."""
    try:
        ttl = await get_redis().ttl(_LLAVE_BLOQUEO.format(clave=clave))
        return max(ttl, 0)
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudo consultar el bloqueo: %s", exc)
        return 0