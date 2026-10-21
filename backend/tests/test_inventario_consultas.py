from tests.test_tickets_horarios import _mundo
from app.services import inventario_service, catalogo_service
from bson import ObjectId

async def test_consultas_seguras_orden_natural_y_faltantes(db, api):
    mundo = await _mundo(api, 'consultas')
    for query in ('pagina=0', 'por_pagina=100000', 'por_pagina=0', 'orden=no_existe'):
        assert (await api.get('/api/activos?' + query, headers=mundo['admin'])).status_code == 422
    for texto in ('(', '[', '.*'):
        r = await api.get('/api/activos', params={'texto': texto}, headers=mundo['admin'])
        assert r.status_code == 200, r.text
        assert r.json()['total'] == 0
    for oficina, numero in [('B', 1), ('A', 10), ('A', 2), ('A', 2)]:
        await db['activos'].insert_one({'clave_natural': str(ObjectId()), 'oficina_id': ObjectId(mundo['oficina']['id']), 'activo': True, 'tipo': 'CPU', 'tipo_normalizado': 'CPU', 'campos_estado': {}, 'zona_nombre': 'Zona', 'oficina_nombre': oficina, 'conjunto_nombre': f'Computadora N°{numero}', 'faltantes_count': 3})
    r1 = (await api.get('/api/activos?por_pagina=2', headers=mundo['admin'])).json()
    r2 = (await api.get('/api/activos?por_pagina=2&pagina=2', headers=mundo['admin'])).json()
    assert r1['total'] == 4
    assert [x['conjunto_nombre'] for x in r1['items']] == ['Computadora N°2'] * 2
    assert r2['items'][0]['conjunto_nombre'] == 'Computadora N°10'
    assert len({x['id'] for x in r1['items'] + r2['items']}) == 4
    assert (await api.get('/api/activos?solo_faltantes=true&por_pagina=1', headers=mundo['admin'])).json()['total'] == 4
    activo = ObjectId(r1['items'][0]['id'])
    esquema = await catalogo_service.esquema('CPU')
    await inventario_service.marcar_campos([activo], esquema['esperados'], 'no_aplica', usuario={'nombre': 'Prueba', 'rol': 'administrador'})
    assert (await db['activos'].find_one({'_id': activo}))['faltantes_count'] == 0
    assert (await api.get('/api/activos?solo_faltantes=true&por_pagina=1', headers=mundo['admin'])).json()['total'] == 3
    assert (await api.get('/api/activos/plantilla-manual', params={'oficina_id': mundo['oficina']['id']}, headers=mundo['admin'])).status_code == 200

async def test_cambiar_esquema_recalcula_calidad_y_cache_caduca(db, api):
    mundo = await _mundo(api, 'esquema')
    assert 'tamano_pantalla' not in (await catalogo_service.esquema('CPU'))['opcionales']
    activo = await inventario_service.crear_activo({'tipo': 'CPU', 'oficina_id': ObjectId(mundo['oficina']['id']), 'marca': 'Conocida'}, usuario={'nombre': 'Prueba', 'rol': 'administrador'})
    await catalogo_service.actualizar_esquema('CPU', {'esperados': ['marca'], 'opcionales': []}, usuario={'nombre': 'Prueba', 'rol': 'administrador'})
    assert (await db['activos'].find_one({'_id': activo['_id']}))['faltantes_count'] == 0
    await db['esquemas_tipos'].update_one({'tipo': 'CPU'}, {'$set': {'esperados': ['modelo']}})
    catalogo_service._CACHE_HASTA['CPU'] = 0
    assert (await catalogo_service.esquema('CPU'))['esperados'] == ['modelo']


async def test_codigos_ip_y_mac_duplicados_se_advierten_sin_bloquear(db, api):
    mundo = await _mundo(api, 'duplicados')
    indices = await db['activos'].index_information()
    assert 'uq_activos_codigo' not in indices
    assert indices['ix_activos_codigo'].get('unique') is not True
    payload = {
        'tipo': 'CPU',
        'oficina_id': mundo['oficina']['id'],
        'codigo_patrimonial': 'TI-001',
        'direccion_ip': '10.8.0.15',
        'direccion_mac': '00:11:22:33:44:55',
    }
    primero = await api.post('/api/activos', json=payload, headers=mundo['admin'])
    segundo = await api.post('/api/activos', json=payload, headers=mundo['admin'])
    assert primero.status_code == 201, primero.text
    assert segundo.status_code == 201, segundo.text

    coincidencias = await api.get(
        '/api/activos/duplicados',
        params={
            'codigo_patrimonial': payload['codigo_patrimonial'],
            'direccion_ip': payload['direccion_ip'],
            'direccion_mac': payload['direccion_mac'],
        },
        headers=mundo['admin'],
    )
    assert coincidencias.status_code == 200, coincidencias.text
    filas = coincidencias.json()['items']
    assert {fila['id'] for fila in filas} == {primero.json()['id'], segundo.json()['id']}
    assert all(set(fila['coincide_en']) == {'codigo_patrimonial', 'direccion_ip', 'direccion_mac'} for fila in filas)

    filtradas = await api.get(
        '/api/activos/duplicados',
        params={'codigo_patrimonial': payload['codigo_patrimonial'], 'excluir_id': segundo.json()['id']},
        headers=mundo['admin'],
    )
    assert [fila['id'] for fila in filtradas.json()['items']] == [primero.json()['id']]
