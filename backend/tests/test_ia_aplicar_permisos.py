"""Las sugerencias confirmadas respetan las mismas reglas que la edición manual."""
from bson import ObjectId
import pytest

from app.services import horario_service
from tests.test_jerarquia_cuentas import mundo
from tests.test_tickets_horarios import _sesion


async def _preparar(api, monkeypatch):
    ids, principal, admin, tecnico = await mundo(api)

    async def disponible(_):
        return {'estado': 'disponible', 'etiqueta': 'Disponible'}

    monkeypatch.setattr(horario_service, 'calcular_disponibilidad', disponible)
    persona = await _sesion(api, 'persona@prueba.local')
    alta = await api.post('/api/tickets', headers=persona,
                          json={'descripcion': 'Revisión de recomendaciones confirmadas por TI'})
    assert alta.status_code == 201, alta.text
    return {'ids': ids, 'principal': principal, 'admin': admin, 'tecnico': tecnico,
            'persona': persona, 'ticket': alta.json()['ticket']['id']}


async def _foto(db, ticket):
    identificador = ObjectId(ticket)
    return (await db.tickets.find_one({'_id': identificador}),
            await db.ticket_eventos.count_documents({'ticket_id': identificador}),
            await db.ia_eventos.count_documents({'ticket_id': identificador}),
            await db.notificaciones.count_documents({'ticket_id': identificador}))


async def _aplicar(api, m, actor, valor):
    return await api.post(f"/api/tickets/{m['ticket']}/ia", headers=m[actor], json={
        'accion': 'aplicar', 'clave': 'tecnico_sugerido_id', 'valor': valor,
    })


async def test_tecnico_sin_reasignar_no_usa_ia_para_elegir_a_otro(db, api, monkeypatch):
    m = await _preparar(api, monkeypatch)
    permiso = await api.put(f"/api/permisos/tecnicos/{m['ids']['tecnico']}", headers=m['admin'],
                            json={'cambios': {'tickets.reasignar': False}})
    assert permiso.status_code == 200, permiso.text
    antes = await _foto(db, m['ticket'])
    respuesta = await _aplicar(api, m, 'tecnico', m['ids']['otro_tecnico'])
    assert respuesta.status_code == 403, respuesta.text
    assert await _foto(db, m['ticket']) == antes
    # El mismo técnico sí puede tomar un caso libre para sí, como en la ficha normal.
    propio = await _aplicar(api, m, 'tecnico', m['ids']['tecnico'])
    assert propio.status_code == 200, propio.text
    assert (await db.tickets.find_one({'_id': ObjectId(m['ticket'])}))['tecnico_id'] == ObjectId(m['ids']['tecnico'])


async def test_ia_no_permite_tomar_un_caso_de_otro_sin_permiso(db, api, monkeypatch):
    m = await _preparar(api, monkeypatch)
    asignado = await api.post(f"/api/tickets/{m['ticket']}/asignar", headers=m['admin'],
                              json={'tecnico_id': m['ids']['otro_tecnico']})
    assert asignado.status_code == 200, asignado.text
    assert (await api.put(f"/api/permisos/tecnicos/{m['ids']['tecnico']}", headers=m['admin'],
                           json={'cambios': {'tickets.reasignar': False}})).status_code == 200
    antes = await _foto(db, m['ticket'])
    respuesta = await _aplicar(api, m, 'tecnico', m['ids']['tecnico'])
    assert respuesta.status_code == 403, respuesta.text
    assert await _foto(db, m['ticket']) == antes


@pytest.mark.parametrize('actor', ['principal', 'admin', 'tecnico'])
async def test_asignacion_ia_autorizada_emite_evento_aviso_y_primera_atencion(db, api, monkeypatch, actor):
    m = await _preparar(api, monkeypatch)
    filtro_avisos = {'ticket_id': ObjectId(m['ticket']), 'tipo': 'asignacion',
                     'usuario_id': ObjectId(m['ids']['otro_tecnico'])}
    # Crear el caso ya avisa al equipo TI. Aplicar la asignación debe añadir
    # exactamente un aviso nuevo al destino, sin confundirlo con aquel anuncio.
    avisos_antes = await db.notificaciones.count_documents(filtro_avisos)
    respuesta = await _aplicar(api, m, actor, m['ids']['otro_tecnico'])
    assert respuesta.status_code == 200, respuesta.text
    ticket = await db.tickets.find_one({'_id': ObjectId(m['ticket'])})
    assert ticket['tecnico_id'] == ObjectId(m['ids']['otro_tecnico'])
    assert ticket['estado'] == 'en_progreso' and ticket['primera_lectura_en']
    assert ticket['ia_sugerencia']['decisiones']['tecnico_sugerido_id']['elegido'] == 'Cuenta otro_tecnico'
    assert await db.ticket_eventos.count_documents({'ticket_id': ticket['_id'], 'tipo': 'asignado'}) == 1
    assert await db.notificaciones.count_documents(filtro_avisos) == avisos_antes + 1
    assert await db.notificaciones.count_documents({
        **filtro_avisos, 'titulo': f"Nuevo ticket {ticket['codigo']}",
    }) == 1


@pytest.mark.parametrize('destino,codigo', [('persona', 422), ('inactivo', 404)])
async def test_ia_rechaza_destinos_no_tecnicos_o_inactivos(db, api, monkeypatch, destino, codigo):
    m = await _preparar(api, monkeypatch)
    destino_id = m['ids']['persona']
    if destino == 'inactivo':
        destino_id = m['ids']['otro_tecnico']
        desactivar = await api.post(f'/api/usuarios/{destino_id}/desactivar', headers=m['admin'])
        assert desactivar.status_code == 200, desactivar.text
    antes = await _foto(db, m['ticket'])
    respuesta = await _aplicar(api, m, 'admin', destino_id)
    assert respuesta.status_code == codigo, respuesta.text
    assert await _foto(db, m['ticket']) == antes


async def test_nombre_en_vez_de_id_no_se_da_por_aplicado(db, api, monkeypatch):
    m = await _preparar(api, monkeypatch)
    antes = await _foto(db, m['ticket'])
    respuesta = await _aplicar(api, m, 'admin', 'Cuenta otro_tecnico')
    assert respuesta.status_code == 422, respuesta.text
    assert await _foto(db, m['ticket']) == antes


async def test_fuera_de_horario_requiere_confirmacion_normal_y_no_marca_aplicado(db, api, monkeypatch):
    m = await _preparar(api, monkeypatch)

    async def ausente(_):
        return {'estado': 'ausente', 'etiqueta': 'Ausente'}

    monkeypatch.setattr(horario_service, 'calcular_disponibilidad', ausente)
    antes = await _foto(db, m['ticket'])
    respuesta = await _aplicar(api, m, 'admin', m['ids']['otro_tecnico'])
    assert respuesta.status_code == 422, respuesta.text
    assert 'Asignar a' in respuesta.json()['mensaje']
    assert await _foto(db, m['ticket']) == antes
    confirmada = await api.post(f"/api/tickets/{m['ticket']}/asignar", headers=m['admin'],
                                json={'tecnico_id': m['ids']['otro_tecnico'], 'confirmar_fuera_de_horario': True})
    assert confirmada.status_code == 200, confirmada.text
    assert confirmada.json()['tecnico_id'] == m['ids']['otro_tecnico']


async def test_usuario_y_ticket_eliminado_no_reciben_via_alternativa(db, api, monkeypatch):
    m = await _preparar(api, monkeypatch)
    antes = await _foto(db, m['ticket'])
    denegado = await _aplicar(api, m, 'persona', m['ids']['otro_tecnico'])
    assert denegado.status_code == 403, denegado.text
    assert await _foto(db, m['ticket']) == antes
    eliminado = await api.post(f"/api/tickets/{m['ticket']}/eliminar", headers=m['admin'])
    assert eliminado.status_code == 200, eliminado.text
    antes = await _foto(db, m['ticket'])
    respuesta = await _aplicar(api, m, 'admin', m['ids']['otro_tecnico'])
    assert respuesta.status_code == 404, respuesta.text
    assert await _foto(db, m['ticket']) == antes


async def test_paquete_mixto_no_escribe_categoria_antes_de_rechazar_asignacion(db, api, monkeypatch):
    m = await _preparar(api, monkeypatch)
    antes = await _foto(db, m['ticket'])
    respuesta = await api.post(f"/api/tickets/{m['ticket']}/ia", headers=m['tecnico'], json={
        'accion': 'aplicar', 'clave': 'tecnico_sugerido_id', 'valor': m['ids']['otro_tecnico'],
        'categoria': 'Hardware', 'prioridad': 'alta',
    })
    assert respuesta.status_code == 422, respuesta.text
    assert await _foto(db, m['ticket']) == antes
