"""Regresiones del panel analítico y del asistente con datos reales de MongoDB."""
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from app.core.time import local_date, utcnow
from app.services import analitica_chat, analitica_service, ia_provider, ml_service
from tests.test_gobernanza_y_reportes import _mundo, _sesion


async def _tickets(db, documentos):
    return await db['tickets'].insert_many([{
        'codigo': str(ObjectId()), 'asunto': 'Revision analitica', 'origen': 'tecnico', 'estado': 'nuevo', **d,
    } for d in documentos])


async def _ticket(db, documento):
    return await _tickets(db, [documento])


async def test_periodos_dias_locales_y_exclusion_de_eliminados(db, api):
    mundo = await _mundo(api, 'periodos-ia')
    dia = local_date()
    inicio = analitica_service._a_utc(dia)
    await _tickets(db, [
        {'creado_en': inicio, 'estado': 'nuevo'},
        {'creado_en': inicio + timedelta(days=1) - timedelta(microseconds=1), 'estado': 'nuevo'},
        {'creado_en': inicio - timedelta(microseconds=1), 'estado': 'nuevo'},
        {'creado_en': inicio - timedelta(days=200), 'estado': 'nuevo'},
        {'creado_en': inicio, 'estado': 'nuevo', 'eliminado': True},
    ])
    filtros = {'desde': dia, 'hasta': dia}
    kpis = await analitica_service.kpis(filtros)
    tendencia = await analitica_service.tendencia(filtros)
    assert kpis['tickets_analizados'] == 2
    assert tendencia['serie'] == [{'fecha': dia.isoformat(), 'valor': 2}]
    respuesta = await api.get('/api/analitica/panel?periodo=365d', headers=mundo['admin'])
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos['kpis']['tickets_analizados'] == 4
    assert len(datos['tendencia']['serie']) == 365
    assert sum(p['valor'] for p in datos['tendencia']['serie']) == 4
    for consulta in ('periodo=invalido', f'desde={dia}&hasta={dia - timedelta(days=1)}', f'desde={dia}'):
        assert (await api.get(f'/api/analitica/panel?{consulta}', headers=mundo['admin'])).status_code == 422


async def test_riesgo_cuenta_plazos_reales_y_soporta_tickets_sin_sla(db):
    ahora = utcnow()
    await _tickets(db, [
        {'creado_en': ahora, 'estado': 'nuevo', 'oficina_nombre': 'Soporte', 'sla_resolver_en': ahora - timedelta(hours=1)},
        {'creado_en': ahora, 'estado': 'nuevo', 'oficina_nombre': 'Soporte', 'sla_resolver_en': ahora + timedelta(days=3)},
        {'creado_en': ahora, 'estado': 'nuevo', 'oficina_nombre': 'Soporte'},
        {'creado_en': ahora, 'estado': 'nuevo', 'oficina_nombre': 'Soporte', 'eliminado': True, 'sla_resolver_en': ahora - timedelta(hours=1)},
    ])
    datos = await analitica_service.riesgo_sla({}, agrupar_por='oficina')
    assert len(datos['items']) == 1
    assert datos['items'][0]['total'] == 3
    assert datos['items'][0]['vencidos'] == 1
    assert datos['items'][0]['sin_plazo'] == 1


async def test_precision_requiere_evaluaciones_no_solo_una_categoria(db):
    ahora = utcnow()
    await _tickets(db, [{'creado_en': ahora, 'categoria': 'Red', 'estado': 'nuevo'} for _ in range(2)])
    kpis = await analitica_service.kpis({})
    assert kpis['cobertura_clasificacion'] == 100
    assert kpis['precision_clasificacion'] is None
    await db['ia_eventos'].insert_many([
        {'tipo': 'retroalimentacion', 'decision': 'correcta', 'creado_en': ahora},
        {'tipo': 'retroalimentacion', 'decision': 'incorrecta', 'creado_en': ahora},
    ])
    kpis = await analitica_service.kpis({})
    assert kpis['precision_clasificacion'] == 50
    assert kpis['retroalimentaciones_clasificacion'] == 2


async def test_asistente_sin_proveedor_conserva_conversacion_fuentes_y_periodo(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'chat-ia')
    await _ticket(db, {'creado_en': utcnow() - timedelta(days=150), 'estado': 'nuevo', 'oficina_nombre': 'Archivo', 'oficina_id': ObjectId(mundo['oficina']['id'])})
    estado = await api.get('/api/configuracion/estado-ia', headers=mundo['admin'])
    assert estado.status_code == 200
    assert estado.json()['disponible'] is False
    respuesta = await api.post('/api/ia/asistente', headers=mundo['admin'], json={
        'pregunta': analitica_chat.PREGUNTAS_SUGERIDAS[0], 'filtros': {'periodo': '365d'},
    })
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert 'Archivo' in datos['texto'] and '1 tickets' in datos['texto']
    assert datos['fuentes'] == ['ranking_oficinas']
    assert datos['enlaces'][0]['href'].startswith('/panel/oficinas/')
    siguiente = await api.post('/api/ia/asistente', headers=mundo['admin'], json={
        'pregunta': '¿Qué técnico está disponible ahora?', 'conversacion_id': datos['conversacion_id'], 'filtros': {'periodo': '365d'},
    })
    assert siguiente.status_code == 200, siguiente.text
    assert siguiente.json()['conversacion_id'] == datos['conversacion_id']
    guardada = await api.get(f"/api/ia/asistente/conversaciones/{datos['conversacion_id']}", headers=mundo['admin'])
    assert guardada.status_code == 200, guardada.text
    mensajes = guardada.json()['mensajes']
    assert len(mensajes) == 4
    assert mensajes[1]['fuentes'] == ['ranking_oficinas']
    assert mensajes[1]['periodo'] == '365d'
    assert mensajes[1]['enlaces'][0]['href'].startswith('/panel/oficinas/')
    # Un identificador ajeno no crea silenciosamente otra conversación.
    assert (await api.post('/api/ia/asistente', headers=mundo['tecnico'], json={'pregunta': 'Hola', 'conversacion_id': datos['conversacion_id']})).status_code == 403
    assert (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': '   '})).status_code == 422
    assert (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Hola', 'filtros': {'desde': 'ayer'}})).status_code == 422


async def test_sugerencias_y_permiso_de_analitica_son_coherentes(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'permiso-chat-ia')
    await api.put(f"/api/permisos/tecnicos/{mundo['tecnico_id']}", headers=mundo['admin'], json={'cambios': {'analitica.ver': True}})
    tecnico = await _sesion(api, 'tecnico-permiso-chat-ia@prueba.local')
    for pregunta in analitica_chat.PREGUNTAS_SUGERIDAS:
        from app.services.ayuda_analisis import responder_ayuda
        assert analitica_chat._detectar_intencion(pregunta)[0] is not None or responder_ayuda(pregunta), pregunta
        respuesta = await api.post('/api/ia/asistente', headers=tecnico, json={'pregunta': pregunta})
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()['fuentes'], respuesta.text
        assert respuesta.json()['texto']
    assert analitica_chat._permitida('tecnicos_rendimiento', {'rol': 'tecnico', 'permisos': {'analitica.ver': True}})


async def test_si_falla_la_redaccion_del_modelo_se_conservan_los_datos(db, monkeypatch):
    class ProveedorIntermitente(ia_provider.ProveedorIA):
        async def disponible(self):
            return True

        async def completar(self, mensajes, *, herramientas=None, **kwargs):
            if herramientas:
                return ia_provider.RespuestaIA(disponible=True, llamadas=[{'nombre': 'ranking_oficinas', 'argumentos': {}}])
            return ia_provider.RespuestaIA(disponible=False)

    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ProveedorIntermitente())
    await _ticket(db, {'creado_en': utcnow(), 'oficina_nombre': 'Archivo', 'estado': 'nuevo'})
    respuesta = await analitica_chat.responder('Oficina con más tickets', usuario={'_id': ObjectId(), 'rol': 'administrador'})
    assert 'Archivo' in respuesta['texto']
    assert respuesta['fuentes'] == ['ranking_oficinas']


async def test_familias_no_confunden_tasa_y_probabilidad(db):
    id_activo = ObjectId()
    await db['activos'].insert_many([{'_id': id_activo, 'tipo': 'Monitor', 'oficina_id': ObjectId(), 'campos_estado': {}, 'clave_natural': 'monitor1'}, {'tipo': 'Monitor', 'oficina_id': ObjectId(), 'campos_estado': {}, 'clave_natural': 'monitor2'}])
    await _tickets(db, [{'activo_id': id_activo, 'creado_en': utcnow()} for _ in range(10)] + [
        {'activo_id': id_activo, 'creado_en': utcnow(), 'eliminado': True},
    ])
    familias = await ml_service.predecir_familias()
    assert len(familias) == 1
    familia = familias[0]
    assert familia['tickets_12m'] == 10
    assert familia['tickets_por_equipo'] == 5
    assert familia['tasa_falla'] == 0.5
    assert 0 <= familia['probabilidad'] <= 1
    assert familia['metodo'] == 'regla_heuristica'
    assert 'histórico' in familia['metodo_explicacion']


async def test_causas_se_agrupan_por_problema_y_filtran_el_tipo_real(db):
    await _tickets(db, [
        {'creado_en': utcnow(), 'categoria': 'Hardware', 'tipo_problema': 'No enciende', 'activo_nombre': 'Monitor 1', 'activo_tipo': 'Monitor'},
        {'creado_en': utcnow(), 'categoria': 'Hardware', 'tipo_problema': 'No enciende', 'activo_nombre': 'Monitor 2', 'activo_tipo': 'Monitor'},
        {'creado_en': utcnow(), 'categoria': 'Hardware', 'tipo_problema': 'No enciende', 'activo_nombre': 'Laptop 1', 'activo_tipo': 'Laptop'},
    ])
    todas = await analitica_service.causas_recurrentes({})
    assert len(todas['items']) == 1
    assert todas['items'][0]['total'] == 3
    monitores = await analitica_service.causas_recurrentes({'tipo_activo': 'Monitor'})
    assert len(monitores['items']) == 1
    assert monitores['items'][0]['total'] == 2
