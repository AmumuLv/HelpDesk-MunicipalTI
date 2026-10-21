"""Rutas de autenticacion, sesion e instalacion."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Request, Response

from app.api.deps import (
    DependeUsuario,
    SesionActual,
    exigir_csrf,
    limite_estricto,
    obtener_sesion,
)
from app.core.config import settings
from app.core.errors import Prohibido
from app.core.security import (
    cookie_csrf_params,
    cookie_nombre_csrf,
    cookie_nombre_refresh,
    cookie_refresh_params,
    verificar_csrf,
)
from app.db.estado import estado_instalacion
from app.schemas.common import RespuestaMensaje
from app.schemas.org import AdministradorInicial, CambioPassword, PreferenciaIA, UsuarioSesion
from app.services import auth_service, config_service, ia_service, usuario_service

router = APIRouter(tags=["autenticacion"])

DependeUsuarioCsrf = Annotated[SesionActual, Depends(exigir_csrf)]


def _ip(request: Request) -> str:
    directo = request.headers.get("x-real-ip")
    if directo:
        return directo
    encadenado = request.headers.get("x-forwarded-for")
    if encadenado:
        return encadenado.split(",")[0].strip()
    return request.client.host if request.client else "local"


def _poner_cookies(response: Response, refresh: str, csrf: str) -> None:
    response.set_cookie(cookie_nombre_refresh(), refresh, **cookie_refresh_params())
    response.set_cookie(cookie_nombre_csrf(), csrf, **cookie_csrf_params())


@router.get("/salud")
async def salud() -> dict[str, Any]:
    return {"ok": True}


@router.get("/instalacion", response_model=dict)
async def instalacion() -> dict[str, Any]:
    """Primer arranque guiado: que falta por hacer."""
    return await estado_instalacion()


@router.post("/instalacion/administrador", response_model=UsuarioSesion)
async def crear_administrador(
    datos: AdministradorInicial, request: Request, response: Response
):
    admin = await auth_service.crear_admin_inicial(datos.model_dump(), ip=_ip(request))
    sesion = await auth_service.ingresar(
        correo=datos.email, password=datos.password, ip=_ip(request), user_agent=request.headers.get("user-agent")
    )
    _poner_cookies(response, sesion["refresh_token"], sesion["csrf"])
    estado = await auth_service.estado_sesion(sesion["usuario"], sesion["csrf"])
    return {**estado, "access_token": sesion["access_token"], "refresh_token": sesion["refresh_token"]}


@router.post("/auth/login")
async def login(
    response: Response,
    request: Request,
    _: Annotated[None, Depends(limite_estricto)] = None,
    correo: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    acceso: Literal['usuario', 'ti'] | None = Body(None, embed=True),
):
    sesion = await auth_service.ingresar(
        correo=correo,
        password=password,
        ip=_ip(request),
        user_agent=request.headers.get("user-agent"),
        acceso=acceso,
    )
    _poner_cookies(response, sesion["refresh_token"], sesion["csrf"])
    estado = await auth_service.estado_sesion(sesion["usuario"], sesion["csrf"])
    return {**estado, "access_token": sesion["access_token"], "refresh_token": sesion["refresh_token"]}


@router.post("/auth/refresh")
async def refresh(
    response: Response, request: Request
):
    refresh_token = request.cookies.get(cookie_nombre_refresh())
    csrf_cookie = request.cookies.get(cookie_nombre_csrf())
    csrf_header = request.headers.get("X-CSRF-Token") or csrf_cookie
    if not refresh_token:
        raise Prohibido("No hay sesion activa.")
    if not verificar_csrf(csrf_header, csrf_cookie):
        raise Prohibido("Token de seguridad invalido. Recarga la pagina.", codigo="csrf_invalido")
    sesion = await auth_service.refrescar(refresh_token=refresh_token, csrf_enviado=csrf_header, ip=_ip(request))
    _poner_cookies(response, sesion["refresh_token"], sesion["csrf"])
    estado = await auth_service.estado_sesion(sesion["usuario"], sesion["csrf"])
    return {**estado, "access_token": sesion["access_token"], "refresh_token": sesion["refresh_token"]}


@router.post("/auth/logout")
async def logout(response: Response, sesion: DependeUsuario) -> RespuestaMensaje:
    await auth_service.cerrar(sesion.id, sesion.sesion.get("session_id"))
    response.delete_cookie(cookie_nombre_refresh(), path="/")
    response.delete_cookie(cookie_nombre_csrf(), path="/")
    return RespuestaMensaje(mensaje="Sesion cerrada.")


@router.get("/auth/sesion", response_model=UsuarioSesion)
async def ver_sesion(sesion: DependeUsuario):
    return await auth_service.estado_sesion(sesion.usuario, sesion.csrf)


@router.post("/auth/password")
async def cambiar_password(
    datos: CambioPassword, response: Response, sesion: DependeUsuarioCsrf
) -> RespuestaMensaje:
    await usuario_service.cambiar_password(sesion.id, datos.password_actual, datos.password_nuevo)
    response.delete_cookie(cookie_nombre_refresh(), path='/')
    response.delete_cookie(cookie_nombre_csrf(), path='/')
    return RespuestaMensaje(mensaje="Contrasena actualizada. Vuelve a ingresar.")


@router.get('/auth/dispositivos')
async def dispositivos(sesion: DependeUsuario):
    return await auth_service.dispositivos(sesion.id, sesion.sesion.get('session_id'))


@router.delete('/auth/dispositivos/{session_id}')
async def cerrar_dispositivo(session_id: str, sesion: DependeUsuarioCsrf):
    await auth_service.cerrar(sesion.id, session_id)
    return {'mensaje': 'Conexión cerrada.'}


@router.post("/auth/preferencia-ia")
async def preferencia_ia(datos: PreferenciaIA, sesion: DependeUsuarioCsrf):
    await usuario_service.actualizar(
        sesion.id, {"recomendaciones_ia": datos.recomendaciones_ia}, usuario=sesion.como_dict()
    )
    usuario = await usuario_service.obtener(sesion.id)
    estado = await ia_service.estado_para_usuario(usuario)
    return {
        "recomendaciones_ia": datos.recomendaciones_ia,
        "estado": estado,
        **estado,
        "mensaje": (
            "No veras sugerencias de IA. El sistema seguira aprendiendo de tu trabajo para mejorar en general."
            if not datos.recomendaciones_ia
            else "Recomendaciones de IA activadas."
        ),
    }


@router.get("/auth/preferencia-ia")
async def leer_preferencia_ia(sesion: DependeUsuario):
    """Estado de las recomendaciones para esta persona, con su interruptor."""
    usuario = await usuario_service.obtener(sesion.id)
    estado = await ia_service.estado_para_usuario(usuario)
    return {
        # El interruptor propio, tal como esta guardado
        "recomendaciones_ia": estado['recomendaciones_personales'],
        **estado,
    }


@router.get("/publico/configuracion")
async def configuracion_publica() -> dict[str, Any]:
    """Datos publicos que el frontend necesita antes de iniciar sesion."""
    seccion = await config_service.seccion("institucion")
    return {
        "institucion": seccion.get("nombre", settings.institution_name),
        "nombre_corto": seccion.get("nombre_corto", settings.institution_short_name),
        "correo": seccion.get("correo", settings.contact_email),
        "zona_horaria": settings.business_timezone,
        "version": "1.0.0",
    }
