"""Directorio de usuarios, preferencias de IA y permisos delegables."""

from __future__ import annotations

import re
import math
from pathlib import Path
from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.core.config import settings
from app.core.db import agregar, get_db
from app.core.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from app.core.ids import clave, clave_oscura, id_requerido, normalizar_texto
from app.core.security import hash_password, necesita_rehash, verify_password
from app.core.time import utcnow
from app.domain.constants import ROL_ADMIN, ROL_TECNICO
from app.domain.permissions import CLAVES_PERMISOS, matriz_inicial
from app.services import config_service, org_service

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIN_ESPACIOS = {"_id", "password_hash", "token_version"}


def iniciales(nombre: str) -> str:
    partes = [p for p in normalizar_texto(nombre).split(" ") if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()


def publico(usuario: dict[str, Any], *, con_preferencias: bool = False) -> dict[str, Any]:
    """Proyeccion segura para la API (nunca incluye hash)."""
    salida = {
        "id": usuario["_id"],
        "nombre": usuario.get("nombre", ""),
        "email": usuario.get("email"),
        "telefono": usuario.get("telefono"),
        "anexo": usuario.get("anexo"),
        "cargo": usuario.get("cargo"),
        "rol": usuario.get("rol", "usuario"),
        "activo": bool(usuario.get("activo", True)),
        "zona_id": usuario.get("zona_id"),
        "zona_nombre": usuario.get("zona_nombre"),
        "oficina_id": usuario.get("oficina_id"),
        "oficina_nombre": usuario.get("oficina_nombre"),
        "iniciales": iniciales(usuario.get("nombre", "")),
        # Solo el booleano: la foto se pide aparte en `/usuarios/{id}/foto`, para que
        # listar 25 personas no signifique pedir 25 imágenes. Se lee el campo y no el
        # disco —25 comprobaciones de archivo por listado no vale la pena—; el archivo
        # se verifica al servirlo.
        "tiene_foto": bool((usuario.get("foto") or {}).get("nombre")),
        "ultimo_acceso": usuario.get("ultimo_acceso"),
        "creado_en": usuario.get("creado_en"),
    }
    if con_preferencias:
        salida["recomendaciones_ia"] = bool(
            (usuario.get("preferencias") or {}).get("recomendaciones_ia", True)
        )
    return salida


async def _resolucion_ubicacion(datos: dict[str, Any]) -> tuple[ObjectId | None, ObjectId | None, str | None, str | None]:
    """Devuelve (zona_id, oficina_id, zona_nombre, oficina_nombre) coherentes."""
    db = get_db()
    oficina_id = id_requerido(datos["oficina_id"], "oficina") if datos.get("oficina_id") else None
    zona_id = id_requerido(datos["zona_id"], "zona") if datos.get("zona_id") else None
    if oficina_id:
        oficina = await db["oficinas"].find_one({"_id": oficina_id})
        if oficina is None:
            raise NoEncontrado("La oficina indicada no existe.")
        return oficina["zona_id"], oficina_id, oficina.get("zona_nombre"), oficina.get("nombre")
    if zona_id:
        zona = await db["zonas"].find_one({"_id": zona_id})
        if zona is None:
            raise NoEncontrado("La zona indicada no existe.")
        return zona_id, None, zona.get("nombre"), None
    return None, None, None, None


async def crear(datos: dict[str, Any], *, usuario: dict[str, Any], es_primer_admin: bool = False) -> dict[str, Any]:
    db = get_db()
    nombre = normalizar_texto(datos.get("nombre"))
    if len(nombre) < 3:
        raise Validacion("El nombre debe tener al menos 3 caracteres.")
    email = normalizar_texto(datos.get("email")).lower() or None
    if email and not EMAIL_RE.match(email):
        raise Validacion("El correo no tiene un formato valido.")
    if email and await db["usuarios"].find_one({"email_normalizado": email}):
        raise Conflicto("Ya existe una cuenta con ese correo.", detalles={"email": email})

    zona_id, oficina_id, zona_nombre, oficina_nombre = await _resolucion_ubicacion(datos)
    rol = datos.get("rol", "usuario")
    if rol not in {"usuario", ROL_TECNICO, ROL_ADMIN}:
        raise Validacion("Rol no valido.")
    if rol == ROL_ADMIN and not es_primer_admin:
        if usuario.get("rol") != ROL_ADMIN:
            raise Prohibido("Solo un administrador puede crear cuentas de administrador.")

    permisos = matriz_inicial()
    if datos.get("permisos") and usuario.get("rol") != ROL_ADMIN:
        raise Prohibido("Solo un administrador asigna permisos delegables.")
    for clave_permiso, valor in (datos.get("permisos") or {}).items():
        if clave_permiso in CLAVES_PERMISOS:
            permisos[clave_permiso] = bool(valor)

    valor_ia = datos.get("recomendaciones_ia")
    if valor_ia is None:
        valor_ia = await config_service.valor_por_defecto_ia()

    password = datos.get("password")
    doc: dict[str, Any] = {
        "nombre": nombre,
        "nombre_busqueda": clave_oscura(nombre),
        "email": email,
        "email_normalizado": email,
        "telefono": normalizar_texto(datos.get("telefono")) or None,
        "anexo": normalizar_texto(datos.get("anexo")) or None,
        "cargo": normalizar_texto(datos.get("cargo")) or None,
        "rol": rol,
        "activo": bool(datos.get("activo", True)),
        "zona_id": zona_id,
        "zona_nombre": zona_nombre,
        "oficina_id": oficina_id,
        "oficina_nombre": oficina_nombre,
        "preferencias": {"recomendaciones_ia": bool(valor_ia), "idioma": "es-PE"},
        "permisos": permisos,
        "password_hash": hash_password(password) if password else None,
        "debe_cambiar_password": bool(password) is False,
        "token_version": 1,
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "actualizado_en": utcnow(),
    }
    if password is None:
        doc["debe_cambiar_password"] = True
    resultado = await db["usuarios"].insert_one(doc)
    doc["_id"] = resultado.inserted_id
    if rol in (ROL_TECNICO, ROL_ADMIN):
        await _asegurar_perfil_tecnico(doc["_id"])
    await registrar(
        "usuario.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=resultado.inserted_id,
        resumen=f"Usuario creado: {nombre} ({rol})",
        despues={"nombre": nombre, "rol": rol, "oficina": oficina_nombre, "email": email},
    )
    return doc


async def _asegurar_perfil_tecnico(usuario_id: ObjectId) -> None:
    from app.domain.horario import horario_base
    db = get_db()
    await db["tecnicos_perfil"].update_one(
        {"usuario_id": usuario_id},
        {
            "$setOnInsert": {
                "usuario_id": usuario_id,
                "especialidades": [],
                "categorias": [],
                "zonas_pref": [],
                "capacidad_diaria": 8,
                "horario": horario_base(),
                "activo": True,
                "creado_en": utcnow(),
            }
        },
        upsert=True,
    )


async def actualizar(usuario_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["usuarios"].find_one({"_id": usuario_id})
    if antes is None:
        raise NoEncontrado("Usuario no encontrado.")
    if antes.get("rol") == ROL_ADMIN and usuario.get("rol") != ROL_ADMIN:
        raise Prohibido("Solo un administrador puede modificar una cuenta de administrador.")
    cambios: dict[str, Any] = {}

    if datos.get("nombre"):
        nombre = normalizar_texto(datos["nombre"])
        if len(nombre) < 3:
            raise Validacion("El nombre debe tener al menos 3 caracteres.")
        cambios["nombre"] = nombre
        cambios["nombre_busqueda"] = clave_oscura(nombre)
    if "email" in datos:
        email = normalizar_texto(datos["email"]).lower() or None
        if email and not EMAIL_RE.match(email):
            raise Validacion("El correo no tiene un formato valido.")
        if email and await db["usuarios"].find_one({"email_normalizado": email, "_id": {"$ne": usuario_id}}):
            raise Conflicto("Ya existe una cuenta con ese correo.")
        cambios["email"] = email
        cambios["email_normalizado"] = email
    for campo in ("telefono", "anexo", "cargo"):
        if campo in datos:
            cambios[campo] = normalizar_texto(datos.get(campo)) or None
    if datos.get("rol"):
        nuevo_rol = datos["rol"]
        if nuevo_rol == ROL_ADMIN and usuario.get("rol") != ROL_ADMIN:
            raise Prohibido("Solo un administrador puede crear cuentas de administrador.")
        if antes.get("rol") == ROL_ADMIN and antes.get("activo", True) and nuevo_rol != ROL_ADMIN:
            otros = await db["usuarios"].count_documents(
                {"rol": ROL_ADMIN, "activo": True, "_id": {"$ne": usuario_id}}
            )
            if otros == 0:
                raise Prohibido("Debe quedar al menos un administrador activo.")
        cambios["rol"] = nuevo_rol
    if "activo" in datos:
        activo = bool(datos["activo"])
        if not activo and antes.get("rol") == ROL_ADMIN:
            otros = await db["usuarios"].count_documents(
                {"rol": ROL_ADMIN, "activo": True, "_id": {"$ne": usuario_id}}
            )
            if otros == 0:
                raise Prohibido("Debe quedar al menos un administrador activo.")
        cambios["activo"] = activo
    if "oficina_id" in datos or "zona_id" in datos:
        zona_id, oficina_id, zona_nombre, oficina_nombre = await _resolucion_ubicacion({
            "oficina_id": datos.get("oficina_id"),
            "zona_id": datos.get("zona_id"),
        })
        cambios.update(
            {
                "zona_id": zona_id,
                "zona_nombre": zona_nombre,
                "oficina_id": oficina_id,
                "oficina_nombre": oficina_nombre,
            }
        )
    if "recomendaciones_ia" in datos and datos["recomendaciones_ia"] is not None:
        cambios["preferencias.recomendaciones_ia"] = bool(datos["recomendaciones_ia"])
    if "permisos" in datos and datos["permisos"] is not None:
        if usuario.get("rol") != ROL_ADMIN:
            raise Prohibido("Solo un administrador cambia permisos delegables.")
        permisos = dict(antes.get("permisos") or matriz_inicial())
        for clave_permiso, valor in (datos["permisos"] or {}).items():
            if clave_permiso in CLAVES_PERMISOS:
                permisos[clave_permiso] = bool(valor)
        cambios["permisos"] = permisos
    if not cambios:
        return antes
    cambios["actualizado_en"] = utcnow()
    await db["usuarios"].update_one({"_id": usuario_id}, {"$set": cambios})
    if cambios.get("rol") in (ROL_TECNICO, ROL_ADMIN):
        await _asegurar_perfil_tecnico(usuario_id)
    despues = await db["usuarios"].find_one({"_id": usuario_id})

    accion = "usuario.editar"
    if "activo" in cambios and not cambios["activo"]:
        accion = "usuario.desactivar"
    elif "activo" in cambios:
        accion = "usuario.reactivar"
    elif "password_hash" in cambios:
        accion = "usuario.password"
    resumen = f"Usuario actualizado: {despues['nombre']}"
    if "permisos" in cambios:
        accion = "permiso.cambiar"
        resumen = f"Permisos de {despues['nombre']} actualizados"
    if "preferencias.recomendaciones_ia" in cambios:
        accion = "ia.preferencia"
        resumen = (
            f"Recomendaciones IA {'activadas' if cambios['preferencias.recomendaciones_ia'] else 'desactivadas'}"
            f" por {despues['nombre']}"
        )
    await registrar(
        accion,
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=usuario_id,
        resumen=resumen,
        antes={k: antes.get(k) for k in cambios},
        despues={k: despues.get(k) for k in cambios},
    )
    if 'preferencias.recomendaciones_ia' in cambios:
        from app.services.notificaciones_service import avisar_preferencia_ia
        await avisar_preferencia_ia(usuario_id, cambios['preferencias.recomendaciones_ia'])
    return despues


async def desactivar(usuario_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    return await actualizar(usuario_id, {"activo": False}, usuario=usuario)


async def listar(
    *,
    zona_id: ObjectId | None = None,
    oficina_id: ObjectId | None = None,
    rol: str | None = None,
    solo_activos: bool = True,
    texto: str | None = None,
    pagina: int = 1,
    por_pagina: int = 25,
) -> dict[str, Any]:
    db = get_db()
    consulta: dict[str, Any] = {}
    if solo_activos:
        consulta["activo"] = True
    if zona_id:
        consulta["zona_id"] = zona_id
    if oficina_id:
        consulta["oficina_id"] = oficina_id
    if rol:
        consulta["rol"] = rol
    if texto:
        termino = re.escape(normalizar_texto(texto))
        consulta["$or"] = [
            {"nombre": {"$regex": termino, "$options": "i"}},
            {"email": {"$regex": termino, "$options": "i"}},
            {"telefono": {"$regex": termino, "$options": "i"}},
            {"anexo": {"$regex": termino, "$options": "i"}},
        ]
        termino_nombre = clave_oscura(texto)
        if termino_nombre:
            consulta["$or"].append({"nombre_busqueda": {"$regex": re.escape(termino_nombre)}})
    total = await db["usuarios"].count_documents(consulta)
    documentos = await (
        db["usuarios"]
        .find(consulta)
        .sort([("creado_en", -1), ("_id", -1)])
        .skip(max(pagina - 1, 0) * por_pagina)
        .limit(por_pagina)
        .to_list(None)
    )
    items = [publico(u, con_preferencias=True) for u in documentos]
    import math

    return {
        "items": items,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": math.ceil(total / por_pagina) if por_pagina else 0,
    }


async def buscar_para_afectado(
    *, zona_id: ObjectId, texto: str | None = None, limite: int = 20, incluir_inactivos: bool = False
) -> list[dict[str, Any]]:
    """Compañeros de una misma oficina (paso 2 del reporte)."""
    db = get_db()
    consulta: dict[str, Any] = {"zona_id": zona_id}
    if not incluir_inactivos:
        consulta["activo"] = True
    if texto:
        consulta["$or"] = [
            {"nombre": {"$regex": normalizar_texto(texto), "$options": "i"}},
            {"nombre_busqueda": {"$regex": clave_oscura(texto)}},
        ]
    documentos = await (
        db["usuarios"].find(consulta, {"nombre": 1, "oficina_id": 1, "oficina_nombre": 1, "rol": 1, "activo": 1})
        .sort("nombre", 1)
        .limit(limite)
        .to_list(None)
    )
    return [
        {
            "id": d["_id"],
            "nombre": d.get("nombre", ""),
            "iniciales": iniciales(d.get("nombre", "")),
            "oficina_id": d.get("oficina_id"),
            "oficina_nombre": d.get("oficina_nombre"),
            "es_registrado": True,
            "activo": bool(d.get("activo", True)),
        }
        for d in documentos
    ]


async def buscar_global(texto: str, *, limite: int = 20, solo_activos: bool = True) -> list[dict[str, Any]]:
    db = get_db()
    consulta: dict[str, Any] = {}
    if solo_activos:
        consulta["activo"] = True
    if texto:
        consulta["$or"] = [
            {"nombre": {"$regex": normalizar_texto(texto), "$options": "i"}},
            {"email": {"$regex": normalizar_texto(texto), "$options": "i"}},
            {"nombre_busqueda": {"$regex": clave_oscura(texto)}},
        ]
    documentos = await (
        db["usuarios"].find(consulta, {"nombre": 1, "email": 1, "oficina_id": 1, "oficina_nombre": 1, "zona_id": 1, "zona_nombre": 1, "activo": 1})
        .sort("nombre", 1)
        .limit(limite)
        .to_list(None)
    )
    return [
        {
            "id": d["_id"],
            "nombre": d.get("nombre", ""),
            "iniciales": iniciales(d.get("nombre", "")),
            "email": d.get("email"),
            "oficina_nombre": d.get("oficina_nombre"),
            "zona_nombre": d.get("zona_nombre"),
            "es_registrado": True,
            "activo": bool(d.get("activo", True)),
        }
        for d in documentos
    ]


async def obtener(usuario_id: ObjectId) -> dict[str, Any]:
    usuario = await get_db()["usuarios"].find_one({"_id": usuario_id})
    if usuario is None:
        raise NoEncontrado("Usuario no encontrado.")
    return usuario


async def detalle(usuario_id: ObjectId) -> dict[str, Any]:
    db = get_db()
    usuario = await db["usuarios"].find_one({"_id": usuario_id})
    if usuario is None:
        raise NoEncontrado("Usuario no encontrado.")
    salida = publico(usuario, con_preferencias=True)
    salida["id"] = usuario["_id"]

    activos = await (db["activos"].find({"responsable_id": usuario_id}).to_list(None))
    from app.services.inventario_service import calcular_completitud

    equipos: list[dict[str, Any]] = []
    for activo in activos:
        completeness = await calcular_completitud(activo)
        equipos.append(
            {
                "id": activo["_id"],
                "nombre": activo.get("nombre_equipo") or activo.get("modelo") or activo.get("marca") or activo.get("tipo"),
                "tipo": activo.get("tipo"),
                "codigo_patrimonial": activo.get("codigo_patrimonial"),
                "estado": activo.get("estado"),
                "oficina_nombre": activo.get("oficina_nombre"),
                "conjunto_nombre": activo.get("conjunto_nombre"),
                "completitud": completeness["porcentaje"],
                "opciones_avanzadas": bool(activo.get("opciones_avanzadas")),
            }
        )
    salida["equipos_responsable"] = equipos
    salida["historial_responsabilidad"] = await db["historial_responsables"].find(
        {"responsable_id": usuario_id}, {"_id": 0}
    ).sort("fecha", -1).limit(50).to_list(None)

    consulta_tickets: dict[str, Any] = {"$or": [{"reportante_id": usuario_id}, {"afectado_id": usuario_id}]}
    from app.core.serializacion import normalizar
    salida["tickets_recientes"] = normalizar(await db["tickets"].find(
        consulta_tickets,
        {"codigo": 1, "asunto": 1, "estado": 1, "prioridad": 1, "creado_en": 1, "reportante_id": 1, "afectado_id": 1},
    ).sort("creado_en", -1).limit(20).to_list(None))
    salida["tickets_creados"] = await db["tickets"].count_documents({"reportante_id": usuario_id})
    salida["tickets_afectado"] = await db["tickets"].count_documents({"afectado_id": usuario_id})
    salida["tickets_activos"] = await db["tickets"].count_documents(
        {**consulta_tickets, "estado": {"$nin": ["resuelto", "cerrado"]}}
    )
    estadisticas = await agregar(
        "tickets",
        [
            {"$match": {"afectado_id": usuario_id, "satisfaccion": {"$ne": None}}},
            {"$group": {"_id": "$satisfaccion", "total": {"$sum": 1}}},
        ],
    )
    if estadisticas:
        salida["satisfaccion_promedio"] = round(
            sum(f["_id"] * f["total"] for f in estadisticas) / sum(f["total"] for f in estadisticas), 2
        )
    from app.services import horario_service

    salida["horario"] = await horario_service.obtener_horario(usuario_id)
    salida["carga_actual"] = await db["tickets"].count_documents(
        {"tecnico_id": usuario_id, "estado": {"$nin": ["resuelto", "cerrado"]}}
    )
    perfil = await db["tecnicos_perfil"].find_one({"usuario_id": usuario_id}) or {}
    salida["especiales"] = perfil.get("especialidades", []) or []
    salida["permisos"] = {k: bool(v) for k, v in (usuario.get("permisos") or {}).items()}
    return salida


async def tickets_de_usuario(
    usuario_id: ObjectId, *, relacion: str = "todos", estado: str | None = None, pagina: int = 1, por_pagina: int = 10,
    activo_id: ObjectId | None = None, conjunto_id: ObjectId | None = None
) -> dict[str, Any]:
    """Historial completo y paginado, incluyendo el trabajo asignado al personal TI."""
    await obtener(usuario_id)
    db = get_db()
    relaciones = {
        "creados": {"reportante_id": usuario_id},
        "afectado": {"afectado_id": usuario_id},
        "asignados": {"tecnico_id": usuario_id},
    }
    from app.services.historial_inventario_service import inventario_persona, consulta_conjunto
    equipos, conjuntos = await inventario_persona(usuario_id)
    patrimonio = [{'activo_id': {'$in': [e['_id'] for e in equipos]}}]
    for conjunto in conjuntos:
        patrimonio.append(await consulta_conjunto(conjunto['_id']))
    consulta = relaciones.get(relacion) or {'$or': [*relaciones.values(), *patrimonio]}
    if activo_id:
        if activo_id not in {e['_id'] for e in equipos}:
            raise Validacion('El equipo no pertenece a esta persona.')
        consulta = {'activo_id': activo_id}
    if conjunto_id:
        if conjunto_id not in {c['_id'] for c in conjuntos}:
            raise Validacion('El conjunto no pertenece a esta persona.')
        conjunto_consulta = await consulta_conjunto(conjunto_id)
        consulta = {'$and': [consulta, conjunto_consulta]} if activo_id else conjunto_consulta
    consulta['eliminado'] = {'$ne': True}
    if estado:
        if estado not in {'nuevo', 'en_progreso', 'en_espera', 'resuelto', 'cerrado'}:
            raise Validacion('El estado del ticket no es válido.')
        consulta['estado'] = {'$in': ['cerrado', 'resuelto']} if estado in {'cerrado', 'resuelto'} else estado
    total = await db["tickets"].count_documents(consulta)
    paginas = math.ceil(total / por_pagina)
    pagina = min(pagina, max(1, paginas))
    documentos = await db["tickets"].find(consulta).sort([("creado_en", -1), ("_id", -1)]).skip((pagina - 1) * por_pagina).limit(por_pagina).to_list(None)
    equipos_ids = [ticket["activo_id"] for ticket in documentos if ticket.get("activo_id")]
    equipos = {equipo["_id"]: equipo for equipo in await db["activos"].find(
        {"_id": {"$in": equipos_ids}},
        {"nombre_equipo": 1, "tipo": 1, "marca": 1, "modelo": 1, "codigo_patrimonial": 1},
    ).to_list(None)} if equipos_ids else {}
    for ticket in documentos:
        equipo = equipos.get(ticket.get("activo_id"), {})
        ticket["activo_nombre"] = ticket.get("activo_nombre") or equipo.get("nombre_equipo") or equipo.get("modelo") or equipo.get("marca") or ticket.get("activo_no_identificado")
        ticket["activo_tipo"] = ticket.get("activo_tipo") or equipo.get("tipo")
        ticket["activo_codigo_patrimonial"] = equipo.get("codigo_patrimonial")
    from app.services.ticket_service import _resumen
    return {"items": [await _resumen(t) for t in documentos], "total": total, "pagina": pagina,
            "por_pagina": por_pagina, "total_paginas": paginas}


async def opciones_historial(usuario_id):
    await obtener(usuario_id)
    from app.services.historial_inventario_service import inventario_persona, consulta_conjunto
    equipos, conjuntos = await inventario_persona(usuario_id)
    salida = []
    for conjunto in conjuntos:
        consulta = await consulta_conjunto(conjunto['_id'])
        consulta['eliminado'] = {'$ne': True}
        salida.append({'id': str(conjunto['_id']), 'nombre': conjunto.get('nombre', 'Computadora'),
                       'tickets': await get_db().tickets.count_documents(consulta)})
    return {'equipos': [{'id': str(e['_id']), 'nombre': e.get('nombre_equipo') or e.get('tipo', 'Equipo'),
                         'conjunto_id': str(e['conjunto_id']) if e.get('conjunto_id') else None} for e in equipos], 'conjuntos': salida}


async def cambiar_password(usuario_id: ObjectId, password_actual: str, password_nuevo: str) -> None:
    db = get_db()
    usuario = await db["usuarios"].find_one({"_id": usuario_id})
    if usuario is None:
        raise NoEncontrado("Usuario no encontrado.")
    if usuario.get('rol') == 'usuario':
        raise Prohibido('Solicita el cambio de contraseña al equipo TI. El administrador debe restablecerla.')
    if not verify_password(password_actual, usuario.get("password_hash")):
        raise Prohibido("La contrasena actual no es correcta.")
    await db["usuarios"].update_one(
        {"_id": usuario_id},
        {
            "$set": {
                "password_hash": hash_password(password_nuevo),
                "debe_cambiar_password": False,
                "actualizado_en": utcnow(),
                "token_version": int(usuario.get("token_version", 1)) + 1,
            }
        },
    )
    await db["sesiones"].update_many({"usuario_id": usuario_id, "revocado": False}, {"$set": {"revocado": True}})
    await registrar(
        "usuario.password",
        usuario_id=usuario_id,
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=usuario_id,
        resumen="Contrasena actualizada por el propio usuario",
    )


async def restablecer_password(
    usuario_id: ObjectId,
    password: str,
    *,
    usuario: dict[str, Any],
) -> None:
    if usuario.get('rol') != ROL_ADMIN:
        raise Prohibido('Solo un administrador puede restablecer contraseñas.')
    db = get_db()
    objetivo = await db["usuarios"].find_one({"_id": usuario_id})
    if objetivo is None:
        raise NoEncontrado("Usuario no encontrado.")
    if objetivo.get("rol") == ROL_ADMIN and usuario.get("rol") != ROL_ADMIN:
        raise Prohibido("Solo un administrador puede restablecer la contraseña de otro administrador.")
    await db["usuarios"].update_one(
        {"_id": usuario_id},
        {
            "$set": {
                "password_hash": hash_password(password),
                "debe_cambiar_password": False,
                "actualizado_en": utcnow(),
                "token_version": int(objetivo.get("token_version", 1)) + 1,
            }
        },
    )
    await db["sesiones"].update_many({"usuario_id": usuario_id, "revocado": False}, {"$set": {"revocado": True}})
    await registrar(
        "usuario.password",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=usuario_id,
        resumen=f"Contraseña restablecida por el equipo TI para {objetivo.get('nombre', 'la persona')}",
    )


async def asegurar_password(usuario_id: ObjectId, usuario: dict[str, Any], password: str) -> bool:
    """Rehashea si el algoritmo cambio. Devuelve True si se actualizo."""
    hash_guardado = usuario.get("password_hash")
    if not hash_guardado or not necesita_rehash(hash_guardado):
        return False
    await get_db()["usuarios"].update_one(
        {"_id": usuario_id}, {"$set": {"password_hash": hash_password(password), "actualizado_en": utcnow()}}
    )
    return True


async def asegurar_admin_activo() -> None:
    """Valida que exista un administrador activo (arranque guiado)."""
    total = await get_db()["usuarios"].count_documents({"rol": ROL_ADMIN, "activo": True})
    if total == 0:
        raise Prohibido("Todavia no existe un administrador activo.")


async def aplicar_permisos(usuario_id: ObjectId, cambios: dict[str, bool], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["usuarios"].find_one({"_id": usuario_id})
    if antes is None:
        raise NoEncontrado("Usuario no encontrado.")
    permisos = dict(antes.get("permisos") or matriz_inicial())
    aplicados: dict[str, bool] = {}
    for clave_permiso, valor in cambios.items():
        if clave_permiso not in CLAVES_PERMISOS:
            raise Validacion(f"Permiso desconocido: {clave_permiso}")
        permisos[clave_permiso] = bool(valor)
        aplicados[clave_permiso] = bool(valor)
    await db["usuarios"].update_one(
        {"_id": usuario_id}, {"$set": {"permisos": permisos, "actualizado_en": utcnow()}}
    )
    await registrar(
        "permiso.cambiar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=usuario_id,
        resumen=f"Permisos delegables de {antes.get('nombre')}",
        antes={k: (antes.get("permisos") or {}).get(k) for k in aplicados},
        despues=aplicados,
        contexto={"cambios": aplicados},
    )
    return permisos


async def companeros_de_oficina(
    oficina_id: ObjectId, *, excluir_id: ObjectId | None = None, texto: str | None = None
) -> list[dict[str, Any]]:
    db = get_db()
    consulta: dict[str, Any] = {"oficina_id": oficina_id, "activo": True}
    if excluir_id:
        consulta["_id"] = {"$ne": excluir_id}
    if texto:
        consulta["$or"] = [
            {"nombre": {"$regex": normalizar_texto(texto), "$options": "i"}},
            {"nombre_busqueda": {"$regex": clave_oscura(texto)}},
        ]
    documentos = await (
        db["usuarios"].find(consulta, {"nombre": 1}).sort("nombre", 1).limit(60).to_list(None)
    )
    return [
        {"id": d["_id"], "nombre": d.get("nombre", ""), "iniciales": iniciales(d.get("nombre", ""))}
        for d in documentos
    ]


async def por_oficina(oficina_id: ObjectId, *, solo_activos: bool = True) -> list[dict[str, Any]]:
    db = get_db()
    consulta: dict[str, Any] = {"oficina_id": oficina_id}
    if solo_activos:
        consulta["activo"] = True
    documentos = await (db["usuarios"].find(consulta).sort("nombre", 1).to_list(None))
    return [publico(u, con_preferencias=True) for u in documentos]


async def resolver_solicitante_no_registrado(
    datos: dict[str, Any], *, usuario: dict[str, Any]
) -> tuple[ObjectId | None, dict[str, Any]]:
    """Crea (o reutiliza) un usuario a partir del formulario minimo, o devuelve None.

    Si el formulario pide crear usuario y hay datos suficientes, crea la cuenta.
    Si no, devuelve un descriptor sin persistir: el ticket guarda el nombre.
    """
    nombre = normalizar_texto(datos.get("nombre"))
    if len(nombre) < 3:
        raise Validacion("Escribe el nombre de la persona afectada (minimo 3 caracteres).")
    db = get_db()
    existente = await db["usuarios"].find_one({"nombre_busqueda": clave_oscura(nombre), "activo": True})
    if existente:
        return existente["_id"], existente
    if not datos.get("crear_usuario"):
        return None, {
            "nombre": nombre,
            "telefono": normalizar_texto(datos.get("telefono")) or None,
            "anexo": normalizar_texto(datos.get("anexo")) or None,
            "zona_id": datos.get("zona_id"),
            "oficina_id": datos.get("oficina_id"),
            "registrado": False,
        }
    nuevo = await crear(datos, usuario=usuario)
    return nuevo["_id"], nuevo


async def recalcular_ubicacion(usuario: dict[str, Any]) -> dict[str, Any]:
    """Completa zona a partir de la oficina (invariante de la jerarquia)."""
    if usuario.get("oficina_id") and not usuario.get("zona_id"):
        oficina = await org_service.obtener_oficina(usuario["oficina_id"])
        return {"zona_id": oficina["zona_id"], "zona_nombre": oficina.get("zona_nombre")}
    return {}


# ══ Foto de perfil ══
#
# Se guarda como archivo junto a los adjuntos, no dentro del documento: una foto
# pesa entre 50 y 500 KB y el documento de usuario se lee en cada lista del sistema.
# El documento solo guarda la referencia.
#
# El contenido se comprueba con la misma funcion que valida los adjuntos, que no se
# fia de la extension ni del `content-type` que declara el navegador, sino de los
# primeros bytes del archivo. Aparte se exige que sea una imagen: para la foto tiene
# que servir `validar()` completo, no solo las imagenes que permite.

MIMES_FOTO = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp"}
MAX_FOTO_BYTES = settings.max_upload_bytes


def ruta_foto(usuario_id: ObjectId, mime: str) -> Path:
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}.get(mime, ".img")
    return Path(settings.upload_dir) / "fotos" / f"{usuario_id}{extension}"


async def guardar_foto(
    usuario_id: ObjectId,
    contenido: bytes,
    *,
    nombre_original: str,
    mime_declarado: str,
    usuario: dict[str, Any],
) -> dict[str, Any]:
    """Guarda la foto de una cuenta y devuelve la referencia."""
    from app.services import adjuntos_service

    db = get_db()
    if await db["usuarios"].find_one({"_id": usuario_id}) is None:
        raise NoEncontrado("Usuario no encontrado.")
    if len(contenido) > MAX_FOTO_BYTES:
        raise Validacion(
            f"La foto supera los {settings.max_upload_mb} MB.",
            detalles={"limite_mb": settings.max_upload_mb, "tamano_mb": round(len(contenido) / 1048576, 2)},
        )
    try:
        _, mime = adjuntos_service.validar(nombre_original, mime_declarado, len(contenido), contenido)
    except Validacion:
        raise
    if mime not in MIMES_FOTO:
        raise Validacion(
            "La foto debe ser una imagen.",
            detalles={"formatos": ["JPG", "PNG", "WEBP", "GIF"]},
        )
    if settings.clamav_enabled:
        await adjuntos_service._escanear_con_clamav(contenido)

    from starlette.concurrency import run_in_threadpool
    from app.services.imagenes_service import optimizar
    contenido, mime = await run_in_threadpool(optimizar, contenido, mime)

    destino = ruta_foto(usuario_id, mime)
    destino.parent.mkdir(parents=True, exist_ok=True)
    from tempfile import NamedTemporaryFile
    temporal = None
    try:
        with NamedTemporaryFile(dir=destino.parent, delete=False) as archivo:
            temporal = Path(archivo.name)
            archivo.write(contenido)
        temporal.replace(destino)
    finally:
        if temporal:
            temporal.unlink(missing_ok=True)
    # Si cambia el formato, el archivo anterior queda suelto en disco.
    for viejo in destino.parent.glob(f"{usuario_id}.*"):
        if viejo != destino:
            viejo.unlink(missing_ok=True)

    await db["usuarios"].update_one(
        {"_id": usuario_id},
        {
            "$set": {
                "foto": {
                    "nombre": destino.name,
                    "mime": mime,
                    "tamano": len(contenido),
                    "actualizado_en": utcnow(),
                },
                "actualizado_en": utcnow(),
            }
        },
    )
    await registrar(
        "usuario.foto",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=str(usuario_id),
        resumen=f"Foto de perfil actualizada ({mime}, {len(contenido) // 1024} KB)",
    )
    return {"foto": True, "mime": mime, "tamano": len(contenido)}


async def quitar_foto(usuario_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    documento = await db["usuarios"].find_one({"_id": usuario_id})
    if documento is None:
        raise NoEncontrado("Usuario no encontrado.")
    for viejo in (Path(settings.upload_dir) / "fotos").glob(f"{usuario_id}.*"):
        viejo.unlink(missing_ok=True)
    await db["usuarios"].update_one({"_id": usuario_id}, {"$unset": {"foto": ""}})
    await registrar(
        "usuario.foto",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="usuario",
        entidad_id=str(usuario_id),
        resumen="Foto de perfil quitada",
    )
    return {"foto": False}


def archivo_foto(usuario: dict[str, Any]) -> Path | None:
    """Ruta del archivo de la foto, o None si no hay o ya no está en disco."""
    nombre = (usuario.get("foto") or {}).get("nombre")
    if not nombre:
        return None
    ruta = Path(settings.upload_dir) / "fotos" / nombre
    return ruta if ruta.is_file() else None
