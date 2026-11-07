"""La herencia de una PC deja trazabilidad sin sustituir dueños particulares."""
from bson import ObjectId

from tests.test_tickets_horarios import _mundo


async def _alta(api, mundo, ruta, datos):
    respuesta = await api.post('/api' + ruta, headers=mundo['admin'], json={
        'oficina_id': mundo['oficina']['id'], **datos,
    })
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


async def test_herencia_registra_cada_componente_y_respeta_responsable_propio(db, api):
    m = await _mundo(api, 'herencia_historial')
    pc = await _alta(api, m, '/conjuntos', {'nombre': 'PC compartida', 'uso_comun': True})
    libres = [await _alta(api, m, '/activos', {
        'tipo': tipo, 'nombre_equipo': f'Componente libre {tipo}', 'conjunto_id': pc['id'],
        'uso_comun': True,
    }) for tipo in ('CPU', 'Monitor', 'Mouse')]
    propio = await _alta(api, m, '/activos', {
        'tipo': 'Teclado', 'conjunto_id': pc['id'], 'responsable_id': m['companero_id'],
    })
    filtro_propio = {'activo_id': ObjectId(propio['id'])}
    historia_propia = await db.historial_responsables.find(filtro_propio).to_list(None)
    ruta = f"/api/conjuntos/{pc['id']}/responsable"
    datos = {'responsable_id': m['usuario_id'], 'motivo': 'Asignación de PC completa'}
    permiso = await api.put(f"/api/permisos/tecnicos/{m['tecnico_id']}", headers=m['admin'],
                            json={'cambios': {'equipos.editar': True}})
    assert permiso.status_code == 200, permiso.text
    antes = await db.historial_responsables.count_documents({})
    assert (await api.post(ruta, headers=m['usuario'], json=datos)).status_code == 403
    assert await db.historial_responsables.count_documents({}) == antes
    resultado = await api.post(ruta, headers=m['tecnico'], json=datos)
    assert resultado.status_code == 200, resultado.text
    for libre in libres:
        equipo = await db.activos.find_one({'_id': ObjectId(libre['id'])})
        historia = await db.historial_responsables.find({'activo_id': equipo['_id']}).to_list(None)
        assert equipo['responsable_id'] == ObjectId(m['usuario_id'])
        assert equipo['uso_comun'] is False
        assert len(historia) == 1
        assert historia[0]['responsable_id'] == equipo['responsable_id']
        assert historia[0]['usuario_id'] == ObjectId(m['tecnico_id'])
        assert historia[0]['motivo'] == datos['motivo'] and historia[0]['fin'] is None
    assert (await db.activos.find_one({'_id': ObjectId(propio['id'])}))['responsable_id'] == ObjectId(m['companero_id'])
    assert await db.historial_responsables.find(filtro_propio).to_list(None) == historia_propia
    foto = await db.historial_responsables.find({}).sort('_id').to_list(None)
    assert (await api.post(ruta, headers=m['tecnico'], json=datos)).status_code == 200
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == foto


async def test_vincular_a_otra_pc_registra_cambio_implicito_sin_mezclar_tickets(db, api):
    m = await _mundo(api, 'vinculo_historial')
    pc = await _alta(api, m, '/conjuntos', {
        'nombre': 'PC del reemplazo', 'responsable_id': m['companero_id'],
    })
    cpu = await _alta(api, m, '/activos', {
        'tipo': 'CPU', 'responsable_id': m['usuario_id'], 'nombre_equipo': 'CPU original',
    })
    ticket = await api.post('/api/tickets', headers=m['usuario'], json={'descripcion': 'Fallo anterior a la transferencia'})
    assert ticket.status_code == 201, ticket.text
    ticket_id = ObjectId(ticket.json()['ticket']['id'])
    vinculo = await api.patch(f'/api/tickets/{ticket_id}', headers=m['admin'], json={
        'categoria': 'Hardware', 'activo_id': cpu['id'],
    })
    assert vinculo.status_code == 200, vinculo.text
    antes = await db.tickets.find_one({'_id': ticket_id})
    cambio = await api.patch(f"/api/activos/{cpu['id']}", headers=m['admin'], json={
        'conjunto_id': pc['id'], 'motivo': 'Componente trasladado a otra PC',
    })
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()['responsable_id'] == m['companero_id']
    historia = await db.historial_responsables.find({'activo_id': ObjectId(cpu['id'])}).sort('inicio').to_list(None)
    assert [h['responsable_id'] for h in historia] == [ObjectId(m['usuario_id']), ObjectId(m['companero_id'])]
    assert historia[0]['fin'] is not None and historia[0]['fin'] <= historia[1]['inicio']
    assert historia[1]['fin'] is None
    assert historia[1]['motivo'] == 'Componente trasladado a otra PC'
    assert await db.tickets.find_one({'_id': ticket_id}) == antes
    repetido = await api.patch(f"/api/activos/{cpu['id']}", headers=m['admin'], json={'conjunto_id': pc['id']})
    assert repetido.status_code == 200, repetido.text
    assert await db.historial_responsables.find({'activo_id': ObjectId(cpu['id'])}).sort('inicio').to_list(None) == historia
