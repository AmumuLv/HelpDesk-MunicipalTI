"""Zonas y oficinas: la jerarquia Zona > Oficina."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from app.core.ids import clave, id_requerido, normalizar_texto
from app.core.time import utcnow


# ── Zonas ────────────────────────────────────────────────────
def _plural(cantidad: int, palabra: str) -> str:
    """«1 oficina», «13 oficinas». Los mensajes van a una persona que no va a leerlos dos veces."""
    return f"{cantidad} {palabra if cantidad == 1 else palabra + 's'}"


async def crear_zona(datos: dict[str, Any], *, usuario: dict[str, Any]) -> ObjectId:
    nombre = normalizar_texto(datos.get("nombre"))
    if len(nombre) < 2:
        raise Validacion("El nombre de la zona es obligatorio.")
    db = get_db()
    if await db["zonas"].find_one({"nombre_normalizado": clave(nombre)}):
        raise Conflicto(f"Ya existe una zona llamada '{nombre}'.")
    doc = {
        "nombre": nombre,
        "nombre_normalizado": clave(nombre),
        "descripcion": normalizar_texto(datos.get("descripcion")) or None,
        "activa": bool(datos.get("activa", True)),
        "color_indice": (await db["zonas"].count_documents({})) % 8 + 1,
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "actualizado_en": utcnow(),
    }
    resultado = await db["zonas"].insert_one(doc)
    await registrar(
        "zona.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="zona",
        entidad_id=resultado.inserted_id,
        resumen=f"Zona creada: {nombre}",
        despues={"nombre": nombre, "descripcion": doc["descripcion"]},
    )
    return resultado.inserted_id


async def actualizar_zona(zona_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["zonas"].find_one({"_id": zona_id})
    if antes is None:
        raise NoEncontrado("Zona no encontrada.")
    cambios: dict[str, Any] = {}
    if "nombre" in datos and datos["nombre"] is not None:
        nombre = normalizar_texto(datos["nombre"])
        if await db["zonas"].find_one({"nombre_normalizado": clave(nombre), "_id": {"$ne": zona_id}}):
            raise Conflicto(f"Ya existe una zona llamada '{nombre}'.")
        cambios["nombre"] = nombre
        cambios["nombre_normalizado"] = clave(nombre)
    for campo in ("descripcion", "activa"):
        if campo in datos and datos[campo] is not None:
            cambios[campo] = normalizar_texto(datos[campo]) if campo == "descripcion" else bool(datos[campo])
    if not cambios:
        return antes
    cambios["actualizado_en"] = utcnow()
    await db["zonas"].update_one({"_id": zona_id}, {"$set": cambios})
    despues = await db["zonas"].find_one({"_id": zona_id})
    await registrar(
        "zona.editar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="zona",
        entidad_id=zona_id,
        resumen=f"Zona actualizada: {despues['nombre']}",
        antes={k: antes.get(k) for k in cambios},
        despues={k: despues.get(k) for k in cambios},
    )
    if cambios.get("nombre"):
        await db["oficinas"].update_many({"zona_id": zona_id}, {"$set": {"zona_nombre": cambios["nombre"]}})
        await db["usuarios"].update_many({"zona_id": zona_id}, {"$set": {"zona_nombre": cambios["nombre"]}})
    return despues


async def bloqueos_borrado_zona(zona_id: ObjectId) -> dict[str, Any]:
    """Qué impide borrar una zona, con los números exactos.

    Vive aparte del borrado y **ambos lo llaman**, para que el aviso que ve la
    persona antes de confirmar y la razón por la que se le rechaza después no puedan
    discrepar. Antes los recuentos de la lista de zonas no servían para esto: el
    contador filtra los equipos dados de baja y el borrado no, así que el aviso podía
    decir «0 equipos» y el borrado responder «tiene 3».
    """
    db = get_db()
    zona = await db["zonas"].find_one({"_id": zona_id})
    if zona is None:
        raise NoEncontrado("Zona no encontrada.")
    oficinas = await db["oficinas"].count_documents({"zona_id": zona_id})
    return {
        "nombre": zona.get("nombre", ""),
        "oficinas": oficinas,
        "personas": await db["usuarios"].count_documents({"zona_id": zona_id}),
        "equipos": await db["activos"].count_documents({"zona_id": zona_id}),
        # El bloqueo real es el de las oficinas: mientras tenga alguna no se puede
        # borrar, aunque no tenga personas ni equipos propios.
        "puede_eliminar": oficinas == 0,
        "motivo": (
            f"La zona tiene {_plural(oficinas, 'oficina')} registradas. "
            "Elimina o traslada las oficinas primero."
            if oficinas
            else None
        ),
    }


async def eliminar_zona(zona_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    db = get_db()
    bloqueos = await bloqueos_borrado_zona(zona_id)
    if bloqueos["motivo"]:
        raise Prohibido(bloqueos["motivo"], detalles={"oficinas": bloqueos["oficinas"]})
    await db["zonas"].delete_one({"_id": zona_id})
    await registrar(
        "zona.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="zona",
        entidad_id=zona_id,
        resumen=f"Zona eliminada: {bloqueos['nombre']}",
        antes={"nombre": bloqueos["nombre"]},
    )


async def listar_zonas(*, solo_activas: bool = False, con_resumen: bool = True) -> list[dict[str, Any]]:
    consulta: dict[str, Any] = {"activa": True} if solo_activas else {}
    zonas = await (get_db()["zonas"].find(consulta).sort("nombre", 1).to_list(None))
    if not con_resumen:
        return zonas
    db = get_db()
    for zona in zonas:
        zona["total_oficinas"] = await db["oficinas"].count_documents({"zona_id": zona["_id"], "activa": True})
        zona["total_usuarios"] = await db["usuarios"].count_documents({"zona_id": zona["_id"], "activo": True})
        zona["total_equipos"] = await db["activos"].count_documents({"zona_id": zona["_id"]})
    return zonas


async def obtener_zona(zona_id: ObjectId) -> dict[str, Any]:
    zona = await get_db()["zonas"].find_one({"_id": zona_id})
    if zona is None:
        raise NoEncontrado("Zona no encontrada.")
    return zona


async def zona_por_nombre(nombre: str, *, crear: bool = False, usuario: dict[str, Any] | None = None) -> dict[str, Any] | None:
    db = get_db()
    normalizado = clave(nombre)
    zona = await db["zonas"].find_one({"nombre_normalizado": normalizado})
    if zona is not None:
        return zona
    if crear and usuario:
        nuevo_id = await crear_zona({"nombre": nombre}, usuario=usuario)
        return await db["zonas"].find_one({"_id": nuevo_id})
    return None


# ── Oficinas ─────────────────────────────────────────────────
async def crear_oficina(datos: dict[str, Any], *, usuario: dict[str, Any]) -> ObjectId:
    nombre = normalizar_texto(datos.get("nombre"))
    zona_id = id_requerido(datos.get("zona_id"), "zona")
    if len(nombre) < 2:
        raise Validacion("El nombre de la oficina es obligatorio.")
    db = get_db()
    zona = await db["zonas"].find_one({"_id": zona_id})
    if zona is None:
        raise NoEncontrado("La zona indicada no existe.")
    if await db["oficinas"].find_one({"zona_id": zona_id, "nombre_normalizado": clave(nombre)}):
        raise Conflicto(f"Ya existe una oficina llamada '{nombre}' en {zona['nombre']}.")
    doc = {
        "nombre": nombre,
        "nombre_normalizado": clave(nombre),
        "zona_id": zona_id,
        "zona_nombre": zona["nombre"],
        "descripcion": normalizar_texto(datos.get("descripcion")) or None,
        "activa": bool(datos.get("activa", True)),
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "actualizado_en": utcnow(),
    }
    resultado = await db["oficinas"].insert_one(doc)
    await registrar(
        "oficina.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="oficina",
        entidad_id=resultado.inserted_id,
        resumen=f"Oficina creada: {nombre} ({zona['nombre']})",
        despues={"nombre": nombre, "zona": zona["nombre"]},
    )
    return resultado.inserted_id


async def actualizar_oficina(oficina_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["oficinas"].find_one({"_id": oficina_id})
    if antes is None:
        raise NoEncontrado("Oficina no encontrada.")
    cambios: dict[str, Any] = {}
    if datos.get("zona_id"):
        zona_id = id_requerido(datos["zona_id"], "zona")
        zona = await db["zonas"].find_one({"_id": zona_id})
        if zona is None:
            raise NoEncontrado("La zona indicada no existe.")
        cambios["zona_id"] = zona_id
        cambios["zona_nombre"] = zona["nombre"]
    if datos.get("nombre"):
        nombre = normalizar_texto(datos["nombre"])
        zona_consulta = cambios.get("zona_id", antes["zona_id"])
        if await db["oficinas"].find_one(
            {"zona_id": zona_consulta, "nombre_normalizado": clave(nombre), "_id": {"$ne": oficina_id}}
        ):
            raise Conflicto(f"Ya existe una oficina llamada '{nombre}' en esa zona.")
        cambios["nombre"] = nombre
        cambios["nombre_normalizado"] = clave(nombre)
    for campo in ("descripcion", "activa"):
        if campo in datos and datos[campo] is not None:
            cambios[campo] = normalizar_texto(datos[campo]) if campo == "descripcion" else bool(datos[campo])
    if not cambios:
        return antes
    cambios["actualizado_en"] = utcnow()
    await db["oficinas"].update_one({"_id": oficina_id}, {"$set": cambios})
    if cambios.get("nombre") or cambios.get("zona_id"):
        await db["usuarios"].update_many(
            {"oficina_id": oficina_id},
            {
                "$set": {
                    "oficina_nombre": cambios.get("nombre", antes["nombre"]),
                    "zona_nombre": cambios.get("zona_nombre", antes["zona_nombre"]),
                    "zona_id": cambios.get("zona_id", antes["zona_id"]),
                }
            },
        )
        await db["activos"].update_many(
            {"oficina_id": oficina_id},
            {
                "$set": {
                    "oficina_nombre": cambios.get("nombre", antes["nombre"]),
                    "zona_nombre": cambios.get("zona_nombre", antes["zona_nombre"]),
                    "zona_id": cambios.get("zona_id", antes["zona_id"]),
                }
            },
        )
    despues = await db["oficinas"].find_one({"_id": oficina_id})
    await registrar(
        "oficina.editar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="oficina",
        entidad_id=oficina_id,
        resumen=f"Oficina actualizada: {despues['nombre']}",
        antes={k: antes.get(k) for k in cambios},
        despues={k: despues.get(k) for k in cambios},
    )
    return despues


async def bloqueos_borrado_oficina(oficina_id: ObjectId) -> dict[str, Any]:
    """Qué impide borrar una oficina, con los números exactos. Ver `bloqueos_borrado_zona`."""
    db = get_db()
    oficina = await db["oficinas"].find_one({"_id": oficina_id})
    if oficina is None:
        raise NoEncontrado("Oficina no encontrada.")
    equipos = await db["activos"].count_documents({"oficina_id": oficina_id})
    personas = await db["usuarios"].count_documents({"oficina_id": oficina_id, "activo": True})
    return {
        "nombre": oficina.get("nombre", ""),
        "zona_nombre": oficina.get("zona_nombre"),
        "personas": personas,
        "equipos": equipos,
        # El bloqueo real son los equipos: las personas se pueden trasladar después,
        # pero un equipo sin oficina no tiene a qué asignarse.
        "puede_eliminar": equipos == 0,
        "motivo": (
            f"La oficina tiene {_plural(equipos, 'equipo')} registrados. "
            "Traslala o dales de baja antes de eliminarla."
            if equipos
            else None
        ),
    }


async def eliminar_oficina(oficina_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    db = get_db()
    bloqueos = await bloqueos_borrado_oficina(oficina_id)
    if bloqueos["motivo"]:
        raise Prohibido(bloqueos["motivo"], detalles={"activos": bloqueos["equipos"]})
    await db["oficinas"].delete_one({"_id": oficina_id})
    await registrar(
        "oficina.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="oficina",
        entidad_id=oficina_id,
        resumen=f"Oficina eliminada: {bloqueos['nombre']}",
        antes={"nombre": bloqueos["nombre"], "zona": bloqueos["zona_nombre"]},
    )


async def listar_oficinas(
    *, zona_id: ObjectId | None = None, solo_activas: bool = True, con_resumen: bool = True
) -> list[dict[str, Any]]:
    consulta: dict[str, Any] = {}
    if zona_id:
        consulta["zona_id"] = zona_id
    if solo_activas:
        consulta["activa"] = True
    oficinas = await (get_db()["oficinas"].find(consulta).sort([("creado_en", -1), ("_id", -1)]).to_list(None))
    if not con_resumen:
        return oficinas
    db = get_db()
    for oficina in oficinas:
        consulta_activos = {"oficina_id": oficina["_id"], "estado": {"$ne": "Dado de baja"}}
        oficina["total_usuarios"] = await db["usuarios"].count_documents({"oficina_id": oficina["_id"], "activo": True})
        oficina["total_equipos"] = await db["activos"].count_documents(consulta_activos)
    return oficinas


async def obtener_oficina(oficina_id: ObjectId) -> dict[str, Any]:
    oficina = await get_db()["oficinas"].find_one({"_id": oficina_id})
    if oficina is None:
        raise NoEncontrado("Oficina no encontrada.")
    return oficina


async def oficina_por_nombre(
    nombre: str, zona_id: ObjectId, *, crear: bool = False, usuario: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    db = get_db()
    normalizado = clave(nombre)
    oficina = await db["oficinas"].find_one({"zona_id": zona_id, "nombre_normalizado": normalizado})
    if oficina is not None:
        return oficina
    if crear and usuario:
        nuevo_id = await crear_oficina({"nombre": nombre, "zona_id": zona_id}, usuario=usuario)
        return await db["oficinas"].find_one({"_id": nuevo_id})
    return None
