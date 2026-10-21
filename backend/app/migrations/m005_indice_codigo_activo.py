"""Indice unico de codigo patrimonial solo para los que realmente lo tienen.

Antes el filtro era ``$exists: true``, pero todos los activos guardan la clave
(incluso con valor null), asi que dos equipos sin codigo chocaban. Ahora el indice
aplica solo a valores de tipo texto y los equipos sin codigo se identifican por su
clave natural (oficina + conjunto + dispositivo).
"""

DESCRIPCION = "Indice parcial de codigo patrimonial solo para valores de texto"

from app.domain.schemas_db import INDICE_CODIGO_ACTIVO

NOMBRE_INDICE = "uq_activos_codigo"


async def aplicar(db) -> None:
    try:
        await db["activos"].drop_index(NOMBRE_INDICE)
    except Exception:
        pass
    await db["activos"].create_index(
        INDICE_CODIGO_ACTIVO, name=NOMBRE_INDICE, unique=True, partialFilterExpression={"codigo_patrimonial": {"$type": "string"}}
    )


async def revertir(db) -> None:
    try:
        await db["activos"].drop_index(NOMBRE_INDICE)
    except Exception:
        pass
    await db["activos"].create_index(
        [("codigo_patrimonial", 1)], name=NOMBRE_INDICE, unique=True, partialFilterExpression={"codigo_patrimonial": {"$exists": True}}
    )