"""El plazo máximo del SLA son 2 días laborables.

Los tiempos del SLA no son horas de reloj: son **horas laborables**, contadas con
el calendario de la configuración —de lunes a viernes, 8 horas al día—. Con la
jornada por defecto, 16 horas laborables son 2 días de trabajo.

El tope estaba en 72 horas laborables: 9 días. Eso hacía dos cosas malas a la vez:

* un ticket de prioridad «baja» podía pasar más de una semana y media sin que nadie
  lo tocara sin que el sistema marcara nada, porque el contador comparaba el
  retraso contra ese mismo plazo, y el plazo lo consentía; y
* como las horas son laborables, el plazo se convertía en un número enorme cuando
  se traducía a tiempo de calendario: una fila podía marcar «116 h 5 min
  restantes», que no es un plazo que nadie pueda leer ni creer.

El tope nuevo es de 2 días laborables. Las cuatro prioridades se reparten por debajo,
conservando el orden y la proporción de escalón entre ellas:

    crítica   1 h responder   2 h resolver    (¼ de día)
    alta      2 h            4 h              (½ día)
    media     4 h            8 h              (1 día)
    baja      8 h           16 h              (2 días)

**Solo cambian los valores por defecto de las reglas**, que son los que trae la
configuración cuando se instala. Se ajustan los tickets que tienen el plazo viejo
grabado en el documento, para que el contador y las fechas que se muestran
coincidan con las reglas nuevas. Las fechas ya cumplidas no se tocan: el plazo de
un ticket se fijó cuando se creó, y reescribirlo sería falsear lo que ocurrió.
"""

DESCRIPCION = "El SLA baja a un maximo de 2 dias laborables"

from app.services.config_service import DEFAULTS

NUEVAS_REGLAS = {regla["prioridad"]: regla for regla in DEFAULTS["sla"]["reglas"]}


async def aplicar(db) -> None:
    await db["configuracion"].update_one(
        {"_id": "config"},
        {"$set": {"sla.reglas": [dict(NUEVAS_REGLAS[clave]) for clave in ("critica", "alta", "media", "baja")]}},
    )

    # Los tickets guardan el plazo que se les aplicó. Si se cambia la regla y el
    # documento se queda con el plazo viejo, el contador mide una cosa y la regla
    # dice otra: el ticket se muestra «en tiempo» cuando ya venció, o al revés.
    # Se recalcula solo en los que aún no se cumplen.
    from app.core.time import utcnow
    from app.services import sla_service

    ahora = utcnow()
    async for ticket in db["tickets"].find({"cerrado_en": None, "eliminado": {"$ne": True}}):
        documento = await sla_service.calcular_deadlines(ticket.get("prioridad") or "media", ticket.get("creado_en") or ahora)
        await db["tickets"].update_one({"_id": ticket["_id"]}, {"$set": documento})


async def revertir(db) -> None:
    """Devuelve los plazos a lo que hadría falta volver a escribirlos a mano.

    Los tickets ya cumplidos conservan la fecha con la que se resolvieron: su
    plazo se fijó cuando se crearon y reescribirlo sería falsear lo ocurrido.
    """
    await db["tickets"].update_many(
        {"cerrado_en": None},
        {"$set": {"sla_horas_responder": None, "sla_horas_resolver": None, "sla_responder_en": None, "sla_resolver_en": None}},
    )