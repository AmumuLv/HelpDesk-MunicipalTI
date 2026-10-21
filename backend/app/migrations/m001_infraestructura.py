"""Colecciones, validadores e indices."""

DESCRIPCION = "Creacion de colecciones, validadores de esquema e indices"

from app.domain.schemas_db import asegurar_estructura


async def aplicar(db) -> None:
    await asegurar_estructura(db)