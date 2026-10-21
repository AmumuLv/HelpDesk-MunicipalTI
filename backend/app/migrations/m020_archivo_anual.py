DESCRIPCION = 'Evita duplicar la misma carga de inventario anual'


async def aplicar(db):
    await db['inventario_versiones'].create_index([('anio', 1), ('archivo_hash', 1)], unique=True, partialFilterExpression={'archivo_hash': {'$exists': True}}, name='uq_anual_archivo')
