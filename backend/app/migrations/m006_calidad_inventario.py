DESCRIPCION = 'Persistir faltantes y ordenar inventario de forma estable'

async def aplicar(db):
    from app.services.catalogo_service import invalidar_cache_esquemas
    from app.services.inventario_service import recalcular_faltantes
    invalidar_cache_esquemas()
    await recalcular_faltantes({})
    await db['activos'].create_index([('faltantes_count', 1), ('activo', 1)])
    await db['activos'].create_index([('zona_nombre', 1), ('oficina_nombre', 1), ('conjunto_nombre', 1), ('tipo', 1), ('_id', 1)], collation={'locale': 'es', 'numericOrdering': True})
