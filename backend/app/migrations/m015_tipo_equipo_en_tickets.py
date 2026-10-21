"""Los tickets guardan el tipo de su equipo.

La columna «Equipo» de la bandeja mostraba el nombre del equipo arriba y el
conjunto al que pertenece abajo. En el inventario importado el nombre del equipo ya
empieza por el del conjunto —«Computadora N°01 - CPU» dentro de «Computadora N°01»—,
así que la segunda línea repetía lo que ya se leía arriba. Y como la columna es
estrecha, el final del nombre se cortaba: el «- CPU» era justo lo que desaparecía,
y sin eso no había forma de saber si lo que se veía era una CPU o una impresora.

Se guarda el tipo del equipo en el ticket y la columna lo enseña aparte. Es un dato
que ya estaba en el inventario, pero vive en otra colección: la bandeja no la mira,
y pedirla en cada fila de la tabla sería una consulta por fila.

Los tickets que ya existían no lo tienen, así que se rellena desde el inventario,
que es de donde sale. Solo se toca el campo nuevo: no se reescribe ni el nombre ni
el conjunto ni nada del equipo.
"""

DESCRIPCION = "Los tickets guardan el tipo del equipo para la columna Equipo"


async def aplicar(db) -> None:
    activos = await db["activos"].find({}, {"tipo": 1}).to_list(None)
    for activo in activos:
        tipo = activo.get("tipo")
        if not tipo:
            continue
        await db["tickets"].update_many(
            {
                "activo_id": activo["_id"],
                "$or": [{"activo_tipo": None}, {"activo_tipo": ""}, {"activo_tipo": {"$exists": False}}],
            },
            {"$set": {"activo_tipo": tipo}},
        )


async def revertir(db) -> None:
    """Quita el campo de todos los tickets.

    No se distinguen los que ya lo traían al crearse de los que lo recibieron
    aquí, pero da igual: un ticket con su tipo escrito es correcto en ambos casos.
    """
    await db["tickets"].update_many({}, {"$unset": {"activo_tipo": ""}})