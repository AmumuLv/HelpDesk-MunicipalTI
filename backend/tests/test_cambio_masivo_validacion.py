"""Un destino inválido no debe dejar a medias una edición masiva."""
from bson import ObjectId

from tests.test_tickets_horarios import _mundo


async def test_oficina_inexistente_no_modifica_el_estado_ni_responsable(db, api):
    mundo = await _mundo(api, 'masivo_validacion')
    respuesta = await api.post('/api/activos', headers=mundo['admin'], json={
        'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id'],
        'responsable_id': mundo['usuario_id'], 'nombre_equipo': 'Equipo de validación',
    })
    assert respuesta.status_code == 201, respuesta.text
    equipo = respuesta.json()
    antes = await db.activos.find_one({'_id': ObjectId(equipo['id'])})
    historial = await db.historial_responsables.find({}).sort('_id').to_list(None)
    cambios = {'activo_ids': [equipo['id']], 'estado': 'En reparación', 'oficina_id': str(ObjectId())}
    rechazo = await api.post('/api/activos/cambio-masivo', headers=mundo['admin'], json=cambios)
    assert rechazo.status_code == 404, rechazo.text
    assert await db.activos.find_one({'_id': antes['_id']}) == antes
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historial
    cambios['oficina_id'] = mundo['oficina']['id']
    valido = await api.post('/api/activos/cambio-masivo', headers=mundo['admin'], json=cambios)
    assert valido.status_code == 200, valido.text
    despues = await db.activos.find_one({'_id': antes['_id']})
    assert despues['estado'] == cambios['estado']
    assert despues['responsable_id'] == antes['responsable_id']
