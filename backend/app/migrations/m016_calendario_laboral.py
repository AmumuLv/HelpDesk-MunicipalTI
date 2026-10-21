"""El calendario laboral es de lunes a viernes, de 8 h con una hora de descanso.

Había dos errores en el calendario, y los dos se notaban en el plazo del SLA:

**El lunes no era día laborable.** Los días guardados eran `[1, 2, 3, 4, 5]` y el
índice es el de `datetime.weekday()`, donde el lunes es 0. O sea que lo que había
era **martes a sábado**, con el lunes fuera. El comentario del código ya decía
«lunes a viernes» y el valor no lo era, que es la clase de error que sobrevive
mucho tiempo porque el comentario miente en la dirección correcta.

Convierte el calendario en dos cosas malas a la vez:

* un caso abierto el lunes no empezaba a contar hasta el martes, así que las 16 h
  del plazo máximo ocupaban lunes, martes y miércoles en vez de dos días; y
* una prioridad crítica con 2 h de plazo abierta el lunes a las 08:00 no vencía
  hasta el martes a las 18:00: un día entero de margen que nadie pidió.

**La tarde estaba corrida una hora.** Los tramos guardados eran 08:00-13:00 y
**15:00-18:00**, y la jornada es 08:00-13:00, una hora de descanso y 14:00-17:00.
Las dos sumaban 8 h, así que el día laboral era el correcto, pero la tarde empezaba
a las tres y acababa a las seis en vez de las dos y las cinco.

Con los dos arreglos, la jornada son 8 h exactas —5 h por la mañana y 3 h por la
tarde— y **las 16 h del plazo máximo son exactamente 2 días laborables**, que es lo
que dice la norma y lo que la migración 014 ya prometía.

**Solo cambian los valores guardados y los tickets que siguen abiertos.** Un caso ya
cerrado conserva el plazo con el que se resolvió: ese plazo se fijó cuando se creó y
reescribirlo sería falsear lo que ocurrió. Los abiertos sí se recalculan, porque si
no el contador mide con un calendario y el caso se creó con otro.
"""

DESCRIPCION = "El calendario laboral vuelve a ser de lunes a viernes, 08:00-13:00 y 14:00-17:00"

# El mismo calendario que queda ahora en `config_service.DEFAULTS`. Se escribe
# literal y no se importa a propósito: una migración que lee el valor de hoy no
# arregla nada, porque si el default se vuelve a equivocar, la migración lo
# reequivoca con él y el fallo pasa desapercibido.
DIAS_LABORABLES = [0, 1, 2, 3, 4]
TRAMOS = [{"entrada": "08:00", "salida": "13:00"}, {"entrada": "14:00", "salida": "17:00"}]


async def aplicar(db) -> None:
    await db["configuracion"].update_one(
        {"_id": "config"},
        {
            "$set": {
                "sla.calendario.dias_laborables": DIAS_LABORABLES,
                "sla.calendario.tramos": TRAMOS,
            }
        },
    )

    # Los tickets guardan la fecha límite con la que se les calculó. Si el
    # calendario cambia y el documento se queda con la fecha vieja, la cuenta no
    # cuadra: el caso puede mostrarse «en tiempo» con el plazo ya vencido, o al
    # revés. Se recalcula solo en los que siguen abiertos, igual que en la 014.
    from app.core.time import utcnow
    from app.services import sla_service

    ahora = utcnow()
    async for ticket in db["tickets"].find({"cerrado_en": None, "eliminado": {"$ne": True}}):
        documento = await sla_service.calcular_deadlines(
            ticket.get("prioridad") or "media", ticket.get("creado_en") or ahora
        )
        await db["tickets"].update_one({"_id": ticket["_id"]}, {"$set": documento})


async def revertir(db) -> None:
    """Deja el calendario como estaba: martes a sábado, con la tarde de 15:00 a 18:00."""
    await db["configuracion"].update_one(
        {"_id": "config"},
        {
            "$set": {
                "sla.calendario.dias_laborables": [1, 2, 3, 4, 5],
                "sla.calendario.tramos": [
                    {"entrada": "08:00", "salida": "13:00"},
                    {"entrada": "15:00", "salida": "18:00"},
                ],
            }
        },
    )
