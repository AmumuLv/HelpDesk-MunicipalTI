"""El índice único de los items de campaña solo aplica a los equipos de verdad.

El índice `uq_item_campana_activo` era único sobre `(campana_id, activo_id)` para
que un equipo no apareciera dos veces en la misma campaña. Correcto, mientras todos
los items tuvieran equipo.

El problema son los **equipos nuevos** que se encuentran en la sala y no están en el
inventario: se guardan como items con `activo_id: null` porque todavía no son un
equipo. En un índice único de Mongo, `null` **es un valor**, no «no hay valor»: todos
esos items comparten la misma clave `(campana_id, null)` y el segundo revienta con
`E11000 duplicate key error`.

O sea, lo contrario de lo que quería la función: solo se podía registrar **un**
equipo nuevo por campaña. Con la lista de la sala, el primero entraba y a partir del
segundo la subida del Excel fallaba entera con un error 500 sin explicación.

La corrección es el índice **parcial**: la unicidad sigue existiendo para los equipos
reales —que es lo que la regla protege— y deja de aplicarse a los items que aún no
tienen equipo. No se pierde ninguna garantía: no se estaba evitando ningún duplicado
real, se estaba impidiendo que hubiera más de un `null`.

No hay que tocar los datos: los items que ya existían con `activo_id: null` son, por
definición, los equipos nuevos pendientes, y ninguno queda huérfano. El índice viejo
se tira y se reconstruye; Mongo lo hace en segundo plano.
"""

DESCRIPCION = "El indice unico de items de campana deja de aplicar a los equipos aun sin registrar"


async def aplicar(db) -> None:
    coleccion = db["campana_items"]
    try:
        await coleccion.drop_index("uq_item_campana_activo")
    except Exception:  # pragma: no cover - el indice puede no existir todavia
        pass
    await coleccion.create_index(
        [("campana_id", 1), ("activo_id", 1)],
        name="uq_item_campana_activo",
        unique=True,
        partialFilterExpression={"activo_id": {"$type": "objectId"}},
    )


async def revertir(db) -> None:
    """Deja el indice como estaba: unico para todos los items, los null incluidos.

    Volver a este estado reproduce el fallo (un solo equipo nuevo por campaña), pero
    es lo que había y por eso se puede volver a él.
    """
    coleccion = db["campana_items"]
    try:
        await coleccion.drop_index("uq_item_campana_activo")
    except Exception:  # pragma: no cover
        pass
    await coleccion.create_index(
        [("campana_id", 1), ("activo_id", 1)], name="uq_item_campana_activo", unique=True
    )