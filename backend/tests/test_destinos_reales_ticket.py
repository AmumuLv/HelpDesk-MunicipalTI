from bson import ObjectId
from tests.test_tickets_horarios import _mundo


async def test_perfil_tecnico_solo_desde_ticket_autorizado_y_datos_acotados(db, api):
    from tests.test_tickets_horarios import _sesion
    m = await _mundo(api, 'perfil-tecnico')
    r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Otro', 'descripcion': 'Necesito ayuda para trabajar'})
    assert r.status_code == 201, r.text
    ticket_id = r.json()['ticket']['id']
    ruta = f'/api/tickets/{ticket_id}/tecnico-perfil'
    assert (await api.get(ruta, headers=m['usuario'])).status_code == 404
    await db.tickets.update_one({'_id': ObjectId(ticket_id)}, {'$set': {'tecnico_id': ObjectId(m['tecnico_id']), 'tecnico_nombre': 'Tecnico prueba'}})
    await db.tecnicos_perfil.update_one({'usuario_id': ObjectId(m['tecnico_id'])}, {'$set': {'especialidades': ['Redes']}}, upsert=True)
    perfil = await api.get(ruta, headers=m['usuario'])
    assert perfil.status_code == 200, perfil.text
    assert set(perfil.json()) == {'nombre', 'cargo', 'oficina', 'especialidades'}
    assert perfil.json()['oficina'] == 'COMUNA'
    assert perfil.json()['especialidades'] == ['Redes']
    ajeno = await _sesion(api, 'companero-perfil-tecnico@prueba.local')
    assert (await api.get(ruta, headers=ajeno)).status_code in (403, 404)


async def test_oficina_agrupa_tipos_y_ti_identifica_sin_adivinar_equipo(db, api):
    m = await _mundo(api, 'reporte-oficina')
    _, equipos = await patrimonio(db, m)
    await db.activos.insert_one({'tipo': 'Impresora', 'nombre_equipo': 'Otra impresora', 'oficina_id': ObjectId(m['oficina']['id']), 'responsable_id': None, 'activo': True, 'campos_estado': {}})
    tipos = (await api.get('/api/portal/equipos-oficina-tipos', headers=m['usuario'])).json()['tipos']
    assert tipos == ['Impresora']
    r = await api.post('/api/tickets', headers=m['usuario'], json={'reporte_para': 'oficina', 'tipo_problema': 'Impresora', 'descripcion': 'No imprime los documentos de la oficina', 'activo_no_identificado': 'Impresora'})
    assert r.status_code == 201, r.text
    ruta = '/api/tickets/' + r.json()['ticket']['id']
    detalle = (await api.get(ruta, headers=m['admin'])).json()
    assert detalle['reporte_para'] == 'oficina'
    assert detalle['activo_id'] is None and detalle['conjunto_id'] is None
    assert detalle['activo_nombre'] == 'Impresora'
    destinos = (await api.get(ruta + '/vinculos', headers=m['admin'])).json()
    assert destinos['grupo_bloqueado'] == 'oficina'
    assert all(e['grupo'] == 'oficina' for e in destinos['equipos'])
    r = await api.patch(ruta, headers=m['admin'], json={'activo_id': str(equipos['Impresora']), 'conjunto_id': None})
    assert r.status_code == 200, r.text
    assert r.json()['activo_id'] == str(equipos['Impresora'])
    r = await api.post('/api/tickets', headers=m['usuario'], json={'reporte_para': 'oficina', 'tipo_problema': 'Otro', 'descripcion': 'Necesitamos ayuda en toda la oficina', 'activo_no_identificado': 'Servidor inventado'})
    assert r.status_code == 422


async def patrimonio(db, m):
    persona, oficina = ObjectId(m['usuario_id']), ObjectId(m['oficina']['id'])
    pc = (await db.conjuntos.insert_one({'nombre': 'PC de Maicol', 'numero': 1, 'responsable_id': persona, 'oficina_id': oficina, 'activo': True})).inserted_id
    equipos = {}
    for tipo, responsable, conjunto in [('CPU', persona, pc), ('Mouse', persona, pc), ('Impresora', None, None), ('Monitor', ObjectId(m['companero_id']), None)]:
        equipos[tipo] = (await db.activos.insert_one({'clave_natural': tipo, 'tipo': tipo, 'nombre_equipo': tipo + ' real', 'responsable_id': responsable, 'oficina_id': oficina, 'conjunto_id': conjunto, 'activo': True, 'campos_estado': {}})).inserted_id
    return pc, equipos


async def test_componente_preservado_bloquea_cambio_a_compartido_y_suma_pc(db, api):
    m = await _mundo(api, 'destino-fisico')
    pc, equipos = await patrimonio(db, m)
    r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id'], 'detectado_por_tec': True}, 'asunto': 'El mouse no funciona', 'categoria': 'Hardware', 'activo_id': str(equipos['Mouse'])})
    assert r.status_code == 201, r.text
    ruta = '/api/tickets/' + r.json()['ticket']['id']
    detalle = (await api.get(ruta, headers=m['admin'])).json()
    assert detalle['activo_id'] == str(equipos['Mouse']) and detalle['conjunto_id'] == str(pc)
    opciones = (await api.get(ruta + '/vinculos', headers=m['admin'])).json()
    assert opciones['grupo_bloqueado'] == 'propios'
    assert str(equipos['Impresora']) not in {e['id'] for e in opciones['equipos']}
    r = await api.patch(ruta, headers=m['admin'], json={'activo_id': str(equipos['Impresora']), 'conjunto_id': None})
    assert r.status_code == 422, r.text
    r = await api.patch(ruta, headers=m['admin'], json={'asunto': 'Mouse revisado', 'activo_id': str(equipos['Mouse']), 'categoria': 'Hardware'})
    assert r.status_code == 200 and r.json()['conjunto_id'] == str(pc), r.text
    assert (await api.get(f'/api/tickets?conjunto_id={pc}', headers=m['admin'])).json()['total'] == 1
    r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id']}, 'asunto': 'Monitor ajeno', 'categoria': 'Hardware', 'activo_id': str(equipos['Monitor'])})
    assert r.status_code == 422


async def test_laptop_independiente_programa_formateo_y_companero_sin_equipo(db, api):
    m = await _mundo(api, 'destino-laptop')
    pc, equipos = await patrimonio(db, m)
    for tipo in ['Laptop', 'Impresora']:
        respuesta = await api.post('/api/activos', headers=m['admin'], json={'tipo': tipo, 'oficina_id': m['oficina']['id'], 'conjunto_id': str(pc)})
        assert respuesta.status_code == 422, respuesta.text
    laptop = (await db.activos.insert_one({'tipo': 'Laptop', 'nombre_equipo': 'Laptop personal', 'responsable_id': ObjectId(m['usuario_id']), 'oficina_id': ObjectId(m['oficina']['id']), 'conjunto_id': pc, 'activo': True, 'campos_estado': {}})).inserted_id
    # Incluso una laptop agrupada por versiones anteriores se ofrece independiente.
    opciones = (await api.get(f"/api/usuarios/{m['usuario_id']}/destinos-ticket", headers=m['admin'])).json()
    assert next(e for e in opciones['equipos'] if e['id'] == str(laptop))['conjunto_id'] is None
    for categoria in ['Sistema / Programa', 'Formateo']:
        r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id']}, 'asunto': 'Office o formateo en laptop', 'categoria': categoria, 'activo_id': str(laptop), 'sistema_afectado': 'Office'})
        assert r.status_code == 201, r.text
        detalle = (await api.get('/api/tickets/' + r.json()['ticket']['id'], headers=m['admin'])).json()
        assert detalle['activo_id'] == str(laptop) and detalle['conjunto_id'] is None
    r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': 'Office no abre, ayuden a mi companero', 'persona': {'es_para_mi': False, 'afectado_id': m['companero_id']}})
    assert r.status_code == 201, r.text
    detalle = (await api.get('/api/tickets/' + r.json()['ticket']['id'], headers=m['admin'])).json()
    assert detalle['activo_id'] is None and detalle['conjunto_id'] is None



async def test_programas_automaticamente_pc_y_formateo_cpu_real(db, api):
    m = await _mundo(api, 'destino-programa')
    pc, equipos = await patrimonio(db, m)
    ajustes = (await api.get('/api/tickets/ajustes-crear', headers=m['admin'])).json()
    assert 'Formateo' in ajustes['categorias']
    for categoria in ['Sistema / Programa', 'Correo / Cuenta']:
        r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id']}, 'asunto': 'Office o correo no abre', 'categoria': categoria, 'sistema_afectado': 'Office'})
        assert r.status_code == 201, r.text
        detalle = (await api.get('/api/tickets/' + r.json()['ticket']['id'], headers=m['admin'])).json()
        assert detalle['conjunto_id'] == str(pc) and detalle['activo_id'] is None
    r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': 'Office no abre en mi computadora', 'persona': {'es_para_mi': True}})
    assert r.status_code == 201, r.text
    detalle = (await api.get('/api/tickets/' + r.json()['ticket']['id'], headers=m['admin'])).json()
    assert detalle['conjunto_id'] is None and detalle['activo_id'] is None
    r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id']}, 'asunto': 'Formatear la computadora', 'categoria': 'Formateo', 'activo_id': str(equipos['CPU'])})
    assert r.status_code == 201, r.text
    detalle = (await api.get('/api/tickets/' + r.json()['ticket']['id'], headers=m['admin'])).json()
    assert detalle['activo_id'] == str(equipos['CPU']) and detalle['conjunto_id'] == str(pc)
    r = await api.post('/api/tickets', headers=m['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': 'Solicito formatear mi computadora', 'activo_id': str(equipos['CPU']), 'persona': {'es_para_mi': True}})
    assert r.status_code == 201, r.text
    detalle = (await api.get('/api/tickets/' + r.json()['ticket']['id'], headers=m['admin'])).json()
    assert detalle['categoria'] == 'Formateo' and detalle['activo_id'] == str(equipos['CPU'])
    r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id']}, 'asunto': 'Tipo inventado', 'activo_tipo': 'Laptop', 'categoria': 'Hardware'})
    assert r.status_code == 422
    otra_pc = (await db.conjuntos.insert_one({'nombre': 'Otra PC', 'numero': 2, 'responsable_id': ObjectId(m['usuario_id']), 'oficina_id': ObjectId(m['oficina']['id']), 'activo': True})).inserted_id
    await db.activos.insert_one({'tipo': 'CPU', 'responsable_id': ObjectId(m['usuario_id']), 'oficina_id': ObjectId(m['oficina']['id']), 'conjunto_id': otra_pc, 'activo': True, 'campos_estado': {}})
    r = await api.post('/api/tickets/manual', headers=m['admin'], json={'persona': {'afectado_id': m['usuario_id']}, 'asunto': 'Office no abre', 'categoria': 'Sistema / Programa'})
    assert r.status_code == 422, r.text
