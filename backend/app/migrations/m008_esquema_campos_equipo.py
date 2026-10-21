"""Quitar el tamaño de pantalla del esquema de CPU."""

DESCRIPCION = "Alinear los campos esperados de CPU con sus características"


async def aplicar(db):
    await db["esquemas_tipos"].update_one(
        {"tipo": "CPU"},
        {"$pull": {"opcionales": "tamano_pantalla"}},
    )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()


async def revertir(db):
    await db["esquemas_tipos"].update_one(
        {"tipo": "CPU"},
        {"$addToSet": {"opcionales": "tamano_pantalla"}},
    )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()
