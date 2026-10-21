from datetime import datetime, timedelta, timezone

from bson import ObjectId

from tests.test_tickets_horarios import _mundo


async def test_perfiles_no_recortan_listas_y_reflejan_cierre(db, api):
    mundo = await _mundo(api, 'listas-org')
    ahora = datetime.now(timezone.utc)
    documentos = [{
        'codigo': f'TKT-PRUEBA-{i}', 'asunto': f'Incidencia {i}',
        'oficina_id': ObjectId(mundo['oficina']['id']),
        'zona_id': ObjectId(mundo['zona']['id']), 'estado': 'nuevo',
        'origen': 'tecnico', 'categoria': f'Categoria {i}', 'activo_id': ObjectId(),
        'activo_nombre': f'Equipo {i}', 'creado_en': ahora - timedelta(days=i),
    } for i in range(12)]
    await db['tickets'].insert_many(documentos)
    oficina_url = f"/api/oficinas/{mundo['oficina']['id']}"
    zona_url = f"/api/zonas/{mundo['zona']['id']}"
    oficina = await api.get(oficina_url, headers=mundo['admin'])
    assert oficina.status_code == 200, oficina.text
    datos = oficina.json()
    assert len(datos['tickets_recientes']) == 12
    assert len(datos['incidencias_recurrentes']) == 12
    assert len(datos['tendencia']) == 12
    zona = await api.get(zona_url, headers=mundo['admin'])
    assert zona.status_code == 200, zona.text
    assert len(zona.json()['categorias_frecuentes']) == 12
    assert zona.json()['oficinas_con_mas_fallas'] == [{'id': mundo['oficina']['id'], 'nombre': mundo['oficina']['nombre'], 'tickets': 12}]
    await db['tickets'].update_one({'_id': documentos[0]['_id']}, {'$set': {'estado': 'cerrado'}})
    actualizado = (await api.get(oficina_url, headers=mundo['admin'])).json()
    assert actualizado['tickets_abiertos'] == 11
    assert len(actualizado['tickets_recientes']) == 11
    assert (await api.get(zona_url, headers=mundo['admin'])).json()['tickets_abiertos'] == 11
    otra = (await api.post('/api/oficinas', headers=mundo['admin'], json={'nombre': 'Otra oficina', 'zona_id': mundo['zona']['id']})).json()
    await db.tickets.insert_many([{'codigo': f'TKT-OFICINA-{i}', 'asunto': 'Incidencia de programa sin equipo',
        'zona_id': ObjectId(mundo['zona']['id']), 'oficina_id': ObjectId(otra['id']),
        'oficina_nombre': 'Nombre anterior', 'estado': 'nuevo', 'origen': 'tecnico',
        'creado_en': ahora, 'eliminado': i == 2} for i in range(3)])
    ranking = (await api.get(zona_url, headers=mundo['admin'])).json()['oficinas_con_mas_fallas']
    assert [f['tickets'] for f in ranking] == [12, 2]
    assert ranking[1]['id'] == otra['id'] and ranking[1]['nombre'] == 'Otra oficina'

