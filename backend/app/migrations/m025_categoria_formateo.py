"""Distingue el trabajo físico de formateo de incidencias de programas."""
DESCRIPCION = 'Categoría Formateo en el catálogo común de tickets'


async def aplicar(db):
    doc = await db.catalogos.find_one({'clave': 'categorias'})
    valores = (doc or {}).get('valores', [])
    if doc and not any((v.get('valor') if isinstance(v, dict) else v).strip().lower() == 'formateo' for v in valores):
        await db.catalogos.update_one({'_id': doc['_id']}, {'$push': {'valores': {'valor': 'Formateo', 'etiqueta': 'Formateo', 'activo': True, 'orden': len(valores)}}})
