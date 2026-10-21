"""Aplica el límite también a las sesiones anteriores al control de dispositivos."""
from app.core.time import utcnow

DESCRIPCION = 'Conserva como máximo las tres conexiones vigentes más recientes por cuenta'


async def aplicar(db):
    ahora = utcnow()
    async for usuario in db['usuarios'].find({}, {'_id': 1}):
        vigentes = await db['sesiones'].find(
            {'usuario_id': usuario['_id'], 'revocado': False, 'expira': {'$gt': ahora}},
            {'session_id': 1},
        ).sort([('creado_en', -1), ('_id', -1)]).to_list(None)
        conservadas = [s['session_id'] for s in reversed(vigentes[:3])]
        await db['usuarios'].update_one({'_id': usuario['_id']}, {'$set': {'sesiones_activas': conservadas}})
        if len(vigentes) > 3:
            await db['sesiones'].update_many(
                {'usuario_id': usuario['_id'], 'session_id': {'$in': [s['session_id'] for s in vigentes[3:]]}},
                {'$set': {'revocado': True, 'revocado_en': ahora}},
            )
