"""Base de conocimiento: articulos, busqueda, valoracion y sugerencias."""

from __future__ import annotations

import math
import re
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.audit import registrar
from app.core.db import agregar, get_db
from app.core.errors import NoEncontrado, Validacion, Prohibido
from app.core.ids import a_id, normalizar_texto
from app.core.time import utcnow

ETIQUETAS_SUGERIDAS = {
    "internet": ["No enciende", "Internet/red"],
    "impresora": ["Impresora"],
    "contrasena": ["Correo/cuenta", "Accesos y permisos"],
    "cuenta": ["Correo/cuenta", "Accesos y permisos"],
    "correo": ["Correo/cuenta"],
    "lento": ["Equipo lento", "Hardware"],
    "monitor": ["Hardware"],
    "apaga": ["No enciende", "Hardware"],
    "programa": ["Sistema/programa", "Software instalado"],
    "instalar": ["Software instalado"],
}


def slug_texto(texto: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(texto).lower()).strip("-")
    return base[:90] or "articulo"


def _es_equipo_ti(usuario: dict[str, Any] | None) -> bool:
    return (usuario or {}).get('rol') in {'administrador', 'tecnico'}


def _filtro_acceso(usuario: dict[str, Any] | None) -> dict[str, Any]:
    return {} if _es_equipo_ti(usuario) else {'visibilidad': {'$in': ['todos', None]}}


def _exigir_lectura(documento: dict[str, Any] | None, usuario: dict[str, Any] | None) -> None:
    if documento is None or (documento.get('visibilidad') == 'equipo_ti' and not _es_equipo_ti(usuario)):
        raise NoEncontrado('Articulo no encontrado.')


async def listar(
    *,
    categoria: str | None = None,
    texto: str | None = None,
    solo_activos: bool = True,
    pagina: int = 1,
    por_pagina: int = 20,
    orden: str = "relevancia",
    usuario: dict[str, Any] | None = None,
    visibilidad: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    consulta: dict[str, Any] = _filtro_acceso(usuario)
    if visibilidad in {'todos', 'equipo_ti'}:
        consulta['$and'] = [{'visibilidad': {'$in': ['todos', None]} if visibilidad == 'todos' else visibilidad}]
    if solo_activos:
        consulta["activo"] = True
    if categoria:
        consulta["categoria"] = categoria
    termino = normalizar_texto(texto)
    if termino:
        palabras = [p for p in re.split(r"\W+", termino.lower()) if len(p) > 2]
        or_ = []
        for palabra in palabras[:6]:
            patron = {"$regex": re.escape(palabra), "$options": "i"}
            or_.extend([{"titulo": patron}, {"resumen": patron}, {"etiquetas": patron}, {"cuerpo": patron}])
        consulta["$or"] = or_ or [{"titulo": {"$regex": re.escape(termino), "$options": "i"}}]
    # Unificar antes de paginar: ocultar duplicados en el navegador dejaba
    # páginas incompletas y un total que no correspondía a lo visible.
    orden_campo = "actualizado_en" if orden == "recientes" else "popularidad"
    resultado = await agregar("articulos_kb", [
        {"$match": consulta},
        {"$sort": {"actualizado_en": -1, "_id": -1}},
        {"$group": {"_id": {campo: {"$toLower": {"$trim": {"input": {"$ifNull": [f"${campo}", "todos" if campo == 'visibilidad' else ""]}}}} for campo in ("titulo", "categoria", "visibilidad")}, "articulo": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$articulo"}},
        {"$sort": {orden_campo: -1, "_id": -1}},
        {"$facet": {"items": [{"$skip": (pagina - 1) * por_pagina}, {"$limit": por_pagina}], "conteo": [{"$count": "total"}]}},
    ])
    bloque = resultado[0]
    total = bloque["conteo"][0]["total"] if bloque["conteo"] else 0
    documentos = bloque["items"]
    votos = await _votos([d['_id'] for d in documentos])
    for documento in documentos:
        documento.update(_estadisticas([v for v in votos if v['articulo_id'] == documento['_id']]))
    items = [_resumen(d) for d in documentos]
    return {
        "items": items,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": math.ceil(total / por_pagina) if por_pagina else 0,
    }


def _resumen(documento: dict[str, Any]) -> dict[str, Any]:
    return {
        "visibilidad": documento.get('visibilidad') or 'todos',
        "id": documento["_id"],
        "titulo": documento.get("titulo"),
        "categoria": documento.get("categoria"),
        "resumen": documento.get("resumen"),
        "etiquetas": documento.get("etiquetas") or [],
        "pasos": documento.get("pasos") or [],
        "imagenes": documento.get("imagenes") or [],
        "relacionados": documento.get("relacionados") or [],
        "popularidad": documento.get("popularidad", 0),
        "visualizaciones": documento.get("visualizaciones", 0),
        "valoracion_promedio": documento.get("valoracion_promedio"),
        "valoraciones": documento.get("valoraciones", 0),
        'me_gusta': documento.get('me_gusta', 0),
        "actualizado_en": documento.get("actualizado_en"),
        "activo": bool(documento.get("activo", True)),
    }


async def obtener(articulo_id: ObjectId, *, usuario: dict[str, Any] | None = None) -> dict[str, Any]:
    db = get_db()
    documento = await db["articulos_kb"].find_one({"_id": articulo_id})
    _exigir_lectura(documento, usuario)
    if documento is None or not documento.get("activo", True):
        raise NoEncontrado("Articulo no encontrado.")
    if (usuario or {}).get('_id'):
        actualizado = await db.articulos_kb.find_one_and_update(
            {'_id': articulo_id, 'activo': {'$ne': False}, 'lectores_ids': {'$ne': usuario['_id']}, **_filtro_acceso(usuario)},
            {'$addToSet': {'lectores_ids': usuario['_id']}, '$inc': {'visualizaciones': 1, 'popularidad': 1}},
            return_document=ReturnDocument.AFTER,
        )
        documento = actualizado or await db.articulos_kb.find_one({'_id': articulo_id})
        _exigir_lectura(documento, usuario)
        if not documento.get('activo', True):
            raise NoEncontrado('Articulo no encontrado.')
    documento.update(_estadisticas(await _votos([articulo_id]), usuario_id=(usuario or {}).get('_id')))
    salida = _resumen(documento)
    salida["cuerpo"] = documento.get("cuerpo", "")
    salida["creado_en"] = documento.get("creado_en")
    salida["creado_por"] = documento.get("creado_por")
    salida['mi_valoracion'] = documento.get('mi_valoracion')
    return salida


async def crear(datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    if datos.get('visibilidad') == 'equipo_ti' and not _es_equipo_ti(usuario):
        raise Prohibido('Solo el equipo TI puede publicar contenido interno.')
    db = get_db()
    documento = {
        "visibilidad": datos.get('visibilidad', 'todos'),
        "titulo": normalizar_texto(datos["titulo"]),
        "categoria": normalizar_texto(datos.get("categoria")) or "Otros",
        "resumen": normalizar_texto(datos.get("resumen")),
        "cuerpo": datos.get("cuerpo", ""),
        "pasos": [normalizar_texto(p) for p in (datos.get("pasos") or [])],
        "imagenes": list(datos.get("imagenes") or []),
        "etiquetas": [normalizar_texto(e) for e in (datos.get("etiquetas") or [])],
        "relacionados": [a_id(r) for r in (datos.get("relacionados") or []) if a_id(r)],
        "activo": bool(datos.get("activo", True)),
        "popularidad": 0,
        "visualizaciones": 0,
        "valoraciones": 0,
        "valoracion_promedio": None,
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "actualizado_en": utcnow(),
    }
    resultado = await db["articulos_kb"].insert_one(documento)
    documento["_id"] = resultado.inserted_id
    await registrar(
        "kb.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="articulo",
        entidad_id=resultado.inserted_id,
        resumen=f"Articulo creado: {documento['titulo']}",
        despues={"titulo": documento["titulo"], "categoria": documento["categoria"], 'visibilidad': documento['visibilidad']},
    )
    return _resumen(documento)


async def actualizar(articulo_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["articulos_kb"].find_one({"_id": articulo_id})
    _exigir_lectura(antes, usuario)
    if datos.get('visibilidad') == 'equipo_ti' and not _es_equipo_ti(usuario):
        raise Prohibido('Solo el equipo TI puede publicar contenido interno.')
    if antes is None:
        raise NoEncontrado("Articulo no encontrado.")
    cambios = {k: v for k, v in datos.items() if v is not None}
    if "relacionados" in cambios:
        cambios["relacionados"] = [a_id(r) for r in cambios["relacionados"] if a_id(r)]
    cambios = {k: v for k, v in cambios.items() if antes.get(k) != v}
    if not cambios:
        return _resumen(antes)
    campos_modificados = list(cambios)
    cambios["actualizado_en"] = utcnow()
    await db["articulos_kb"].update_one({"_id": articulo_id}, {"$set": cambios})
    await registrar(
        "kb.editar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="articulo",
        entidad_id=articulo_id,
        resumen=f"Articulo actualizado: {antes.get('titulo')}",
        antes={k: antes.get(k) for k in campos_modificados},
        despues={k: cambios.get(k) for k in campos_modificados},
    )
    documento = await db["articulos_kb"].find_one({"_id": articulo_id}) or {}
    return _resumen(documento)


async def eliminar(articulo_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    db = get_db()
    documento = await db["articulos_kb"].find_one({"_id": articulo_id})
    _exigir_lectura(documento, usuario)
    if documento is None:
        raise NoEncontrado("Articulo no encontrado.")
    await db["articulos_kb"].update_one(
        {"_id": articulo_id}, {"$set": {"activo": False, "eliminado_en": utcnow()}}
    )
    await registrar(
        "kb.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="articulo",
        entidad_id=articulo_id,
        resultado="eliminado",
        resumen=f"Articulo desactivado: {documento.get('titulo')}",
    )


async def valorar(articulo_id: ObjectId, util: bool, comentario: str | None, *, usuario: dict[str, Any]) -> dict[str, Any]:
    """Registra una valoracion y recalcula el promedio con la agregacion real."""
    db = get_db()
    documento = await db["articulos_kb"].find_one({"_id": articulo_id})
    _exigir_lectura(documento, usuario)
    if documento is None or not documento.get("activo", True):
        raise NoEncontrado("Articulo no encontrado.")
    if not usuario.get('_id'):
        raise Prohibido('Inicia sesión para valorar el artículo.')
    filtro = {'_id': f"{articulo_id}:{usuario['_id']}"}
    cambios = {"$set": {
        'articulo_id': articulo_id, 'usuario_id': usuario['_id'], 'util': util,
        'comentario': normalizar_texto(comentario) or None, 'fecha': utcnow(),
        'formato': 2,
    }}
    try:
        await db.articulos_kb_valoraciones.update_one(filtro, cambios, upsert=True)
    except DuplicateKeyError:
        await db.articulos_kb_valoraciones.update_one(filtro, cambios)
    return await _actualizar_estadisticas(articulo_id, usuario['_id'])


async def _votos(articulos: list[ObjectId]) -> list[dict[str, Any]]:
    if not articulos:
        return []
    return await agregar('articulos_kb_valoraciones', [
        {'$match': {'articulo_id': {'$in': articulos}}},
        {'$sort': {'fecha': 1, 'formato': 1, '_id': 1}},
        {'$group': {'_id': {'articulo': '$articulo_id', 'usuario': '$usuario_id'}, 'util': {'$last': '$util'}, 'fecha': {'$last': '$fecha'}}},
        {'$project': {'_id': 0, 'articulo_id': '$_id.articulo', 'usuario_id': '$_id.usuario', 'util': 1, 'fecha': 1}},
    ])


def _estadisticas(votos: list[dict[str, Any]], *, usuario_id=None) -> dict[str, Any]:
    total = len(votos)
    utiles = sum(bool(v.get('util')) for v in votos)
    return {'valoraciones': total, 'valoracion_promedio': round(100 * utiles / total, 1) if total else None,
            'me_gusta': utiles, 'utiles': utiles,
            'mi_valoracion': next((bool(v['util']) for v in votos if v['usuario_id'] == usuario_id), None)}


async def _actualizar_estadisticas(articulo_id: ObjectId, usuario_id: ObjectId) -> dict[str, Any]:
    estadisticas = _estadisticas(await _votos([articulo_id]), usuario_id=usuario_id)
    await get_db().articulos_kb.update_one({'_id': articulo_id}, {'$set': {k: estadisticas[k] for k in ['valoraciones', 'valoracion_promedio', 'me_gusta']}})
    return estadisticas


async def quitar_valoracion(articulo_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    documento = await get_db().articulos_kb.find_one({'_id': articulo_id, 'activo': {'$ne': False}})
    _exigir_lectura(documento, usuario)
    await get_db().articulos_kb_valoraciones.delete_many({'articulo_id': articulo_id, 'usuario_id': usuario['_id']})
    return await _actualizar_estadisticas(articulo_id, usuario['_id'])


async def personas_me_gusta(articulo_id: ObjectId, *, usuario: dict[str, Any], pagina: int = 1, por_pagina: int = 10) -> dict[str, Any]:
    documento = await get_db().articulos_kb.find_one({'_id': articulo_id, 'activo': {'$ne': False}})
    _exigir_lectura(documento, usuario)
    votos = [v for v in await _votos([articulo_id]) if v.get('util')]
    votos.sort(key=lambda voto: str(voto.get('fecha') or ''), reverse=True)
    pagina_votos = votos[(pagina - 1) * por_pagina:pagina * por_pagina]
    nombres = {u['_id']: u.get('nombre') or 'Usuario' for u in await get_db().usuarios.find({'_id': {'$in': [v['usuario_id'] for v in pagina_votos]}}, {'nombre': 1}).to_list(None)}
    return {'items': [{'usuario_id': str(v['usuario_id']), 'nombre': nombres.get(v['usuario_id'], 'Cuenta no disponible')} for v in pagina_votos],
            'total': len(votos), 'pagina': pagina, 'por_pagina': por_pagina, 'total_paginas': math.ceil(len(votos) / por_pagina)}


async def categorias(*, usuario: dict[str, Any] | None = None) -> list[str]:
    from app.services import catalogo_service

    try:
        base = await catalogo_service.listar("categorias")
    except Exception:  # pragma: no cover
        base = []
    propias = await get_db()["articulos_kb"].distinct("categoria", {"activo": True, **_filtro_acceso(usuario)})
    return sorted({c for c in [*base, *propias, "Tutoriales", "Software", "Recomendaciones"] if isinstance(c, str) and c.strip()})


async def sugerir_para_ticket(
    texto: str, categoria: str | None = None, *, limite: int = 4, usuario: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Articulos relacionados con el texto de un ticket (usado por la IA y por la UI)."""
    termino = normalizar_texto(texto)
    if not termino and not categoria:
        return []
    db = get_db()
    consulta: dict[str, Any] = {"activo": True, **_filtro_acceso(usuario)}
    or_: list[dict[str, Any]] = []
    if categoria:
        # La categoria llega del ticket (texto libre del reportante) o de la IA:
        # se busca literal, asi que tambien se escapa. Sin esto, una categoria
        # como «PC (recepción» reventaba las sugerencias con 500.
        or_.append({"categoria": {"$regex": re.escape(categoria), "$options": "i"}})
    palabras = [p for p in re.split(r"\W+", termino.lower()) if len(p) > 3]
    for palabra in ETIQUETAS_SUGERIDAS:
        if any(palabra in p for p in palabras) or any(p in palabra for p in palabras):
            or_.append({"categoria": {"$regex": palabra, "$options": "i"}})
            or_.append({"etiquetas": palabra})
    for palabra in palabras[:5]:
        patron = {"$regex": re.escape(palabra), "$options": "i"}
        or_.extend([{"titulo": patron}, {"etiquetas": patron}, {"resumen": patron}])
    if or_:
        consulta["$or"] = or_[:12]
    # Se traen más de los pedidos porque puede haber títulos repetidos y lo que se
    # enseña son títulos. En la base de conocimiento había siete copias de cada
    # artículo y el panel de sugerencias sacaba cuatro líneas idénticas: la misma
    # respuesta cuatro veces no es una sugerencia, es un fallo que hace creer que
    # la IA no sabe filtrar.
    documentos = await (
        db["articulos_kb"]
        .find(consulta)
        .sort("popularidad", -1)
        .limit(limite * 4)
        .to_list(None)
    )
    vistos: set[str] = set()
    unicos: list[dict[str, Any]] = []
    for documento in documentos:
        titulo = (documento.get("titulo") or "").strip()
        clave = titulo.casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(documento)
        if len(unicos) >= limite:
            break
    documentos = unicos
    return [
        {
            "id": d["_id"],
            "titulo": d.get("titulo"),
            "resumen": d.get("resumen"),
            "categoria": d.get("categoria"),
        }
        for d in documentos
    ]


async def respuestas_rapidas() -> list[dict[str, Any]]:
    documentos = await (get_db()["respuestas_rapidas"].find({}).sort("titulo", 1).to_list(None))
    for documento in documentos:
        documento["id"] = documento.pop("_id")
    return documentos


async def guardar_respuesta_rapida(datos: dict[str, Any], respuesta_id: ObjectId | None, *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    documento = {
        "titulo": normalizar_texto(datos["titulo"]),
        "cuerpo": datos["cuerpo"],
        "categoria": normalizar_texto(datos.get("categoria")) or None,
        "actualizado_en": utcnow(),
        "actualizado_por": usuario.get("nombre", ""),
    }
    antes = None
    if respuesta_id:
        antes = await db["respuestas_rapidas"].find_one({"_id": respuesta_id})
        if not antes:
            raise NoEncontrado("Respuesta rápida no encontrada.")
        if all(antes.get(campo) == documento[campo] for campo in ("titulo", "cuerpo", "categoria")):
            return {"id": respuesta_id, **documento}
        await db["respuestas_rapidas"].update_one({"_id": respuesta_id}, {"$set": documento})
        resultado_id = respuesta_id
    else:
        documento["creado_en"] = utcnow()
        resultado_id = (await db["respuestas_rapidas"].insert_one(documento)).inserted_id
    await registrar(
        "kb.editar" if respuesta_id else "kb.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="respuesta_rapida",
        entidad_id=resultado_id,
        resumen=f"Respuesta rapida guardada: {documento['titulo']}",
        antes={c: antes.get(c) for c in ("titulo", "cuerpo", "categoria")} if antes else None,
        despues={c: documento[c] for c in ("titulo", "cuerpo", "categoria")},
    )
    return {"id": resultado_id, **documento}


async def eliminar_respuesta_rapida(respuesta_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    await get_db()["respuestas_rapidas"].delete_one({"_id": respuesta_id})
    await registrar(
        "kb.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="respuesta_rapida",
        entidad_id=respuesta_id,
        resultado="eliminado",
        resumen="Respuesta rapida eliminada",
    )
