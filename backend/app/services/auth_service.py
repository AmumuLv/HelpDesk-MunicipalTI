"""Autenticacion: ingreso, rotacion de refresh, cierre y estado de sesion."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core import ratelimit
from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import NoAutorizado, Prohibido, Validacion
from app.core.ids import normalizar_texto
from app.core.security import (
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
    generar_csrf,
    hash_password,
    hash_token,
    token_aleatorio,
    verificar_csrf,
    verify_password,
)
from app.core.time import utcnow
from app.domain.permissions import permisos_del_usuario
from app.services import config_service, usuario_service


def _ip(headers: Any) -> str | None:
    if headers is None:
        return None
    directo = headers.get("x-real-ip")
    if directo:
        return directo
    encadenado = headers.get("x-forwarded-for")
    if encadenado:
        return encadenado.split(",")[0].strip()
    return None


async def _crear_sesion(usuario: dict[str, Any], ip: str | None, user_agent: str | None, *, reemplazar: dict | None = None) -> dict[str, Any]:
    db = get_db()
    session_id = reemplazar['session_id'] if reemplazar else token_aleatorio(12)
    refresh_token, expira = crear_refresh_token(
        usuario_id=str(usuario["_id"]), session_id=session_id
    )
    access_token, _ = crear_access_token(
        usuario_id=str(usuario["_id"]), rol=usuario.get("rol", "usuario"), session_id=session_id
    )
    csrf = generar_csrf()
    documento = {
            "usuario_id": usuario["_id"],
            "session_id": session_id,
            "refresh_hash": hash_token(refresh_token),
            "csrf": csrf,
            "ip": ip,
            "user_agent": (user_agent or "")[:300],
            "creado_en": utcnow(),
            "expira": expira,
            "ultimo_uso": utcnow(),
            "revocado": False,
            "token_version": int(usuario.get("token_version", 1)),
        }
    if reemplazar:
        cambios = {k: v for k, v in documento.items() if k not in {'creado_en', 'usuario_id', 'session_id'}}
        resultado = await db['sesiones'].update_one({'_id': reemplazar['_id'], 'refresh_hash': reemplazar['refresh_hash'], 'revocado': False}, {'$set': cambios})
        if not resultado.matched_count:
            raise NoAutorizado('La sesión ya fue renovada o cerrada. Ingresa nuevamente.')
    else:
        # La lista se actualiza atómicamente: dos inicios simultáneos no pueden
        # superar el límite. La cuarta conexión sustituye a la más antigua.
        anteriores = await db['sesiones'].find({'usuario_id': usuario['_id'], 'revocado': False, 'expira': {'$gt': utcnow()}}, {'session_id': 1}).sort('creado_en', 1).to_list(None)
        await db['usuarios'].update_one({'_id': usuario['_id'], 'sesiones_activas': {'$exists': False}}, {'$set': {'sesiones_activas': [s['session_id'] for s in anteriores]}})
        previo = await db['usuarios'].find_one_and_update({'_id': usuario['_id']}, {'$push': {'sesiones_activas': {'$each': [session_id], '$slice': -3}}})
        expulsadas = (previo or {}).get('sesiones_activas', [])[:-2]
        if expulsadas:
            await db['sesiones'].update_many({'usuario_id': usuario['_id'], 'session_id': {'$in': expulsadas}}, {'$set': {'revocado': True, 'revocado_en': utcnow()}})
        await db['sesiones'].insert_one(documento)
    await db["usuarios"].update_one({"_id": usuario["_id"]}, {"$set": {"ultimo_acceso": utcnow()}})
    return {"access_token": access_token, "refresh_token": refresh_token, "csrf": csrf, "expira": expira}


async def ingresar(
    *,
    correo: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
    headers: Any = None,
    acceso: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    correo = normalizar_texto(correo).lower()
    clave_bloqueo = f"{correo}|{ip or 'local'}"
    bloqueado = await ratelimit.esta_bloqueado(clave_bloqueo)
    if bloqueado:
        raise Prohibido(
            f"Demasiados intentos fallidos. Intenta en {bloqueado // 60 + 1} minuto(s).",
            codigo="cuenta_bloqueada",
            detalles={"segundos": bloqueado},
        )
    usuario = await db["usuarios"].find_one({"email_normalizado": correo})
    if usuario is None:
        await ratelimit.registrar_intento_fallido(clave_bloqueo)
        await registrar(
            "auth.login_fallido",
            usuario_nombre=correo,
            entidad="usuario",
            resultado="error",
            resumen="Correo inexistente",
            ip=ip or _ip(headers),
            user_agent=user_agent,
        )
        raise NoAutorizado("Correo o contrasena incorrectos.")
    if not verify_password(password, usuario.get("password_hash")):
        intentos = await ratelimit.registrar_intento_fallido(clave_bloqueo)
        await registrar(
            "auth.login_fallido",
            usuario_id=usuario["_id"],
            usuario_nombre=usuario.get("nombre", ""),
            rol=usuario.get("rol", ""),
            entidad="usuario",
            entidad_id=usuario["_id"],
            resultado="error",
            resumen=f"Contrasena incorrecta (intento {intentos})",
            ip=ip or _ip(headers),
            user_agent=user_agent,
        )
        raise NoAutorizado("Correo o contrasena incorrectos.")
    if not usuario.get("activo", True):
        raise Prohibido("Esta cuenta esta desactivada. Contacta al área de soporte.")

    if acceso == 'ti' and usuario.get('rol') not in {'tecnico', 'administrador'}:
        raise Prohibido('Esta cuenta pertenece a trabajadores. Entra desde Acceso de trabajadores.', codigo='acceso_equivocado')
    if acceso == 'usuario' and usuario.get('rol') in {'tecnico', 'administrador'}:
        raise Prohibido('Esta cuenta pertenece al equipo TI. Entra desde Acceso del equipo TI.', codigo='acceso_equivocado')

    await ratelimit.limpiar_intentos(clave_bloqueo)
    await usuario_service.asegurar_password(usuario["_id"], usuario, password)
    sesion = await _crear_sesion(usuario, ip, user_agent)
    await registrar(
        "auth.login",
        usuario_id=usuario["_id"],
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="sesion",
        resultado="ok",
        resumen="Inicio de sesion",
        ip=ip or _ip(headers),
        user_agent=user_agent,
    )
    return {"usuario": usuario, **sesion}


async def refrescar(*, refresh_token: str, csrf_enviado: str | None, ip: str | None = None) -> dict[str, Any]:
    """Rota el refresh token: el anterior queda invalidado de inmediato."""
    db = get_db()
    payload = decodificar_token(refresh_token, tipo="refresh")
    hash_enviado = hash_token(refresh_token)
    sesion = await db["sesiones"].find_one({"refresh_hash": hash_enviado, "revocado": False})
    if sesion is None:
        raise NoAutorizado("La sesion ya no es valida. Ingresa nuevamente.", codigo="refresh_invalido")
    if not verificar_csrf(csrf_enviado, sesion.get("csrf")):
        raise Prohibido("Token de seguridad invalido. Recarga la pagina.", codigo="csrf_invalido")
    if sesion.get("expira") and sesion["expira"] < utcnow():
        await db["sesiones"].update_one({"_id": sesion["_id"]}, {"$set": {"revocado": True}})
        raise NoAutorizado("La sesion expiro. Ingresa nuevamente.", codigo="token_expirado")

    usuario = await db["usuarios"].find_one({"_id": sesion["usuario_id"]})
    if usuario is None or not usuario.get("activo", True):
        raise Prohibido("La cuenta ya no esta disponible.")
    if 'sesiones_activas' in usuario and sesion['session_id'] not in usuario['sesiones_activas']:
        raise NoAutorizado('La conexión se cerró al iniciar sesión en otro dispositivo.')
    if int(usuario.get("token_version", 1)) != int(sesion.get("token_version", 1)):
        await db["sesiones"].update_one({"_id": sesion["_id"]}, {"$set": {"revocado": True}})
        raise NoAutorizado("Las credenciales cambiaron. Ingresa nuevamente.", codigo="token_invalido")

    nueva = await _crear_sesion(usuario, ip, sesion.get("user_agent"), reemplazar=sesion)
    return {"usuario": usuario, **nueva}


async def cerrar(usuario_id: ObjectId, session_id: str | None = None) -> None:
    consulta: dict[str, Any] = {"usuario_id": usuario_id, "revocado": False}
    if session_id:
        consulta["session_id"] = session_id
    await get_db()["sesiones"].update_many(consulta, {"$set": {"revocado": True, "revocado_en": utcnow()}})
    await get_db()['usuarios'].update_one({'_id': usuario_id}, {'$pull': {'sesiones_activas': session_id}} if session_id else {'$set': {'sesiones_activas': []}})
    await registrar(
        "auth.logout",
        usuario_id=usuario_id,
        entidad="sesion",
        resultado="ok",
        resumen="Cierre de sesion",
    )


async def invalidar_todas(usuario_id: ObjectId) -> None:
    await get_db()["sesiones"].update_many(
        {"usuario_id": usuario_id, "revocado": False}, {"$set": {"revocado": True, "revocado_en": utcnow()}}
    )


async def payload_sesion(access_token: str) -> dict[str, Any]:
    datos = decodificar_token(access_token, tipo="access")
    db = get_db()
    usuario = await db["usuarios"].find_one({"_id": ObjectId(datos["sub"])})
    if usuario is None:
        raise NoAutorizado("La cuenta ya no existe.")
    if not usuario.get("activo", True):
        raise Prohibido("Esta cuenta esta desactivada.")
    sesion = await db["sesiones"].find_one({"session_id": datos.get("sid"), "revocado": False})
    if sesion is None:
        raise NoAutorizado("La sesion no es valida. Ingresa nuevamente.")
    if 'sesiones_activas' in usuario and sesion['session_id'] not in usuario['sesiones_activas']:
        raise NoAutorizado('Se cerró esta conexión al iniciar sesión en otro dispositivo.')
    if int(usuario.get("token_version", 1)) != int(sesion.get("token_version", 1)):
        raise NoAutorizado("Las credenciales cambiaron. Ingresa nuevamente.")
    return {"usuario": usuario, "sesion": sesion, "csrf": sesion.get("csrf")}


async def dispositivos(usuario_id: ObjectId, actual: str | None = None) -> dict:
    filas = await get_db()['sesiones'].find({'usuario_id': usuario_id, 'revocado': False, 'expira': {'$gt': utcnow()}}, {'session_id': 1, 'user_agent': 1, 'creado_en': 1, 'ultimo_uso': 1}).sort('creado_en', -1).to_list(None)
    usuario = await get_db()['usuarios'].find_one({'_id': usuario_id}, {'sesiones_activas': 1}) or {}
    if 'sesiones_activas' in usuario:
        filas = [f for f in filas if f['session_id'] in usuario['sesiones_activas']]
    return {'total': len(filas), 'limite': 3, 'items': [{'id': f['session_id'], 'agente': f.get('user_agent') or 'Navegador', 'inicio': f.get('creado_en'), 'ultimo_uso': f.get('ultimo_uso'), 'actual': f['session_id'] == actual} for f in filas]}


async def crear_admin_inicial(datos: dict[str, Any], *, ip: str | None = None) -> dict[str, Any]:
    db = get_db()
    ya_hay = await db["usuarios"].count_documents({"rol": "administrador"})
    if ya_hay:
        raise Prohibido("Ya existe un administrador. Ingresa con tu cuenta.")
    admin = await usuario_service.crear(
        {
            "nombre": datos["nombre"],
            "email": datos["email"],
            "password": datos["password"],
            "telefono": datos.get("telefono"),
            "rol": "administrador",
        },
        usuario={"nombre": "Instalador", "rol": "sistema", "_id": None},
        es_primer_admin=True,
    )
    await db["usuarios"].update_one({"_id": admin["_id"]}, {"$set": {"debe_cambiar_password": False}})
    await registrar(
        "usuario.crear",
        usuario_nombre="Instalador",
        rol="sistema",
        entidad="usuario",
        entidad_id=admin["_id"],
        resumen=f"Administrador inicial creado: {admin['nombre']}",
        ip=ip,
    )
    return admin


async def estado_sesion(usuario: dict[str, Any], csrf: str | None) -> dict[str, Any]:
    institucion = await config_service.nombre_institucion()
    return {
        "id": usuario["_id"],
        "nombre": usuario.get("nombre", ""),
        "email": usuario.get("email"),
        "rol": usuario.get("rol", "usuario"),
        "superadministrador": usuario.get("rol") == "administrador" and usuario.get("superadministrador") is True,
        "zona_id": usuario.get("zona_id"),
        "zona_nombre": usuario.get("zona_nombre"),
        "oficina_id": usuario.get("oficina_id"),
        "oficina_nombre": usuario.get("oficina_nombre"),
        "iniciales": usuario_service.iniciales(usuario.get("nombre", "")),
        "permisos": sorted(permisos_del_usuario(usuario)),
        "recomendaciones_ia": bool((usuario.get("preferencias") or {}).get("recomendaciones_ia", True)),
        "csrf_token": csrf,
        "institucion": institucion,
        "debe_cambiar_password": bool(usuario.get("debe_cambiar_password")),
    }


async def validar_cambio_password(password_nuevo: str, confirmacion: str) -> None:
    if password_nuevo != confirmacion:
        raise Validacion("Las contrasenas no coinciden.")
    if len(password_nuevo) < 8:
        raise Validacion("La contrasena debe tener al menos 8 caracteres.")


async def fijar_password_inicial(usuario_id: ObjectId, password: str) -> None:
    await get_db()["usuarios"].update_one(
        {"_id": usuario_id},
        {"$set": {"password_hash": hash_password(password), "debe_cambiar_password": False, "actualizado_en": utcnow()}},
    )
