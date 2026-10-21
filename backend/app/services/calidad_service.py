"""Panel de calidad del inventario: completitud global, por zona, oficina y tipo."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core.db import agregar, get_db
from app.domain.constants import CAMPOS_BASE
from app.services import catalogo_service, inventario_service


async def _analizar(
    consulta: dict[str, Any], *, limite_pendientes: int = 50, con_detalle_por_campo: bool = True
) -> dict[str, Any]:
    db = get_db()
    activos = await db["activos"].find(
        {**consulta, "activo": {"$ne": False}},
        {
            "tipo": 1,
            "marca": 1,
            "modelo": 1,
            "nombre_equipo": 1,
            "codigo_patrimonial": 1,
            "oficina_nombre": 1,
            "zona_nombre": 1,
            "responsable_nombre": 1,
            "campos_estado": 1,
            "opciones_avanzadas": 1,
        },
    ).to_list(None)
    filas: list[dict[str, Any]] = []
    total_faltantes = 0
    total_esperados = 0
    completos = 0
    por_campo: dict[str, int] = {campo: 0 for campo in CAMPOS_BASE}
    for activo in activos:
        completeness = await inventario_service.calcular_completitud(activo)
        total_faltantes += completeness["faltantes"]
        total_esperados += completeness["esperados"]
        if completeness["faltantes"] == 0:
            completos += 1
        if con_detalle_por_campo:
            for campo in completeness["campos_faltantes"]:
                por_campo[campo] = por_campo.get(campo, 0) + 1
        filas.append(
            {
                "activo_id": activo["_id"],
                "nombre": activo.get("nombre_equipo") or activo.get("modelo") or activo.get("marca") or activo.get("tipo"),
                "tipo": activo.get("tipo"),
                "codigo_patrimonial": activo.get("codigo_patrimonial"),
                "oficina_nombre": activo.get("oficina_nombre"),
                "oficina_id": activo.get("oficina_id"),
                "zona_nombre": activo.get("zona_nombre"),
                "zona_id": activo.get("zona_id"),
                "responsable_nombre": activo.get("responsable_nombre") or "Uso comun de la oficina",
                "porcentaje": completeness["porcentaje"],
                "faltantes": completeness["faltantes"],
                "campos_faltantes": completeness["campos_faltantes"],
                "esperados": completeness["esperados"],
            }
        )
    pendientes = sorted([f for f in filas if f["faltantes"] > 0], key=lambda f: (-f["faltantes"], f["tipo"] or ""))
    total = len(activos)
    porcentaje_global = round(100 * completos / total, 1) if total else 100.0
    # El porcentaje de **datos escritos**, que es el que se entiende de un vistazo:
    # «de 3.000 casillas hay 2.500 escritas». El de arriba —equipos con todo
    # completo— es más severo y por eso solo con 5 zonas sale 0 %: no es que no
    # haya datos, es que a ningún equipo le falta cero campos. Con los dos, la
    # cifra sola deja de confundirse.
    porcentaje_datos = round(100 * (total_esperados - total_faltantes) / total_esperados, 1) if total_esperados else 100.0
    return {
        "porcentaje_global": porcentaje_global,
        "porcentaje_datos": porcentaje_datos,
        "esperados_totales": total_esperados,
        "total_activos": total,
        "con_datos_completos": completos,
        "faltantes_totales": total_faltantes,
        "por_campo": [
            {"campo": campo, "faltantes": cantidad}
            for campo, cantidad in sorted(por_campo.items(), key=lambda kv: -kv[1])
            if cantidad > 0
        ],
        "pendientes": pendientes[:limite_pendientes],
        "pendientes_total": len(pendientes),
    }


async def resumen(
    *,
    zona_id: ObjectId | None = None,
    oficina_id: ObjectId | None = None,
    tipo: str | None = None,
    limite_pendientes: int = 50,
) -> dict[str, Any]:
    consulta: dict[str, Any] = {}
    if zona_id:
        consulta["zona_id"] = zona_id
    if oficina_id:
        consulta["oficina_id"] = oficina_id
    if tipo:
        consulta["tipo"] = tipo
    global_info = await _analizar(consulta, limite_pendientes=limite_pendientes)

    por_zona = await _agrupar("zona_id", "zona_nombre", consulta)
    por_oficina = await _agrupar("oficina_id", "oficina_nombre", consulta, incluir_campos_faltantes=True)
    por_tipo = await _agrupar("tipo", None, consulta)
    return {
        "porcentaje_global": global_info["porcentaje_global"],
        "porcentaje_datos": global_info["porcentaje_datos"],
        "esperados_totales": global_info["esperados_totales"],
        "total_activos": global_info["total_activos"],
        "con_datos_completos": global_info["con_datos_completos"],
        "faltantes_totales": global_info["faltantes_totales"],
        "por_zona": por_zona,
        "por_oficina": por_oficina,
        "por_tipo": por_tipo,
        "por_campo": global_info["por_campo"],
        "pendientes": global_info["pendientes"],
        "pendientes_total": global_info["pendientes_total"],
    }


async def _agrupar(
    campo: str,
    campo_nombre: str | None,
    consulta_base: dict[str, Any],
    *,
    incluir_campos_faltantes: bool = False,
) -> list[dict[str, Any]]:
    consulta: dict[str, Any] = {**consulta_base, "activo": {"$ne": False}}
    if campo_nombre:
        grupos = await agregar(
            "activos",
            [
                {"$match": consulta},
                {"$group": {"_id": {campo: f"${campo}", "nombre": f"${campo_nombre}"}, "total": {"$sum": 1}}},
                {"$sort": {"total": -1}},
            ],
        )
    else:
        grupos = await agregar(
            "activos",
            [
                {"$match": consulta},
                {"$group": {"_id": {"tipo": "$tipo"}, "total": {"$sum": 1}}},
                {"$sort": {"total": -1}},
            ],
        )
    salida: list[dict[str, Any]] = []
    for grupo in grupos:
        identificador = grupo["_id"].get(campo)
        nombre = grupo["_id"].get("nombre") if campo_nombre else grupo["_id"].get("tipo")
        if not identificador and not nombre:
            continue
        subconsulta = dict(consulta_base)
        if identificador:
            subconsulta[campo] = identificador
        elif nombre:
            subconsulta[campo] = nombre
        info = await _analizar(
            subconsulta,
            limite_pendientes=0,
            con_detalle_por_campo=incluir_campos_faltantes,
        )
        salida.append(
            {
                "id": str(identificador) if identificador else None,
                "nombre": nombre or "Sin asignar",
                "total": grupo["total"],
                "porcentaje": info["porcentaje_global"],
                # Los dos porcentajes, que no dicen lo mismo: `porcentaje` es la
                # parte de equipos con **todo** escrito —severo, y por eso da 0 %
                # en cuanto un solo equipo del grupo tenga un hueco—, y
                # `porcentaje_datos` es la parte de casillas escritas, que es lo que
                # se lee de un vistazo.
                "porcentaje_datos": info["porcentaje_datos"],
                "esperados": info["esperados_totales"],
                "completos": info["con_datos_completos"],
                "faltantes": info["faltantes_totales"],
                "equipos_incompletos": info["total_activos"] - info["con_datos_completos"],
                **({"campos_faltantes": info["por_campo"]} if incluir_campos_faltantes else {}),
            }
        )
    return salida


async def pendientes_exportables(filtros: dict[str, Any]) -> list[dict[str, Any]]:
    """Lista completa de pendientes para exportar a Excel."""
    consulta: dict[str, Any] = {}
    if filtros.get("zona_id"):
        consulta["zona_id"] = filtros["zona_id"]
    if filtros.get("oficina_id"):
        consulta["oficina_id"] = filtros["oficina_id"]
    if filtros.get("tipo"):
        consulta["tipo"] = filtros["tipo"]
    info = await _analizar(consulta, limite_pendientes=100000)
    return info["pendientes"]


async def esquema_de(tipo: str) -> dict[str, list[str]]:
    return await catalogo_service.esquema(tipo)
