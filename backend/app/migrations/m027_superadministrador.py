"""Un único titular de la administración de cuentas, sin cambiar los roles operativos."""

DESCRIPCION = "Protege la cuenta de superadministrador y reserva su indicador único"


async def aplicar(db):
    # No elegir arbitrariamente un propietario cuando ya existen varios admins.
    if not await db['usuarios'].find_one({'superadministrador': True}):
        candidatos = await db['usuarios'].find({'rol': 'administrador', 'activo': True}).limit(2).to_list(None)
        if len(candidatos) == 1:
            await db['usuarios'].update_one({'_id': candidatos[0]['_id']}, {'$set': {'superadministrador': True}})
    await db['usuarios'].create_index(
        [('superadministrador', 1)], unique=True,
        partialFilterExpression={'superadministrador': True}, name='superadministrador_unico',
    )
