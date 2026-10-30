"""Dependencias de FastAPI: sesion actual, permisos, CSRF y rate limit."""

from __future__ import annotations

from typing import Annotated, Any, Callable

from bson import ObjectId
from fastapi import Cookie, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import ratelimit
from app.core.config import settings
from app.core.errors import NoAutorizado, Prohibido, Validacion
from app.core.ids import a_id
from app.core.security import cookie_nombre_csrf, verificar_csrf
from app.domain.permissions import (
    es_admin,
    es_tecnico,
    es_usuario,
    matriz_inicial,
    permisos_del_usuario,
    tiene_permiso,
)
from app.services import auth_service

bearer = HTTPBearer(auto_error=False, description="Token de acceso de vida corta")


class SesionActual:
    """Contexto de la peticion: usuario, sesion, csrf y utilidades de permiso."""

    def __init__(self, usuario: dict[str, Any], sesion: dict[str, Any], csrf: str | None, ip: str | None, user_agent: str | None):
        self.usuario = usuario
        self.sesion = sesion
        self.csrf = csrf
        self.ip = ip
        self.user_agent = user_agent

    # ── Identidad ──
    @property
    def id(self) -> ObjectId:
        return self.usuario["_id"]

    @property
    def rol(self) -> str:
        return self.usuario.get("rol", "usuario")

    @property
    def es_admin(self) -> bool:
        return es_admin(self.usuario)

    @property
    def es_tecnico(self) -> bool:
        return es_tecnico(self.usuario)

    @property
    def es_usuario(self) -> bool:
        return es_usuario(self.usuario)

    # ── Permisos ──
    @property
    def permisos(self) -> set[str]:
        return permisos_del_usuario(self.usuario)

    def tiene(self, permiso: str) -> bool:
        return tiene_permiso(self.usuario, permiso)

    def exigir(self, permiso: str) -> None:
        if not self.tiene(permiso):
            raise Prohibido(
                "Tu rol no tiene este permiso habilitado. Pide al administrador que lo active en Configuracion.",
                codigo="sin_permiso",
                detalles={"permiso": permiso},
            )

    def exigir_tecnico(self) -> None:
        if not self.es_tecnico:
            raise Prohibido("Esta accion es del equipo de soporte.")

    def exigir_admin(self) -> None:
        if not self.es_admin:
            raise Prohibido("Esta accion es solo para administradores.")

    def como_dict(self) -> dict[str, Any]:
        """Diccio de usuario con los campos de auditoria."""
        return {
            "_id": self.usuario.get("_id"),
            "nombre": self.usuario.get("nombre", ""),
            "rol": self.usuario.get("rol", "usuario"),
            "superadministrador": self.usuario.get("superadministrador") is True,
        }


def _ip(request: Request) -> str | None:
    # Uvicorn resuelve el proxy de confianza; las cabeceras del navegador no
    # deben permitir eludir límites cambiando X-Real-IP en cada solicitud.
    return request.client.host if request.client else None


async def obtener_sesion(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=cookie_nombre_csrf())] = None,
) -> SesionActual:
    token = credenciales.credentials if credenciales else None
    if not token:
        raise NoAutorizado("No hay sesion activa. Ingresa al sistema.")
    payload = await auth_service.payload_sesion(token)
    return SesionActual(
        payload["usuario"], payload["sesion"], payload["csrf"], _ip(request), request.headers.get("user-agent")
    )


async def exigir_csrf(
    request: Request,
    sesion: Annotated[SesionActual, Depends(obtener_sesion)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> SesionActual:
    """Proteccion CSRF en toda operacion que modifica datos."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return sesion
    if not verificar_csrf(x_csrf_token, sesion.csrf):
        raise Prohibido("Token de seguridad invalido. Recarga la pagina e intenta otra vez.", codigo="csrf_invalido")
    return sesion


async def limite_amplio(request: Request) -> None:
    await ratelimit.comprobar_limite(f"ampio:{_ip(request)}", limite=settings.rate_limit_per_minute)


async def limite_estricto(request: Request) -> None:
    await ratelimit.comprobar_limite(f"estricto:{_ip(request)}", limite=max(20, settings.rate_limit_per_minute // 6))


def id_opcional(valor: Any, campo: str = "id") -> ObjectId | None:
    """
    Id que puede venir vacío. Un valor que **no** es un id se devuelve tal cual.

    Esto se usa para los filtros de las listas, y ahí la diferencia importa: un filtro
    mal formado viene de la barra de direcciones —un marcador guardado, una URL
    editada a mano— y no de un error de quien está usando la pantalla. Antes devolvía
    `422`, y el efecto era una pantalla a medias y dos peticiones fallidas en la
    consola, sin decir nada: el filtro no es aplicable y lo sensato es no aplicarlo.

    Cuando sí tiene que ser un id —el de una ruta, el de un cuerpo— se usa
    `id_requerido`, que sigue fallando si no lo es.
    """
    if valor in (None, "", "null", "todos"):
        return None
    return a_id(valor)


def id_obligatorio(valor: Any, campo: str = "id") -> ObjectId:
    resultado = a_id(valor)
    if resultado is None:
        raise Validacion(f"Identificador de {campo} no valido.")
    return resultado


DependeUsuario = Annotated[SesionActual, Depends(obtener_sesion)]
DependeUsuarioCsrf = Annotated[SesionActual, Depends(exigir_csrf)]


def requiere(permiso: str) -> Callable[[SesionActual], None]:
    """Dependencia reutilizable: exigir un permiso delegable."""

    async def _check(sesion: DependeUsuario) -> None:
        sesion.exigir(permiso)

    return _check


def requiere_admin(sesion: DependeUsuario) -> None:
    sesion.exigir_admin()


def requiere_tecnico(sesion: DependeUsuario) -> None:
    sesion.exigir_tecnico()


MATRIZ_INICIAL = matriz_inicial
