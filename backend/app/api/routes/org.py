"""Rutas de zonas, oficinas y directorio de usuarios, con perfiles navegables."""

from __future__ import annotations

from typing import Annotated, Any
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import (
    DependeUsuario,
    DependeUsuarioCsrf,
    id_opcional,
    requiere,
    requiere_admin,
    requiere_tecnico,
)
from app.core.db import agregar, get_db
from app.core.serializacion import normalizar
from app.domain.constants import ROL_TECNICO
from app.schemas.org import (
    OficinaActualizar,
    OficinaCrear,
    RestablecerPassword,
    UsuarioActualizar,
    UsuarioCrear,
    ZonaActualizar,
    ZonaCrear,
)
from app.services import (
    calidad_service,
    inventario_service,
    org_service,
    ticket_service,
    usuario_service,
)

router = APIRouter(tags=["organizacion"])


@router.get('/portal/equipos-oficina-tipos')
async def tipos_equipos_oficina(sesion: DependeUsuario):
    from app.services.historial_inventario_service import tipos_oficina
    return {'tipos': await tipos_oficina(sesion.usuario.get('oficina_id'))}

DependeEditarOrg = Annotated[None, Depends(requiere("org.editar"))]
DependeVerOrg = Annotated[None, Depends(requiere('org.ver'))]
DependeEditarUsuarios = Annotated[None, Depends(requiere("usuarios.editar"))]
DependeVerUsuarios = Annotated[None, Depends(requiere("usuarios.ver"))]


# ── Zonas ────────────────────────────────────────────────────
@router.get("/zonas")
async def listar_zonas(sesion: DependeUsuario, solo_activas: bool = Query(True)):
    return {"items": normalizar(await org_service.listar_zonas(solo_activas=solo_activas))}


@router.post("/zonas", status_code=201)
async def crear_zona(datos: ZonaCrear, sesion: DependeUsuarioCsrf, _: DependeEditarOrg):
    zona_id = await org_service.crear_zona(datos.model_dump(), usuario=sesion.como_dict())
    return normalizar(await org_service.obtener_zona(zona_id))


@router.get("/zonas/{zona_id}")
async def obtener_zona(zona_id: str, sesion: DependeUsuario, _: DependeVerOrg):
    from app.core.ids import id_requerido

    zona = await org_service.obtener_zona(id_requerido(zona_id, "zona"))
    db = get_db()
    desde, hasta = ticket_service.rango_30d()
    zona_id_obj = zona["_id"]
    total_oficinas = await db["oficinas"].count_documents({"zona_id": zona_id_obj, "activa": True})
    total_usuarios = await db["usuarios"].count_documents({"zona_id": zona_id_obj, "activo": True})
    total_equipos = await db["activos"].count_documents({"zona_id": zona_id_obj, "activo": {"$ne": False}})
    tickets_abiertos = await db["tickets"].count_documents(
        {"zona_id": zona_id_obj, "estado": {"$nin": ticket_service.ESTADOS_CERRADOS}}
    )
    tickets_periodo = await db["tickets"].count_documents(
        {"zona_id": zona_id_obj, "creado_en": {"$gte": desde}}
    )
    tiempos = [
        t["tiempo_resolucion_min"]
        for t in await (
            db["tickets"]
            .find({"zona_id": zona_id_obj, "tiempo_resolucion_min": {"$ne": None}}, {"tiempo_resolucion_min": 1})
            .to_list(None)
        )
    ]
    categorias = await agregar("tickets", [
            {"$match": {"zona_id": zona_id_obj, "creado_en": {"$gte": desde}}},
            {"$group": {"_id": "$categoria", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
        ])
    oficinas_fallas = await agregar("tickets", [
            {"$match": {"zona_id": zona_id_obj, "oficina_id": {"$ne": None}, "eliminado": {"$ne": True}}},
            {"$group": {"_id": "$oficina_id", "nombre_registrado": {"$last": "$oficina_nombre"}, "total": {"$sum": 1}}},
            {"$sort": {"total": -1, "_id": 1}},
            {"$lookup": {"from": "oficinas", "localField": "_id", "foreignField": "_id", "as": "oficina"}},
            {"$set": {"nombre": {"$ifNull": [{"$arrayElemAt": ["$oficina.nombre", 0]}, "$nombre_registrado"]}}},
        ])
    calidad = await calidad_service.resumen(zona_id=zona_id_obj, limite_pendientes=0)
    return {
        "id": str(zona["_id"]),
        "nombre": zona["nombre"],
        "descripcion": zona.get("descripcion"),
        "activa": bool(zona.get("activa", True)),
        "color_indice": zona.get("color_indice", 1),
        "creado_en": zona.get("creado_en"),
        "total_oficinas": total_oficinas,
        "total_usuarios": total_usuarios,
        "total_equipos": total_equipos,
        "tickets_abiertos": tickets_abiertos,
        "tickets_periodo": tickets_periodo,
        "tiempo_medio_resolucion_min": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
        "categorias_frecuentes": [{"categoria": c["_id"] or "Sin clasificar", "total": c["total"]} for c in categorias],
        "oficinas_con_mas_fallas": [
            {"id": str(e["_id"]) if e.get("oficina") else None, "nombre": e.get("nombre") or "Oficina sin identificar", "tickets": e["total"]}
            for e in oficinas_fallas
        ],
        "completitud_inventario": calidad["porcentaje_global"],
        "oficinas": normalizar(await org_service.listar_oficinas(zona_id=zona_id_obj)),
        "puede_crear_oficina": sesion.tiene("org.editar"),
    }


@router.patch("/zonas/{zona_id}")
async def actualizar_zona(zona_id: str, datos: ZonaActualizar, sesion: DependeUsuarioCsrf, _: DependeEditarOrg):
    from app.core.ids import id_requerido

    zona = await org_service.actualizar_zona(
        id_requerido(zona_id, "zona"), datos.model_dump(exclude_unset=True), usuario=sesion.como_dict()
    )
    return normalizar(zona)


@router.get("/zonas/{zona_id}/borrado")
async def bloqueos_borrado_zona(zona_id: str, sesion: DependeUsuario, _: DependeVerOrg):
    """Qué se perdería al borrar la zona, antes de borrarla.

    Lo pide el diálogo de confirmación. Usa la misma función que el borrado, así que
    el aviso y la razón por la que se rechaza después no pueden decir cosas distintas.
    """
    from app.core.ids import id_requerido

    return await org_service.bloqueos_borrado_zona(id_requerido(zona_id, "zona"))


@router.delete("/zonas/{zona_id}")
async def eliminar_zona(zona_id: str, sesion: DependeUsuarioCsrf, _: DependeEditarOrg) -> dict[str, Any]:
    from app.core.ids import id_requerido

    await org_service.eliminar_zona(id_requerido(zona_id, "zona"), usuario=sesion.como_dict())
    return {"mensaje": "Zona eliminada."}


# ── Oficinas ─────────────────────────────────────────────────
@router.get("/oficinas")
async def listar_oficinas(sesion: DependeUsuario, zona_id: str | None = None, solo_activas: bool = Query(True)):
    return {
        "items": normalizar(
            await org_service.listar_oficinas(
                zona_id=id_opcional(zona_id, "zona"), solo_activas=solo_activas
            )
        )
    }


@router.post("/oficinas", status_code=201)
async def crear_oficina(datos: OficinaCrear, sesion: DependeUsuarioCsrf, _: DependeEditarOrg):
    oficina_id = await org_service.crear_oficina(datos.model_dump(), usuario=sesion.como_dict())
    return normalizar(await org_service.obtener_oficina(oficina_id))


@router.get("/oficinas/{oficina_id}")
async def obtener_oficina(oficina_id: str, sesion: DependeUsuario, _: DependeVerOrg):
    from app.core.ids import id_requerido

    oficina = await org_service.obtener_oficina(id_requerido(oficina_id, "oficina"))
    db = get_db()
    oficina_id_obj = oficina["_id"]
    desde, hasta = ticket_service.rango_30d()
    usuarios = await usuario_service.por_oficina(oficina_id_obj)
    activos = await (db["activos"].find({"oficina_id": oficina_id_obj, "activo": {"$ne": False}}).to_list(None))
    uso_comun = []
    por_usuario: dict[str, dict[str, Any]] = {}
    for activo in activos:
        completeness = await inventario_service.calcular_completitud(activo)
        fila = {
            "id": activo["_id"],
            "nombre": activo.get("nombre_equipo") or activo.get("modelo") or activo.get("tipo"),
            "tipo": activo.get("tipo"),
            "codigo_patrimonial": activo.get("codigo_patrimonial"),
            "estado": activo.get("estado"),
            "conjunto_nombre": activo.get("conjunto_nombre"),
            "responsable_nombre": activo.get("responsable_nombre"),
            'responsable_id': activo.get('responsable_id'),
            "faltantes": completeness["faltantes"],
        }
        if not activo.get('responsable_id') and not activo.get('responsable_nombre'):
            uso_comun.append(fila)
        else:
            # El grupo se forma por el **id** del responsable, no por su nombre.
            #
            # Con el nombre, dos personas que se llamen igual terminaban en la misma
            # fila y sus equipos se sumaban como si fueran de una; y un nombre con un
            # espacio de más o una tilde distinta partía el grupo en dos, dejando
            # fuera a quien quedaba y que aparecía «sin equipo» teniendo equipos. El
            # nombre va solo para poder leerlo, y únicamente si no hay id con el que
            # agrupar.
            clave = activo.get("responsable_id") or f"nombre:{activo.get('responsable_nombre')}"
            grupo = por_usuario.setdefault(
                clave,
                {
                    "responsable_id": activo.get("responsable_id"),
                    "responsable": activo.get("responsable_nombre") or "Sin responsable",
                    "equipos": [],
                },
            )
            grupo["equipos"].append(fila)
    calidad = await calidad_service.resumen(oficina_id=oficina_id_obj, limite_pendientes=10)
    recientes = await db["tickets"].find(
        {"oficina_id": oficina_id_obj, "eliminado": {"$ne": True}, "estado": {"$nin": ticket_service.ESTADOS_CERRADOS}},
        {"codigo": 1, "asunto": 1, "estado": 1, "prioridad": 1, "creado_en": 1},
    ).sort([("creado_en", -1), ("_id", -1)]).limit(25).to_list(None)
    tendencia = await agregar("tickets", [
            {"$match": {"oficina_id": oficina_id_obj, "eliminado": {"$ne": True}, "creado_en": {"$gte": desde}}},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$creado_en", "timezone": "America/Lima"}}, "total": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ])
    recurrentes = await agregar("tickets", [
            {"$match": {"oficina_id": oficina_id_obj, "eliminado": {"$ne": True}, "creado_en": {"$gte": desde}}},
            {"$group": {"_id": {"categoria": "$categoria", "equipo": "$activo_nombre"}, "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
        ])
    return {
        "id": str(oficina["_id"]),
        "nombre": oficina["nombre"],
        "zona_id": oficina.get("zona_id"),
        "zona_nombre": oficina.get("zona_nombre"),
        "zona_color_indice": (await org_service.obtener_zona(oficina["zona_id"])).get("color_indice", 1),
        "descripcion": oficina.get("descripcion"),
        "activa": bool(oficina.get("activa", True)),
        "creado_en": oficina.get("creado_en"),
        "total_usuarios": len(usuarios),
        "total_equipos": len(activos),
        "tickets_abiertos": await db["tickets"].count_documents(
            {"oficina_id": oficina_id_obj, "eliminado": {"$ne": True}, "estado": {"$nin": ticket_service.ESTADOS_CERRADOS}}
        ),
        "usuarios": usuarios,
        "equipos_uso_comun": uso_comun,
        "equipos_por_usuario": [
            {
                "responsable_id": grupo["responsable_id"],
                "responsable": grupo["responsable"],
                "equipos": grupo["equipos"],
            }
            for grupo in sorted(
                por_usuario.values(), key=lambda g: (g["responsable"] or "").casefold()
            )
        ],
        "pendientes_calidad": calidad["pendientes"],
        "completitud_inventario": calidad["porcentaje_global"],
        "tickets_recientes": normalizar(recientes),
        "tendencia": [{"mes": t["_id"], "total": t["total"]} for t in tendencia],
        "incidencias_recurrentes": [
            {"categoria": r["_id"].get("categoria") or "Sin clasificar", "equipo": r["_id"].get("equipo"), "total": r["total"]}
            for r in recurrentes
        ],
    }


@router.patch("/oficinas/{oficina_id}")
async def actualizar_oficina(oficina_id: str, datos: OficinaActualizar, sesion: DependeUsuarioCsrf, _: DependeEditarOrg):
    from app.core.ids import id_requerido

    oficina = await org_service.actualizar_oficina(
        id_requerido(oficina_id, "oficina"), datos.model_dump(exclude_unset=True), usuario=sesion.como_dict()
    )
    return normalizar(oficina)


@router.get("/oficinas/{oficina_id}/borrado")
async def bloqueos_borrado_oficina(oficina_id: str, sesion: DependeUsuario, _: DependeVerOrg):
    """Qué se perdería al borrar la oficina, antes de borrarla. Ver la de zonas."""
    from app.core.ids import id_requerido

    return await org_service.bloqueos_borrado_oficina(id_requerido(oficina_id, "oficina"))


@router.delete("/oficinas/{oficina_id}")
async def eliminar_oficina(oficina_id: str, sesion: DependeUsuarioCsrf, _: DependeEditarOrg) -> dict[str, Any]:
    from app.core.ids import id_requerido

    await org_service.eliminar_oficina(id_requerido(oficina_id, "oficina"), usuario=sesion.como_dict())
    return {"mensaje": "Oficina eliminada."}


# ── Directorio de usuarios ───────────────────────────────────
@router.get("/usuarios")
async def listar_usuarios(
    sesion: DependeUsuario,
    # `usuarios.ver`, como la pantalla que consume esta lista. Antes no exigía nada:
    # bastaba con estar conectado y una cuenta de rol `usuario` —la que reporta
    # problemas— recibía nombre, correo, teléfono, rol y oficina de las 267 cuentas.
    # La única guarda era «si no tienes oficina, no hay nada», que no es lo mismo que
    # un permiso: quien tiene oficina —casi todo el mundo— pasaba de largo.
    _: DependeVerUsuarios,
    zona_id: str | None = None,
    oficina_id: str | None = None,
    rol: str | None = None,
    solo_activos: bool = Query(True),
    estado: Literal["activos", "desactivados", "archivados", "todos"] | None = None,
    texto: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(25, ge=1, le=200),
):
    return await usuario_service.listar(
        zona_id=id_opcional(zona_id, "zona"),
        oficina_id=id_opcional(oficina_id, "oficina"),
        rol=rol,
        solo_activos=solo_activos,
        estado=estado,
        texto=texto,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.post("/usuarios", status_code=201)
async def crear_usuario(datos: UsuarioCrear, sesion: DependeUsuarioCsrf, _: DependeEditarUsuarios):
    usuario = await usuario_service.crear(datos.model_dump(), usuario=sesion.como_actor_cuentas())
    return usuario_service.publico(usuario, con_preferencias=True)


@router.get("/usuarios/buscar")
async def buscar_usuarios(
    sesion: DependeUsuario, texto: str = Query("", max_length=120), limite: int = Query(20, ge=1, le=50)
):
    # Con el texto vacío no se devuelve nada, ni siquiera para quien tiene permiso:
    # un desplegable de 40 nombres sin escribir una letra no es buscar, es volcar el
    # directorio en pantalla. La pantalla de registro manual abre el buscador vacío y
    # espera a que se escriba.
    termino = (texto or "").strip()
    if not termino:
        return {"items": []}
    if sesion.rol == "usuario":
        zona = sesion.usuario.get("zona_id")
        return {"items": await usuario_service.buscar_para_afectado(zona_id=zona, texto=termino, limite=limite) if zona else []}
    return {"items": await usuario_service.buscar_global(termino, limite=limite)}


@router.get("/usuarios/companeros")
async def companeros(
    sesion: DependeUsuario, zona_id: str | None = None, texto: str | None = None, otra_oficina: bool = False
):
    """El portal solo ofrece otras cuentas activas de la misma oficina."""
    if sesion.rol == 'usuario':
        oficina_id = sesion.usuario.get('oficina_id')
        items = await usuario_service.companeros_de_oficina(oficina_id, excluir_id=sesion.id, texto=texto) if oficina_id else []
        return {'items': items, 'ambito': 'oficina', 'puede_cambiar_ambito': False}
    zona_objetivo = id_opcional(zona_id, "zona") or sesion.usuario.get("zona_id")
    if not zona_objetivo:
        return {"items": [], "ambito": "institucion", "puede_cambiar_ambito": True}
    if otra_oficina or sesion.rol in {ROL_TECNICO, "administrador"} and zona_id and zona_id != str(sesion.usuario.get("zona_id")):
        return {
            "items": await usuario_service.buscar_global(texto or "", limite=40),
            "ambito": "institucion",
            "puede_cambiar_ambito": sesion.rol in {ROL_TECNICO, "administrador"},
        }
    items = await usuario_service.buscar_para_afectado(
        zona_id=zona_objetivo, texto=texto, limite=40, incluir_inactivos=False
    )
    if sesion.rol in {ROL_TECNICO, "administrador"}:
        items = await usuario_service.buscar_para_afectado(zona_id=zona_objetivo, texto=texto, limite=40, incluir_inactivos=True)
    return {"items": items, "ambito": "oficina", "puede_cambiar_ambito": True}


@router.get("/usuarios/{usuario_id}")
async def obtener_usuario(usuario_id: str, sesion: DependeUsuario):
    from app.core.errors import Prohibido
    from app.core.ids import id_requerido

    objetivo = id_requerido(usuario_id, "usuario")
    if objetivo != sesion.id and not sesion.tiene("usuarios.ver"):
        raise Prohibido("Solo puedes ver tu propio perfil.")
    detalle = await usuario_service.detalle(objetivo)
    if objetivo != sesion.id and not sesion.tiene("tickets.operar"):
        detalle.pop("tickets_recientes", None)
    return detalle


@router.get("/usuarios/{usuario_id}/tickets")
async def tickets_usuario(
    usuario_id: str, sesion: DependeUsuario,
    relacion: Literal["todos", "creados", "afectado", "asignados"] = "todos",
    estado: str | None = None,
    activo_id: str | None = None, conjunto_id: str | None = None,
    pagina: int = Query(1, ge=1), por_pagina: int = Query(10, ge=1, le=50),
):
    from app.core.ids import id_requerido
    objetivo = id_requerido(usuario_id, "usuario")
    sesion.exigir("tickets.operar")
    if objetivo != sesion.id:
        sesion.exigir("usuarios.ver")
    return await usuario_service.tickets_de_usuario(
        objetivo, relacion=relacion, estado=estado, pagina=pagina, por_pagina=por_pagina,
        activo_id=id_opcional(activo_id, 'equipo'), conjunto_id=id_opcional(conjunto_id, 'conjunto')
    )


@router.get('/usuarios/{usuario_id}/inventario-historial')
async def inventario_historial(usuario_id: str, sesion: DependeUsuario):
    from app.core.ids import id_requerido
    objetivo = id_requerido(usuario_id, 'usuario')
    sesion.exigir('tickets.operar')
    if objetivo != sesion.id:
        sesion.exigir('usuarios.ver')
    return await usuario_service.opciones_historial(objetivo)


@router.get('/usuarios/{usuario_id}/destinos-ticket')
async def destinos_ticket_persona(usuario_id: str, sesion: DependeUsuario):
    from app.core.ids import id_requerido
    from app.core.errors import NoEncontrado, Prohibido
    from app.services.historial_inventario_service import opciones_ticket
    objetivo = id_requerido(usuario_id, 'usuario')
    persona = await get_db().usuarios.find_one({'_id': objetivo, 'activo': {'$ne': False}})
    if not persona:
        raise NoEncontrado('Persona no encontrada.')
    if sesion.usuario.get('rol') == 'usuario' and objetivo != sesion.id and (not sesion.usuario.get('oficina_id') or persona.get('oficina_id') != sesion.usuario.get('oficina_id')):
        raise Prohibido('Solo puedes consultar los equipos de tu oficina.')
    return await opciones_ticket({'afectado_id': objetivo, 'oficina_id': persona.get('oficina_id')})


@router.get('/usuarios/{usuario_id}/dispositivos')
async def dispositivos_usuario(usuario_id: str, sesion: DependeUsuario):
    from app.core.ids import id_requerido
    from app.services import auth_service
    objetivo = id_requerido(usuario_id, 'usuario')
    if objetivo != sesion.id:
        sesion.exigir_admin()
        usuario_service.exigir_gestion_cuenta(await usuario_service.obtener(objetivo), sesion.como_actor_cuentas())
    return await auth_service.dispositivos(objetivo, sesion.sesion.get('session_id'))


@router.delete('/usuarios/{usuario_id}/dispositivos/{session_id}')
async def desconectar_usuario(usuario_id: str, session_id: str, sesion: DependeUsuarioCsrf):
    from app.core.ids import id_requerido
    from app.services import auth_service
    objetivo = id_requerido(usuario_id, 'usuario')
    if objetivo != sesion.id:
        sesion.exigir_admin()
        usuario_service.exigir_gestion_cuenta(await usuario_service.obtener(objetivo), sesion.como_actor_cuentas())
    await auth_service.cerrar(objetivo, session_id)
    return {'mensaje': 'Conexión cerrada.'}


# ── Foto de perfil ─────────────────────────────────────────────
#
# Va aparte del documento de usuario a proposito: la foto pesa cientos de KB y el
# perfil se pide en cada ficha y en cada lista. El documento solo guarda el nombre
# del archivo.


@router.get("/usuarios/{usuario_id}/foto")
async def obtener_foto(usuario_id: str, sesion: DependeUsuario):
    """Devuelve la foto. 404 si la cuenta no tiene, que es lo que el avatar espera."""
    from fastapi.responses import FileResponse

    from app.core.errors import NoEncontrado, Prohibido
    from app.core.ids import id_requerido

    objetivo = id_requerido(usuario_id, "usuario")
    # Mismo límite que `GET /usuarios/{id}`: una cuenta normal solo se ve a sí misma.
    if sesion.rol == "usuario" and objetivo != sesion.id:
        raise Prohibido("Solo puedes ver tu propio perfil.")
    documento = await get_db()["usuarios"].find_one({"_id": objetivo})
    if documento is None:
        raise NoEncontrado("Usuario no encontrado.")
    archivo = usuario_service.archivo_foto(documento)
    if archivo is None:
        raise NoEncontrado("Esta cuenta no tiene foto de perfil.")
    return FileResponse(
        archivo,
        media_type=documento["foto"]["mime"],
        # La ruta de la foto es estable: no reutilizar la imagen anterior al reemplazarla.
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/usuarios/{usuario_id}/foto")
async def subir_foto(
    usuario_id: str,
    sesion: DependeUsuarioCsrf,
    archivo: Annotated[UploadFile, File()],
):
    from app.core.ids import id_requerido

    objetivo = id_requerido(usuario_id, "usuario")
    # Uno mismo siempre; los demas, quien tenga `usuarios.editar`. Mismo criterio que
    # el resto de datos de la cuenta, para que la foto no sea la puerta trasera.
    if objetivo != sesion.id:
        sesion.exigir("usuarios.editar")
    return await usuario_service.guardar_foto(
        objetivo,
        await archivo.read(),
        nombre_original=archivo.filename or "foto",
        mime_declarado=archivo.content_type or "application/octet-stream",
        usuario=sesion.como_actor_cuentas(),
    )


@router.delete("/usuarios/{usuario_id}/foto")
async def borrar_foto(usuario_id: str, sesion: DependeUsuarioCsrf):
    from app.core.ids import id_requerido

    objetivo = id_requerido(usuario_id, "usuario")
    if objetivo != sesion.id:
        sesion.exigir("usuarios.editar")
    return await usuario_service.quitar_foto(objetivo, usuario=sesion.como_actor_cuentas())


@router.patch("/usuarios/{usuario_id}")
async def actualizar_usuario(
    usuario_id: str, datos: UsuarioActualizar, sesion: DependeUsuarioCsrf
):
    from app.core.ids import id_requerido

    objetivo = id_requerido(usuario_id, "usuario")
    cambios = datos.model_dump(exclude_unset=True)
    if objetivo == sesion.id:
        cambios.pop("rol", None)
        cambios.pop("permisos", None)
        cambios.pop("activo", None)
    elif sesion.rol == "usuario":
        from app.core.errors import Prohibido

        raise Prohibido("No puedes modificar la cuenta de otra persona.")
    elif "permisos" in cambios:
        sesion.exigir_admin()
    elif "rol" in cambios:
        sesion.exigir_admin()
    elif sesion.rol == "usuario":
        from app.core.errors import Prohibido

        raise Prohibido("No tienes permiso para modificar usuarios.")
    else:
        sesion.exigir("usuarios.editar")
    usuario = await usuario_service.actualizar(objetivo, cambios, usuario=sesion.como_actor_cuentas())
    return usuario_service.publico(usuario, con_preferencias=True)


@router.post("/usuarios/{usuario_id}/restablecer-password")
async def restablecer_password(
    usuario_id: str,
    datos: RestablecerPassword,
    sesion: DependeUsuarioCsrf,
    _: DependeEditarUsuarios,
):
    from app.core.ids import id_requerido

    await usuario_service.restablecer_password(
        id_requerido(usuario_id, "usuario"),
        datos.password,
        usuario=sesion.como_actor_cuentas(),
    )
    return {"mensaje": "Contraseña restablecida. Entrega la nueva clave de forma segura."}


@router.post("/usuarios/{usuario_id}/desactivar")
async def desactivar_usuario(usuario_id: str, sesion: DependeUsuarioCsrf):
    from app.core.ids import id_requerido

    sesion.exigir("usuarios.editar")
    usuario = await usuario_service.desactivar(id_requerido(usuario_id, "usuario"), usuario=sesion.como_actor_cuentas())
    return usuario_service.publico(usuario, con_preferencias=True)


@router.get("/mi-perfil")
async def mi_perfil(sesion: DependeUsuario):
    detalle = await usuario_service.detalle(sesion.id)
    detalle["permisos_efectivos"] = sorted(sesion.permisos)
    return detalle


@router.patch("/mi-perfil")
async def editar_mi_perfil(sesion: DependeUsuarioCsrf, datos: UsuarioActualizar):
    cambios = datos.model_dump(exclude_unset=True)
    for clave in ("rol", "permisos", "activo", "oficina_id", "zona_id"):
        cambios.pop(clave, None)
    usuario = await usuario_service.actualizar(sesion.id, cambios, usuario=sesion.como_actor_cuentas())
    return usuario_service.publico(usuario, con_preferencias=True)
