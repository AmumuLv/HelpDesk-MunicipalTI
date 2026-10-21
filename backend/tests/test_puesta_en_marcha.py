from bson import ObjectId
from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _mundo


async def test_login_separado_valida_el_rol_sin_crear_sesion_equivocada(db, api):
    await _mundo(api, 'accesos')
    for correo, correcto, incorrecto, rol in [
        ('admin-accesos@prueba.local', 'ti', 'usuario', 'administrador'),
        ('tecnico-accesos@prueba.local', 'ti', 'usuario', 'tecnico'),
        ('usuario-accesos@prueba.local', 'usuario', 'ti', 'usuario'),
    ]:
        antes = await db['sesiones'].count_documents({})
        rechazado = await api.post('/api/auth/login', json={'correo': correo, 'password': PASSWORD, 'acceso': incorrecto})
        assert rechazado.status_code == 403
        assert rechazado.json()['codigo'] == 'acceso_equivocado'
        assert await db['sesiones'].count_documents({}) == antes
        permitido = await api.post('/api/auth/login', json={'correo': correo, 'password': PASSWORD, 'acceso': correcto})
        assert permitido.status_code == 200, permitido.text
        assert permitido.json()['rol'] == rol
        assert permitido.json()['access_token']


async def test_puesta_en_marcha_cuenta_ti_horarios_validos_y_responsables_vigentes(db, api):
    mundo = await _mundo(api, 'arranque')
    await db['tecnicos_perfil'].update_many({}, {'$set': {'horario': {'dias': {}}}})
    admin = await db['usuarios'].find_one({'email': 'admin-arranque@prueba.local'})
    usuario = await db['usuarios'].find_one({'_id': ObjectId(mundo['usuario_id'])})
    activo = await db['activos'].insert_one({
        'tipo': 'CPU', 'tipo_normalizado': 'cpu', 'activo': True, 'campos_estado': {},
        'zona_id': ObjectId(mundo['zona']['id']), 'oficina_id': ObjectId(mundo['oficina']['id']),
        'responsable_nombre': usuario['nombre'], 'responsable_id': None,
    })
    horario = {'dias': {'0': {'libre': False, 'tramos': [{'entrada': '08:00', 'salida': '17:00'}]}}}
    await db['tecnicos_perfil'].insert_one({'usuario_id': ObjectId(), 'horario': horario})
    inicial = (await api.get('/api/instalacion')).json()
    assert inicial['hay_tecnicos'] is True
    assert inicial['equipo_ti_total'] == 2
    assert inicial['horarios_definidos'] == 0
    assert inicial['responsables_pendientes'] == 1
    assert all(p['ruta'] and p['accion'] for p in inicial['pasos'])
    pendientes = await api.get('/api/activos?responsables_pendientes=true', headers=mundo['admin'])
    assert pendientes.status_code == 200, pendientes.text
    assert pendientes.json()['total'] == 1
    await db['tecnicos_perfil'].update_one({'usuario_id': admin['_id']}, {'$set': {'horario': horario}})
    parcial = (await api.get('/api/instalacion')).json()
    assert parcial['horarios_definidos'] == 1
    assert parcial['horarios_completos'] is False
    await db['tecnicos_perfil'].update_one({'usuario_id': ObjectId(mundo['tecnico_id'])}, {'$set': {'horario': horario}})
    await db['activos'].update_one({'_id': activo.inserted_id}, {'$set': {'responsable_id': usuario['_id']}})
    completo = (await api.get('/api/instalacion')).json()
    assert completo['horarios_completos'] is True
    assert completo['responsables_pendientes'] == 0
    assert completo['configurado'] is True
    await db['usuarios'].update_one({'_id': usuario['_id']}, {'$set': {'activo': False}})
    assert (await api.get('/api/instalacion')).json()['responsables_pendientes'] == 1
    assert (await api.get('/api/activos?responsables_pendientes=true', headers=mundo['admin'])).json()['total'] == 1


def test_horario_libre_o_invalido_no_completa_arranque():
    from app.db.estado import _horario_util
    assert not _horario_util({'dias': {'0': {'libre': True, 'tramos': [{'entrada': '08:00', 'salida': '17:00'}]}}})
    assert not _horario_util({'dias': {'0': {'libre': False, 'tramos': []}}})
    assert not _horario_util({'dias': {'0': {'libre': False, 'tramos': [{'entrada': '17:00', 'salida': '08:00'}]}}})
    assert not _horario_util({'dias': {'0': {'libre': False, 'tramos': [{'entrada': '25:00', 'salida': '26:00'}]}}})
