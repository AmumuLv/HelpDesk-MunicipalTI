"""Un solo estado final: «cerrado».

Habia seis estados y dos de ellos decian lo mismo. Cuando el tecnico terminaba un
caso, este pasaba a «resuelto» y luego habia que cerrarlo aparte: dos palabras
distintas para la misma realidad —el problema esta solucionado— y dos pasos donde
bastaba uno. En una cola de trabajo real, «resuelto» se quedaba ahi semanas sin
que nadie viniera a cerrarlo, y la pregunta de siempre era si un ticket ya
resuelto estaba ademas cerrado.

Aqui los tickets que estaban en «resuelto» pasan a «cerrado», que es el estado en
el que ya estaban de hecho: la solucion estaba escrita y el caso ya no tenia
trabajo pendiente.

**Se conservan las dos fechas.** `resuelto_en` —cuando se resolvio— y
`cerrado_en` —cuando se archivó— siguen escribiéndose al cerrar, porque de ellas
salen los tiempos de resolucion, el cumplimiento de SLA y las valoraciones. Donde
`cerrado_en` no estuviera, se rellena con `resuelto_en`: el caso se dio por
concluido en ese momento. La de los reabiertos se toma de `reabierto_en`, que es
cuando el ticket dejo de estar concluido.
"""

DESCRIPCION = "Los tickets en estado resuelto pasan a cerrado"

from app.core.time import utcnow
from app.domain.constants import ESTADO_CERRADO, ESTADO_RESUELTO_LEGADO

# Los tickets devueltos a la cola tienen trabajo real pendiente: su estado se
# corrige, pero la fecha de cierre se toma del momento de la reapertura.
REABIERTO = {"veces_reabierto": {"$gt": 0}}


async def aplicar(db) -> None:
    ahora = utcnow()
    await db["tickets"].update_many(
        {"estado": ESTADO_RESUELTO_LEGADO, **REABIERTO, "cerrado_en": {"$in": [None]}},
        [{"$set": {"cerrado_en": "$reabierto_en"}}],
    )
    await db["tickets"].update_many(
        {"estado": ESTADO_RESUELTO_LEGADO, "cerrado_en": {"$in": [None]}},
        [{"$set": {"cerrado_en": "$resuelto_en"}}],
    )
    await db["tickets"].update_many(
        {"estado": ESTADO_RESUELTO_LEGADO},
        {"$set": {"estado": ESTADO_CERRADO, "actualizado_en": ahora}},
    )
    # Las vistas guardadas filtraban por el estado retirado; si se deja ahi, la
    # vista se queda vacia sin avisar de nada.
    await db["vistas_guardadas"].update_many(
        {"filtros.estado": ESTADO_RESUELTO_LEGADO},
        {"$set": {"filtros.estado": [ESTADO_CERRADO], "actualizado_en": ahora}},
    )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()


async def revertir(db) -> None:
    ahora = utcnow()
    await db["tickets"].update_many(
        {"estado": ESTADO_CERRADO, "resuelto_en": {"$ne": None}, "cerrado_en": {"$ne": None}},
        {"$set": {"estado": ESTADO_RESUELTO_LEGADO, "actualizado_en": ahora}},
    )
    await db["vistas_guardadas"].update_many(
        {"filtros.estado": ESTADO_CERRADO},
        {"$set": {"filtros.estado": [ESTADO_RESUELTO_LEGADO], "actualizado_en": ahora}},
    )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()