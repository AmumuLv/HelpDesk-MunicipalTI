"""Acceso al documento unico de configuracion."""

from __future__ import annotations

from typing import Any

from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import NoEncontrado

ID_CONFIG = "config"

DEFAULTS: dict[str, Any] = {
    "institucion": {"nombre": "Municipalidad", "nombre_corto": "Municipalidad", "correo": ""},
    "negocio": {"zona_horaria": "America/Lima", "horario_inicio_global": "08:00", "horario_fin_global": "17:00"},
    "sla": {
        "activo": True,
        "pausa_fuera_de_horario": True,
        "reglas": [
            # El plazo máximo son 2 días laborables (16 h con la jornada de 8 h).
            # Antes «baja» daba 72 h laborables: nueve días. Un ticket sin prisa
            # podía llevar más de una semana y media sin que nadie lo tocara, y el
            # contador marcaba en verde todo ese tiempo porque el plazo —y solo el
            # plazo— lo consentía.
            {"prioridad": "critica", "horas_responder": 1, "horas_resolver": 2},
            {"prioridad": "alta", "horas_responder": 2, "horas_resolver": 4},
            {"prioridad": "media", "horas_responder": 4, "horas_resolver": 8},
            {"prioridad": "baja", "horas_responder": 8, "horas_resolver": 16},
        ],
        "calendario": {
            # Lunes a viernes. El índice es el de `datetime.weekday()`, donde el
            # lunes es 0: `[1, 2, 3, 4, 5]` era martes a sábado y dejaba fuera el
            # lunes, así que un caso abierto un lunes no empezaba a contar hasta
            # el martes y el plazo se coría un día entero.
            "dias_laborables": [0, 1, 2, 3, 4],
            # Jornada de 8 h con una hora de descanso: 08:00-13:00 (5 h) y
            # 14:00-17:00 (3 h). Con esto, las 16 h del plazo máximo son
            # exactamente 2 días laborables.
            "tramos": [{"entrada": "08:00", "salida": "13:00"}, {"entrada": "14:00", "salida": "17:00"}],
            "incluir_feriados": False,
            "feriados_extra": [],
        },
    },
    "ia": {
        "global_activa": True,
        "aprendizaje_activo": True,
        "recomendaciones_activas": True,
        "valor_por_defecto": True,
        "confianza_minima": 0.55,
    },
    "notificaciones": {"email_activo": False, "correo_destino": "", "avisar_al_afectado": True, "avisar_al_reportante": True},
    "inventario": {"importacion_completada": False},
    "sistema": {"primer_arranque_completo": False},
}


async def obtener() -> dict[str, Any]:
    db = get_db()
    doc = await db["configuracion"].find_one({"_id": ID_CONFIG})
    if doc is None:
        doc = {"_id": ID_CONFIG, **DEFAULTS}
        await db["configuracion"].insert_one(doc)
    return doc


async def seccion(nombre: str) -> dict[str, Any]:
    doc = await obtener()
    return doc.get(nombre) or DEFAULTS.get(nombre, {})


async def actualizar(
    cambios: dict[str, Any], *, usuario: dict[str, Any] | None = None, aviso: str | None = None
) -> dict[str, Any]:
    """Actualiza secciones del documento de configuracion y deja auditoria."""
    db = get_db()
    antes_doc = await obtener()
    set_operaciones: dict[str, Any] = {}
    for seccion_nombre, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(antes_doc.get(seccion_nombre), dict):
            set_operaciones[seccion_nombre] = _fusionar(antes_doc[seccion_nombre], valor)
        else:
            set_operaciones[seccion_nombre] = valor
    if aviso:
        set_operaciones.setdefault("sistema", {})["ultimo_aviso"] = aviso
    await db["configuracion"].update_one({"_id": ID_CONFIG}, {"$set": set_operaciones}, upsert=True)
    despues_doc = await obtener()

    if usuario:
        diferencias = {
            seccion_nombre: {
                "antes": antes_doc.get(seccion_nombre),
                "despues": despues_doc.get(seccion_nombre),
            }
            for seccion_nombre in cambios
            if antes_doc.get(seccion_nombre) != despues_doc.get(seccion_nombre)
        }
        if diferencias:
            await registrar(
                "config.actualizar",
                usuario_id=usuario.get("_id"),
                usuario_nombre=usuario.get("nombre", ""),
                rol=usuario.get("rol", ""),
                entidad="configuracion",
                entidad_id=ID_CONFIG,
                resumen=", ".join(diferencias.keys()),
                antes=diferencias,
                contexto={"aviso": aviso} if aviso else None,
            )
    if antes_doc.get('ia') != despues_doc.get('ia'):
        from app.services.notificaciones_service import avisar_configuracion_ia
        await avisar_configuracion_ia(despues_doc)
    return despues_doc


def _fusionar(base: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
    """Fusiona en profundidad preservando claves no presentes en el cambio."""
    salida = dict(base)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = valor
    return salida


async def marcar_arranque_completo() -> None:
    await get_db()["configuracion"].update_one(
        {"_id": ID_CONFIG}, {"$set": {"sistema.primer_arranque_completo": True}}, upsert=True
    )


async def reglas_sla() -> list[dict[str, Any]]:
    sla = await seccion("sla")
    reglas = sla.get("reglas") or DEFAULTS["sla"]["reglas"]
    return reglas


async def regla_sla(prioridad: str) -> dict[str, Any]:
    for regla in await reglas_sla():
        if regla.get("prioridad") == prioridad:
            return regla
    return {"prioridad": prioridad, "horas_responder": 8, "horas_resolver": 24}


async def calendario() -> dict[str, Any]:
    sla = await seccion("sla")
    return sla.get("calendario") or DEFAULTS["sla"]["calendario"]


async def pausa_fuera_de_horario() -> bool:
    sla = await seccion("sla")
    return bool(sla.get("pausa_fuera_de_horario", True))


async def ia_activada() -> bool:
    return bool((await seccion("ia")).get("global_activa", True))


async def aprendizaje_activado() -> bool:
    return bool((await seccion("ia")).get("aprendizaje_activo", True))


async def recomendaciones_globales() -> bool:
    ia = await seccion("ia")
    return bool(ia.get("global_activa", True) and ia.get("recomendaciones_activas", True))


async def valor_por_defecto_ia() -> bool:
    return bool((await seccion("ia")).get("valor_por_defecto", True))


async def confianza_minima() -> float:
    return float((await seccion("ia")).get("confianza_minima", 0.55))


async def nombre_institucion() -> str:
    return (await seccion("institucion")).get("nombre", "Municipalidad")


async def existe() -> bool:
    doc = await get_db()["configuracion"].find_one({"_id": ID_CONFIG})
    if doc is None:
        raise NoEncontrado("No existe el documento de configuracion.")
    return True
