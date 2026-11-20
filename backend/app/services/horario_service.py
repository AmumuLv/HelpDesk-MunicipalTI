"""Horarios del equipo TI, ausencias y disponibilidad calculada.

El horario gobierna el sistema: asignacion, SLA, capacidad y analitica solo se
calculan sobre horas laborables reales. Ningun proceso interpreta un dia libre o
una ausencia como "tecnico inactivo".
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import NoEncontrado, Prohibido, Validacion
from app.core.time import a_fecha, business_tz, fecha_iso, utcnow
from app.domain.horario import horario_base
from app.domain.constants import (
    AUSENTE,
    DIA_LIBRE,
    DISPONIBLE,
    EN_ESPERA,
    FUERA_DE_HORARIO,
    OCUPADO,
    ROL_ADMIN,
    ROL_TECNICO,
)

DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

ETIQUETAS_DISPONIBILIDAD = {
    DISPONIBLE: "Disponible",
    OCUPADO: "Ocupado",
    EN_ESPERA: "En espera",
    FUERA_DE_HORARIO: "Fuera de horario",
    DIA_LIBRE: "Dia libre",
    AUSENTE: "Ausente",
}

def _hhmm(valor: str) -> time:
    hora, minuto = str(valor).split(":")
    return time(int(hora), int(minuto))


def dias_semana_index(weekday: int) -> int:
    """0 = lunes ... 6 = domingo (criterio del calendario interno)."""
    return weekday % 7


def inicio_utc(dia: date) -> datetime:
    return datetime.combine(dia, time(0, 0), tzinfo=business_tz()).astimezone(timezone.utc)


def fin_utc(dia: date) -> datetime:
    return datetime.combine(dia, time(23, 59, 59, 999999), tzinfo=business_tz()).astimezone(timezone.utc)


def minutos_tramos(tramos: list[dict[str, Any]]) -> int:
    total = 0
    for tramo in tramos or []:
        try:
            inicio = _hhmm(tramo["entrada"])
            fin = _hhmm(tramo["salida"])
        except (KeyError, ValueError):
            continue
        momento_inicio = datetime.combine(date(2000, 1, 1), inicio)
        momento_fin = datetime.combine(date(2000, 1, 1), fin)
        if momento_fin <= momento_inicio:
            momento_fin += timedelta(days=1)
        total += int((momento_fin - momento_inicio).total_seconds() // 60)
    return total


def esta_dentro_de_horario(horario: dict[str, Any], momento: datetime) -> tuple[bool, list[dict[str, str]]]:
    """Comprueba si un instante local cae dentro de un tramo laborable."""
    local = momento.astimezone(business_tz())
    hora_local = local.time()
    dias = horario.get("dias") or {}
    config = dias.get(str(dias_semana_index(local.weekday()))) or dias.get(dias_semana_index(local.weekday()))
    if not config or config.get("libre"):
        return False, []
    dentro: list[dict[str, str]] = []
    for tramo in config.get("tramos") or []:
        try:
            entrada = _hhmm(tramo["entrada"])
            salida = _hhmm(tramo["salida"])
        except (KeyError, ValueError):
            continue
        if entrada <= hora_local < salida:
            dentro.append({"entrada": tramo["entrada"], "salida": tramo["salida"]})
    return bool(dentro), dentro


# ── Horario y perfil ─────────────────────────────────────────
async def obtener_horario(tecnico_id: ObjectId) -> dict[str, Any]:
    db = get_db()
    perfil = await db["tecnicos_perfil"].find_one({"usuario_id": tecnico_id})
    if perfil is None:
        await db["tecnicos_perfil"].update_one(
            {"usuario_id": tecnico_id},
            {
                "$setOnInsert": {
                    "usuario_id": tecnico_id,
                    "especialidades": [],
                    "categorias": [],
                    "zonas_pref": [],
                    "capacidad_diaria": 8,
                    "horario": horario_base(),
                    "creado_en": utcnow(),
                }
            },
            upsert=True,
        )
        perfil = await db["tecnicos_perfil"].find_one({"usuario_id": tecnico_id}) or {}
    return perfil.get("horario") or {"dias": {}}


async def obtener_perfil(tecnico_id: ObjectId) -> dict[str, Any]:
    await obtener_horario(tecnico_id)
    return await get_db()["tecnicos_perfil"].find_one({"usuario_id": tecnico_id}) or {}


async def actualizar_horario(
    tecnico_id: ObjectId, horario: dict[str, Any], *, usuario: dict[str, Any], puede_editar_todos: bool = False
) -> dict[str, Any]:
    from app.domain.permissions import tiene_permiso
    await exigir_tecnico(tecnico_id)

    if usuario.get("rol") != ROL_ADMIN:
        if usuario.get("_id") == tecnico_id and tiene_permiso(usuario, "horarios.editar_propio"):
            pass
        elif puede_editar_todos and tiene_permiso(usuario, "horarios.editar_todos"):
            pass
        else:
            raise Prohibido("No tienes permiso para editar este horario.")
    dias = horario.get("dias") or {}
    limpio: dict[str, Any] = {}
    for dia, config in dias.items():
        try:
            indice = int(dia)
        except (TypeError, ValueError) as exc:
            raise Validacion("Dia de semana no valido.") from exc
        if indice < 0 or indice > 6:
            raise Validacion("Dia de semana no valido.")
        tramos = []
        for tramo in config.get("tramos") or []:
            entrada, salida = tramo.get("entrada"), tramo.get("salida")
            try:
                hora_entrada, hora_salida = _hhmm(entrada), _hhmm(salida)
            except (AttributeError, ValueError) as exc:
                raise Validacion(f"Hora invalida en el dia {DIAS_SEMANA[indice]}.") from exc
            if hora_salida <= hora_entrada:
                raise Validacion(
                    f"En {DIAS_SEMANA[indice]} la salida ({salida}) debe ser posterior a la entrada ({entrada}).",
                    detalles={"dia": indice},
                )
            tramos.append({"entrada": entrada, "salida": salida})
        tramos.sort(key=lambda t: t["entrada"])
        for anterior, siguiente in zip(tramos, tramos[1:]):
            if siguiente["entrada"] < anterior["salida"]:
                raise Validacion(f"Los tramos de {DIAS_SEMANA[indice]} no pueden superponerse.")
        libre = bool(config.get("libre")) or not tramos
        limpio[str(indice)] = {"tramos": [] if libre else tramos, "libre": libre}
    for indice in range(7):
        limpio.setdefault(str(indice), {"tramos": [], "libre": True})
    db = get_db()
    await db["tecnicos_perfil"].update_one(
        {"usuario_id": tecnico_id},
        {"$set": {"horario": {"dias": limpio}, "actualizado_en": utcnow()}},
        upsert=True,
    )
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="tecnico_perfil",
        entidad_id=str(tecnico_id),
        resumen="Horario semanal actualizado",
        despues={"horario": limpio},
    )
    return {"dias": limpio}


async def actualizar_perfil(tecnico_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    await exigir_tecnico(tecnico_id)
    db = get_db()
    actualizacion = {
        campo: datos[campo]
        for campo in ("especialidades", "categorias", "zonas_pref", "capacidad_diaria", "notas")
        if campo in datos
    }
    if datos.get("activo") is not None:
        actualizacion["activo"] = bool(datos["activo"])
    await db["tecnicos_perfil"].update_one(
        {"usuario_id": tecnico_id}, {"$set": actualizacion}, upsert=True
    )
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="tecnico_perfil",
        entidad_id=str(tecnico_id),
        resumen="Perfil tecnico actualizado",
        despues=actualizacion,
    )
    return await db["tecnicos_perfil"].find_one({"usuario_id": tecnico_id}) or {}


# ── Ausencias y feriados ─────────────────────────────────────
async def crear_ausencia(datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    await exigir_tecnico(datos["tecnico_id"], activo=True)
    inicio, fin = datos["inicio"], datos["fin"]
    if fin < inicio:
        raise Validacion("La fecha final no puede ser anterior a la inicial.")
    if await get_db()["ausencias"].find_one({"tecnico_id": datos["tecnico_id"],
            "inicio": {"$lte": fin.isoformat()}, "fin": {"$gte": inicio.isoformat()}}):
        raise Validacion("Ya existe una ausencia que coincide con estas fechas para esta persona.")
    doc = {
        "tecnico_id": datos["tecnico_id"],
        "tipo": datos.get("tipo", "Vacaciones"),
        # Fechas como texto ISO: BSON no admite datetime.date
        "inicio": inicio.isoformat(),
        "fin": fin.isoformat(),
        "motivo": datos.get("motivo"),
        "creado_por": usuario.get("nombre", ""),
        "creado_en": utcnow(),
    }
    resultado = await get_db()["ausencias"].insert_one(doc)
    doc["id"] = resultado.inserted_id
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ausencia",
        entidad_id=resultado.inserted_id,
        resumen=f"Ausencia registrada: {doc['tipo']} ({inicio} a {fin})",
        despues={"tecnico": str(datos["tecnico_id"]), "tipo": doc["tipo"], "inicio": str(inicio), "fin": str(fin)},
    )
    return doc


async def eliminar_ausencia(ausencia_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    resultado = await get_db()["ausencias"].delete_one({"_id": ausencia_id})
    if not resultado.deleted_count:
        raise NoEncontrado("La ausencia ya no existe.")
    if resultado.deleted_count:
        await registrar(
            "config.actualizar",
            usuario_id=usuario.get("_id"),
            usuario_nombre=usuario.get("nombre", ""),
            rol=usuario.get("rol", ""),
            entidad="ausencia",
            entidad_id=ausencia_id,
            resumen="Ausencia eliminada",
        )


async def ausencias_de(
    tecnico_id: ObjectId | None = None, *, desde: date | None = None, hasta: date | None = None
) -> list[dict[str, Any]]:
    consulta: dict[str, Any] = {}
    if tecnico_id is not None:
        consulta["tecnico_id"] = tecnico_id
    if desde:
        consulta["fin"] = {"$gte": fecha_iso(desde)}
    if hasta:
        consulta["inicio"] = {"$lte": fecha_iso(hasta)}
    documentos = await (get_db()["ausencias"].find(consulta).sort("inicio", 1).to_list(None))
    for documento in documentos:
        documento["id"] = documento.pop("_id")
        documento["inicio"] = a_fecha(documento.get("inicio"))
        documento["fin"] = a_fecha(documento.get("fin"))
    ids = list({documento["tecnico_id"] for documento in documentos})
    nombres = {u["_id"]: u.get("nombre", "Sin nombre") for u in await get_db()["usuarios"].find(
        {"_id": {"$in": ids}}, {"nombre": 1}
    ).to_list(None)} if ids else {}
    for documento in documentos:
        documento["tecnico_nombre"] = nombres.get(documento["tecnico_id"], "Cuenta no disponible")
    return documentos


async def tecnico_de_ausencia(ausencia_id: ObjectId) -> ObjectId | None:
    ausencia = await get_db()["ausencias"].find_one(
        {"_id": ausencia_id}, {"tecnico_id": 1}
    )
    return ausencia.get("tecnico_id") if ausencia else None


async def feriados() -> list[dict[str, Any]]:
    documentos = await (get_db()["feriados"].find().sort("fecha", 1).to_list(None))
    for documento in documentos:
        documento["id"] = documento.pop("_id")
        documento["fecha"] = a_fecha(documento.get("fecha"))
    return documentos


async def guardar_feriado(datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    fecha = fecha_iso(datos["fecha"])
    await db["feriados"].update_one(
        {"fecha": fecha},
        {
            "$set": {"nombre": datos["nombre"], "tipo": datos.get("tipo", "feriado"), "actualizado_en": utcnow()},
            "$setOnInsert": {"creado_en": utcnow()},
        },
        upsert=True,
    )
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="feriado",
        resumen=f"Feriado registrado: {datos['fecha']} - {datos['nombre']}",
        despues={"fecha": str(datos["fecha"]), "nombre": datos["nombre"]},
    )
    documento = await db["feriados"].find_one({"fecha": fecha}) or {}
    documento["id"] = documento.pop("_id", None)
    documento["fecha"] = a_fecha(documento.get("fecha"))
    return documento


async def eliminar_feriado(feriado_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    await get_db()["feriados"].delete_one({"_id": feriado_id})
    await registrar(
        "config.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="feriado",
        entidad_id=feriado_id,
        resumen="Feriado eliminado",
    )


async def es_feriado(dia: date) -> bool:
    from app.services import config_service

    db = get_db()
    if await db["feriados"].count_documents({"fecha": fecha_iso(dia)}, limit=1):
        return True
    calendario = await config_service.calendario()
    extras = {str(fecha_iso(f)) for f in calendario.get("feriados_extra") or []}
    return dia.isoformat() in extras


# ── Disponibilidad calculada ─────────────────────────────────
async def calcular_disponibilidad(tecnico_id: ObjectId, *, momento: datetime | None = None) -> dict[str, Any]:
    """Disponible, Ocupado, En espera, Fuera de horario, Dia libre o Ausente."""
    db = get_db()
    ahora = momento or utcnow()
    local = ahora.astimezone(business_tz())
    hoy = local.date()
    usuario = await db["usuarios"].find_one({"_id": tecnico_id}) or {}
    perfil = await db["tecnicos_perfil"].find_one({"usuario_id": tecnico_id}) or {}
    horario = perfil.get("horario") or {"dias": {}}
    capacidad = int(perfil.get("capacidad_diaria") or 8)

    # Los tickets borrados no cuentan. Antes no se filtraban y pasaban dos cosas:
    # el técnico aparecía «Ocupado» por un caso que ya no existe, y la carga iba
    # inflada. El caso más visible era el enlace «Atendiendo TKT-…», que llevaba a
    # un ticket borrado y devolvía un 404 al pulsarlo.
    asignados = await db["tickets"].find(
        {"tecnico_id": tecnico_id, "estado": {"$nin": ["cerrado"]}, "eliminado": {"$ne": True}},
        {
            "codigo": 1,
            "estado": 1,
            "asunto": 1,
            "zona_nombre": 1,
            "oficina_nombre": 1,
            "actualizado_en": 1,
            "creado_en": 1,
            "sla_resolver_en": 1,
            "prioridad": 1,
        },
    ).to_list(None)
    en_progreso = [t for t in asignados if t.get("estado") == "en_progreso"]
    en_espera = [t for t in asignados if t.get("estado") == "en_espera"]
    sin_responder = [t for t in asignados if t.get("estado") == "nuevo"]

    ausencias = await ausencias_de(tecnico_id, desde=hoy, hasta=hoy)
    dias = horario.get("dias") or {}
    indice_dia = dias_semana_index(local.weekday())
    dia_config = dias.get(str(indice_dia)) or dias.get(indice_dia) or {}
    dentro, tramos_hoy = esta_dentro_de_horario(horario, ahora)

    if ausencias:
        estado = AUSENTE
    elif await es_feriado(hoy) or dia_config.get("libre") or not dia_config.get("tramos"):
        estado = DIA_LIBRE
    elif not dentro:
        estado = FUERA_DE_HORARIO
    elif en_progreso:
        estado = OCUPADO
    elif en_espera:
        estado = EN_ESPERA
    else:
        estado = DISPONIBLE

    # «El caso en curso» es el que se movió hace más poco. Sin ordenar, Mongo
    # devuelve los documentos en su orden natural y el panel enseñaba un ticket
    # arbitrario de los que tiene abiertos.
    actual = max(en_progreso, key=lambda t: t.get("actualizado_en") or t.get("creado_en"), default=None)
    desde = (actual.get("actualizado_en") or actual.get("creado_en")) if actual else None
    deadlines = [t["sla_resolver_en"] for t in asignados if t.get("sla_resolver_en")]
    minutos_restantes = int((min(deadlines) - ahora).total_seconds() // 60) if deadlines else None

    carga = len(asignados)
    metricas = await metricas_tecnico(tecnico_id, desde=hoy - timedelta(days=29), hasta=hoy)

    return {
        "tecnico_id": tecnico_id,
        "tecnico_nombre": usuario.get("nombre", "Sin nombre"),
        **{campo: valor for campo, valor in _datos_personales(usuario).items() if campo != "id"},
        "estado": estado,
        "etiqueta": ETIQUETAS_DISPONIBILIDAD.get(estado, estado),
        "ticket_actual_id": actual.get("_id") if actual else None,
        "ticket_actual_codigo": actual.get("codigo") if actual else None,
        "ticket_desde": desde,
        "ticket_zona": actual.get("zona_nombre") if actual else None,
        "ticket_oficina": actual.get("oficina_nombre") if actual else None,
        "carga_asignados": carga,
        "carga_espera": len(en_espera),
        "capacidad_diaria": capacidad,
        "porcentaje_carga": round(100 * carga / capacidad, 1) if capacidad else 0.0,
        "sla_mas_critico_min": minutos_restantes,
        "horario_hoy": list(tramos_hoy),
        "ausencias": ausencias,
        "dia_libre": estado == DIA_LIBRE,
        "fuera_de_horario": estado == FUERA_DE_HORARIO,
        "metricas": metricas,
        "pendientes_sin_responder": len(sin_responder),
    }


async def tecnicos_activos(*, recientes_primero: bool = False) -> list[dict[str, Any]]:
    return await get_db()["usuarios"].find(
        {"rol": {"$in": [ROL_TECNICO, ROL_ADMIN]}, "activo": True}
    ).sort([("creado_en", -1), ("_id", -1)] if recientes_primero else [("nombre", 1)]).to_list(None)


async def panel_equipo(*, momento: datetime | None = None) -> list[dict[str, Any]]:
    """Panel de Equipo TI: estado y carga de cada tecnico."""
    tecnicos = await tecnicos_activos(recientes_primero=True)
    panel = [await calcular_disponibilidad(tecnico["_id"], momento=momento) for tecnico in tecnicos]
    return panel


async def metricas_tecnico(tecnico_id: ObjectId, *, desde: date, hasta: date) -> dict[str, Any]:
    """Metricas normalizadas por horas laborables reales del periodo."""
    db = get_db()
    tickets = await db["tickets"].find(
        {"tecnico_id": tecnico_id, "eliminado": {"$ne": True}, "creado_en": {"$gte": inicio_utc(desde), "$lte": fin_utc(hasta)}},
        {
            "estado": 1,
            "prioridad": 1,
            "tiempo_resolucion_min": 1,
            "sla_incumplido": 1,
            "veces_reabierto": 1,
            "satisfaccion": 1,
        },
    ).to_list(None)
    cerrados = [t for t in tickets if t.get("tiempo_resolucion_min") is not None]
    tiempos = [t["tiempo_resolucion_min"] for t in cerrados]
    promedio = round(sum(tiempos) / len(tiempos), 1) if tiempos else None
    incumplidos = sum(1 for t in tickets if t.get("sla_incumplido"))
    cumplimiento = round(100 * (1 - incumplidos / len(tickets)), 1) if tickets else None
    reaperturas = sum(t.get("veces_reabierto", 0) for t in tickets)
    valoraciones = [t["satisfaccion"] for t in tickets if t.get("satisfaccion")]
    satisfaccion = round(sum(valoraciones) / len(valoraciones), 2) if valoraciones else None
    horas = await horas_laborables(tecnico_id, desde, hasta)
    por_ticket = round(horas / len(cerrados), 2) if cerrados and horas else None
    return {
        "tickets_atendidos": len(cerrados),
        "tickets_asignados_periodo": len(tickets),
        "tiempo_medio_resolucion_min": promedio,
        "cumplimiento_sla": cumplimiento,
        "reaperturas": reaperturas,
        "satisfaccion": satisfaccion,
        "horas_laborables_periodo": horas,
        "horas_laborables_por_ticket": por_ticket,
        "insuficientes_datos": len(cerrados) < 3,
    }


async def horas_laborables(tecnico_id: ObjectId, desde: date, hasta: date) -> float:
    """Cuenta cada jornada una vez, recortando ausencias al periodo solicitado."""
    perfil = await get_db()["tecnicos_perfil"].find_one({"usuario_id": tecnico_id}) or {}
    horario = (perfil.get("horario") or {}).get("dias") or {}
    ausencias = await ausencias_de(tecnico_id, desde=desde, hasta=hasta)
    festivos = await _feriados_en_rango(desde, hasta)
    total = 0
    for desplazamiento in range(max((hasta - desde).days + 1, 0)):
        dia = desde + timedelta(days=desplazamiento)
        if dia in festivos or any(a["inicio"] <= dia <= a["fin"] for a in ausencias):
            continue
        config = horario.get(str(dia.weekday())) or horario.get(dia.weekday()) or {}
        if not config.get("libre"):
            total += minutos_tramos(config.get("tramos") or [])
    return round(total / 60, 2)


async def _feriados_en_rango(desde: date, hasta: date) -> set[date]:
    from app.services import config_service
    documentos = await get_db()["feriados"].find({"fecha": {"$gte": desde.isoformat(), "$lte": hasta.isoformat()}}).to_list(None)
    calendario = await config_service.calendario()
    fechas = {a_fecha(d.get("fecha")) for d in documentos}
    fechas.update(a_fecha(f) for f in calendario.get("feriados_extra") or [])
    return {f for f in fechas if f is not None and desde <= f <= hasta}


async def calendario_equipo(desde: date, hasta: date) -> list[dict[str, Any]]:
    """Plan semanal y vencimientos reales; no simula carga futura."""
    if hasta < desde or (hasta - desde).days > 119:
        raise Validacion("El calendario debe abarcar entre 1 y 120 dias.")
    db = get_db()
    tecnicos = await tecnicos_activos()
    ids = [t["_id"] for t in tecnicos]
    perfiles = {p["usuario_id"]: p for p in await db["tecnicos_perfil"].find({"usuario_id": {"$in": ids}}).to_list(None)}
    ausencias = await ausencias_de(desde=desde, hasta=hasta)
    por_tecnico = {identificador: [] for identificador in ids}
    for ausencia in ausencias:
        if ausencia["tecnico_id"] in por_tecnico:
            por_tecnico[ausencia["tecnico_id"]].append(ausencia)
    pendientes = {identificador: 0 for identificador in ids}
    vencimientos: dict[tuple, int] = {}
    async for ticket in db["tickets"].find({"tecnico_id": {"$in": ids}, "estado": {"$nin": ["cerrado", "resuelto"]}, "eliminado": {"$ne": True}}, {"tecnico_id": 1, "sla_resolver_en": 1}):
        tecnico_id = ticket["tecnico_id"]
        pendientes[tecnico_id] += 1
        if isinstance(ticket.get("sla_resolver_en"), datetime):
            clave = (tecnico_id, ticket["sla_resolver_en"].astimezone(business_tz()).date())
            vencimientos[clave] = vencimientos.get(clave, 0) + 1
    filas = []
    festivos = await _feriados_en_rango(desde, hasta)
    for dia in _rango_dias(desde, hasta):
        festivo = dia in festivos
        for tecnico in tecnicos:
            perfil = perfiles.get(tecnico["_id"], {})
            dias = (perfil.get("horario") or {}).get("dias") or {}
            config = dias.get(str(dia.weekday())) or dias.get(dia.weekday()) or {}
            ausencia = next((a for a in por_tecnico[tecnico["_id"]] if a["inicio"] <= dia <= a["fin"]), None)
            libre = bool(config.get("libre")) or not config.get("tramos")
            tramos = [] if libre or festivo or ausencia else config.get("tramos") or []
            filas.append({
                "fecha": dia, "tecnico_id": tecnico["_id"], "tecnico_nombre": tecnico.get("nombre"),
                "oficina_nombre": tecnico.get('oficina_nombre'),
                "tramos": tramos, "libre": libre, "feriado": festivo,
                "ausencia": ausencia["tipo"] if ausencia else None,
                "horas_disponibles": minutos_tramos(tramos) / 60,
                "carga_pendiente": pendientes[tecnico["_id"]],
                "vencimientos": vencimientos.get((tecnico["_id"], dia), 0),
            })
    return filas


async def exigir_tecnico(tecnico_id: ObjectId, *, activo: bool = False) -> dict[str, Any]:
    consulta = {"_id": tecnico_id, "rol": {"$in": [ROL_TECNICO, ROL_ADMIN]}}
    if activo:
        consulta["activo"] = True
    usuario = await get_db()["usuarios"].find_one(consulta)
    if usuario is None:
        raise NoEncontrado("No se encontro una cuenta del equipo TI disponible.")
    return usuario


def _datos_personales(usuario: dict[str, Any]) -> dict[str, Any]:
    from app.services.usuario_service import publico
    return publico(usuario, con_preferencias=True)


def _rango_dias(desde: date, hasta: date) -> list[date]:
    dias = (hasta - desde).days + 1
    return [desde + timedelta(days=i) for i in range(max(min(dias, 120), 0))]


async def obtener_tecnico(tecnico_id: ObjectId) -> dict[str, Any]:
    db = get_db()
    usuario = await exigir_tecnico(tecnico_id)
    perfil = await obtener_perfil(tecnico_id)
    from app.services import usuario_service

    disponibilidad = await calcular_disponibilidad(tecnico_id)
    metricas = await metricas_tecnico(
        tecnico_id, desde=utcnow().astimezone(business_tz()).date() - timedelta(days=89), hasta=utcnow().astimezone(business_tz()).date()
    )
    return {
        **usuario_service.publico(usuario, con_preferencias=True),
        "id": usuario["_id"],
        "perfil": {
            "especialidades": perfil.get("especialidades", []),
            "categorias": perfil.get("categorias", []),
            "zonas_pref": perfil.get("zonas_pref", []),
            "capacidad_diaria": perfil.get("capacidad_diaria", 8),
            "notas": perfil.get("notas"),
            "activo": bool(perfil.get("activo", True)),
        },
        "horario": perfil.get("horario") or {"dias": {}},
        "disponibilidad": disponibilidad,
        "metricas": metricas,
        "ausencias": await ausencias_de(
            tecnico_id,
            desde=utcnow().astimezone(business_tz()).date() - timedelta(days=90),
            hasta=utcnow().astimezone(business_tz()).date() + timedelta(days=180),
        ),
    }
