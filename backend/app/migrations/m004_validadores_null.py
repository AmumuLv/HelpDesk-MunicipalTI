"""Correccion de validadores: los campos opcionales admiten null.

El sistema nunca inventa datos: un equipo sin codigo patrimonial guarda ``null``.
El validador anterior exigia ``string`` y rechazaba esa escritura.
"""

DESCRIPCION = "Validadores que admiten null en campos opcionales (codigo, zona, oficina)"

from app.domain.schemas_db import VALIDADORES


async def aplicar(db) -> None:
    for coleccion, opciones in VALIDADORES.items():
        existe = await db.list_collection_names()
        if coleccion not in existe:
            await db.create_collection(coleccion, validator=opciones, validationLevel="moderate", validationAction="error")
            continue
        await db.command(
            "collMod",
            coleccion,
            validator=opciones,
            validationLevel="moderate",
            validationAction="error",
        )


async def revertir(db) -> None:
    for coleccion in VALIDADORES:
        existe = await db.list_collection_names()
        if coleccion in existe:
            await db.command("collMod", coleccion, validator={}, validationLevel="off")