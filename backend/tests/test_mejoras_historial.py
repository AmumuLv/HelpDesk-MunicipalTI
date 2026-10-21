from bson import ObjectId
from tests.test_tickets_horarios import _mundo
from app.services import analitica_service, analitica_chat


async def test_seleccion_separa_persona_compartidos_y_rechaza_ajenos(db, api):
    m = await _mundo(api, 'seleccion-pc')
    oficina = ObjectId(m['oficina']['id'])
    usuario, otro = ObjectId(m['usuario_id']), ObjectId(m['companero_id'])
    conjuntos, equipos = {}, {}
    for numero, (grupo, responsable) in enumerate([('propio', usuario), ('compartido', None), ('ajeno', otro)], 1):
        c = (await db.conjuntos.insert_one({'numero': numero, 'nombre': grupo, 'oficina_id': oficina, 'responsable_id': responsable, 'activo': True})).inserted_id
        e = (await db.activos.insert_one({'clave_natural': grupo, 'nombre_equipo': grupo, 'tipo': 'CPU', 'campos_estado': {}, 'oficina_id': oficina, 'responsable_id': responsable, 'conjunto_id': c, 'activo': True})).inserted_id
        conjuntos[grupo], equipos[grupo] = c, e
    r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': 'Necesito instalar Office', 'persona': {'es_para_mi': True}})
    assert r.status_code == 201, r.text
    ruta = f"/api/tickets/{r.json()['ticket']['id']}"
    opciones = (await api.get(ruta + '/vinculos', headers=m['tecnico'])).json()
    assert {e['id'] for e in opciones['equipos']} == {str(equipos['propio']), str(equipos['compartido'])}
    assert {c['id'] for c in opciones['conjuntos']} == {str(conjuntos['propio']), str(conjuntos['compartido'])}
    assert (await api.get(ruta + '/vinculos', headers=m['usuario'])).status_code == 403
    for campo, identificador in [('activo_id', equipos['ajeno']), ('conjunto_id', conjuntos['ajeno'])]:
        r = await api.patch(ruta, headers=m['tecnico'], json={'alcance_incidencia': 'programa', campo: str(identificador)})
        assert r.status_code == 422, r.text
    r = await api.patch(ruta, headers=m['tecnico'], json={'alcance_incidencia': 'programa', 'sistema_afectado': 'Office', 'conjunto_id': str(conjuntos['propio'])})
    assert r.status_code == 200, r.text
    assert r.json()['conjunto_id'] == str(conjuntos['propio'])


async def test_historial_sigue_equipo_y_conjunto_sin_cambiar_reportante(db, api):
    m = await _mundo(api, 'historial-pc')
    usuario, otro = ObjectId(m['usuario_id']), ObjectId(m['companero_id'])
    oficina = ObjectId(m['oficina']['id'])
    c = (await db.conjuntos.insert_one({'nombre': 'Computadora 2', 'oficina_id': oficina, 'responsable_id': usuario, 'activo': True})).inserted_id
    e = (await db.activos.insert_one({'clave_natural': 'transferido', 'nombre_equipo': 'CPU transferida', 'tipo': 'CPU', 'campos_estado': {}, 'oficina_id': oficina, 'responsable_id': None, 'activo': True})).inserted_id
    r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Impresora', 'descripcion': 'La impresora no funciona', 'persona': {'es_para_mi': True}})
    assert r.status_code == 201, r.text
    t = ObjectId(r.json()['ticket']['id'])
    # Simula un registro legado: el validador actual ya no permite crear resueltos.
    await db.tickets.update_one({'_id': t}, {'$set': {'activo_id': e, 'conjunto_id': None, 'reportante_id': otro, 'afectado_id': otro, 'estado': 'resuelto'}}, bypass_document_validation=True)
    await db.activos.update_one({'_id': e}, {'$set': {'responsable_id': usuario, 'conjunto_id': c}})
    for i in range(16):
        r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': f'Office no abre en mi computadora caso {i}', 'persona': {'es_para_mi': True}})
        assert r.status_code == 201, r.text
        await db.tickets.update_one({'_id': ObjectId(r.json()['ticket']['id'])}, {'$set': {'conjunto_id': c, 'alcance_incidencia': 'programa'}})
    ruta = f'/api/usuarios/{usuario}/tickets'
    r = await api.get(ruta, headers=m['admin'], params={'conjunto_id': str(c), 'por_pagina': 15})
    assert r.status_code == 200, r.text
    assert r.json()['total'] == 17 and len(r.json()['items']) == 15 and r.json()['total_paginas'] == 2
    r = await api.get(ruta, headers=m['admin'], params={'activo_id': str(e), 'estado': 'cerrado'})
    assert r.status_code == 200, r.text
    assert r.json()['total'] == 1 and r.json()['items'][0]['estado'] == 'cerrado'
    assert r.json()['items'][0]['reportante_id'] == str(otro)
    assert (await db.tickets.find_one({'_id': t}))['conjunto_id'] is None
    r = await api.get(f'/api/tickets?conjunto_id={c}', headers=m['admin'])
    assert r.status_code == 200 and r.json()['total'] == 17, r.text
    opciones = await api.get(f'/api/usuarios/{usuario}/inventario-historial', headers=m['admin'])
    assert opciones.status_code == 200 and opciones.json()['conjuntos'][0]['tickets'] == 17, opciones.text
    assert (await api.get(f'/api/usuarios/{usuario}/inventario-historial', headers=m['usuario'])).status_code == 403
    ranking = await analitica_service.ranking_conjuntos({'periodo': '30d'})
    assert ranking['items'][0]['total'] == 17
    assert ranking['items'][0]['programas'] == 16
    assert ranking['items'][0]['responsable_id'] == str(usuario)
    assert analitica_chat._detectar_intencion('Que conjunto tiene mas incidencias')[0] == 'ranking_conjuntos'
    assert '17 tickets' in analitica_chat._formatear('ranking_conjuntos', ranking)[0]


async def test_oficina_pagina_25_y_excluye_eliminados_de_indicadores(db, api):
    from app.core.time import utcnow
    m = await _mundo(api, 'oficina-paginada')
    oficina = ObjectId(m['oficina']['id'])
    await db.tickets.insert_many([{'codigo': f'OF-{i}', 'asunto': f'Incidencia {i}', 'estado': 'nuevo',
        'origen': 'usuario', 'oficina_id': oficina, 'creado_en': utcnow(), 'prioridad': 'media',
        'categoria': 'Hardware', 'eliminado': i == 26} for i in range(27)])
    r = await api.get(f'/api/oficinas/{oficina}', headers=m['admin'])
    assert r.status_code == 200, r.text
    datos = r.json()
    assert len(datos['tickets_recientes']) == 25
    assert datos['tickets_abiertos'] == 26
    assert sum(f['total'] for f in datos['tendencia']) == 26
    assert sum(f['total'] for f in datos['incidencias_recurrentes']) == 26
    for pagina, cantidad in [(1, 25), (2, 1)]:
        r = await api.get('/api/tickets', headers=m['admin'], params={'oficina_id': str(oficina), 'solo_abiertos': True, 'por_pagina': 25, 'pagina': pagina})
        assert r.status_code == 200, r.text
        assert r.json()['total'] == 26 and len(r.json()['items']) == cantidad
