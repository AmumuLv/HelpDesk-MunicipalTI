"""Historial, ramas, propiedad y concurrencia del asistente interno."""
import asyncio
from datetime import timedelta
from uuid import uuid4

from bson import ObjectId

from app.core.errors import Validacion
from app.core.time import local_date
from app.services import analitica_chat, analitica_service, ia_provider
from tests.test_analisis_flujos import _tickets
from tests.test_gobernanza_y_reportes import _mundo, _sesion


async def test_renombrar_regenerar_y_editar_conservan_un_turno_y_sus_fuentes(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'ramas-analisis')
    hoy = analitica_service._a_utc(local_date())
    await _tickets(db, [{'creado_en': hoy, 'estado': 'nuevo'}, {'creado_en': hoy - timedelta(hours=1), 'estado': 'cerrado'}])
    registros = await db.tickets.find({}).sort('_id').to_list(None)
    creada = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Resumen del servicio hoy'})
    assert creada.status_code == 200, creada.text
    datos = creada.json()
    assert len(datos['mensajes']) == 2 and datos['version'] == 1
    ruta = '/api/ia/asistente/conversaciones/' + datos['conversacion_id']
    renombrada = await api.patch(ruta, headers=mundo['admin'], json={'titulo': '  Mi revisión  ', 'version': 1})
    assert renombrada.status_code == 200, renombrada.text
    assert renombrada.json()['titulo'] == 'Mi revisión'
    regenerada = await api.post(ruta + '/regenerar', headers=mundo['admin'], json={'version': 2})
    assert regenerada.status_code == 200, regenerada.text
    assert regenerada.json()['version'] == 3
    assert len(regenerada.json()['mensajes']) == 2
    siguiente = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': '¿Y ayer?', 'conversacion_id': datos['conversacion_id'], 'version': 3})
    assert siguiente.status_code == 200, siguiente.text
    assert len(siguiente.json()['mensajes']) == 4
    editada = await api.post(ruta + '/editar', headers=mundo['admin'], json={'indice': 0, 'pregunta': 'Cuántos tickets están abiertos hoy', 'version': 4})
    assert editada.status_code == 200, editada.text
    assert editada.json()['version'] == 5
    assert len(editada.json()['mensajes']) == 2
    assert editada.json()['fuentes'] == ['estados_tickets']
    guardada = (await api.get(ruta, headers=mundo['admin'])).json()
    assert guardada['titulo'] == 'Mi revisión' and guardada['version'] == 5
    assert guardada['mensajes'][-1]['fuentes'] == ['estados_tickets']
    assert await db.tickets.find({}).sort('_id').to_list(None) == registros


async def test_fallos_y_versiones_obsoletas_no_borran_historial_ni_crean_chats_vacios(db, api, monkeypatch):
    mundo = await _mundo(api, 'errores-analisis')
    async def valida(*args, **kwargs):
        return {'texto': 'Lectura ficticia.', 'fuentes': ['guia_analisis']}
    monkeypatch.setattr(analitica_chat, 'responder', valida)
    creada = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Hola'})).json()
    ruta = '/api/ia/asistente/conversaciones/' + creada['conversacion_id']
    antes = await db.conversaciones_ia.find_one({'_id': ObjectId(creada['conversacion_id'])})
    for accion, carga in [('/regenerar', {'version': 0}), ('/editar', {'version': 1, 'indice': 1, 'pregunta': 'Otra pregunta'})]:
        rechazo = await api.post(ruta + accion, headers=mundo['admin'], json=carga)
        assert rechazo.status_code == (409 if accion == '/regenerar' else 422)
    assert (await api.patch(ruta, headers=mundo['admin'], json={'titulo': '   '})).status_code == 422
    async def falla(*args, **kwargs):
        raise Validacion('No se pudo identificar la ubicación.')
    monkeypatch.setattr(analitica_chat, 'responder', falla)
    for url, carga in [('/api/ia/asistente', {'pregunta': 'Resumen oficina desconocida'}), (ruta + '/editar', {'indice': 0, 'pregunta': 'Resumen desconocido', 'version': 1})]:
        assert (await api.post(url, headers=mundo['admin'], json=carga)).status_code == 422
    assert await db.conversaciones_ia.count_documents({}) == 1
    assert await db.conversaciones_ia.find_one({'_id': antes['_id']}) == antes


async def test_mutaciones_del_chat_exigen_propiedad_permiso_y_csrf(db, api, monkeypatch):
    mundo = await _mundo(api, 'propiedad-analisis')
    async def valida(*args, **kwargs):
        return {'texto': 'Lectura ficticia.', 'fuentes': ['guia_analisis']}
    monkeypatch.setattr(analitica_chat, 'responder', valida)
    creada = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Hola'})).json()
    ruta = '/api/ia/asistente/conversaciones/' + creada['conversacion_id']
    await api.put('/api/permisos/tecnicos/' + mundo['tecnico_id'], headers=mundo['admin'], json={'cambios': {'analitica.ver': True}})
    tecnico = await _sesion(api, 'tecnico-propiedad-analisis@prueba.local')
    for metodo, url, carga in [('patch', ruta, {'titulo': 'Ajena'}), ('post', ruta + '/regenerar', {}), ('post', ruta + '/editar', {'indice': 0, 'pregunta': 'Ajena'})]:
        respuesta = await getattr(api, metodo)(url, headers=tecnico, json=carga)
        assert respuesta.status_code == 403, respuesta.text
    sin_csrf = {k: v for k, v in mundo['admin'].items() if k != 'X-CSRF-Token'}
    assert (await api.patch(ruta, headers=sin_csrf, json={'titulo': 'Sin CSRF'})).status_code == 403
    assert await db.conversaciones_ia.count_documents({}) == 1


async def test_dos_pestanas_no_intercalan_preguntas_ni_pierden_turnos(db, api, monkeypatch):
    mundo = await _mundo(api, 'concurrencia-analisis')
    async def simple(pregunta, **kwargs):
        return {'texto': 'Respuesta a ' + pregunta, 'fuentes': ['guia_analisis']}
    monkeypatch.setattr(analitica_chat, 'responder', simple)
    creada = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Primera'})).json()
    llegada = asyncio.Event()
    entradas = 0
    async def pausada(pregunta, **kwargs):
        nonlocal entradas
        entradas += 1
        if entradas == 2:
            llegada.set()
        await asyncio.wait_for(llegada.wait(), timeout=10)
        return await simple(pregunta)
    monkeypatch.setattr(analitica_chat, 'responder', pausada)
    resultados = await asyncio.gather(*[api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': pregunta, 'conversacion_id': creada['conversacion_id'], 'version': 1}) for pregunta in ('Pestaña uno', 'Pestaña dos')])
    assert sorted(r.status_code for r in resultados) == [200, 409]
    guardada = await db.conversaciones_ia.find_one({'_id': ObjectId(creada['conversacion_id'])})
    assert guardada['version'] == 2 and len(guardada['mensajes']) == 4
    assert guardada['mensajes'][-1]['texto'] == 'Respuesta a ' + guardada['mensajes'][-2]['texto']


async def test_explicaciones_y_seguimiento_conservan_fechas_y_oficina(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'contexto-natural')
    hoy = analitica_service._a_utc(local_date())
    await _tickets(db, [{'creado_en': hoy, 'estado': 'nuevo', 'sla_resolver_en': hoy - timedelta(hours=1), 'oficina_id': ObjectId(mundo['oficina']['id'])}, {'creado_en': hoy - timedelta(days=1), 'estado': 'cerrado', 'oficina_id': ObjectId(mundo['oficina']['id'])}])
    async def pregunta(texto, id=None):
        r = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': texto, 'conversacion_id': id})
        assert r.status_code == 200, r.text
        return r.json()
    inicio = await pregunta('Resumen del servicio hoy en la oficina COMUNA')
    explicada = await pregunta('Explícame eso', inicio['conversacion_id'])
    assert explicada['contexto_consulta']['herramienta'] == 'metricas_generales'
    ayer = await pregunta('¿Y ayer?', inicio['conversacion_id'])
    assert ayer['fuentes'] == ['metricas_generales'] and '1 tickets' in ayer['texto']
    regenerada = await api.post('/api/ia/asistente/conversaciones/' + inicio['conversacion_id'] + '/regenerar',
        headers=mundo['admin'], json={'version': ayer['version']})
    assert regenerada.status_code == 200, regenerada.text
    assert regenerada.json()['texto'] == ayer['texto']
    assert regenerada.json()['tabla'] == ayer['tabla']
    assert regenerada.json()['alcance_consulta'] == ayer['alcance_consulta']
    assert len(regenerada.json()['mensajes']) == len(ayer['mensajes'])
    cerrados = await pregunta('¿Y los cerrados?', inicio['conversacion_id'])
    assert cerrados['fuentes'] == ['estados_tickets']
    assert cerrados['tabla']['filas'] == [{'estado': 'Cerrados', 'total': 1}]
    assert cerrados['alcance_consulta'] == 'Oficina: COMUNA'
    vencidos = await pregunta('¿Y cuáles están vencidos?', inicio['conversacion_id'])
    assert vencidos['fuentes'] == ['plazos_atencion']
    assert '0 tickets' in vencidos['texto']
    assert vencidos['alcance_consulta'] == 'Oficina: COMUNA'


async def test_historial_muestra_hasta_cien_propias_e_indica_si_hay_mas(db, api, monkeypatch):
    mundo = await _mundo(api, 'historial-cien')
    async def simple(*args, **kwargs):
        return {'texto': 'Lectura ficticia.', 'fuentes': ['guia_analisis']}
    monkeypatch.setattr(analitica_chat, 'responder', simple)
    creada = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Primera'})).json()
    documento = await db.conversaciones_ia.find_one({'_id': ObjectId(creada['conversacion_id'])})
    copia = {k: v for k, v in documento.items() if k != '_id'}
    await db.conversaciones_ia.insert_many([{**copia, 'titulo': f'Conversación {i}'} for i in range(100)] + [{**copia, 'usuario_id': ObjectId(), 'titulo': 'Ajena'}])
    historial = (await api.get('/api/ia/asistente/conversaciones', headers=mundo['admin'])).json()
    assert len(historial['items']) == 100 and historial['hay_mas'] is True
    assert all(c['titulo'] != 'Ajena' for c in historial['items'])
    await db.conversaciones_ia.delete_many({'usuario_id': documento['usuario_id'], 'titulo': {'$in': ['Conversación 0', 'Conversación 1']}})
    historial = (await api.get('/api/ia/asistente/conversaciones', headers=mundo['admin'])).json()
    assert len(historial['items']) == 99 and historial['hay_mas'] is False


async def test_reintento_del_primer_turno_recupera_respuesta_sin_recalcular_y_aisla_propietario(db, api, monkeypatch):
    mundo = await _mundo(api, 'reintento-analisis')
    consultas = 0
    async def simple(*args, **kwargs):
        nonlocal consultas
        consultas += 1
        return {'texto': f'Lectura ficticia {consultas}.', 'fuentes': ['guia_analisis']}
    monkeypatch.setattr(analitica_chat, 'responder', simple)
    solicitud = {'pregunta': 'Resumen inicial', 'filtros': {'periodo': '7d'}, 'solicitud_id': str(uuid4())}
    primera = await api.post('/api/ia/asistente', headers=mundo['admin'], json=solicitud)
    assert primera.status_code == 200, primera.text
    # Simula que la respuesta HTTP se perdió, pero el servidor ya la guardó.
    repetida = await api.post('/api/ia/asistente', headers=mundo['admin'], json=solicitud)
    assert repetida.status_code == 200, repetida.text
    assert repetida.json() == primera.json()
    assert consultas == 1 and await db.conversaciones_ia.count_documents({}) == 1
    alterada = await api.post('/api/ia/asistente', headers=mundo['admin'], json={**solicitud, 'pregunta': 'Una pregunta distinta'})
    assert alterada.status_code == 409 and consultas == 1
    invalida = await api.post('/api/ia/asistente', headers=mundo['admin'], json={**solicitud, 'solicitud_id': 'no-es-uuid'})
    assert invalida.status_code == 422
    ambigua = await api.post('/api/ia/asistente', headers=mundo['admin'], json={**solicitud, 'conversacion_id': primera.json()['conversacion_id']})
    assert ambigua.status_code == 422
    await api.put('/api/permisos/tecnicos/' + mundo['tecnico_id'], headers=mundo['admin'], json={'cambios': {'analitica.ver': True}})
    tecnico = await _sesion(api, 'tecnico-reintento-analisis@prueba.local')
    ajena = await api.post('/api/ia/asistente', headers=tecnico, json=solicitud)
    assert ajena.status_code == 200, ajena.text
    assert ajena.json()['conversacion_id'] != primera.json()['conversacion_id']
    assert consultas == 2 and await db.conversaciones_ia.count_documents({}) == 2
    listado = (await api.get('/api/ia/asistente/conversaciones', headers=mundo['admin'])).json()['items']
    assert len(listado) == 1
    assert set(listado[0]) <= {'id', 'titulo', 'usuario_id', 'usuario_nombre', 'rol', 'creado_en', 'actualizado_en', 'version'}
    assert {'mensajes', 'respuesta_inicial', 'firma_inicial', 'solicitud_inicial'}.isdisjoint(listado[0])


async def test_primer_turno_simultaneo_con_mismo_uuid_solo_crea_una_conversacion(db, api, monkeypatch):
    mundo = await _mundo(api, 'nonce-simultaneo')
    llegada = asyncio.Event()
    entradas = 0
    async def pausada(pregunta, **kwargs):
        nonlocal entradas
        entradas += 1
        numero = entradas
        if entradas == 2:
            llegada.set()
        await asyncio.wait_for(llegada.wait(), timeout=10)
        return {'texto': f'Resultado confirmado {numero}.', 'fuentes': ['guia_analisis']}
    monkeypatch.setattr(analitica_chat, 'responder', pausada)
    solicitud = {'pregunta': 'Primera pregunta', 'solicitud_id': str(uuid4())}
    respuestas = await asyncio.gather(*[api.post('/api/ia/asistente', headers=mundo['admin'], json=solicitud) for _ in range(2)])
    assert [r.status_code for r in respuestas] == [200, 200]
    assert respuestas[0].json() == respuestas[1].json()
    assert await db.conversaciones_ia.count_documents({}) == 1
    documento = await db.conversaciones_ia.find_one({})
    assert len(documento['mensajes']) == 2 and documento['version'] == 1
    repetida = await api.post('/api/ia/asistente', headers=mundo['admin'], json=solicitud)
    assert repetida.json() == respuestas[0].json() and entradas == 2
