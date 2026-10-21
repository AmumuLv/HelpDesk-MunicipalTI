"""«Asignado» desaparece: tener técnico es estar trabajando en ello.

Había cinco estados y dos de ellos decían lo mismo a propósito. «Asignado» quería
decir «ya tiene técnico», y «en progreso» «el técnico lo está tocando»: una
distinción que en la práctica no se notaba en ninguna parte. El contador que la
medía —los pendientes sin responder— no se mostraba en ninguna pantalla.

Peor: obligaba a dos clics para decir una cosa. Al asignar un técnico, el ticket
pasaba solo a «asignado»; para pasarlo a «en progreso» hacía falta un segundo clic
en otro control. Ese segundo clic no lo daba nadie. En la base había 13 tickets
parados en «asignado» y ni uno solo en «en progreso»: el estado no describía nada,
era un sitio donde los casos se quedaban.

Así que asignar un técnico hace lo que la persona que lo asigna espera: el caso
pasa a «en progreso» en el mismo paso. Quedan cuatro estados, y se lee lo que
significan de un vistazo:

    nuevo       acaba de reportarse y nadie lo ha tomado
    en progreso hay un técnico con el caso
    en espera   está parado, esperando un repuesto o una respuesta
    cerrado      terminado, con su solución escrita

Aquí los tickets que estaban en «asignado» pasan a «en progreso», que es donde
estaban de hecho: nadie los había vuelto a tocar. Si alguno no tenía técnico —que
no debería ocurrir, porque asignar es lo que ponía el estado— se devuelven a
«nuevo», que es lo que significa no tener a nadie con el caso.
"""

DESCRIPCION = "Los tickets en estado asignado pasan a en progreso"

from app.domain.constants import (
    ESTADO_ASIGNADO_LEGADO,
    ESTADO_EN_PROGRESO,
    ESTADO_NUEVO,
)


async def aplicar(db) -> None:
    from app.core.time import utcnow

    ahora = utcnow()
    # Sin técnico asignado el estado «en progreso» mentiría, así que vuelve a la
    # cola. Es la situación que no debería existir; se deja explícita para que un
    # dato raro no produzca una etiqueta falsa.
    await db["tickets"].update_many(
        {"estado": ESTADO_ASIGNADO_LEGADO, "tecnico_id": None},
        {"$set": {"estado": ESTADO_NUEVO, "actualizado_en": ahora}},
    )
    await db["tickets"].update_many(
        {"estado": ESTADO_ASIGNADO_LEGADO},
        {"$set": {"estado": ESTADO_EN_PROGRESO, "actualizado_en": ahora}},
    )
    # Las vistas guardadas filtraban por el estado retirado; si se deja ahi, la
    # vista se queda vacia sin avisar de nada.
    await db["vistas_guardadas"].update_many(
        {"filtros.estado": ESTADO_ASIGNADO_LEGADO},
        {"$set": {"filtros.estado": [ESTADO_EN_PROGRESO], "actualizado_en": ahora}},
    )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()


async def revertir(db) -> None:
    from app.core.time import utcnow

    ahora = utcnow()
    await db["tickets"].update_many(
        {"estado": ESTADO_EN_PROGRESO},
        {"$set": {"estado": ESTADO_ASIGNADO_LEGADO, "actualizado_en": ahora}},
    )
    await db["vistas_guardadas"].update_many(
        {"filtros.estado": ESTADO_EN_PROGRESO},
        {"$set": {"filtros.estado": [ESTADO_ASIGNADO_LEGADO], "actualizado_en": ahora}},
    )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()