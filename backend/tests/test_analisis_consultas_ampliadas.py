"""Consultas reales, contexto y permisos del centro analítico, en base aislada."""
from datetime import timedelta
from bson import ObjectId

from app.core.time import local_date, utcnow
from app.services import analitica_chat, analitica_service, ia_provider
from tests.test_gobernanza_y_reportes import _mundo
from tests.test_analisis_flujos import _tickets


async def test_resumen_continua_periodo_guarda_explicacion_y_no_modifica_negocio(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'analisis-ampliado')
    hoy = analitica_service._a_utc(local_date())
    documentos = [{'codigo': f'ampliado-{i}', 'asunto': 'Caso ficticio', 'creado_en': hoy + timedelta(minutes=i),
                   'estado': estado, 'oficina_id': ObjectId(mundo['oficina']['id']) if i < 2 else None, 'sla_resolver_en': utcnow() - timedelta(hours=1)}
                  for i, estado in enumerate(['nuevo', 'cerrado', 'cerrado'])]
    documentos += [{'codigo': 'ampliado-ayer', 'estado': 'en_espera', 'creado_en': hoy - timedelta(hours=1), 'oficina_id': ObjectId(mundo['oficina']['id'])},
                   {'codigo': 'ampliado-eliminado', 'estado': 'nuevo', 'creado_en': hoy, 'eliminado': True}]
    await _tickets(db, documentos)
    antes = await db['tickets'].find({}).sort('_id').to_list(None)
    async def preguntar(texto, conversacion_id=None):
        respuesta = await api.post('/api/ia/asistente', headers=mundo['admin'], json={
            'pregunta': texto, 'conversacion_id': conversacion_id, 'filtros': {'periodo': '30d'},
        })
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()
    primero = await preguntar('¿Puedes darme un resumen del servicio hoy?')
    assert '3 tickets' in primero['texto']
    assert primero['fuentes'] == ['metricas_generales']
    assert primero['analisis']['limite']
    assert primero['seguimientos']
    segundo = await preguntar('¿Y ayer?', primero['conversacion_id'])
    assert '1 tickets' in segundo['texto']
    assert segundo['fuentes'] == ['metricas_generales']
    guardada = await api.get('/api/ia/asistente/conversaciones/' + primero['conversacion_id'], headers=mundo['admin'])
    assert guardada.json()['mensajes'][-1]['analisis'] == segundo['analisis']
    assert guardada.json()['mensajes'][-1]['contexto_consulta']['herramienta'] == 'metricas_generales'
    explicada = await preguntar('Explícame eso', primero['conversacion_id'])
    assert explicada['fuentes'] == ['guia_analisis']
    estados = await preguntar('¿Cuántos tickets están abiertos y cerrados hoy?')
    filas = estados['tabla']['filas']
    assert sum(f['total'] for f in filas) == 3
    assert next(f['total'] for f in filas if f['estado'] == 'Cerrados') == 2
    assert all(f['estado'] != 'Resueltos' for f in filas)
    vencidos = await preguntar('¿Qué tickets tienen el plazo vencido hoy?')
    assert sum(f['vencidos'] for f in vencidos['tabla']['filas']) == 1
    evolucion = await preguntar('¿Cómo evolucionan los tickets por día hoy?')
    assert sum(f['valor'] for f in evolucion['tabla']['filas']) == 3
    oficina = await preguntar('Resumen del servicio hoy en la oficina COMUNA')
    assert '2 tickets' in oficina['texto']
    assert oficina['alcance_consulta'] == 'Oficina: COMUNA'
    continuada = await preguntar('¿Y ayer?', oficina['conversacion_id'])
    assert '1 tickets' in continuada['texto']
    assert continuada['alcance_consulta'] == 'Oficina: COMUNA'
    desconocida = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Resumen del servicio en la oficina que no existe'})
    assert desconocida.status_code == 422
    assert await db['tickets'].find({}).sort('_id').to_list(None) == antes


async def test_inventario_cuenta_dispositivos_y_mantiene_limites_de_roles(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'inventario-analisis')
    await db['activos'].insert_many([
        {'tipo': 'CPU', 'activo': True, 'responsable_id': None, 'oficina_id': ObjectId(mundo['oficina']['id']), 'campos_estado': {}, 'clave_natural': 'analisis-cpu'},
        {'tipo': 'Laptop', 'activo': True, 'responsable_id': None, 'oficina_id': ObjectId(mundo['oficina']['id']), 'campos_estado': {}, 'clave_natural': 'analisis-laptop'},
        {'tipo': 'Monitor', 'activo': False, 'oficina_id': ObjectId(mundo['oficina']['id']), 'campos_estado': {}, 'clave_natural': 'analisis-monitor'},
    ])
    respuesta = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': '¿Cuántos equipos tenemos registrados?'})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert sum(f['total'] for f in datos['tabla']['filas']) == 2
    assert 'equipos compartidos' in datos['texto']
    assert datos['fuentes'] == ['resumen_inventario']
    for headers in [mundo['tecnico']]:
        negada = await api.post('/api/ia/asistente', headers=headers, json={'pregunta': '¿Puedes darme un resumen del servicio?'})
        assert negada.status_code == 403


async def test_satisfaccion_sin_muestra_no_es_cero_y_plazos_separan_sin_fecha(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'muestra-analisis')
    await _tickets(db, [{'codigo': 'sin-muestra', 'creado_en': utcnow(), 'estado': 'nuevo'}])
    respuesta = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': '¿Cuál es la satisfacción del servicio?'})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['tabla']['filas'][0]['valor'] is None
    assert 'no significa' in respuesta.json()['texto']
    plazos = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': '¿Qué tickets tienen el plazo vencido?'})
    assert sum(f['sin_plazo'] for f in plazos.json()['tabla']['filas']) == 1
    assert sum(f['vencidos'] for f in plazos.json()['tabla']['filas']) == 0
