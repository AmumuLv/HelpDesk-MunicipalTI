from datetime import datetime, timezone

from bson import ObjectId

from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _mundo, _sesion


async def test_cambiar_correo_y_restablecer_password(db, api):
    mundo = await _mundo(api, 'correo-password')
    usuario_id = mundo['usuario_id']
    original = 'usuario-correo-password@prueba.local'
    nuevo = 'correo.nuevo@prueba.local'
    cambio = await api.patch(f'/api/usuarios/{usuario_id}', headers=mundo['admin'], json={'email': nuevo.upper()})
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()['email'] == nuevo
    assert (await api.post('/api/auth/login', json={'correo': original, 'password': PASSWORD})).status_code == 401
    nueva_sesion = await _sesion(api, nuevo)
    duplicado = await api.patch(f'/api/usuarios/{usuario_id}', headers=mundo['admin'], json={'email': 'tecnico-correo-password@prueba.local'})
    assert duplicado.status_code == 409, duplicado.text
    assert (await api.get(f'/api/usuarios/{usuario_id}', headers=mundo['admin'])).json()['email'] == nuevo
    restablecer = await api.post(f'/api/usuarios/{usuario_id}/restablecer-password', headers=mundo['admin'], json={'password': 'NuevaClave987!'})
    assert restablecer.status_code == 200, restablecer.text
    assert 'password' not in restablecer.json()
    assert (await api.get('/api/mi-perfil', headers=nueva_sesion)).status_code == 401
    assert (await api.post('/api/auth/login', json={'correo': nuevo, 'password': PASSWORD})).status_code == 401
    await _sesion(api, nuevo, 'NuevaClave987!')
    assert not (await db['usuarios'].find_one({'_id': ObjectId(usuario_id)}))['password_hash'].startswith('NuevaClave')


async def test_historial_pagina_todos_los_tickets_asignados_sin_duplicados(db, api):
    mundo = await _mundo(api, 'historial-paginado')
    tecnico = (await api.get('/api/mi-perfil', headers=mundo['tecnico'])).json()['id']
    creado_equipo = await api.post('/api/activos', headers=mundo['admin'], json={
        'tipo': 'CPU', 'nombre_equipo': 'PC de soporte', 'codigo_patrimonial': 'PAT-001',
        'oficina_id': mundo['oficina']['id'],
    })
    assert creado_equipo.status_code == 201, creado_equipo.text
    equipo_id = ObjectId(creado_equipo.json()['id'])
    for numero in range(23):
        await db['tickets'].insert_one({
            'codigo': f'TEST-{numero:03}', 'asunto': f'Caso {numero}',
            'estado': 'cerrado', 'origen': 'usuario', 'prioridad': 'media', 'creado_en': datetime.now(timezone.utc),
            'tecnico_id': ObjectId(tecnico),
            'reportante_id': ObjectId(tecnico) if numero == 0 else ObjectId(mundo['usuario_id']),
            'afectado_id': ObjectId(mundo['usuario_id']),
            'activo_id': equipo_id if numero == 22 else None,
            'activo_nombre': 'Nombre histórico' if numero == 21 else None,
            'activo_tipo': 'Monitor' if numero == 21 else None,
        })
    ids = []
    for pagina, cantidad in [(1, 10), (2, 10), (3, 3)]:
        respuesta = await api.get(f'/api/usuarios/{tecnico}/tickets?pagina={pagina}', headers=mundo['admin'])
        assert respuesta.status_code == 200, respuesta.text
        datos = respuesta.json()
        assert datos['total'] == 23
        assert datos['total_paginas'] == 3
        assert len(datos['items']) == cantidad
        if pagina == 1:
            equipo = next(ticket for ticket in datos['items'] if ticket.get('activo_id'))
            assert equipo['activo_nombre'] == 'PC de soporte'
            assert equipo['activo_tipo'] == 'CPU'
            assert equipo['activo_codigo_patrimonial'] == 'PAT-001'
            historico = next(ticket for ticket in datos['items'] if ticket['activo_nombre'] == 'Nombre histórico')
            assert historico['activo_tipo'] == 'Monitor'
        ids.extend(ticket['id'] for ticket in datos['items'])
    assert len(set(ids)) == 23
    creados = (await api.get(f'/api/usuarios/{tecnico}/tickets?relacion=creados', headers=mundo['admin'])).json()
    assert creados['total'] == 1
    assert (await api.get(f'/api/usuarios/{tecnico}/tickets', headers=mundo['usuario'])).status_code == 403
    fuera = (await api.get(f'/api/usuarios/{tecnico}/tickets?pagina=99', headers=mundo['admin'])).json()
    assert fuera['pagina'] == 3


async def test_buscar_correo_es_literal_y_horario_nuevo_lunes_a_viernes(db, api):
    mundo = await _mundo(api, 'busqueda-literal')
    resultado = await api.get('/api/usuarios', params={'texto': '.*'}, headers=mundo['admin'])
    assert resultado.status_code == 200
    assert resultado.json()['total'] == 0
    tecnico = (await api.get('/api/mi-perfil', headers=mundo['tecnico'])).json()['id']
    perfil = await db['tecnicos_perfil'].find_one({'usuario_id': ObjectId(tecnico)})
    assert set(perfil['horario']['dias']) == {'0', '1', '2', '3', '4', '5', '6'}
    assert perfil['horario']['dias']['5'] == {'libre': True, 'tramos': []}
    assert perfil['horario']['dias']['0']['tramos'][1] == {'entrada': '14:00', 'salida': '17:00'}


async def test_tecnico_delegado_no_toma_control_de_un_administrador(db, api):
    mundo = await _mundo(api, 'proteccion-admin')
    tecnico = (await api.get('/api/mi-perfil', headers=mundo['tecnico'])).json()['id']
    admin = (await api.get('/api/mi-perfil', headers=mundo['admin'])).json()['id']
    permiso = await api.patch(f'/api/usuarios/{tecnico}', headers=mundo['admin'], json={'permisos': {'usuarios.editar': True}})
    assert permiso.status_code == 200, permiso.text
    normal = await api.patch(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo['tecnico'], json={'cargo': 'Contacto actualizado'})
    assert normal.status_code == 200, normal.text
    for ruta, metodo, cuerpo in [
        (f'/api/usuarios/{admin}', 'PATCH', {'email': 'otro.admin@prueba.local'}),
        (f'/api/usuarios/{admin}/restablecer-password', 'POST', {'password': 'TomarControl987!'}),
        ('/api/usuarios', 'POST', {'nombre': 'Cuenta delegada', 'email': 'delegada@prueba.local', 'password': PASSWORD,
                                  'rol': 'tecnico', 'permisos': {'usuarios.editar': True}}),
    ]:
        respuesta = await api.request(metodo, ruta, headers=mundo['tecnico'], json=cuerpo)
        assert respuesta.status_code == 403, respuesta.text
    vacio = await api.patch(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo['admin'], json={'nombre': '   '})
    assert vacio.status_code == 422
