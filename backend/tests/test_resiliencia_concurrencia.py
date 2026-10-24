"""Carreras reales sobre MongoDB, accesos cruzados y operaciones simultáneas."""
import asyncio
from uuid import uuid4

from bson import ObjectId
from tests.test_cierre_y_reapertura import _mundo


async def nuevo(api, mundo, texto='Prueba de concurrencia'):
    r = await api.post('/api/tickets', headers=mundo['persona'], json={'descripcion': texto})
    assert r.status_code == 201, r.text
    return r.json()['ticket']['id']


async def test_creaciones_paralelas_tienen_codigos_unicos(db, api):
    m = await _mundo(api, 'paralelo')
    respuestas = await asyncio.gather(*(api.post('/api/tickets', headers=m['persona'], json={'descripcion': f'Incidencia simultanea {i}'}) for i in range(20)))
    assert all(r.status_code == 201 for r in respuestas), [r.status_code for r in respuestas]
    assert len({r.json()['ticket']['codigo'] for r in respuestas}) == 20
    assert await db.tickets.count_documents({}) == 20


async def test_dos_tecnicos_no_pueden_adjudicarse_el_mismo_ticket(db, api, monkeypatch):
    from app.services import horario_service
    m = await _mundo(api, 'adjudicar')
    ticket = await nuevo(api, m)
    personas = [await db.usuarios.find_one({'email': f'{t}-adjudicar@prueba.local'}) for t in ('tec1', 'tec2')]
    barrera = asyncio.Barrier(2)

    async def disponibles(*args, **kwargs):
        await asyncio.wait_for(barrera.wait(), 10)
        return {'estado': 'disponible', 'etiqueta': 'Disponible'}

    monkeypatch.setattr(horario_service, 'calcular_disponibilidad', disponibles)
    respuestas = await asyncio.gather(*(api.post(f'/api/tickets/{ticket}/asignar', headers=m[t], json={'tecnico_id': str(p['_id']), 'confirmar_fuera_de_horario': True}) for t, p in zip(('tec1', 'tec2'), personas)))
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    ganador = await db.tickets.find_one({'_id': ObjectId(ticket)})
    assert ganador['tecnico_id'] in {p['_id'] for p in personas}
    assert await db.ticket_eventos.count_documents({'ticket_id': ObjectId(ticket), 'tipo': 'asignado'}) == 1


async def test_ediciones_de_campos_distintos_no_se_pierden(db, api):
    m = await _mundo(api, 'editar-paralelo')
    ticket = await nuevo(api, m)
    respuestas = await asyncio.gather(api.patch(f'/api/tickets/{ticket}', headers=m['admin'], json={'asunto': 'Asunto conservado'}), api.patch(f'/api/tickets/{ticket}', headers=m['admin'], json={'descripcion': 'Descripcion conservada simultaneamente'}))
    assert all(r.status_code == 200 for r in respuestas)
    guardado = await db.tickets.find_one({'_id': ObjectId(ticket)})
    assert guardado['asunto'] == 'Asunto conservado'
    assert guardado['descripcion'] == 'Descripcion conservada simultaneamente'


async def test_mensajes_paralelos_se_conservan_completos(db, api):
    m = await _mundo(api, 'mensajes-paralelo')
    ticket = await nuevo(api, m)
    respuestas = await asyncio.gather(*(api.post(f'/api/tickets/{ticket}/mensajes', headers=m['persona'], json={'cuerpo': f'Mensaje simultaneo {i}'}) for i in range(15)))
    assert all(r.status_code == 201 for r in respuestas)
    assert await db.ticket_mensajes.count_documents({'ticket_id': ObjectId(ticket)}) == 15


async def test_reintentar_envio_y_concurrencia_no_duplican_ticket(db, api):
    m = await _mundo(api, 'idempotencia')
    headers = {**m['persona'], 'Idempotency-Key': str(uuid4())}
    cuerpo = {'descripcion': 'Se perdio la respuesta pero el ticket fue guardado'}
    respuestas = await asyncio.gather(*(api.post('/api/tickets', headers=headers, json=cuerpo) for _ in range(6)))
    assert all(r.status_code == 201 for r in respuestas), [(r.status_code, r.text[:80]) for r in respuestas]
    assert len({r.json()['ticket']['id'] for r in respuestas}) == 1
    assert await db.tickets.count_documents({}) == 1
    assert (await api.post('/api/tickets', headers=headers, json={'descripcion': 'Contenido diferente con la misma clave'})).status_code == 409
    assert (await api.post('/api/tickets', headers={**m['persona'], 'Idempotency-Key': 'invalido'}, json=cuerpo)).status_code == 422


async def test_una_edicion_antigua_no_sobrescribe_cambios_recientes(db, api):
    m = await _mundo(api, 'version')
    ticket = await nuevo(api, m)
    version = (await api.get(f'/api/tickets/{ticket}', headers=m['admin'])).json()['actualizado_en']
    primero = await api.patch(f'/api/tickets/{ticket}', headers=m['admin'], json={'asunto': 'Cambio del primer tecnico', 'version_esperada': version})
    assert primero.status_code == 200, primero.text
    segundo = await api.patch(f'/api/tickets/{ticket}', headers=m['admin'], json={'asunto': 'Cambio sobre datos obsoletos', 'version_esperada': version})
    assert segundo.status_code == 409, segundo.text
    assert (await db.tickets.find_one({'_id': ObjectId(ticket)}))['asunto'] == 'Cambio del primer tecnico'


async def test_usuario_ajeno_no_lee_ticket_ni_notas_ni_modifica_estado(db, api):
    m = await _mundo(api, 'acceso-cruzado')
    ticket = await nuevo(api, m)
    # Otra persona independiente; el rol usuario no hereda permisos del área TI.
    from app.services import usuario_service
    from tests.conftest import PASSWORD
    await usuario_service.crear({'nombre': 'Ajeno', 'email': 'ajeno@prueba.local', 'password': PASSWORD, 'rol': 'usuario'}, usuario={'nombre': 'Instalador', 'rol': 'sistema'})
    login = (await api.post('/api/auth/login', json={'correo': 'ajeno@prueba.local', 'password': PASSWORD})).json()
    headers = {'Authorization': f"Bearer {login['access_token']}", 'X-CSRF-Token': login['csrf_token']}
    for url in (f'/api/tickets/{ticket}', f'/api/tickets/{ticket}/mensajes'):
        assert (await api.get(url, headers=headers)).status_code == 403
    assert (await api.patch(f'/api/tickets/{ticket}', headers=headers, json={'asunto': 'Intento no autorizado'})).status_code == 403
    assert (await api.post(f'/api/tickets/{ticket}/estado', headers=headers, json={'estado': 'cerrado', 'nota_resolucion': 'Intento no autorizado'})).status_code == 403
    assert (await api.post(f'/api/tickets/{ticket}/notas', headers=headers, json={'cuerpo': 'Nota indebida'})).status_code == 403
    assert (await db.tickets.find_one({'_id': ObjectId(ticket)}))['estado'] == 'nuevo'


async def test_reintento_manual_conserva_ticket_y_no_repite_historial(db, api):
    from tests.conftest import equipo_para_persona
    m = await _mundo(api, 'manual-reintento')
    equipo = await equipo_para_persona(api, m['admin'], m['persona_id'])
    cuerpo = {'persona': {'afectado_id': m['persona_id']}, 'activo_id': equipo, 'asunto': 'Alta manual con respuesta perdida', 'prioridad': 'alta'}
    headers = {**m['admin'], 'Idempotency-Key': str(uuid4())}
    primero = await api.post('/api/tickets/manual', headers=headers, json=cuerpo)
    assert primero.status_code == 201, primero.text
    eventos = await db.ticket_eventos.count_documents({})
    repetido = await api.post('/api/tickets/manual', headers=headers, json=cuerpo)
    assert repetido.status_code == 201, repetido.text
    assert repetido.json()['ticket']['id'] == primero.json()['ticket']['id']
    assert await db.tickets.count_documents({}) == 1
    assert await db.ticket_eventos.count_documents({}) == eventos


def test_limites_de_dia_local_entre_anios_y_anio_bisiesto():
    from datetime import date, datetime, timezone
    from app.core.time import local_date, month_bounds
    from app.services.horario_service import inicio_utc, fin_utc
    assert inicio_utc(date(2026, 12, 31)) == datetime(2026, 12, 31, 5, tzinfo=timezone.utc)
    assert fin_utc(date(2026, 12, 31)) == datetime(2027, 1, 1, 4, 59, 59, 999999, tzinfo=timezone.utc)
    assert local_date(datetime(2027, 1, 1, 4, 59, tzinfo=timezone.utc)) == date(2026, 12, 31)
    assert local_date(datetime(2027, 1, 1, 5, tzinfo=timezone.utc)) == date(2027, 1, 1)
    assert month_bounds(date(2028, 2, 10)) == (date(2028, 2, 1), date(2028, 2, 29))


async def test_csrf_logout_y_desactivacion_invalidan_acceso(db, api):
    m = await _mundo(api, 'sesion-vigente')
    sin_csrf = {'Authorization': m['persona']['Authorization']}
    assert (await api.post('/api/tickets', headers=sin_csrf, json={'descripcion': 'No debe registrarse sin CSRF'})).status_code == 403
    assert await db.tickets.count_documents({}) == 0
    assert (await api.post('/api/auth/logout', headers=m['persona'])).status_code == 200
    assert (await api.get('/api/tickets', headers=m['persona'])).status_code == 401
    tecnico = await db.usuarios.find_one({'email': 'tec2-sesion-vigente@prueba.local'})
    desactivar = await api.post(f"/api/usuarios/{tecnico['_id']}/desactivar", headers=m['admin'])
    assert desactivar.status_code == 200, desactivar.text
    assert (await api.get('/api/tickets', headers=m['tec2'])).status_code == 403


async def test_dos_cierres_simultaneos_generan_un_solo_evento(db, api, monkeypatch):
    from app.services import sla_service
    m = await _mundo(api, 'cerrar-paralelo')
    ticket = await nuevo(api, m)
    barrera = asyncio.Barrier(2)
    original = sla_service.minutos_laborables_entre
    llamadas = 0

    async def medir(*args, **kwargs):
        nonlocal llamadas
        llamadas += 1
        if llamadas <= 2:
            await asyncio.wait_for(barrera.wait(), 10)
        return await original(*args, **kwargs)

    monkeypatch.setattr(sla_service, 'minutos_laborables_entre', medir)
    respuestas = await asyncio.gather(*(api.post(f'/api/tickets/{ticket}/estado', headers=m['admin'], json={'estado': 'cerrado', 'nota_resolucion': f'Solucion simultanea {i}'}) for i in range(2)))
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    assert await db.ticket_eventos.count_documents({'ticket_id': ObjectId(ticket), 'tipo': 'estado'}) == 1
    assert (await db.tickets.find_one({'_id': ObjectId(ticket)}))['estado'] == 'cerrado'
