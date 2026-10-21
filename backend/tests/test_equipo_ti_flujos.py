from datetime import date, datetime, timedelta, timezone

from bson import ObjectId

from app.core.time import business_tz
from app.services import horario_service
from tests.test_tickets_horarios import _mundo


async def test_identidad_compartida_y_horario_base(db, api):
    mundo = await _mundo(api, 'identidad-ti')
    identificador = mundo['tecnico_id']
    editar = await api.patch(f'/api/usuarios/{identificador}', headers=mundo['admin'], json={
        'cargo': 'Soporte municipal', 'telefono': '999123456', 'anexo': '102',
    })
    assert editar.status_code == 200, editar.text
    perfil = (await api.get(f'/api/equipo-ti/{identificador}', headers=mundo['admin'])).json()
    assert perfil['cargo'] == 'Soporte municipal'
    assert perfil['telefono'] == '999123456'
    assert perfil['anexo'] == '102'
    assert perfil['oficina_id'] == mundo['oficina']['id']
    assert perfil['tiene_foto'] is False
    for dia in range(7):
        jornada = perfil['horario']['dias'][str(dia)]
        assert jornada['libre'] == (dia >= 5)
        assert jornada['tramos'] == ([{'entrada': '08:00', 'salida': '13:00'}, {'entrada': '14:00', 'salida': '17:00'}] if dia < 5 else [])
    lista = (await api.get('/api/equipo-ti/tecnicos', headers=mundo['admin'])).json()['items']
    assert next(t for t in lista if t['id'] == identificador)['anexo'] == '102'
    panel = (await api.get('/api/equipo-ti/panel', headers=mundo['admin'])).json()['items']
    assert next(t for t in panel if t['tecnico_id'] == identificador)['telefono'] == '999123456'


async def test_limites_jornada_ausencia_y_horas_sin_doble_resta(db, api):
    mundo = await _mundo(api, 'jornada-ti')
    identificador = ObjectId(mundo['tecnico_id'])
    for hora, minuto, estado in [(8, 0, 'disponible'), (12, 59, 'disponible'), (13, 0, 'fuera_de_horario'),
                                 (14, 0, 'disponible'), (17, 0, 'fuera_de_horario')]:
        resultado = await horario_service.calcular_disponibilidad(identificador,
            momento=datetime(2026, 10, 12, hora, minuto, tzinfo=business_tz()))
        assert resultado['estado'] == estado
    assert (await horario_service.calcular_disponibilidad(identificador,
        momento=datetime(2026, 10, 17, 10, tzinfo=business_tz())))['estado'] == 'dia_libre'
    assert await horario_service.horas_laborables(identificador, date(2026, 10, 12), date(2026, 10, 18)) == 40
    ausencia = await api.post('/api/ausencias', headers=mundo['admin'], json={
        'tecnico_id': str(identificador), 'inicio': '2026-10-09', 'fin': '2026-10-13', 'tipo': 'Permiso',
    })
    assert ausencia.status_code == 201, ausencia.text
    assert (await horario_service.calcular_disponibilidad(identificador,
        momento=datetime(2026, 10, 12, 10, tzinfo=business_tz())))['estado'] == 'ausente'
    # Solo dos jornadas dentro del periodo: no se descuentan el viernes previo ni el fin de semana.
    assert await horario_service.horas_laborables(identificador, date(2026, 10, 12), date(2026, 10, 18)) == 24
    repetida = await api.post('/api/ausencias', headers=mundo['admin'], json={
        'tecnico_id': str(identificador), 'inicio': '2026-10-13', 'fin': '2026-10-14', 'tipo': 'Vacaciones',
    })
    assert repetida.status_code == 422
    # Un solapamiento histórico no puede descontar dos veces la misma jornada.
    await db['ausencias'].insert_one({'tecnico_id': identificador, 'inicio': '2026-10-12', 'fin': '2026-10-12', 'tipo': 'Permiso'})
    assert await horario_service.horas_laborables(identificador, date(2026, 10, 12), date(2026, 10, 18)) == 24


async def test_calendario_vencimientos_y_dias_no_disponibles(db, api):
    mundo = await _mundo(api, 'calendario-ti')
    identificador = ObjectId(mundo['tecnico_id'])
    await db['tickets'].insert_one({'codigo': 'TI-CAL-1', 'asunto': 'Calendario', 'origen': 'usuario', 'estado': 'en_progreso',
        'tecnico_id': identificador, 'sla_resolver_en': datetime(2026, 10, 15, 3, tzinfo=timezone.utc),
        'creado_en': datetime(2026, 10, 12, 15, tzinfo=timezone.utc)})
    ausencia = await api.post('/api/ausencias', headers=mundo['admin'], json={
        'tecnico_id': str(identificador), 'inicio': '2026-10-14', 'fin': '2026-10-14', 'tipo': 'Permiso',
    })
    assert ausencia.status_code == 201
    respuesta = await api.get('/api/equipo-ti/calendario?desde=2026-10-12&hasta=2026-10-18', headers=mundo['admin'])
    assert respuesta.status_code == 200, respuesta.text
    filas = {f['fecha']: f for f in respuesta.json()['items'] if f['tecnico_id'] == str(identificador)}
    assert len(filas) == 7
    assert filas['2026-10-12']['horas_disponibles'] == 8
    assert filas['2026-10-14']['horas_disponibles'] == 0
    assert filas['2026-10-14']['ausencia'] == 'Permiso'
    assert filas['2026-10-14']['vencimientos'] == 1  # La fecha local, no el jueves UTC.
    assert filas['2026-10-17']['libre'] is True
    assert filas['2026-10-17']['tramos'] == []
    assert all(f['carga_pendiente'] == 1 for f in filas.values())
    borrado = await api.delete(f"/api/ausencias/{ausencia.json()['id']}", headers=mundo['admin'])
    assert borrado.status_code == 200
    filas = await horario_service.calendario_equipo(date(2026, 10, 14), date(2026, 10, 14))
    assert next(f for f in filas if f['tecnico_id'] == identificador)['horas_disponibles'] == 8


async def test_validacion_de_horario_y_destinatario(db, api):
    mundo = await _mundo(api, 'validacion-ti')
    ruta = f"/api/equipo-ti/{mundo['tecnico_id']}/horario"
    respuesta = await api.put(ruta, headers=mundo['admin'], json={'dias': {'0': {'libre': False, 'tramos': [
        {'entrada': '08:00', 'salida': '14:00'}, {'entrada': '13:00', 'salida': '17:00'},
    ]}}})
    assert respuesta.status_code == 422
    invalida = await api.post('/api/ausencias', headers=mundo['admin'], json={
        'tecnico_id': mundo['usuario_id'], 'inicio': '2026-10-14', 'fin': '2026-10-14', 'tipo': 'Permiso',
    })
    assert invalida.status_code == 404
    assert (await api.get(f"/api/equipo-ti/{mundo['usuario_id']}", headers=mundo['admin'])).status_code == 404
    assert (await api.patch(f"/api/equipo-ti/{mundo['usuario_id']}/perfil", headers=mundo['usuario'], json={'capacidad_diaria': 1})).status_code == 403
    assert (await api.get('/api/equipo-ti/calendario?desde=2026-10-18&hasta=2026-10-12', headers=mundo['admin'])).status_code == 422


async def test_migracion_repara_solo_horarios_iniciales(db, api):
    mundo = await _mundo(api, 'migracion-ti')
    from app.migrations.m018_horario_base_ti import aplicar, revertir
    viejo = {'dias': {str(d): {'libre': False, 'tramos': [{'entrada': '08:00', 'salida': '13:00'}, {'entrada': '15:00', 'salida': '18:00'}]} for d in range(1, 6)}}
    await db['tecnicos_perfil'].update_one({'usuario_id': ObjectId(mundo['tecnico_id'])}, {'$set': {'horario': viejo}})
    admin = (await api.get('/api/mi-perfil', headers=mundo['admin'])).json()['id']
    personalizado = {'dias': {'0': {'libre': False, 'tramos': [{'entrada': '09:00', 'salida': '12:00'}]}}}
    await db['tecnicos_perfil'].update_one({'usuario_id': ObjectId(admin)}, {'$set': {'horario': personalizado}})
    nueva = await api.post('/api/usuarios', headers=mundo['admin'], json={
        'nombre': 'Tecnico sin perfil', 'email': 'sin-perfil@prueba.local', 'password': 'Prueba987!', 'rol': 'tecnico',
    })
    assert nueva.status_code == 201
    nuevo_id = ObjectId(nueva.json()['id'])
    await db['tecnicos_perfil'].delete_one({'usuario_id': nuevo_id})
    await aplicar(db)
    assert (await db['tecnicos_perfil'].find_one({'usuario_id': nuevo_id}))['horario']['dias']['0']['tramos'][1]['entrada'] == '14:00'
    perfil = await db['tecnicos_perfil'].find_one({'usuario_id': ObjectId(mundo['tecnico_id'])})
    assert perfil['horario']['dias']['0']['tramos'][1]['entrada'] == '14:00'
    assert perfil['horario']['dias']['5']['libre'] is True
    assert (await db['tecnicos_perfil'].find_one({'usuario_id': ObjectId(admin)}))['horario'] == personalizado
    await revertir(db)
    assert (await db['tecnicos_perfil'].find_one({'usuario_id': ObjectId(mundo['tecnico_id'])}))['horario'] == viejo
