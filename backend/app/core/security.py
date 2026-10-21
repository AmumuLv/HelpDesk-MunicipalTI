"""Hashing de contrasenas (argon2id), JWT de vida corta y proteccion CSRF."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import NoAutorizado, Validacion
from app.core.time import utcnow

ALGORITMO_PWD = "argon2id"
ALGORITMO_JWT = "HS256"

_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)


# ── Contrasenas ──────────────────────────────────────────────
def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise Validacion("La contrasena debe tener al menos 8 caracteres.")
    return _hasher.hash(password)


def verify_password(password: str, hash_guardado: str | None) -> bool:
    if not hash_guardado:
        return False
    try:
        return _hasher.verify(hash_guardado, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def necesita_rehash(hash_guardado: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hash_guardado)
    except InvalidHashError:
        return True


# ── Tokens ───────────────────────────────────────────────────
TOKEN_ACCESO = "access"
TOKEN_REFRESH = "refresh"


def _clave() -> str:
    return settings.secret_key


def crear_access_token(
    *,
    usuario_id: str,
    rol: str,
    session_id: str,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    ahora = utcnow()
    expira = ahora + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": usuario_id,
        "rol": rol,
        "sid": session_id,
        "tipo": TOKEN_ACCESO,
        "iat": int(ahora.timestamp()),
        "exp": int(expira.timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _clave(), algorithm=ALGORITMO_JWT), expira


def crear_refresh_token(*, usuario_id: str, session_id: str) -> tuple[str, datetime]:
    ahora = utcnow()
    expira = ahora + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {
        "sub": usuario_id,
        "sid": session_id,
        "tipo": TOKEN_REFRESH,
        "iat": int(ahora.timestamp()),
        "exp": int(expira.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, _clave(), algorithm=ALGORITMO_JWT), expira


def decodificar_token(token: str, *, tipo: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _clave(), algorithms=[ALGORITMO_JWT])
    except jwt.ExpiredSignatureError as exc:
        raise NoAutorizado("La sesion expiro. Ingresa nuevamente.", codigo="token_expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise NoAutorizado("Sesion no valida. Ingresa nuevamente.") from exc
    if tipo and payload.get("tipo") != tipo:
        raise NoAutorizado("Tipo de token incorrecto.")
    return payload


# ── Cookies y CSRF (doble envio) ─────────────────────────────
def cookie_nombre_refresh() -> str:
    return "ma_refresh"


def cookie_nombre_csrf() -> str:
    return "ma_csrf"


def cookie_refresh_params() -> dict[str, Any]:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": settings.jwt_refresh_ttl_days * 24 * 3600,
    }


def cookie_csrf_params() -> dict[str, Any]:
    # Legible por JavaScript a proposito: es la mitad del patron de doble envio.
    return {
        "httponly": False,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": settings.jwt_refresh_ttl_days * 24 * 3600,
    }


def generar_csrf() -> str:
    return secrets.token_urlsafe(32)


def verificar_csrf(recibido: str | None, esperado: str | None) -> bool:
    if not recibido or not esperado:
        return False
    return hmac.compare_digest(str(recibido), str(esperado))


def hash_token(token: str) -> str:
    """Huella del refresh token para guardarlo sin el valor en claro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_aleatorio(bytes_entrada: int = 32) -> str:
    return secrets.token_urlsafe(bytes_entrada)


def huella(valor: str) -> str:
    digest = hashlib.sha256(valor.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


# ── Cifrado de secretos (licencias) ──────────────────────────
def cifrar(valor: str) -> str | None:
    """Cifra con Fernet. Si no hay clave configurada, no se guarda nada."""
    if not valor:
        return None
    clave = settings.license_encryption_key
    if not clave:
        raise Validacion(
            "No hay clave de cifrado configurada (LICENSE_ENCRYPTION_KEY). "
            "No se pueden guardar claves de licencia."
        )
    from cryptography.fernet import Fernet

    material = hashlib.sha256(clave.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material)).encrypt(valor.encode("utf-8")).decode("ascii")


def descifrar(valor_cifrado: str | None) -> str | None:
    if not valor_cifrado:
        return None
    clave = settings.license_encryption_key
    if not clave:
        return None
    from cryptography.fernet import Fernet, InvalidToken

    material = hashlib.sha256(clave.encode("utf-8")).digest()
    try:
        return Fernet(base64.urlsafe_b64encode(material)).decrypt(
            valor_cifrado.encode("ascii")
        ).decode("utf-8")
    except InvalidToken:
        return None


__all__ = [
    "hash_password",
    "verify_password",
    "necesita_rehash",
    "crear_access_token",
    "crear_refresh_token",
    "decodificar_token",
    "cookie_nombre_refresh",
    "cookie_nombre_csrf",
    "cookie_refresh_params",
    "cookie_csrf_params",
    "generar_csrf",
    "verificar_csrf",
    "hash_token",
    "token_aleatorio",
    "cifrar",
    "descifrar",
    "utcnow",
    "datetime",
]