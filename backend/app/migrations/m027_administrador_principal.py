"""Protege al administrador inicial sin retirar facultades operativas a los demás."""

DESCRIPCION = 'Cuenta principal protegida y única; primera cuenta administrativa activa existente'


async def aplicar(db):
    await db['usuarios'].create_index(
        [('administrador_principal', 1)], unique=True,
        partialFilterExpression={'administrador_principal': True}, name='administrador_principal_unico',
    )
    if not await db['usuarios'].find_one({'administrador_principal': True}):
        primera = await db['usuarios'].find_one(
            {'rol': 'administrador', 'activo': True}, sort=[('creado_en', 1), ('_id', 1)],
        )
        if primera:
            await db['usuarios'].update_one(
                {'_id': primera['_id'], 'rol': 'administrador', 'activo': True},
                {'$set': {'administrador_principal': True}},
            )
