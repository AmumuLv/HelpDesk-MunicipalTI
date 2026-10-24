"""Modelos estadisticos: prediccion de fallas de equipos y proyeccion de volumen.

Reglas de honestidad estadistica:
- Si no hay suficientes datos se responde "Datos insuficientes" indicando el minimo.
- Toda prediccion muestra probabilidad, horizonte, confianza y fecha de actualizacion.
- Nunca se presenta como certeza; el metodo usado se declara explicitamente.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import numpy as np
from bson import ObjectId
from sklearn.linear_model import LinearRegression, LogisticRegression

from app.core.db import agregar, get_db
from app.core.time import utcnow

MINIMO_MUESTRAS_MODELO = 30
MINIMO_MUESTRAS_PRONOSTICO = 14
_CACHE: dict[str, Any] = {"modelo": None, "generado": None, "datos": None}


def _datos_suficientes(n: int, minimo: int = MINIMO_MUESTRAS_MODELO) -> dict[str, Any]:
    return {
        "suficiente_datos": n >= minimo,
        "muestras": n,
        "minimo_requerido": minimo,
    }


def antiguedad_dias(activo: dict[str, Any]) -> int | None:
    garantia = ((activo.get("detalle_avanzado") or {}).get("compra_garantia") or {}) if activo.get("opciones_avanzadas") else {}
    referencia = garantia.get("fecha_compra") or activo.get("creado_en")
    if not referencia:
        return None
    if isinstance(referencia, date) and not hasattr(referencia, "hour"):
        dias = (utcnow().date() - referencia).days
    elif hasattr(referencia, "date"):
        dias = (utcnow().date() - referencia.date()).days
    else:
        dias = None
    return dias if dias is not None and dias >= 0 else None


def garantia_vigente(activo: dict[str, Any]) -> bool | None:
    garantia = ((activo.get("detalle_avanzado") or {}).get("compra_garantia") or {}) if activo.get("opciones_avanzadas") else {}
    vencimiento = garantia.get("vencimiento_garantia")
    if not vencimiento:
        return None
    try:
        fecha = (
            vencimiento
            if isinstance(vencimiento, date) and not hasattr(vencimiento, "hour")
            else (vencimiento.date() if hasattr(vencimiento, "date") else date.fromisoformat(str(vencimiento)[:10]))
        )
    except (TypeError, ValueError):
        return None
    return fecha >= utcnow().date()


def ram_instalada(activo: dict[str, Any]) -> float | None:
    detalle = activo.get("detalle_avanzado") or {}
    modulos = detalle.get("memoria_modulos") or []
    if modulos:
        return round(sum(float(m.get("capacidad_gb") or 0) for m in modulos), 1)
    texto = (activo.get("memoria_ram") or "").lower()
    coincidencia = re.search(r"(\d+(?:[.,]\d+)?)\s*gb", texto)
    if coincidencia:
        try:
            return float(coincidencia.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def ram_libre_gb(activo: dict[str, Any]) -> float | None:
    detalle = activo.get("detalle_avanzado") or {}
    madre = detalle.get("placa_madre") or {}
    if not madre:
        return None
    try:
        maxima = float(madre.get("ram_maxima_soportada") or 0)
        instalada = ram_instalada(activo) or 0.0
    except (TypeError, ValueError):
        return None
    if maxima <= 0:
        return None
    return round(max(maxima - instalada, 0), 1)


def _caracteristicas(activo: dict[str, Any], conteo_tickets: int) -> list[float] | None:
    dias = antiguedad_dias(activo)
    if dias is None:
        return None
    tipos = ["cpu", "laptop", "monitor", "impresora", "teclado", "mouse", "router", "switch", "servidor", "ups"]
    tipo_indice = next((i for i, t in enumerate(tipos) if t in str(activo.get("tipo", "")).lower()), len(tipos))
    ram = ram_instalada(activo) or 0.0
    garantia = garantia_vigente(activo)
    return [
        min(dias, 3650) / 365.0,
        float(tipo_indice),
        ram / 16.0,
        float(conteo_tickets),
        1.0 if garantia else (0.0 if garantia is False else 0.5),
        1.0 if (activo.get("opciones_avanzadas") and activo.get("detalle_avanzado")) else 0.0,
    ]


def _a_utc(dia: date) -> datetime:
    return datetime.combine(dia, time(0, 0), tzinfo=timezone.utc)


async def _datos_entrenamiento() -> dict[str, Any]:
    """Arma el conjunto de datos con informacion real del historial."""
    db = get_db()
    fecha_corte = utcnow().date() - timedelta(days=365)
    desde = _a_utc(fecha_corte)
    pipeline = [
        {
            "$match": {
                "activo": {"$ne": False},
                "creado_en": {"$lte": desde},
                "tipo_normalizado": {"$in": ["cpu", "laptop", "monitor", "impresora"]},
            }
        },
        {
            "$lookup": {
                "from": "tickets",
                "let": {"id_activo": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$activo_id", "$$id_activo"]}, "creado_en": {"$gte": desde}, "eliminado": {"$ne": True}}},
                    {"$group": {"_id": None, "total": {"$sum": 1}, "hardware": {"$sum": {"$cond": [{"$eq": ["$categoria", "Hardware"]}, 1, 0]}}}},
                ],
                "as": "historial",
            }
        },
        {
            "$addFields": {
                "tickets_12m": {"$ifNull": [{"$arrayElemAt": ["$historial.total", 0]}, 0]},
                "fallos_12m": {"$ifNull": [{"$arrayElemAt": ["$historial.hardware", 0]}, 0]},
            }
        },
        {"$project": {"_id": 1, "historial": 0}},
    ]
    filas_x: list[list[float]] = []
    filas_y: list[int] = []
    referencia: dict[ObjectId, float] = {}
    documentos = await agregar('activos', pipeline)
    for documento in documentos:
        caracteristicas = _caracteristicas(documento, int(documento.get("tickets_12m", 0)))
        if caracteristicas is None:
            continue
        filas_x.append(caracteristicas)
        filas_y.append(1 if documento.get("fallos_12m", 0) > 0 else 0)
        referencia[documento["_id"]] = float(documento.get("tickets_12m", 0))
    return {"x": filas_x, "y": filas_y, "referencia": referencia}


async def _modelo() -> dict[str, Any]:
    ahora = utcnow()
    if _CACHE["modelo"] is not None and _CACHE["generado"] and (ahora - _CACHE["generado"]).total_seconds() < 3600:
        return _CACHE
    datos = await _datos_entrenamiento()
    suficiente = _datos_suficientes(len(datos["x"]))
    modelo = None
    if suficiente["suficiente_datos"] and len(set(datos["y"])) > 1:
        try:
            modelo = LogisticRegression(max_iter=500, class_weight="balanced")
            modelo.fit(np.array(datos["x"]), np.array(datos["y"]))
        except Exception:  # pragma: no cover
            modelo = None
    _CACHE.update({"modelo": modelo, "generado": ahora, "datos": datos, "suficiente": suficiente})
    return _CACHE


def _probabilidad_regla(activo: dict[str, Any], conteo_tickets: int) -> tuple[float, list[str], str]:
    """Regla transparente usada cuando no hay datos para entrenar."""
    factores: list[str] = []
    puntos = 0.10
    dias = antiguedad_dias(activo)
    if dias is not None:
        if dias > 1095:
            puntos += 0.28
            factores.append(f"antiguedad de {dias // 365} anos")
        elif dias > 730:
            puntos += 0.18
            factores.append(f"antiguedad de {dias // 365} anos")
        elif dias > 365:
            puntos += 0.08
            factores.append("antiguedad de 1 ano o mas")
    if not garantia_vigente(activo) and garantia_vigente(activo) is False:
        puntos += 0.12
        factores.append("garantia vencida")
    if conteo_tickets >= 3:
        puntos += 0.20
        factores.append(f"{conteo_tickets} tickets en los ultimos 12 meses")
    elif conteo_tickets == 2:
        puntos += 0.10
        factores.append("2 tickets en los ultimos 12 meses")
    estado = (activo.get("estado") or "").lower()
    if "reparaci" in estado:
        puntos += 0.20
        factores.append("ya estuvo en reparacion")
    if (activo.get("tipo") or "").lower() == "impresora":
        puntos += 0.05
        factores.append("las impresoras fallan mas seguido")
    ram = ram_instalada(activo)
    if ram is not None and ram <= 4:
        puntos += 0.05
        factores.append("memoria RAM reducida")
    return round(min(puntos, 0.9), 2), factores, "regla_heuristica"


def _nivel(probabilidad: float) -> str:
    if probabilidad >= 0.6:
        return "alta"
    if probabilidad >= 0.3:
        return "media"
    return "baja"


async def predecir_falla(activo: dict[str, Any]) -> dict[str, Any]:
    """Probabilidad de falla con horizonte y confianza. Nunca como certeza."""
    db = get_db()
    desde = utcnow() - timedelta(days=365)
    conteo = await db["tickets"].count_documents({"activo_id": activo["_id"], "creado_en": {"$gte": desde}, "eliminado": {"$ne": True}})
    cache = await _modelo()
    suficiente = cache.get("suficiente") or _datos_suficientes(0)
    modelo = cache.get("modelo")
    factores: list[str] = []
    metodo = "regla_heuristica"
    probabilidad: float | None = None
    confianza = 0.35
    if modelo is not None:
        caracteristicas = _caracteristicas(activo, conteo)
        if caracteristicas is not None:
            try:
                probabilidad = float(modelo.predict_proba(np.array([caracteristicas]))[0][1])
                metodo = "modelo_entrenado"
                confianza = 0.6
                dias = antiguedad_dias(activo)
                if dias:
                    factores.append(f"antiguedad de {dias} dias")
                if conteo:
                    factores.append(f"{conteo} tickets en 12 meses")
                if garantia_vigente(activo) is False:
                    factores.append("garantia vencida")
                ram = ram_instalada(activo)
                if ram:
                    factores.append(f"RAM instalada {ram} GB")
            except Exception:  # pragma: no cover
                probabilidad = None
    if probabilidad is None:
        probabilidad, factores, metodo = _probabilidad_regla(activo, conteo)
        confianza = 0.35
    return {
        "probabilidad": round(probabilidad, 3),
        "nivel": _nivel(probabilidad),
        "horizonte_dias": 90,
        "confianza": round(confianza, 2),
        "factores": factores,
        "suficiente_datos": metodo == "modelo_entrenado",
        "muestras": suficiente.get("muestras", 0),
        "minimo_requerido": suficiente.get("minimo_requerido", MINIMO_MUESTRAS_MODELO),
        "actualizado_en": utcnow(),
        "tickets_historia": conteo,
        "dias_activo": antiguedad_dias(activo),
        "garantia_vigente": garantia_vigente(activo),
        "metodo": metodo,
        "aviso": "Indicador orientativo basado en el historial. No es una probabilidad de falla futura validada; requiere evaluación de TI.",
    }


async def predecir_familias(limite: int = 10) -> list[dict[str, Any]]:
    """Familias de equipos con mayor tasa de falla y su prediccion."""
    db = get_db()
    desde_utc = _a_utc(utcnow().date() - timedelta(days=365))
    pipeline = [
        {"$match": {"activo": {"$ne": False}}},
        {
            "$lookup": {
                "from": "tickets",
                "let": {"id_activo": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$activo_id", "$$id_activo"]}, "creado_en": {"$gte": desde_utc}, "eliminado": {"$ne": True}}},
                    {"$group": {"_id": None, "total": {"$sum": 1}}},
                ],
                "as": "historial",
            }
        },
        {"$addFields": {"tickets_12m": {"$ifNull": [{"$arrayElemAt": ["$historial.total", 0]}, 0]}}},
        {"$group": {"_id": "$tipo", "activos": {"$sum": 1}, "tickets": {"$sum": "$tickets_12m"}, "con_fallas": {"$sum": {"$cond": [{"$gt": ["$tickets_12m", 0]}, 1, 0]}}}},
        {"$sort": {"tickets": -1}},
        {"$limit": limite},
    ]
    filas = await agregar('activos', pipeline)
    salida: list[dict[str, Any]] = []
    for fila in filas:
        activos = fila.get("activos", 0) or 1
        tickets = fila.get("tickets", 0) or 0
        con_fallas = fila.get("con_fallas", 0) or 0
        tasa = round(tickets / activos, 3)
        proporcion = round(con_fallas / activos, 3)
        salida.append(
            {
                "tipo": fila.get("_id"),
                "activos": activos,
                "tickets_12m": tickets,
                "tasa_falla": round(con_fallas / activos, 3),
                "tickets_por_equipo": tasa,
                # Compatibilidad: es la proporción observada, nunca tickets/equipos (>1).
                "probabilidad": proporcion,
                "nivel": _nivel(proporcion),
                "metodo": "regla_heuristica",
                "metodo_explicacion": "Proporción de equipos con al menos un ticket en los últimos 12 meses. Es un dato histórico, no una probabilidad futura ni la salida de un modelo entrenado.",
                "horizonte_dias": 365,
                "confianza": 0.3,
                "suficiente_datos": activos >= MINIMO_MUESTRAS_MODELO and tickets >= 5,
                "minimo_requerido": MINIMO_MUESTRAS_MODELO,
                "actualizado_en": utcnow(),
            }
        )
    return salida


async def proyectar_volumen(
    serie: list[tuple[date, int]], *, horizonte_dias: int = 30
) -> dict[str, Any]:
    """Proyeccion de volumen diario con banda de confianza (regresion lineal)."""
    suficiente = _datos_suficientes(len(serie), MINIMO_MUESTRAS_PRONOSTICO)
    if not suficiente["suficiente_datos"] or sum(valor for _, valor in serie) < 5:
        return {
            "suficiente_datos": False,
            "muestras": suficiente["muestras"],
            "minimo_requerido": suficiente["minimo_requerido"],
            "observado": [{"fecha": d.isoformat(), "valor": v} for d, v in serie],
            "proyectado": [],
            "banda": [],
            "mensaje": "Datos insuficientes para proyectar. Se necesitan al menos 14 días de historial y 5 tickets.",
        }
    x = np.array([indice for indice, _ in enumerate(serie)], dtype=float)
    y = np.array([valor for _, valor in serie], dtype=float)
    modelo = LinearRegression()
    modelo.fit(x.reshape(-1, 1), y)
    inicio = len(serie)
    puntos = np.arange(inicio, inicio + horizonte_dias, dtype=float)
    predicciones = modelo.predict(puntos.reshape(-1, 1))
    residuos = y - modelo.predict(x.reshape(-1, 1))
    desviacion = float(np.std(residuos)) if len(residuos) > 1 else 0.0
    ultimo_dia = serie[-1][0]
    proyectado = [
        {
            "fecha": (ultimo_dia + timedelta(days=int(p - inicio + 1))).isoformat(),
            "valor": max(int(round(valor)), 0),
            "minimo": max(int(round(valor - 1.28 * desviacion)), 0),
            "maximo": max(int(round(valor + 1.28 * desviacion)), 0),
        }
        for p, valor in zip(puntos, predicciones)
    ]
    return {
        "suficiente_datos": True,
        "muestras": suficiente["muestras"],
        "minimo_requerido": suficiente["minimo_requerido"],
        "observado": [{"fecha": d.isoformat(), "valor": v} for d, v in serie],
        "proyectado": proyectado,
        "tendencia": "sube" if modelo.coef_[0] > 0.05 else ("baja" if modelo.coef_[0] < -0.05 else "estable"),
        "pendiente": round(float(modelo.coef_[0]), 4),
        "actualizado_en": utcnow(),
    }


def distribucion_confianza(valores: list[float]) -> list[dict[str, Any]]:
    total = len(valores)
    if not total:
        return []
    baja = sum(1 for v in valores if v < 0.55)
    media = sum(1 for v in valores if 0.55 <= v < 0.8)
    alta = sum(1 for v in valores if v >= 0.8)
    return [
        {"nivel": "baja", "cantidad": baja, "porcentaje": round(100 * baja / total, 1)},
        {"nivel": "media", "cantidad": media, "porcentaje": round(100 * media / total, 1)},
        {"nivel": "alta", "cantidad": alta, "porcentaje": round(100 * alta / total, 1)},
    ]


def media(valores: list[float]) -> float | None:
    if not valores:
        return None
    return round(sum(valores) / len(valores), 3)


def desviacion(valores: list[float]) -> float:
    if len(valores) < 2:
        return 0.0
    promedio = sum(valores) / len(valores)
    return math.sqrt(sum((v - promedio) ** 2 for v in valores) / (len(valores) - 1))


async def invalidar_cache() -> None:
    _CACHE.update({"modelo": None, "generado": None, "datos": None})
