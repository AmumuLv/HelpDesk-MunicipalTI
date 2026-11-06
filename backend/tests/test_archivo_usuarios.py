"""Bajas, conservaci?n de identidad y archivo autom?tico sin borrar registros."""
from datetime import timedelta
from bson import ObjectId
from app.core.time import utcnow
from app.services import usuario_service
from tests.test_jerarquia_cuentas import mundo


async def test_baja_archivo_filtros_y_reactivacion(db, api):
    ids, _, admin, _ = await mundo(api)
    persona = ObjectId(ids['persona'])
    base = f'/api/usuarios/{persona}'
    assert (await api.patch(base, headers=admin, json={'activo': False})).status_code == 200
    baja = await db.usuarios.find_one({'_id': persona})
    assert baja['desactivado_en'] and not baja.get('archivado')
    assert (await usuario_service.archivar_desactivados())['archivados'] == 0
    await db.usuarios.update_one({'_id': persona}, {'$set': {'desactivado_en': utcnow() - timedelta(days=31)}})
    historia = {'reportante_id': persona, 'afectado_id': persona, 'asunto': 'Historia original', 'codigo': 'TKT-ARCHIVO-1', 'estado': 'nuevo', 'origen': 'usuario'}
    ticket = await db.tickets.insert_one(historia)
    assert (await usuario_service.archivar_desactivados())['archivados'] == 1
    assert (await usuario_service.archivar_desactivados())['archivados'] == 0
    resultado = await api.get('/api/usuarios?estado=archivados', headers=admin)
    assert resultado.status_code == 200
    assert [p['id'] for p in resultado.json()['items']] == [str(persona)]
    assert resultado.json()['items'][0]['archivado'] is True
    for estado in ['activos', 'desactivados']:
        respuesta = await api.get(f'/api/usuarios?estado={estado}', headers=admin)
        assert str(persona) not in [p['id'] for p in respuesta.json()['items']]
    assert await db.tickets.find_one({'_id': ticket.inserted_id}) == historia
    assert (await api.patch(base, headers=admin, json={'activo': True})).status_code == 200
    vuelta = await db.usuarios.find_one({'_id': persona})
    assert vuelta['activo'] and not vuelta['archivado'] and vuelta['desactivado_en'] is None
    assert vuelta['nombre'] == baja['nombre']


async def test_bajas_antiguas_inician_plazo_y_principal_no_se_archiva(db, api):
    ids, _, _, _ = await mundo(api)
    persona = ObjectId(ids['persona'])
    principal = ObjectId(ids['principal'])
    await db.usuarios.update_one({'_id': persona}, {'$set': {'activo': False}})
    await db.usuarios.update_one({'_id': principal}, {'$set': {'activo': False, 'desactivado_en': utcnow() - timedelta(days=40)}})
    assert (await usuario_service.archivar_desactivados())['archivados'] == 0
    assert (await db.usuarios.find_one({'_id': persona}))['desactivado_en']
    assert not (await db.usuarios.find_one({'_id': principal})).get('archivado')
