"""Identificador estable de cada componente dentro de su conjunto."""
DESCRIPCION = 'Numera los equipos de cada conjunto y reserva los números usados'

async def aplicar(db):
    async for conjunto in db['conjuntos'].find({}, {'ultimo_numero_equipo': 1}):
        equipos = await db['activos'].find({'conjunto_id': conjunto['_id']}).sort([('creado_en', 1), ('_id', 1)]).to_list(None)
        ocupados = {e['numero_equipo'] for e in equipos if isinstance(e.get('numero_equipo'), int)}
        siguiente = 1
        for equipo in equipos:
            if isinstance(equipo.get('numero_equipo'), int):
                continue
            while siguiente in ocupados:
                siguiente += 1
            await db['activos'].update_one({'_id': equipo['_id']}, {'$set': {'numero_equipo': siguiente}})
            ocupados.add(siguiente)
        await db['conjuntos'].update_one({'_id': conjunto['_id']}, {'$max': {'ultimo_numero_equipo': max(ocupados, default=0)}})
    await db['activos'].create_index([('conjunto_id', 1), ('numero_equipo', 1)], unique=True,
        partialFilterExpression={'conjunto_id': {'$type': 'objectId'}, 'numero_equipo': {'$type': 'number'}}, name='uq_numero_equipo_conjunto')
