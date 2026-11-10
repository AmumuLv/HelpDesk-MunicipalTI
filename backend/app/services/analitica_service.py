"""Analitica institucional: agregaciones reales sobre MongoDB y metricas honestas.

Ninguna cifra se inventa: cada bloque dice de donde sale, y cuando faltan datos
devuelve "datos insuficientes" con el minimo requerido.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId

from app.core.db import agregar, get_db
from app.core.ids import rango_fechas
from app.core.errors import Validacion
from app.core.time import business_tz, local_date, utcnow
from app.domain.constants import ESTADOS_CERRADOS, PESO_PRIORIDAD
from app.services import horario_service, ml_service, sla_service

CAMPOS_ESTADO = list(ESTADOS_CERRADOS)


def _a_utc(dia: date) -> datetime:
    return datetime.combine(dia, time(0, 0), tzinfo=business_tz()).astimezone(timezone.utc)


def _b_utc(dia: date) -> datetime:
    return datetime.combine(dia, time(23, 59, 59, 999999), tzinfo=business_tz()).astimezone(timezone.utc)


def resolver_periodo(filtros: dict[str, Any]) -> tuple[date, date, date, date]:
    """Devuelve (desde, hasta, desde_anterior, hasta_anterior)."""
    if bool(filtros.get("desde")) != bool(filtros.get("hasta")):
        raise Validacion("Indica tanto la fecha inicial como la final.")
    if filtros.get("desde") and filtros.get("hasta"):
        try:
            desde, hasta = (date.fromisoformat(v) if isinstance(v, str) else v for v in (filtros["desde"], filtros["hasta"]))
        except (ValueError, TypeError):
            raise Validacion("Las fechas del periodo no son válidas.")
    else:
        if filtros.get("periodo") not in (None, "", "7d", "30d", "90d", "365d", "mes", "mes_anterior", "anio"):
            raise Validacion("Selecciona un periodo válido.")
        desde, hasta = rango_fechas(filtros.get("periodo") or "30d", local_date())
    dias = (hasta - desde).days + 1
    if dias < 1 or dias > 366:
        raise Validacion("El periodo debe tener entre 1 y 366 días.")
    hasta_anterior = desde - timedelta(days=1)
    desde_anterior = hasta_anterior - timedelta(days=dias - 1)
    return desde, hasta, desde_anterior, hasta_anterior


def _match(filtros: dict[str, Any], desde: date, hasta: date) -> dict[str, Any]:
    consulta: dict[str, Any] = {"eliminado": {"$ne": True}, "creado_en": {"$gte": _a_utc(desde), "$lt": _a_utc(hasta + timedelta(days=1))}}
    if filtros.get("zona_id"):
        consulta["zona_id"] = filtros["zona_id"]
    if filtros.get("oficina_id"):
        consulta["oficina_id"] = filtros["oficina_id"]
    if filtros.get("categoria"):
        consulta["categoria"] = filtros["categoria"]
    if filtros.get("tecnico_id"):
        consulta["tecnico_id"] = filtros["tecnico_id"]
    if filtros.get("equipo_id"):
        consulta["activo_id"] = filtros["equipo_id"]
    if filtros.get("tipo_activo"):
        consulta["activo_tipo"] = filtros["tipo_activo"]
    return consulta


async def _conteo_por(consulta: dict[str, Any], campo: str) -> list[dict[str, Any]]:
    pipeline = [
        {"$match": consulta},
        {"$group": {"_id": f"${campo}", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
    ]
    return await agregar('tickets', pipeline)


# ── Bloque 1 y 2: ranking por oficina y por zona ─────────────
async def ranking_oficinas(filtros: dict[str, Any]) -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    db = get_db()
    consulta = _match(filtros, desde, hasta)
    pipeline = [
        {"$match": consulta},
        {
            "$group": {
                "_id": {"oficina_id": "$oficina_id", "nombre": "$oficina_nombre", "zona": "$zona_nombre"},
                "total": {"$sum": 1},
                "criticas": {"$sum": {"$cond": [{"$eq": ["$prioridad", "critica"]}, 1, 0]}},
                "abiertos": {"$sum": {"$cond": [{"$in": ["$estado", ["nuevo", "en_progreso", "en_espera"]]}, 1, 0]}},
                "vencidos": {"$sum": {"$cond": [{"$eq": ["$sla_incumplido", True]}, 1, 0]}},
            }
        },
        {"$sort": {"total": -1}},
    ]
    filas = await agregar('tickets', pipeline)
    offices_ids = [f["_id"].get("oficina_id") for f in filas if f["_id"].get("oficina_id")]
    zonas_ids = [f["_id"].get("zona") for f in filas]
    equipos_por_oficina = {}
    if offices_ids:
        for fila in await agregar(
            "activos",
            [
                {"$match": {"oficina_id": {"$in": offices_ids}, "activo": {"$ne": False}}},
                {"$group": {"_id": "$oficina_id", "total": {"$sum": 1}}},
            ],
        ):
            equipos_por_oficina[str(fila["_id"])] = fila["total"]
    usuarios_por_oficina = {}
    if offices_ids:
        for fila in await agregar(
            "usuarios",
            [
                {"$match": {"oficina_id": {"$in": offices_ids}, "activo": True}},
                {"$group": {"_id": "$oficina_id", "total": {"$sum": 1}}},
            ],
        ):
            usuarios_por_oficina[str(fila["_id"])] = fila["total"]

    items = []
    for fila in filas:
        id_oficina = fila["_id"].get("oficina_id")
        clave_oficina = str(id_oficina) if id_oficina else ""
        equipos = equipos_por_oficina.get(clave_oficina, 0) or 0
        usuarios = usuarios_por_oficina.get(clave_oficina, 0) or 0
        items.append(
            {
                "id": clave_oficina or None,
                "oficina": fila["_id"].get("nombre") or "Sin oficina",
                "zona": fila["_id"].get("zona") or "Sin zona",
                "total": fila["total"],
                "criticas": fila.get("criticas", 0),
                "abiertos": fila.get("abiertos", 0),
                "vencidos": fila.get("vencidos", 0),
                "por_equipo": round(fila["total"] / equipos, 2) if equipos else None,
                "por_usuario": round(fila["total"] / usuarios, 2) if usuarios else None,
                "equipos": equipos,
                "usuarios": usuarios,
            }
        )
    return {
        "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "items": items,
        "normalizado": any(i["por_equipo"] is not None for i in items),
        "maximo": max((i["total"] for i in items), default=0),
    }


async def ranking_zonas(filtros: dict[str, Any]) -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    db = get_db()
    consulta = _match(filtros, desde, hasta)
    pipeline = [
        {"$match": consulta},
        {
            "$group": {
                "_id": {"zona_id": "$zona_id", "nombre": "$zona_nombre"},
                "total": {"$sum": 1},
                "abiertos": {"$sum": {"$cond": [{"$in": ["$estado", ["nuevo", "en_progreso", "en_espera"]]}, 1, 0]}},
                "criticas": {"$sum": {"$cond": [{"$eq": ["$prioridad", "critica"]}, 1, 0]}},
            }
        },
        {"$sort": {"total": -1}},
    ]
    zonas = await agregar('tickets', pipeline)
    items: list[dict[str, Any]] = []
    for zona in zonas:
        sub = {**consulta, "zona_id": zona["_id"].get("zona_id")}
        oficinas = await agregar("tickets", [
                {"$match": sub},
                {"$group": {"_id": {"oficina_id": "$oficina_id", "nombre": "$oficina_nombre"}, "total": {"$sum": 1}}},
                {"$sort": {"total": -1}},
            ])
        usuarios = await agregar("tickets", [
                {"$match": sub},
                {
                    "$group": {
                        "_id": {"usuario": "$afectado_nombre", "oficina": "$oficina_nombre"},
                        "total": {"$sum": 1},
                    }
                },
                {"$sort": {"total": -1}},
                {"$limit": 8},
            ])
        equipos = await agregar("tickets", [
                {"$match": sub},
                {"$group": {"_id": {"activo": "$activo_nombre", "tipo": None}, "total": {"$sum": 1}}},
                {"$sort": {"total": -1}},
                {"$limit": 8},
            ])
        items.append(
            {
                "id": str(zona["_id"].get("zona_id")) if zona["_id"].get("zona_id") else None,
                "zona": zona["_id"].get("nombre") or "Sin zona",
                "total": zona["total"],
                "abiertos": zona.get("abiertos", 0),
                "criticas": zona.get("criticas", 0),
                "oficinas": [
                    {
                        "id": str(o["_id"].get("oficina_id")) if o["_id"].get("oficina_id") else None,
                        "oficina": o["_id"].get("nombre") or "Sin oficina",
                        "total": o["total"],
                    }
                    for o in oficinas
                ],
                "usuarios": [
                    {"nombre": u["_id"].get("usuario") or "Sin nombre", "oficina": u["_id"].get("oficina"), "total": u["total"]}
                    for u in usuarios
                ],
                "equipos": [{"nombre": e["_id"].get("activo") or "Sin equipo", "total": e["total"]} for e in equipos],
            }
        )
    return {"items": items}


# ── Bloque 3: mapa de calor ───────────────────────────────────
async def mapa_calor(filtros: dict[str, Any], *, eje: str = "categoria") -> dict[str, Any]:
    desde, hasta, desde_anterior, hasta_anterior = resolver_periodo(filtros)
    consulta = _match(filtros, desde, hasta)
    campo_valor = "$prioridad" if eje == "prioridad" else "$categoria"
    filas = await agregar(
        "tickets",
        [
            {"$match": consulta},
            {"$group": {"_id": {"zona": "$zona_nombre", "oficina": "$oficina_nombre", "valor": campo_valor}, "total": {"$sum": 1}}},
        ],
    )
    filas_anteriores = await agregar(
        "tickets",
        [
            {"$match": _match(filtros, desde_anterior, hasta_anterior)},
            {"$group": {"_id": {"zona": "$zona_nombre", "oficina": "$oficina_nombre", "valor": campo_valor}, "total": {"$sum": 1}}},
        ],
    )
    base_previa = {f"{f['_id'].get('zona')}|{f['_id'].get('oficina')}|{f['_id'].get('valor')}": f["total"] for f in filas_anteriores}
    total_general = sum(f["total"] for f in filas) or 1
    celdas = []
    for fila in filas:
        clave = f"{fila['_id'].get('zona')}|{fila['_id'].get('oficina')}|{fila['_id'].get('valor')}"
        celdas.append(
            {
                "zona": fila["_id"].get("zona") or "Sin zona",
                "oficina": fila["_id"].get("oficina") or "Sin oficina",
                "valor": fila["_id"].get("valor") or "Sin clasificar",
                "total": fila["total"],
                "porcentaje": round(100 * fila["total"] / total_general, 1),
                "variacion": round(100 * (fila["total"] - base_previa.get(clave, 0)) / max(base_previa.get(clave, 0), 1), 1)
                if base_previa.get(clave)
                else None,
            }
        )
    return {"eje": eje, "celdas": celdas, "total": total_general}


# ── Bloque 4: tendencia y proyeccion ──────────────────────────
async def tendencia(filtros: dict[str, Any], *, horizonte: int = 30) -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    consulta = _match(filtros, desde, hasta)
    pipeline = [
        {"$match": consulta},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$creado_en", "timezone": business_tz().key}},
                "total": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    filas = await agregar('tickets', pipeline)
    mapa = {f["_id"]: f["total"] for f in filas}
    serie: list[tuple[date, int]] = []
    dias = (hasta - desde).days + 1
    for indice in range(max(dias, 1)):
        dia = desde + timedelta(days=indice)
        serie.append((dia, mapa.get(dia.isoformat(), 0)))
    primer_registro = next((i for i, (_, valor) in enumerate(serie) if valor > 0), len(serie))
    proyeccion = await ml_service.proyectar_volumen(serie[primer_registro:], horizonte_dias=horizonte)
    return {
        "serie": [{"fecha": d.isoformat(), "valor": v} for d, v in serie],
        "proyeccion": proyeccion,
        "total_periodo": sum(v for _, v in serie),
    }


# ── Bloque 5: riesgo de SLA ──────────────────────────────────
async def riesgo_sla(filtros: dict[str, Any], *, agrupar_por: str = "categoria") -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    consulta = {**_match(filtros, desde, hasta), "estado": {"$nin": CAMPOS_ESTADO}}
    if agrupar_por == "oficina":
        campo = "$oficina_nombre"
    elif agrupar_por == "tecnico":
        campo = "$tecnico_nombre"
    else:
        campo = "$categoria"
    pipeline = [
        {"$match": consulta},
        {
            "$group": {
                "_id": campo,
                "total": {"$sum": 1},
                "vencidos": {"$sum": {"$cond": [{"$eq": ["$sla_incumplido", True]}, 1, 0]}},
                "riesgo_critico": {"$sum": {"$cond": [{"$eq": ["$sla_riesgo", "critico"]}, 1, 0]}},
            }
        },
    ]
    filas = await agregar('tickets', pipeline)
    ahora = utcnow()
    detalle: list[dict[str, Any]] = []
    for fila in filas:
        sub = dict(consulta)
        if agrupar_por == "oficina":
            sub["oficina_nombre"] = fila["_id"]
        elif agrupar_por == "tecnico":
            sub["tecnico_nombre"] = fila["_id"]
        else:
            sub["categoria"] = fila["_id"]
        tickets = await get_db()["tickets"].find(
            sub, {"sla_resolver_en": 1, "sla_horas_resolver": 1, "estado": 1}
        ).to_list(None)
        safe = attention = critical = vencidos = sin_plazo = 0
        for ticket in tickets:
            if not ticket.get("sla_resolver_en"):
                sin_plazo += 1
                continue
            restante = (ticket["sla_resolver_en"] - ahora).total_seconds() / 60
            total = float(ticket.get("sla_horas_resolver") or 1) * 60
            if restante <= 0:
                critical += 1
                vencidos += 1
            elif restante / max(total, 1) < 0.25:
                critical += 1
            elif restante / max(total, 1) < 0.6:
                attention += 1
            else:
                safe += 1
        total = safe + attention + critical or 1
        detalle.append(
            {
                "nombre": fila["_id"] or "Sin clasificar",
                "total": fila["total"],
                "seguro": safe,
                "atencion": attention,
                "critico": critical,
                "vencidos": vencidos,
                "sin_plazo": sin_plazo,
                "porcentaje_critico": round(100 * critical / total, 1),
            }
        )
    detalle.sort(key=lambda item: -item["porcentaje_critico"])
    return {"agrupar_por": agrupar_por, "items": detalle}


# ── Bloque 6: causas recurrentes ─────────────────────────────
async def causas_recurrentes(filtros: dict[str, Any], *, limite: int = 12) -> dict[str, Any]:
    desde, hasta, desde_anterior, hasta_anterior = resolver_periodo(filtros)
    consulta = _match(filtros, desde, hasta)
    actual = await agregar("tickets", [
            {"$match": consulta},
            {
                "$group": {
                    "_id": {
                        "categoria": "$categoria",
                        "problema": {"$ifNull": ["$tipo_problema", None]},
                    },
                    "total": {"$sum": 1},
                }
            },
            {"$sort": {"total": -1}},
            {"$limit": limite},
        ]
    )
    consulta_anterior = {**_match(filtros, desde_anterior, hasta_anterior)}
    previos = await agregar("tickets", [
            {"$match": consulta_anterior},
            {
                "$group": {
                    "_id": {
                        "categoria": "$categoria",
                        "problema": {"$ifNull": ["$tipo_problema", None]},
                    },
                    "total": {"$sum": 1},
                }
            },
        ])
    mapa_previo = {
        f"{f['_id'].get('categoria')}|{f['_id'].get('equipo')}|{f['_id'].get('problema')}": f["total"] for f in previos
    }
    items = []
    for fila in actual:
        clave = f"{fila['_id'].get('categoria')}|{fila['_id'].get('equipo')}|{fila['_id'].get('problema')}"
        anterior = mapa_previo.get(clave, 0)
        tendencia_pct = round(100 * (fila["total"] - anterior) / anterior, 1) if anterior else None
        items.append(
            {
                "categoria": fila["_id"].get("categoria") or "Sin clasificar",
                "equipo": filtros.get("tipo_activo") or "Todos los equipos",
                "problema": fila["_id"].get("problema"),
                "total": fila["total"],
                "periodo_anterior": anterior,
                "tendencia": tendencia_pct,
            }
        )
    return {"items": items, "suficiente_datos": bool(items)}


# ── Bloque 8 y 9: confianza y calidad de recomendaciones ─────
async def distribucion_confianza(filtros: dict[str, Any]) -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    consulta = _match(filtros, desde, hasta)
    valores = [
        float(t["confianza_ia"])
        for t in await get_db()["tickets"].find(
            consulta, {"confianza_ia": 1}
        ).to_list(None)
        if t.get("confianza_ia") is not None
    ]
    eventos = await get_db()["ia_eventos"].find(
        {"tipo": "clasificacion", "creado_en": {"$gte": _a_utc(desde), "$lte": _b_utc(hasta)}},
        {"confianza": 1},
    ).to_list(None)
    valores += [float(e["confianza"]) for e in eventos if e.get("confianza") is not None]
    if not valores:
        return {"items": [], "suficiente_datos": False, "minimo_requerido": 5, "confianza_media": None}
    return {
        "items": ml_service.distribucion_confianza(valores),
        "confianza_media": ml_service.media(valores),
        "suficiente_datos": len(valores) >= 5,
        "minimo_requerido": 5,
        "muestras": len(valores),
    }


async def calidad_recomendaciones(filtros: dict[str, Any]) -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    rango = {"$gte": _a_utc(desde), "$lte": _b_utc(hasta)}
    aplicadas = await get_db()["ia_eventos"].count_documents({"tipo": "decision", "decision": "aplicar", "creado_en": rango})
    editadas = await get_db()["ia_eventos"].count_documents({"tipo": "decision", "decision": "editar", "creado_en": rango})
    descartadas = await get_db()["ia_eventos"].count_documents({"tipo": "decision", "decision": "descartar", "creado_en": rango})
    feedback = await get_db()["ia_eventos"].find(
        {"tipo": "retroalimentacion", "creado_en": rango}, {"decision": 1}
    ).to_list(None)
    correctas = sum(1 for f in feedback if f.get("decision") == "correcta")
    precision = round(100 * correctas / len(feedback), 1) if feedback else None
    total = aplicadas + editadas + descartadas
    return {
        "aplicadas": aplicadas,
        "editadas": editadas,
        "descartadas": descartadas,
        "total_decisiones": total,
        "tasa_aplicacion": round(100 * aplicadas / total, 1) if total else None,
        "precision_confirmada": precision,
        "retroalimentaciones": len(feedback),
        "suficiente_datos": bool(feedback),
        "minimo_requerido": 5,
    }


# ── Bloque 10: carga y desempenho por tecnico ─────────────────
async def carga_tecnicos(filtros: dict[str, Any]) -> dict[str, Any]:
    desde, hasta, _, _ = resolver_periodo(filtros)
    db = get_db()
    consulta = _match(filtros, desde, hasta)
    consulta_asignados = {**consulta, "tecnico_id": consulta.get("tecnico_id", {"$ne": None})}
    filas = await agregar("tickets", [
            {"$match": consulta_asignados},
            {
                "$group": {
                    "_id": {"id": "$tecnico_id", "nombre": "$tecnico_nombre"},
                    "asignados": {"$sum": 1},
                    "resueltos": {"$sum": {"$cond": [{"$in": ["$estado", CAMPOS_ESTADO]}, 1, 0]}},
                    "incumplidos": {"$sum": {"$cond": [{"$eq": ["$sla_incumplido", True]}, 1, 0]}},
                    "tiempos": {"$push": "$tiempo_resolucion_min"},
                    "reaperturas": {"$sum": "$veces_reabierto"},
                    "valoraciones": {"$push": "$satisfaccion"},
                }
            },
            {"$sort": {"asignados": -1}},
        ])
    if not filtros.get("tecnico_id"):
        filas.append({"_id": {"id": None, "nombre": "Sin asignar"}, "asignados": await db["tickets"].count_documents(
            {**consulta, "tecnico_id": None}
        ), "resueltos": 0, "incumplidos": 0, "tiempos": [], "reaperturas": 0, "valoraciones": []})
    items = []
    for fila in filas:
        tecnico_id = fila["_id"].get("id")
        horas = 0.0
        carga_actual = 0
        disponibilidad = None
        if tecnico_id:
            horas = await horario_service.horas_laborables(tecnico_id, desde, hasta)
            carga_actual = await db["tickets"].count_documents(
                {"tecnico_id": tecnico_id, "estado": {"$nin": CAMPOS_ESTADO}, "eliminado": {"$ne": True}}
            )
            disponibilidad = (await horario_service.calcular_disponibilidad(tecnico_id))["etiqueta"]
        tiempos = [t for t in (fila.get("tiempos") or []) if t is not None]
        valoraciones = [v for v in (fila.get("valoraciones") or []) if v is not None]
        total = fila["asignados"] or 1
        items.append(
            {
                "tecnico_id": str(tecnico_id) if tecnico_id else None,
                "tecnico": fila["_id"].get("nombre") or "Sin asignar",
                "asignados": fila["asignados"],
                "resueltos": fila.get("resueltos", 0),
                "carga_actual": carga_actual,
                "disponibilidad": disponibilidad,
                "incumplidos": fila.get("incumplidos", 0),
                "cumplimiento_sla": round(100 * (1 - fila.get("incumplidos", 0) / total), 1),
                "tiempo_medio_resolucion_min": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
                "reaperturas": fila.get("reaperturas", 0),
                "satisfaccion": round(sum(valoraciones) / len(valoraciones), 2) if valoraciones else None,
                "horas_laborables": horas,
                "tickets_por_hora": round(fila.get("resueltos", 0) / horas, 2) if horas and fila.get("resueltos") else None,
                "horas_por_ticket": round(horas / fila["resueltos"], 2) if horas and fila.get("resueltos") else None,
                "suficiente_datos": len(tiempos) >= 3,
            }
        )
    return {"items": items, "normalizado_por_horas": True}


# ── KPIs ─────────────────────────────────────────────────────
async def kpis(filtros: dict[str, Any]) -> dict[str, Any]:
    desde, hasta, desde_anterior, hasta_anterior = resolver_periodo(filtros)
    db = get_db()
    consulta = _match(filtros, desde, hasta)
    total = await db["tickets"].count_documents(consulta)
    total_anterior = await db["tickets"].count_documents(_match(filtros, desde_anterior, hasta_anterior))
    resueltos = await agregar("tickets", [
            {"$match": consulta},
            {
                "$group": {
                    "_id": None,
                    "tiempos": {"$push": "$tiempo_resolucion_min"},
                    "incumplidos": {"$sum": {"$cond": [{"$eq": ["$sla_incumplido", True]}, 1, 0]}},
                    "valoraciones": {"$push": "$satisfaccion"},
                    "atendidos_a_tiempo": {"$sum": {"$cond": [{"$and": [{"$in": ["$estado", CAMPOS_ESTADO]}, {"$ne": ["$sla_incumplido", True]}]}, 1, 0]}},
                    "cerrados": {"$sum": {"$cond": [{"$in": ["$estado", CAMPOS_ESTADO]}, 1, 0]}},
                }
            },
        ])
    resumen = resueltos[0] if resueltos else {}
    tiempos = [t for t in (resumen.get("tiempos") or []) if t is not None]
    valoraciones = [v for v in (resumen.get("valoraciones") or []) if v is not None]
    cerrados = resumen.get("cerrados", 0) or 0
    cumplimiento = round(100 * resumen.get("atendidos_a_tiempo", 0) / cerrados, 1) if cerrados else None
    clasificacion = await agregar("tickets", [
            {"$match": {**consulta, "categoria": {"$ne": None}}},
            {"$group": {"_id": None, "total": {"$sum": 1}}},
        ])
    con_categoria = clasificacion[0]["total"] if clasificacion else 0
    riesgos = await db["tickets"].count_documents({**consulta, "sla_riesgo": "critico"})
    desde_ia = {"$gte": _a_utc(desde), "$lte": _b_utc(hasta)}
    decisiones = await db["ia_eventos"].count_documents({"tipo": "decision", "creado_en": desde_ia})
    aplicados = await db["ia_eventos"].count_documents({"tipo": "decision", "decision": "aplicar", "creado_en": desde_ia})
    tiempo_potencial = None
    if aplicados and tiempos:
        promedio = sum(tiempos) / len(tiempos)
        tiempo_potencial = round(promedio * aplicados / 60, 1)
    confianza = await distribucion_confianza(filtros)
    calidad = await calidad_recomendaciones(filtros)
    return {
        "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "tickets_analizados": total,
        "tickets_periodo_anterior": total_anterior,
        "variacion": round(100 * (total - total_anterior) / total_anterior, 1) if total_anterior else None,
        "cerrados": cerrados,
        "tiempo_medio_resolucion_min": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
        "muestras_tiempo": len(tiempos),
        "muestras_satisfaccion": len(valoraciones),
        "cerrados_a_tiempo": resumen.get("atendidos_a_tiempo", 0),
        "cumplimiento_sla": cumplimiento,
        "satisfaccion_promedio": round(sum(valoraciones) / len(valoraciones), 2) if valoraciones else None,
        "precision_clasificacion": calidad["precision_confirmada"],
        "cobertura_clasificacion": round(100 * con_categoria / total, 1) if total else None,
        "retroalimentaciones_clasificacion": calidad["retroalimentaciones"],
        "riesgos_detectados": riesgos,
        "casos_atendidos_anticipadamente": resumen.get("atendidos_a_tiempo", 0),
        "tiempo_potencial_ahorrado_h": tiempo_potencial,
        "confianza_media_modelo": confianza.get("confianza_media"),
        "recomendaciones_aplicadas": aplicados,
        "decisiones_ia": decisiones,
        "suficiente_datos": total >= 5,
        "minimo_requerido": 5,
    }


async def panel_completo(filtros: dict[str, Any]) -> dict[str, Any]:
    """Todo lo que necesita la pantalla de Analisis IA en una sola llamada."""
    familias = await ml_service.predecir_familias()
    return {
        "kpis": await kpis(filtros),
        "ranking_oficinas": await ranking_oficinas(filtros),
        "ranking_zonas": await ranking_zonas(filtros),
        "ranking_conjuntos": await ranking_conjuntos(filtros),
        "mapa_calor_categoria": await mapa_calor(filtros, eje="categoria"),
        "mapa_calor_prioridad": await mapa_calor(filtros, eje="prioridad"),
        "tendencia": await tendencia(filtros),
        "riesgo_sla_categoria": await riesgo_sla(filtros, agrupar_por="categoria"),
        "riesgo_sla_oficina": await riesgo_sla(filtros, agrupar_por="oficina"),
        "riesgo_sla_tecnico": await riesgo_sla(filtros, agrupar_por="tecnico"),
        "causas": await causas_recurrentes(filtros),
        "familias_equipos": familias,
        "confianza_modelo": await distribucion_confianza(filtros),
        "calidad_recomendaciones": await calidad_recomendaciones(filtros),
        "carga_tecnicos": await carga_tecnicos(filtros),
        "actualizado_en": utcnow(),
        "respaldo": {
            "fuente": "agregaciones MongoDB sobre la coleccion tickets",
            "zona_horaria": business_tz().key,
        },
    }


async def ranking_conjuntos(filtros: dict[str, Any]) -> dict[str, Any]:
    """Un caso se cuenta una vez: componente actual o vínculo directo a la PC."""
    desde, hasta, _, _ = resolver_periodo(filtros)
    filas = await agregar('tickets', [
        {'$match': _match(filtros, desde, hasta)},
        {'$lookup': {'from': 'activos', 'localField': 'activo_id', 'foreignField': '_id', 'as': 'equipo_actual'}},
        {'$set': {'pc_id': {'$ifNull': [{'$arrayElemAt': ['$equipo_actual.conjunto_id', 0]}, '$conjunto_id']}}},
        {'$match': {'pc_id': {'$ne': None}}},
        {'$group': {'_id': '$pc_id', 'total': {'$sum': 1},
                    'programas': {'$sum': {'$cond': [{'$eq': ['$alcance_incidencia', 'programa']}, 1, 0]}},
                    'abiertos': {'$sum': {'$cond': [{'$in': ['$estado', list(ESTADOS_CERRADOS)]}, 0, 1]}}}},
        {'$sort': {'total': -1, '_id': 1}},
        {'$lookup': {'from': 'conjuntos', 'localField': '_id', 'foreignField': '_id', 'as': 'pc'}},
        {'$unwind': '$pc'},
        {'$lookup': {'from': 'activos', 'localField': '_id', 'foreignField': 'conjunto_id', 'as': 'componentes'}},
    ])
    items = []
    db = get_db()
    for fila in filas:
        pc = fila['pc']
        responsables = {a.get('responsable_id') for a in fila['componentes'] if a.get('responsable_id') and a.get('activo', True)}
        responsable_id = pc.get('responsable_id') or (next(iter(responsables)) if len(responsables) == 1 else None)
        responsable = await db.usuarios.find_one({'_id': responsable_id}, {'nombre': 1}) if responsable_id else None
        oficina = await db.oficinas.find_one({'_id': pc.get('oficina_id')}, {'nombre': 1})
        items.append({'id': str(fila['_id']), 'nombre': pc.get('nombre'), 'oficina_id': str(pc['oficina_id']) if pc.get('oficina_id') else None,
                      'oficina': (oficina or {}).get('nombre') or pc.get('oficina_nombre') or 'Sin oficina',
                      'responsable_id': str(responsable_id) if responsable_id else None,
                      'responsable': (responsable or {}).get('nombre') or ('Varios responsables' if len(responsables) > 1 else 'Uso compartido'),
                      'total': fila['total'], 'programas': fila['programas'], 'abiertos': fila['abiertos']})
    return {'items': items, 'periodo': {'desde': desde, 'hasta': hasta}}


async def minimo_para_pronostico() -> dict[str, Any]:
    return {
        "dias_observados": ml_service.MINIMO_MUESTRAS_PRONOSTICO,
        "activos_para_modelo": ml_service.MINIMO_MUESTRAS_MODELO,
        "nota": "Sin estos datos el sistema muestra 'Datos insuficientes' en lugar de inventar valores.",
    }
