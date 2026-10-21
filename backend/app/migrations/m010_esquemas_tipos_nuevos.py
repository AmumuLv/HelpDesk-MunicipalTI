"""Esquemas de campos para los tipos de equipo que no tenian el suyo.

El alta de equipos pide segun el tipo: a un sistema de audio no se le pregunta
la direccion IP y a un UPS tampoco, pero a un servidor se le pide lo mismo que a
una CPU. Como el esquema vive en ``esquemas_tipos`` —que el administrador puede
editar en Configuracion— aqui solo se insertan los tipos que **no** existen
todavia: los que ya estaban no se tocan, para no perder personalizaciones.
"""

DESCRIPCION = "Esquemas de campos de switch, servidor, tablet, celular, UPS, disco externo, audio y otros"

from app.core.time import utcnow
from app.domain.constants import ESQUEMAS_POR_TIPO, OPCIONES_AVANZADAS_POR_TIPO


async def aplicar(db) -> None:
    ahora = utcnow()
    for tipo, esquema in ESQUEMAS_POR_TIPO.items():
        await db["esquemas_tipos"].update_one(
            {"tipo": tipo},
            {
                "$setOnInsert": {
                    "tipo": tipo,
                    "esperados": list(esquema["esperados"]),
                    "opcionales": list(esquema["opcionales"]),
                    "avanzadas": list(OPCIONES_AVANZADAS_POR_TIPO.get(tipo, [])),
                    "creado_en": ahora,
                }
            },
            upsert=True,
        )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()


async def revertir(db) -> None:
    # Insertar no se deshace: los esquemas que se borren habria que reponerlos
    # a mano desde Configuracion.
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()