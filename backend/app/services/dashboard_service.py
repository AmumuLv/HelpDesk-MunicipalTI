"""Resumen del panel TI: cifras de cabecera con datos reales y acciones siguientes."""

from __future__ import annotations

from typing import Any

from app.core.db import agregar, get_db
from app.core.time import local_date, utcnow
from app.domain.constants import ESTADOS_CERRADOS, ROL_ADMIN, ROL_TECNICO
from app.services import calidad_service, horario_service, ticket_service


async def resumen(sesion) -> dict[str, Any]:
    db = get_db()
    desde, hasta = ticket_service.rango_30d()
    es_tecnico = sesion.es_tecnico
    consultas_base = {"creado_en": {"$gte": desde}, "$or": [{"reportante_id": sesion.id}, {"afectado_id": sesion.id}]}

    if not es_tecnico:
        abiertos = await db["tickets"].count_documents(
            {**consultas_base, "estado": {"$nin": list(ESTADOS_CERRADOS)}}
        )
        return {
            "es_usuario": True,
            "tickets_abiertos": abiertos,
            "tickets_mios": abiertos,
            "mis_equipos": await db["activos"].count_documents({"responsable_id": sesion.id, "activo": {"$ne": False}}),
            "ultimas_actualizaciones": await _ultima_actualizacion(db, consultas_base),
        }

    abiertos = await db["tickets"].count_documents({"estado": {"$nin": list(ESTADOS_CERRADOS)}})
    sin_asignar = await db["tickets"].count_documents({"tecnico_id": None, "estado": {"$nin": list(ESTADOS_CERRADOS)}})
    criticos = await db["tickets"].count_documents(
        {"prioridad": "critica", "estado": {"$nin": list(ESTADOS_CERRADOS)}}
    )
    mios = await db["tickets"].count_documents(
        {"tecnico_id": sesion.id, "estado": {"$nin": list(ESTADOS_CERRADOS)}}
    )
    resueltos = await db["tickets"].find(
        {"creado_en": {"$gte": desde}, "tiempo_resolucion_min": {"$ne": None}},
        {"tiempo_resolucion_min": 1, "sla_incumplido": 1, "satisfaccion": 1, "estado": 1},
    ).to_list(None)
    tiempos = [t["tiempo_resolucion_min"] for t in resueltos if t.get("tiempo_resolucion_min") is not None]
    incumplidos = sum(1 for t in resueltos if t.get("sla_incumplido"))
    valoraciones = [t["satisfaccion"] for t in resueltos if t.get("satisfaccion") is not None]
    cumplimiento = (
        round(100 * (1 - incumplidos / len(resueltos)), 1) if resueltos else None
    )
    riesgo = await db["tickets"].count_documents(
        {
            "estado": {"$nin": list(ESTADOS_CERRADOS)},
            "sla_resolver_en": {"$lte": ticket_service.riesgo_horas()},
        }
    )
    total_activos = await db["activos"].count_documents({"activo": {"$ne": False}})
    calidad = await calidad_service.resumen(limite_pendientes=6)
    panel = await horario_service.panel_equipo()
    carga = sorted(panel, key=lambda t: t.get("porcentaje_carga", 0), reverse=True)
    top_oficinas = await agregar(
        "tickets",
        [
            {"$match": {"creado_en": {"$gte": desde}}},
            {"$group": {"_id": "$oficina_nombre", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": 5},
        ],
    )
    top_categorias = await agregar(
        "tickets",
        [
            {"$match": {"creado_en": {"$gte": desde}}},
            {"$group": {"_id": "$categoria", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": 5},
        ],
    )
    from app.services import campana_service

    return {
        "es_usuario": False,
        "tickets_abiertos": abiertos,
        "tickets_sin_asignar": sin_asignar,
        "tickets_sla_riesgo": riesgo,
        "tickets_criticos": criticos,
        "tickets_mios": mios,
        "tickets_resueltos_periodo": len(resueltos),
        "tiempo_medio_resolucion_min": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
        "cumplimiento_sla": cumplimiento,
        "satisfaccion_promedio": round(sum(valoraciones) / len(valoraciones), 2) if valoraciones else None,
        "total_activos": total_activos,
        "activos_con_datos_faltantes": calidad["total_activos"] - calidad["con_datos_completos"],
        "completitud_inventario": calidad["porcentaje_global"],
        "usuarios_activos": await db["usuarios"].count_documents({"activo": True}),
        "zonas": await db["zonas"].count_documents({"activa": True}),
        "oficinas": await db["oficinas"].count_documents({"activa": True}),
        "equipo_disponible": sum(1 for t in panel if t["estado"] == "disponible"),
        "equipo_total": len(panel),
        "tecnico_mas_carga": carga[0]["tecnico_nombre"] if carga else None,
        "top_oficinas": [{"oficina": o["_id"] or "Sin oficina", "total": o["total"]} for o in top_oficinas],
        "top_categorias": [{"categoria": c["_id"] or "Sin clasificar", "total": c["total"]} for c in top_categorias],
        "pendientes_calidad": calidad["pendientes"],
        "campana_activa": await campana_service.campana_activa(),
        "ultimas_actualizaciones": await _ultima_actualizacion(db, {}),
        "actualizado_en": utcnow(),
        "puede_ver_reportes": sesion.tiene("reportes.ver"),
        "puede_gestionar_inventario": sesion.tiene("equipos.editar") or sesion.es_admin,
    }


async def _ultima_actualizacion(db, consulta: dict[str, Any]):
    documento = await db["tickets"].find_one(consulta, {"actualizado_en": 1}, sort=[("actualizado_en", -1)])
    return (documento or {}).get("actualizado_en")
