"""Secuencias cruzadas sobre los mismos registros y sesiones de los cuatro roles."""
import asyncio
from datetime import timedelta

import pytest
from bson import ObjectId

from app.core.time import utcnow
from app.services import usuario_service
from tests.conftest import PASSWORD
from tests.test_jerarquia_cuentas import mundo
from tests.test_tickets_horarios import _sesion


async def _post(api, ruta, datos, headers):
    respuesta = await api.post('/api' + ruta, json=datos, headers=headers)
    assert respuesta.status_code in (200, 201), respuesta.text
    return respuesta.json()


async def _entorno(api, *, equipo=False):
    ids, principal, admin, tecnico = await mundo(api)
    entorno = {
        'ids': ids, 'principal': principal, 'admin': admin, 'tecnico': tecnico,
        'persona': await _sesion(api, 'persona@prueba.local'),
        'otro_tecnico': await _sesion(api, 'otro_tecnico@prueba.local'),
    }
    if equipo:
        zona = await _post(api, '/zonas', {'nombre': 'Zona combinada'}, admin)
        oficina = await _post(api, '/oficinas', {'nombre': 'Oficina combinada', 'zona_id': zona['id']}, admin)
        respuesta = await api.patch(f"/api/usuarios/{ids['persona']}", headers=admin,
                                   json={'oficina_id': oficina['id']})
        assert respuesta.status_code == 200, respuesta.text
        entorno['oficina'] = oficina
        entorno['equipo'] = await _post(api, '/activos', {
            'tipo': 'Laptop', 'nombre_equipo': 'Laptop del trabajador original',
            'oficina_id': oficina['id'], 'responsable_id': ids['persona'],
        }, admin)
    ticket = await _post(api, '/tickets', {'descripcion': 'Incidencia combinada del trabajador original'}, entorno['persona'])
    entorno['ticket_id'] = ticket['ticket']['id']
    return entorno


async def test_revocar_y_devolver_permisos_cruza_cuentas_equipos_y_ticket_en_la_misma_sesion(db, api):
    m = await _entorno(api, equipo=True)
    ticket = m['ticket_id']
    equipo = m['equipo']['id']
    persona = m['ids']['persona']
    permisos = {'usuarios.editar': False, 'equipos.editar': False, 'tickets.eliminar': False}
    retirada = await api.put(f"/api/permisos/tecnicos/{m['ids']['tecnico']}",
                            headers=m['admin'], json={'cambios': permisos})
    assert retirada.status_code == 200, retirada.text
    antes_equipo = await db.activos.find_one({'_id': ObjectId(equipo)})
    antes_persona = await db.usuarios.find_one({'_id': ObjectId(persona)})
    intentos = await asyncio.gather(
        api.patch(f'/api/activos/{equipo}', headers=m['tecnico'], json={'observaciones': 'Cambio prohibido'}),
        api.patch(f'/api/usuarios/{persona}', headers=m['tecnico'], json={'cargo': 'Cargo prohibido'}),
        api.post(f'/api/tickets/{ticket}/eliminar', headers=m['tecnico'],
                 params={'motivo': 'Intento del técnico con permiso retirado'}),
        api.post(f'/api/tickets/{ticket}/mensajes', headers=m['persona'], json={'cuerpo': 'El trabajador sigue conversando'}),
    )
    assert [r.status_code for r in intentos] == [403, 403, 403, 201], [r.text for r in intentos]
    assert await db.activos.find_one({'_id': ObjectId(equipo)}) == antes_equipo
    assert await db.usuarios.find_one({'_id': ObjectId(persona)}) == antes_persona
    assert not (await db.tickets.find_one({'_id': ObjectId(ticket)})).get('eliminado')
    assert (await api.patch(f'/api/usuarios/{persona}', headers=m['admin'], json={'cargo': 'Administración autorizada'})).status_code == 200
    devuelta = await api.put(f"/api/permisos/tecnicos/{m['ids']['tecnico']}", headers=m['principal'],
                            json={'cambios': {p: True for p in permisos}})
    assert devuelta.status_code == 200, devuelta.text
    # Se reutiliza el token anterior: la concesión y la retirada no exigen iniciar sesión otra vez.
    permitida = await api.patch(f'/api/activos/{equipo}', headers=m['tecnico'],
                               json={'observaciones': 'Cambio del técnico nuevamente autorizado'})
    assert permitida.status_code == 200, permitida.text
    assert (await api.patch(f'/api/activos/{equipo}', headers=m['persona'],
                            json={'observaciones': 'No hereda el permiso del técnico'})).status_code == 403
    assert (await db.activos.find_one({'_id': ObjectId(equipo)}))['observaciones'] == 'Cambio del técnico nuevamente autorizado'


async def test_bajar_tecnico_a_usuario_retira_acceso_al_ticket_asignado_y_a_sus_permisos_guardados(db, api):
    m = await _entorno(api)
    ticket = m['ticket_id']
    asignado = await api.post(f'/api/tickets/{ticket}/asignar', headers=m['admin'],
                             json={'tecnico_id': m['ids']['tecnico'], 'confirmar_fuera_de_horario': True})
    assert asignado.status_code == 200, asignado.text
    assert (await api.get(f'/api/tickets/{ticket}', headers=m['tecnico'])).status_code == 200
    cambio = await api.patch(f"/api/usuarios/{m['ids']['tecnico']}", headers=m['admin'], json={'rol': 'usuario'})
    assert cambio.status_code == 200, cambio.text
    sesion = await api.get('/api/auth/sesion', headers=m['tecnico'])
    assert sesion.status_code == 200, sesion.text
    assert sesion.json()['rol'] == 'usuario'
    assert 'usuarios.editar' not in sesion.json()['permisos']
    assert (await api.get(f'/api/tickets/{ticket}', headers=m['tecnico'])).status_code == 403
    assert (await api.patch(f"/api/usuarios/{m['ids']['persona']}", headers=m['tecnico'],
                            json={'cargo': 'Permiso antiguo no válido'})).status_code == 403
    assert (await api.put(f"/api/permisos/tecnicos/{m['ids']['otro_tecnico']}", headers=m['tecnico'],
                          json={'cambios': {'usuarios.editar': True}})).status_code == 403
    propio = await _post(api, '/tickets', {'descripcion': 'Ahora reporta como trabajador'}, m['tecnico'])
    nuevo = await db.tickets.find_one({'_id': ObjectId(propio['ticket']['id'])})
    assert nuevo['reportante_id'] == ObjectId(m['ids']['tecnico'])
    assert (await api.get(f'/api/tickets/{ticket}', headers=m['persona'])).status_code == 200
    assert (await api.get(f'/api/tickets/{ticket}', headers=m['principal'])).status_code == 200


async def test_relevo_archivo_reasignacion_y_reactivacion_no_mezclan_las_identidades(db, api):
    m = await _entorno(api, equipo=True)
    anterior = ObjectId(m['ids']['persona'])
    ticket_id = ObjectId(m['ticket_id'])
    equipo_id = ObjectId(m['equipo']['id'])
    vinculacion = await api.patch(f'/api/tickets/{ticket_id}', headers=m['tecnico'],
                                 json={'categoria': 'Hardware', 'activo_id': str(equipo_id)})
    assert vinculacion.status_code == 200, vinculacion.text
    original = await db.tickets.find_one({'_id': ticket_id})
    assert original['reportante_id'] == original['afectado_id'] == anterior
    assert (await api.post(f'/api/usuarios/{anterior}/desactivar', headers=m['admin'])).status_code == 200
    assert (await api.post(f'/api/tickets/{ticket_id}/mensajes', headers=m['persona'],
                           json={'cuerpo': 'La sesión de baja debe rechazarse'})).status_code == 403
    reemplazo = await _post(api, '/usuarios', {
        'nombre': 'Trabajador de reemplazo', 'email': 'reemplazo@prueba.local', 'password': PASSWORD,
        'rol': 'usuario', 'oficina_id': m['oficina']['id'],
    }, m['admin'])
    nueva_sesion = await _sesion(api, 'reemplazo@prueba.local')
    await db.usuarios.update_one({'_id': anterior}, {'$set': {'desactivado_en': utcnow() - timedelta(days=31)}})
    assert (await usuario_service.archivar_desactivados())['archivados'] == 1
    assert (await db.activos.find_one({'_id': equipo_id}))['responsable_id'] == anterior
    conservado = await api.post(f'/api/activos/{equipo_id}/responsable', headers=m['tecnico'],
                               json={'responsable_id': str(anterior)})
    # Reenviar el responsable histórico es un no-op; asignar otro equipo nuevo a la baja sí se rechaza.
    assert conservado.status_code == 200, conservado.text
    nuevo_equipo = await api.post('/api/activos', headers=m['tecnico'], json={
        'tipo': 'Laptop', 'oficina_id': m['oficina']['id'], 'responsable_id': str(anterior),
    })
    assert nuevo_equipo.status_code == 422, nuevo_equipo.text
    reasignado = await api.post(f'/api/activos/{equipo_id}/responsable', headers=m['tecnico'],
                                json={'responsable_id': reemplazo['id'], 'motivo': 'Relevo del trabajador'})
    assert reasignado.status_code == 200, reasignado.text
    assert (await db.activos.find_one({'_id': equipo_id}))['responsable_id'] == ObjectId(reemplazo['id'])
    assert await db.tickets.find_one({'_id': ticket_id}) == original
    assert (await api.get(f'/api/tickets/{ticket_id}', headers=nueva_sesion)).status_code == 403
    propio = await _post(api, '/tickets', {'descripcion': 'Incidencia exclusiva del reemplazo'}, nueva_sesion)
    assert (await db.tickets.find_one({'_id': ObjectId(propio['ticket']['id'])}))['reportante_id'] == ObjectId(reemplazo['id'])
    regreso = await api.patch(f'/api/usuarios/{anterior}', headers=m['tecnico'], json={'activo': True})
    assert regreso.status_code == 200, regreso.text
    assert (await api.get(f'/api/tickets/{ticket_id}', headers=m['persona'])).status_code == 401
    sesion_regreso = await _sesion(api, 'persona@prueba.local')
    assert (await api.get(f'/api/tickets/{ticket_id}', headers=sesion_regreso)).status_code == 200
    assert (await api.get(f'/api/tickets/{propio["ticket"]["id"]}', headers=sesion_regreso)).status_code == 403
    cuenta = await db.usuarios.find_one({'_id': anterior})
    assert cuenta['nombre'] == 'Cuenta persona' and not cuenta['archivado']
    historia = await db.historial_responsables.find({'activo_id': equipo_id}).to_list(None)
    assert {h['responsable_id'] for h in historia} >= {anterior, ObjectId(reemplazo['id'])}


async def test_operaciones_simultaneas_de_admin_tecnico_y_usuario_conservan_mensaje_y_nota_privada(db, api):
    m = await _entorno(api)
    ticket = m['ticket_id']
    respuestas = await asyncio.gather(
        api.patch(f'/api/tickets/{ticket}', headers=m['admin'], json={'asunto': 'Asunto revisado por administración'}),
        api.post(f'/api/tickets/{ticket}/notas', headers=m['tecnico'], json={'cuerpo': 'Diagnóstico interno reservado de TI'}),
        api.post(f'/api/tickets/{ticket}/mensajes', headers=m['persona'], json={'cuerpo': 'Mensaje del trabajador conservado'}),
        api.post(f'/api/tickets/{ticket}/eliminar', headers=m['otro_tecnico'],
                 params={'motivo': 'Intento del técnico sin permiso'}),
    )
    assert [r.status_code for r in respuestas] == [200, 201, 201, 403], [r.text for r in respuestas]
    guardado = await db.tickets.find_one({'_id': ObjectId(ticket)})
    assert guardado['asunto'] == 'Asunto revisado por administración' and not guardado.get('eliminado')
    lectura_usuario = await api.get(f'/api/tickets/{ticket}', headers=m['persona'])
    assert lectura_usuario.status_code == 200
    assert 'Diagnóstico interno reservado de TI' not in lectura_usuario.text
    assert not lectura_usuario.json().get('notas_internas')
    lectura_tecnico = await api.get(f'/api/tickets/{ticket}', headers=m['tecnico'])
    assert lectura_tecnico.status_code == 200
    assert [n['cuerpo'] for n in lectura_tecnico.json()['notas_internas']] == ['Diagnóstico interno reservado de TI']
    mensajes = await api.get(f'/api/tickets/{ticket}/mensajes', headers=m['persona'])
    assert mensajes.status_code == 200
    assert 'Mensaje del trabajador conservado' in mensajes.text


async def test_intentos_cruzados_contra_principal_no_bloquean_su_edicion_legitima(db, api):
    m = await _entorno(api)
    base = f"/api/usuarios/{m['ids']['principal']}"
    antes = await db.usuarios.find_one({'_id': ObjectId(m['ids']['principal'])})
    respuestas = await asyncio.gather(
        api.patch(base, headers=m['principal'], json={'cargo': 'Titular que conserva el control'}),
        api.post(base + '/desactivar', headers=m['admin']),
        api.post(base + '/restablecer-password', headers=m['tecnico'], json={'password': 'NoDebeCambiar987!'}),
        api.patch(base, headers=m['persona'], json={'rol': 'usuario', 'email': 'no-debe-cambiar@prueba.local'}),
    )
    assert [r.status_code for r in respuestas] == [200, 403, 403, 403], [r.text for r in respuestas]
    despues = await db.usuarios.find_one({'_id': antes['_id']})
    assert despues['cargo'] == 'Titular que conserva el control'
    for campo in ('rol', 'administrador_principal', 'activo', 'password_hash', 'email', 'token_version'):
        assert despues[campo] == antes[campo]
    assert (await api.get('/api/auth/sesion', headers=m['principal'])).status_code == 200


@pytest.mark.parametrize('tipo', ['activo', 'conjunto'])
async def test_historial_cruzado_a_b_libre_c_solo_deja_abierto_el_ultimo_tramo(db, api, tipo):
    m = await _entorno(api, equipo=True)
    if tipo == 'conjunto':
        entidad = await _post(api, '/conjuntos', {
            'nombre': 'Computadora del relevo', 'oficina_id': m['oficina']['id'],
            'responsable_id': m['ids']['persona'],
        }, m['admin'])
        await _post(api, '/activos', {
            'tipo': 'CPU', 'nombre_equipo': 'CPU de la computadora del relevo',
            'oficina_id': m['oficina']['id'], 'conjunto_id': entidad['id'],
            'responsable_id': m['ids']['persona'],
        }, m['admin'])
        coleccion = db.conjuntos
        ruta = '/api/conjuntos'
        vinculo = {'alcance_incidencia': 'programa', 'sistema_afectado': 'Office',
                   'conjunto_id': entidad['id']}
    else:
        entidad = m['equipo']
        coleccion = db.activos
        ruta = '/api/activos'
        vinculo = {'categoria': 'Hardware', 'activo_id': entidad['id']}
    equipo = ObjectId(entidad['id'])
    filtro_historia = {f'{tipo}_id': equipo}
    ruta_responsable = f'{ruta}/{equipo}/responsable'
    persona_a = ObjectId(m['ids']['persona'])
    personas = []
    for nombre in ('Persona B del relevo', 'Persona C del relevo'):
        persona = await _post(api, '/usuarios', {
            'nombre': nombre, 'rol': 'usuario', 'oficina_id': m['oficina']['id'],
        }, m['principal'])
        personas.append(ObjectId(persona['id']))
    persona_b, persona_c = personas
    vinculado = await api.patch(f"/api/tickets/{m['ticket_id']}", headers=m['admin'],
                                json=vinculo)
    assert vinculado.status_code == 200, vinculado.text
    ticket_antes = await db.tickets.find_one({'_id': ObjectId(m['ticket_id'])})
    assert ticket_antes['reportante_id'] == ticket_antes['afectado_id'] == persona_a
    for destino, actor, motivo in (
        (str(persona_b), m['tecnico'], 'El técnico asigna a B'),
        (None, m['admin'], 'El administrador libera el equipo'),
        (str(persona_c), m['principal'], 'El principal asigna a C'),
    ):
        cambio = await api.post(ruta_responsable, headers=actor,
                                json={'responsable_id': destino, 'motivo': motivo})
        assert cambio.status_code == 200, cambio.text
        if destino in (str(persona_b), None):
            antes_repetir = await db.historial_responsables.find(filtro_historia).sort('_id').to_list(None)
            repetido = await api.post(ruta_responsable, headers=actor,
                                     json={'responsable_id': destino, 'motivo': motivo})
            assert repetido.status_code == 200, repetido.text
            assert await db.historial_responsables.find(filtro_historia).sort('_id').to_list(None) == antes_repetir
    historia = await db.historial_responsables.find(filtro_historia).sort([
        ('inicio', 1), ('_id', 1),
    ]).to_list(None)
    assert [tramo['responsable_id'] for tramo in historia] == [persona_a, persona_b, None, persona_c]
    assert [tramo['usuario_id'] for tramo in historia] == [
        ObjectId(m['ids']['admin']), ObjectId(m['ids']['tecnico']),
        ObjectId(m['ids']['admin']), ObjectId(m['ids']['principal']),
    ]
    assert [indice for indice, tramo in enumerate(historia) if tramo.get('fin') is None] == [3]
    for anterior, siguiente in zip(historia, historia[1:]):
        assert anterior['inicio'] <= anterior['fin'] <= siguiente['inicio']
    assert (await coleccion.find_one({'_id': equipo}))['responsable_id'] == persona_c
    assert await db.tickets.find_one({'_id': ticket_antes['_id']}) == ticket_antes
    indebido = await api.post(ruta_responsable, headers=m['persona'],
                              json={'responsable_id': str(persona_b)})
    assert indebido.status_code == 403, indebido.text
    assert await db.historial_responsables.find(filtro_historia).sort([
        ('inicio', 1), ('_id', 1),
    ]).to_list(None) == historia
