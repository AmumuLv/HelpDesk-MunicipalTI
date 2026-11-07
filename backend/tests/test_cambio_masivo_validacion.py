"""Un destino inválido no debe dejar a medias una edición masiva."""
from bson import ObjectId
import pytest

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


async def test_ids_inexistentes_no_generan_historial_ni_cambios_parciales(db, api):
    mundo = await _mundo(api, 'masivo_ids')
    alta = await api.post('/api/activos', headers=mundo['admin'], json={
        'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id'], 'nombre_equipo': 'Equipo real del lote',
    })
    assert alta.status_code == 201, alta.text
    equipo_id = ObjectId(alta.json()['id'])
    antes = await db.activos.find_one({'_id': equipo_id})
    historia = await db.historial_responsables.find({}).sort('_id').to_list(None)
    respuesta = await api.post('/api/activos/cambio-masivo', headers=mundo['admin'], json={
        'activo_ids': [str(equipo_id), str(ObjectId())], 'estado': 'En reparación',
        'responsable_id': mundo['usuario_id'],
    })
    assert respuesta.status_code == 404, respuesta.text
    assert await db.activos.find_one({'_id': equipo_id}) == antes
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historia


@pytest.mark.parametrize('repetir_id', [False, True])
async def test_resultado_cuenta_equipos_distintos_y_no_campos_editados(db, api, repetir_id):
    mundo = await _mundo(api, 'masivo_conteo')
    alta = await api.post('/api/activos', headers=mundo['admin'], json={
        'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id'], 'nombre_equipo': 'Equipo del conteo',
    })
    assert alta.status_code == 201, alta.text
    equipo_id = alta.json()['id']
    respuesta = await api.post('/api/activos/cambio-masivo', headers=mundo['admin'], json={
        'activo_ids': [equipo_id] * (2 if repetir_id else 1), 'estado': 'En reparación',
        'oficina_id': mundo['oficina']['id'], 'responsable_id': mundo['usuario_id'],
    })
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {'actualizados': 1, 'solicitados': 1}
    historia = await db.historial_responsables.find({'activo_id': ObjectId(equipo_id)}).to_list(None)
    assert len(historia) == 1 and historia[0]['responsable_id'] == ObjectId(mundo['usuario_id'])
