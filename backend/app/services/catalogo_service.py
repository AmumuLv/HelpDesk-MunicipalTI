"""Catalogos editables, esquemas por tipo y registro de valores sugeridos."""

from __future__ import annotations

from typing import Any
from time import monotonic

from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Validacion
from app.core.ids import clave, normalizar_texto
from app.core.time import utcnow
from app.domain.constants import CAMPOS_BASE

CATALOGOS_EDITABLES = (
    "tipos_dispositivo",
    "estados_activo",
    "propiedades",
    "categorias",
    "motivos_no_aplica",
    "motivos_no_disponible",
    "sinonimos_dispositivo",
    "componentes_conjunto",
    "tipos_ausencia",
    "canales_notificacion",
)


async def listar(clave_cat: str) -> list[str]:
    doc = await get_db()["catalogos"].find_one({"clave": clave_cat})
    if doc is None:
        raise NoEncontrado(f"El catalogo '{clave_cat}' no existe.")
    return [v["valor"] if isinstance(v, dict) else str(v) for v in doc.get("valores", [])]


async def listar_detallado(clave_cat: str) -> list[dict[str, Any]]:
    doc = await get_db()["catalogos"].find_one({"clave": clave_cat})
    if doc is None:
        raise NoEncontrado(f"El catalogo '{clave_cat}' no existe.")
    salida: list[dict[str, Any]] = []
    for posicion, valor in enumerate(doc.get("valores", [])):
        if isinstance(valor, dict):
            salida.append(
                {
                    "valor": valor.get("valor"),
                    "etiqueta": valor.get("etiqueta") or valor.get("valor"),
                    "activo": valor.get("activo", True),
                    "orden": valor.get("orden", posicion),
                }
            )
        else:
            salida.append({"valor": str(valor), "etiqueta": str(valor), "activo": True, "orden": posicion})
    return sorted(salida, key=lambda item: (not item["activo"], item["orden"], str(item["valor"])))


async def todos() -> dict[str, list[dict[str, Any]]]:
    resultado: dict[str, list[dict[str, Any]]] = {}
    async for doc in get_db()["catalogos"].find({}).sort("clave", 1):
        resultado[doc["clave"]] = await listar_detallado(doc["clave"])
    return resultado


async def actualizar_catalogo(
    clave_cat: str, valores: list[dict[str, Any]], *, usuario: dict[str, Any]
) -> list[dict[str, Any]]:
    if clave_cat not in CATALOGOS_EDITABLES:
        raise Validacion("Ese catalogo no se puede editar.")
    normalizados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for orden, item in enumerate(valores):
        valor = normalizar_texto(item.get("valor"))
        if not valor:
            continue
        k = clave(valor)
        if k in vistos:
            raise Conflicto(f"El valor '{valor}' esta duplicado.", detalles={"valor": valor})
        vistos.add(k)
        normalizados.append(
            {
                "valor": valor,
                "etiqueta": normalizar_texto(item.get("etiqueta") or valor) or valor,
                "activo": bool(item.get("activo", True)),
                "orden": int(item.get("orden", orden)),
            }
        )
    if not normalizados:
        raise Validacion("El catalogo no puede quedar vacio.")
    antes = await listar_detallado(clave_cat)
    await get_db()["catalogos"].update_one(
        {"clave": clave_cat},
        {"$set": {"valores": normalizados, "actualizado_en": utcnow(), "actualizado_por": usuario.get("_id")}},
        upsert=True,
    )
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="catalogo",
        entidad_id=clave_cat,
        resumen=f"Catalogo {clave_cat} actualizado",
        antes=[v["valor"] for v in antes],
        despues=[v["valor"] for v in normalizados],
    )
    return await listar_detallado(clave_cat)


# ── Esquemas por tipo ────────────────────────────────────────
# Los esquemas cambian muy rara vez (solo en Configuracion), asi que se cachean
# para no consultar MongoDB una vez por cada activo al calcular la completitud.
_CACHE_ESQUEMAS: dict[str, dict[str, list[str]]] = {}
_CACHE_HASTA: dict[str, float] = {}


async def esquema(tipo: str) -> dict[str, list[str]]:
    if tipo in _CACHE_ESQUEMAS and _CACHE_HASTA.get(tipo, 0) > monotonic():
        return _CACHE_ESQUEMAS[tipo]
    db = get_db()
    doc = await db["esquemas_tipos"].find_one({"tipo": tipo}) or await db["esquemas_tipos"].find_one(
        {"tipo": "__generico__"}
    )
    if doc is None:
        resultado = {"esperados": ["codigo_patrimonial", "marca", "modelo"], "opcionales": [], "avanzadas": []}
    else:
        resultado = {
            "esperados": list(doc.get("esperados") or []),
            "opcionales": list(doc.get("opcionales") or []),
            "avanzadas": list(doc.get("avanzadas") or []),
        }
    _CACHE_ESQUEMAS[tipo] = resultado
    _CACHE_HASTA[tipo] = monotonic() + 2
    return resultado


def invalidar_cache_esquemas() -> None:
    _CACHE_ESQUEMAS.clear()
    _CACHE_HASTA.clear()


async def todos_los_esquemas() -> list[dict[str, Any]]:
    documentos = await (
        get_db()["esquemas_tipos"]
        .find({"tipo": {"$nin": ["__base__", "__generico__"]}})
        .sort("tipo", 1)
        .to_list(None)
    )
    return [
        {
            "tipo": doc["tipo"],
            "esperados": doc.get("esperados", []),
            "opcionales": doc.get("opcionales", []),
            "avanzadas": doc.get("avanzadas", []),
        }
        for doc in documentos
    ]


async def actualizar_esquema(
    tipo: str, datos: dict[str, list[str]], *, usuario: dict[str, Any]
) -> dict[str, list[str]]:
    db = get_db()
    antes = await esquema(tipo)
    permitidos = set(CAMPOS_BASE)
    for clave_campo in ("esperados", "opcionales"):
        if clave_campo in datos and datos[clave_campo] is not None:
            for campo in datos[clave_campo]:
                if campo not in permitidos:
                    raise Validacion(f"El campo '{campo}' no existe en el inventario.", detalles={"campo": campo})
    esperando = set(datos.get("esperados") or antes["esperados"])
    opcionales = set(datos.get("opcionales") or antes["opcionales"])
    if not esperando:
        raise Validacion("Debe quedar al menos un campo esperado para poder avisar de faltantes.")
    solapados = esperando & opcionales
    if solapados:
        raise Validacion(
            "Un campo no puede ser esperado y opcional a la vez.",
            detalles={"campos": sorted(solapados)},
        )
    actualizacion = {
        "esperados": sorted(esperando),
        "opcionales": sorted(opcionales),
        "actualizado_en": utcnow(),
        "actualizado_por": usuario.get("_id"),
    }
    if "avanzadas" in datos and datos["avanzadas"] is not None:
        actualizacion["avanzadas"] = list(datos["avanzadas"])
    await db["esquemas_tipos"].update_one({"tipo": tipo}, {"$set": actualizacion}, upsert=True)
    invalidar_cache_esquemas()
    from app.services.inventario_service import recalcular_faltantes
    await recalcular_faltantes({} if tipo == '__generico__' else {'tipo': tipo})
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="esquema_tipo",
        entidad_id=tipo,
        resumen=f"Esquema de '{tipo}' actualizado",
        antes=antes,
        despues={**await esquema(tipo)},
    )
    return await esquema(tipo)


async def tipos_existentes() -> list[str]:
    tipos = await listar("tipos_dispositivo")
    for item in await todos_los_esquemas():
        if item["tipo"] not in tipos:
            tipos.append(item["tipo"])
    return tipos


# ── Sinonimos de importacion ─────────────────────────────────
def _parsear_sinonimos(valores: list[str]) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for valor in valores:
        texto = normalizar_texto(valor)
        if "=" in texto:
            origen, destino = texto.split("=", 1)
            origen = clave(origen)
            destino = normalizar_texto(destino)
            if origen and destino:
                mapa[origen] = destino
    return mapa


async def mapa_sinonimos() -> dict[str, str]:
    from app.domain.constants import SINONIMOS_DISPOSITIVO

    mapa = dict(SINONIMOS_DISPOSITIVO)
    mapa.update(_parsear_sinonimos(await listar("sinonimos_dispositivo")))
    return {clave(k): v for k, v in mapa.items()}


async def valores_sin_dato() -> set[str]:
    return {clave(v) for v in await listar("motivos_sin_dato")} | {
        clave(v) for v in ["-", "n/a", "s/n", "no tiene", "sin codigo", "na", "ninguno", "."]
    }


# ── Registro de valores usados (base de las sugerencias) ─────
async def registrar_valor(campo: str, valor: str, *, tipo: str | None = None, marca: str | None = None) -> None:
    """Suma 1 al contador de frecuencia de un valor escrito a mano."""
    texto = normalizar_texto(valor)
    if not texto or len(texto) > 120:
        return
    await get_db()["valores_inventario"].update_one(
        {"campo": campo, "valor": texto, "tipo": tipo},
        {
            "$inc": {"frecuencia": 1},
            "$set": {"marca": marca, "actualizado_en": utcnow()},
            "$setOnInsert": {"campo": campo, "valor": texto, "tipo": tipo, "creado_en": utcnow()},
        },
        upsert=True,
    )


async def registrar_lote(valores: list[tuple[str, str, str | None, str | None]]) -> None:
    """Registra varios valores en una sola pasada (importaciones)."""
    from pymongo import UpdateOne

    db = get_db()
    operaciones = []
    for campo, valor, tipo, marca in valores:
        texto = normalizar_texto(valor)
        if not texto or len(texto) > 120:
            continue
        operaciones.append(
            UpdateOne(
                {"campo": campo, "valor": texto, "tipo": tipo},
                {
                    "$inc": {"frecuencia": 1},
                    "$set": {"marca": marca, "actualizado_en": utcnow()},
                    "$setOnInsert": {"campo": campo, "valor": texto, "tipo": tipo, "creado_en": utcnow()},
                },
                upsert=True,
            )
        )
    if not operaciones:
        return
    await db["valores_inventario"].bulk_write(operaciones, ordered=False)


async def sugerencias(campo: str, tipo: str | None = None, marca: str | None = None, limite: int = 12) -> list[dict[str, Any]]:
    consulta: dict[str, Any] = {'activo': {'$ne': False}, campo: {'$exists': True, '$nin': [None, '', 'Pendiente', 'No aplica', 'No disponible']}}
    if tipo:
        consulta['tipo'] = tipo
    if marca:
        consulta['marca'] = marca
    cursor = await get_db()['activos'].aggregate([
        {'$match': consulta}, {'$group': {'_id': '$' + campo, 'frecuencia': {'$sum': 1}}},
        {'$sort': {'frecuencia': -1, '_id': 1}}, {'$limit': limite},
    ])
    valores = await cursor.to_list(None)
    return [{'valor': str(v['_id']), 'frecuencia': v['frecuencia'], 'marca': marca,
             'frecuencia_marca': v['frecuencia'] if marca else 0, 'ejemplo_completo': None} for v in valores]
