"""Calculo de SLA con calendario laboral configurable.

El reloj se pausa fuera de horario, en dias libres, en feriados y en dias no
laborables del calendario institucional. Todo se acumula solo sobre horas
laborables reales.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from app.core.time import business_tz, utcnow
from app.services import config_service, horario_service

MAX_ITERACIONES = 5000


def utc_tz():
    from datetime import timezone

    return timezone.utc


def dias_semana_index_local(dia: date) -> int:
    return dia.weekday() % 7


def _parsear_hora(valor: str) -> time | None:
    try:
        partes = [int(p) for p in str(valor).split(":")[:2]]
        return time(partes[0], partes[1])
    except (ValueError, IndexError):
        return None


def _tramos_del_dia(dia_local: date, tramos: list[dict[str, Any]]) -> list[tuple[datetime, datetime]]:
    """Tramos laborables de un dia local, expresados en UTC."""
    if dias_semana_index_local(dia_local) not in DIAS_LABORABLES_CACHE:
        return []
    tz = business_tz()
    utc = utc_tz()
    ventana: list[tuple[datetime, datetime]] = []
    for tramo in tramos:
        hora_entrada = _parsear_hora(tramo.get("entrada", ""))
        hora_salida = _parsear_hora(tramo.get("salida", ""))
        if hora_entrada is None or hora_salida is None:
            continue
        inicio = datetime.combine(dia_local, hora_entrada, tzinfo=tz).astimezone(utc)
        fin = datetime.combine(dia_local, hora_salida, tzinfo=tz).astimezone(utc)
        if fin <= inicio:
            fin += timedelta(days=1)
        ventana.append((inicio, fin))
    return ventana


# Dias laborables del calendario institucional (se rellena por peticion)
DIAS_LABORABLES_CACHE: list[int] = [1, 2, 3, 4, 5]


async def _ventanas_laborables(desde_utc: datetime, hasta_utc: datetime) -> list[tuple[datetime, datetime]]:
    """Tramos laborables (en UTC) dentro de un rango, saltando dias no laborables."""
    calendario = await config_service.calendario()
    dias_laborables = [int(d) for d in (calendario.get("dias_laborables") or [0, 1, 2, 3, 4])]
    DIAS_LABORABLES_CACHE.clear()
    DIAS_LABORABLES_CACHE.extend(dias_laborables)
    tramos = calendario.get("tramos") or [{"entrada": "08:00", "salida": "18:00"}]
    excluir_feriados = not bool(calendario.get("incluir_feriados", False))
    tz = business_tz()
    desde_local = desde_utc.astimezone(tz).date() - timedelta(days=1)
    hasta_local = hasta_utc.astimezone(tz).date() + timedelta(days=1)
    ventanas: list[tuple[datetime, datetime]] = []
    dia = desde_local
    while dia <= hasta_local:
        if dias_semana_index_local(dia) in dias_laborables:
            if not (excluir_feriados and await horario_service.es_feriado(dia)):
                for inicio, fin in _tramos_del_dia(dia, tramos):
                    ventana_inicio = max(inicio, desde_utc)
                    ventana_fin = min(fin, hasta_utc)
                    if ventana_fin > ventana_inicio:
                        ventanas.append((ventana_inicio, ventana_fin))
        dia += timedelta(days=1)
    return ventanas


async def minutos_laborables_entre(desde_utc: datetime, hasta_utc: datetime) -> float:
    """Minutos de horario laboral entre dos instantes."""
    if hasta_utc <= desde_utc:
        return 0.0
    if not await config_service.pausa_fuera_de_horario():
        return (hasta_utc - desde_utc).total_seconds() / 60
    total = 0.0
    for inicio, fin in await _ventanas_laborables(desde_utc, hasta_utc):
        total += (fin - inicio).total_seconds() / 60
    return total


async def minutos_restantes_laborables(hasta_utc: datetime, desde_utc: datetime) -> float:
    """Minutos de horario laboral que faltan hasta ``hasta_utc``, con signo.

    Negativo si el plazo ya pasó. El negativo son los minutos laborables que se
    pasaron de la fecha límite, no los de reloj: si el caso venció un viernes y se
    mira el sábado, el retraso es de cero minutos laborables porque el fin de
    semana no se cuenta, aunque hayan pasado 48 horas.

    Que el resto y lo transcurrido cuenten **con el mismo reloj** es lo que hace
    que la columna SLA no se contradiga. Antes el resto salía del reloj de reloj
    (`resolver_en - ahora`) y lo transcurrido del reloj laboral, así que un caso
    creado un sábado salía «Quedan 2 días y 4 h» junto a una barra en 0 %: dos
    clocks distintos en la misma celda, y el segundo estaba en días de trabajo
    mientras el primero contaba la noche.
    """
    if hasta_utc <= desde_utc:
        return -await minutos_laborables_entre(hasta_utc, desde_utc)
    return await minutos_laborables_entre(desde_utc, hasta_utc)


async def sumar_minutos_laborables(desde_utc: datetime, minutos: float) -> datetime:
    """Instante en el que se acumulan ``minutos`` minutos laborables desde ``desde_utc``."""
    if minutos <= 0:
        return desde_utc
    if not await config_service.pausa_fuera_de_horario():
        return desde_utc + timedelta(minutes=minutos)
    restantes = float(minutos)
    momento = desde_utc
    for _ in range(MAX_ITERACIONES):
        if restantes <= 0:
            return momento
        ventanas = await _ventanas_laborables(momento, momento + timedelta(days=40))
        siguiente_inicio: datetime | None = None
        siguiente_fin: datetime | None = None
        for inicio, fin in ventanas:
            if fin <= momento:
                continue
            if siguiente_inicio is None or inicio < siguiente_inicio:
                siguiente_inicio, siguiente_fin = inicio, fin
        if siguiente_inicio is None or siguiente_fin is None:
            momento = (momento + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue
        tramo_inicio = max(siguiente_inicio, momento)
        disponible = (siguiente_fin - tramo_inicio).total_seconds() / 60
        if disponible >= restantes:
            return tramo_inicio + timedelta(minutes=restantes)
        restantes -= disponible
        momento = siguiente_fin
    return momento  # pragma: no cover - salvaguarda


async def calcular_deadlines(prioridad: str, desde: datetime | None = None) -> dict[str, Any]:
    """Fechas limite de respuesta y resolucion para una prioridad dada."""
    inicio = desde or utcnow()
    regla = await config_service.regla_sla(prioridad)
    pausa = await config_service.pausa_fuera_de_horario()
    if not pausa:
        responder_en = inicio + timedelta(hours=float(regla["horas_responder"]))
        resolver_en = inicio + timedelta(hours=float(regla["horas_resolver"]))
    else:
        responder_en = await sumar_minutos_laborables(inicio, float(regla["horas_responder"]) * 60)
        resolver_en = await sumar_minutos_laborables(inicio, float(regla["horas_resolver"]) * 60)
        if resolver_en < responder_en:
            resolver_en = responder_en
    return {
        "sla_responder_en": responder_en,
        "sla_resolver_en": resolver_en,
        "sla_horas_responder": float(regla["horas_responder"]),
        "sla_horas_resolver": float(regla["horas_resolver"]),
        "sla_prioridad_regla": prioridad,
        "sla_pausa_fuera_horario": pausa,
    }


async def estado_sla(ticket: dict[str, Any], *, momento: datetime | None = None) -> dict[str, Any]:
    """Estado del SLA de un ticket en formato listo para la interfaz.

    Hay **dos** plazos por ticket —responder y resolver— y cuál de los dos está
    corriendo depende de si alguien lo ha tomado:

    * sin tomar, lo que corre es el de **responder**: lo que importa es cuánto
      tarda el equipo TI en hacerse cargo;
    * ya tomado, lo que corre es el de **resolver**.

    Los dos ocupan el mismo sitio en pantalla y se alternan solos, así que el
    nombre del que está corriendo viaja en `modo` y el resto de la cuenta se hace
    contra ese. Los dos plazos se devuelven igual en sus propios campos, para el
    que necesite el de resolver de un caso que nadie ha tomado todavía.
    """
    ahora = momento or utcnow()
    estado_ticket = ticket.get("estado")
    activo = estado_ticket not in ("resuelto", "cerrado")
    referencia_cierre = ticket.get("cerrado_en") or ticket.get("resuelto_en")
    fin_ventana = referencia_cierre if referencia_cierre else ahora
    deadlines = {
        "responder": ticket.get("sla_responder_en"),
        "resolver": ticket.get("sla_resolver_en"),
    }
    horas = {
        "responder": float(ticket.get("sla_horas_responder") or 0),
        "resolver": float(ticket.get("sla_horas_resolver") or 0),
    }
    # Nadie lo ha tomado todavía mientras siga en «nuevo»: asignarlo lo mueve a
    # «en progreso» en el mismo paso, así que ese es el corte.
    modo = "responder" if estado_ticket == "nuevo" else "resolver"
    salida: dict[str, Any] = {
        "activo": activo and bool(deadlines["resolver"]),
        "modo": modo,
        "estado": "seguro",
        "minutos_restantes": None,
        "minutos_transcurridos": None,
        # Minutos de trabajo que el caso se pasó del plazo. Solo tiene sentido con
        # el caso ya cerrado; abierto es 0 porque va dentro de `minutos_restantes`.
        "minutos_retraso": 0,
        "responder_en": deadlines["responder"],
        "resolver_en": deadlines["resolver"],
        # Los dos plazos, siempre, para el que necesite el que no está corriendo.
        "minutos_responder_restantes": None,
        "minutos_resolver_restantes": None,
        "pausado": bool(ticket.get("sla_pausa_fuera_horario")) and activo,
        "progreso": 0.0,
    }
    if not deadlines["resolver"]:
        salida["estado"] = "sin_configuracion"
        return salida
    if not activo:
        # Un caso cerrado ya no tiene plazo corriendo. Lo que importa es cuánto
        # tardó y si se pasó del plazo, y se cuenta en horas de trabajo como todo
        # lo demás. No se marca como «vencido»: un caso cerrado no está vencido,
        # se cerró tarde, y decirlo en rojo dentro del historial cerrado parece una
        # alarma que nadie tiene que resolver.
        transcurrido = await minutos_laborables_entre(ticket["creado_en"], fin_ventana)
        salida["minutos_transcurridos"] = int(transcurrido)
        salida["estado"] = "cerrado_en_plazo" if not ticket.get("sla_incumplido") else "cerrado_tarde"
        horas_totales = float(ticket.get("sla_horas_resolver") or 1)
        salida["progreso"] = min(round(100 * transcurrido / (horas_totales * 60), 1), 100.0)
        if ticket.get("sla_incumplido") and deadlines["resolver"] and fin_ventana > deadlines["resolver"]:
            salida["minutos_retraso"] = int(await minutos_laborables_entre(deadlines["resolver"], fin_ventana))
        else:
            salida["minutos_retraso"] = 0
        return salida
    # El resto y lo transcurrido salen del mismo reloj —el de horas de trabajo—,
    # así que las dos cifras de la columna no pueden contradecirse: lo que queda
    # es siempre el plazo menos lo que se lleva gastado.
    for nombre in ("responder", "resolver"):
        if deadlines[nombre]:
            salida[f"minutos_{nombre}_restantes"] = int(
                await minutos_restantes_laborables(deadlines[nombre], ahora)
            )
    restante = salida[f"minutos_{modo}_restantes"] or 0
    transcurrido = await minutos_laborables_entre(ticket["creado_en"], ahora)
    salida["minutos_restantes"] = int(restante)
    salida["minutos_transcurridos"] = int(transcurrido)
    # El progreso se mide contra el plazo que está corriendo, no siempre contra el
    # de resolver: si lo que corre es «responder» y el plazo es de 4 h, una barra
    # llena al 50 % tiene que ser la mitad de 4 h.
    horas_totales = horas[modo] or horas["resolver"] or 1
    salida["progreso"] = min(round(100 * transcurrido / (horas_totales * 60), 1), 100.0)
    if restante <= 0:
        salida["estado"] = "vencido"
    elif restante <= 60 or (restante / max(horas_totales * 60, 1)) < 0.25:
        salida["estado"] = "critico"
    elif (restante / max(horas_totales * 60, 1)) < 0.6:
        salida["estado"] = "atencion"
    else:
        salida["estado"] = "seguro"
    return salida


async def recalcular_prioridad(ticket: dict[str, Any], nueva_prioridad: str, *, momento: datetime | None = None) -> dict[str, Any]:
    """Recalcula deadlines cuando cambia la prioridad."""
    ahora = momento or utcnow()
    base = ticket.get("creado_en") or ahora
    if nueva_prioridad == ticket.get("prioridad"):
        return {
            "sla_responder_en": ticket.get("sla_responder_en"),
            "sla_resolver_en": ticket.get("sla_resolver_en"),
            "sla_horas_responder": ticket.get("sla_horas_responder"),
            "sla_horas_resolver": ticket.get("sla_horas_resolver"),
            "sla_incumplido": ticket.get("sla_incumplido", False),
            "sla_prioridad_regla": nueva_prioridad,
        }
    return await calcular_deadlines(nueva_prioridad, base)


async def recalcular_todos_abiertos(*, momento: datetime | None = None) -> dict[str, Any]:
    """Tarea periodica del worker: marca incumplimientos y recalcula pendientes."""
    from app.core.db import get_db

    ahora = momento or utcnow()
    db = get_db()
    abiertos = await db["tickets"].find(
        {"estado": {"$nin": ["resuelto", "cerrado"]}, "sla_resolver_en": {"$ne": None}},
        {"codigo": 1, "sla_resolver_en": 1, "sla_horas_resolver": 1, "sla_incumplido": 1, "creado_en": 1},
    ).to_list(None)
    vencidos = 0
    actualizados = 0
    for ticket in abiertos:
        restante = (ticket["sla_resolver_en"] - ahora).total_seconds() / 60
        if restante <= 0 and not ticket.get("sla_incumplido"):
            await db["tickets"].update_one({"_id": ticket["_id"]}, {"$set": {"sla_incumplido": True}})
            vencidos += 1
        else:
            restante_absoluto = abs(restante)
            horas = float(ticket.get("sla_horas_resolver") or 1)
            if restante > 0 and restante_absoluto / max(horas * 60, 1) < 0.25:
                await db["tickets"].update_one({"_id": ticket["_id"]}, {"$set": {"sla_riesgo": "critico"}})
                actualizados += 1
    return {"revisados": len(abiertos), "vencidos": vencidos, "marcados_riesgo": actualizados}
