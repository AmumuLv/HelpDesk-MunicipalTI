"""Recorridos reales del catálogo nuevo por API, con MongoDB ficticio."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId

from app.core.time import local_date
from app.services import analisis_catalogo, analitica_service, ia_provider
from tests.test_analisis_flujos import _tickets
from tests.test_gobernanza_y_reportes import _mundo, _sesion


async def test_todas_las_preguntas_nuevas_llegan_a_datos_o_piden_precision_sin_modificar_registros(db, api, monkeypatch):
    mundo = await _mundo(api, 'catalogo-completo-ia')
    proveedor = MagicMock()
    proveedor.disponible = AsyncMock(side_effect=AssertionError('Las consultas reconocidas no consumen proveedor'))
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: proveedor)
    await _tickets(db, [{'creado_en': analitica_service._a_utc(local_date()), 'oficina_id': ObjectId(mundo['oficina']['id']), 'categoria': 'Impresora'}])
    colecciones = ('tickets', 'activos', 'conjuntos', 'articulos_kb', 'inventario_versiones', 'tecnicos_perfil')
    antes = {c: await db[c].find({}).sort('_id', 1).to_list(None) for c in colecciones}
    catalogo = await api.get('/api/ia/asistente/preguntas', headers=mundo['admin'])
    assert catalogo.status_code == 200
    for pregunta, nombre, grupo in analisis_catalogo.preguntas():
        assert catalogo.json()['grupos'][pregunta] == grupo
        respuesta = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': pregunta})
        assert respuesta.status_code == 200, (pregunta, respuesta.text)
        contenido = respuesta.json()
        assert contenido['texto'].strip()
        assert 'Necesito una pregunta más concreta' not in contenido['texto']
        if nombre == 'auditoria_responsables':
            assert 'nombre exacto' in contenido['texto']
        else:
            assert contenido['fuentes'] == [nombre], (pregunta, contenido)
        guardada = await api.get('/api/ia/asistente/conversaciones/' + contenido['conversacion_id'], headers=mundo['admin'])
        assert guardada.status_code == 200
        assert guardada.json()['mensajes'][-1]['texto'] == contenido['texto']
    for c in colecciones:
        assert await db[c].find({}).sort('_id', 1).to_list(None) == antes[c], c
    proveedor.disponible.assert_not_awaited()


async def test_catalogo_filtra_permisos_y_servidor_rechaza_consultas_reservadas(db, api):
    mundo = await _mundo(api, 'catalogo-permisos-ia')
    await api.put('/api/permisos/tecnicos/' + mundo['tecnico_id'], headers=mundo['admin'], json={'cambios': {'analitica.ver': True}})
    tecnico = await _sesion(api, 'tecnico-catalogo-permisos-ia@prueba.local')
    respuesta = await api.get('/api/ia/asistente/preguntas', headers=tecnico)
    assert respuesta.status_code == 200
    preguntas = respuesta.json()['preguntas']
    assert 'Muéstrame los tickets sin asignar' in preguntas
    assert '¿Qué cambios se registraron en el periodo?' not in preguntas
    assert 'Compara dos inventarios anuales' not in preguntas
    for pregunta in ('¿Qué cambios se registraron en el periodo?', 'Compara los inventarios de 2025 y 2026'):
        denegada = await api.post('/api/ia/asistente', headers=tecnico, json={'pregunta': pregunta})
        assert denegada.status_code == 403, denegada.text
    assert await db['conversaciones_ia'].count_documents({'usuario_id': ObjectId(mundo['tecnico_id'])}) == 0


async def test_listados_y_auditoria_conservan_contexto_pero_respetan_la_nueva_fecha(db, api, monkeypatch):
    mundo = await _mundo(api, 'catalogo-contexto-ia')
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    inicio = analitica_service._a_utc(local_date())
    await _tickets(db, [{'codigo': 'PENDIENTE-HOY', 'creado_en': inicio, 'tecnico_id': None},
                       {'codigo': 'PENDIENTE-AYER', 'creado_en': inicio - timedelta(hours=1), 'tecnico_id': None}])
    primero = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': 'Muéstrame los tickets sin asignar hoy'})).json()
    assert primero['fuentes'] == ['tickets_pendientes_detalle']
    assert [f['codigo'] for f in primero['tabla']['filas']] == ['PENDIENTE-HOY']
    segundo = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={
        'pregunta': '¿Y ayer?', 'conversacion_id': primero['conversacion_id'], 'version': primero['version'],
    })).json()
    assert segundo['fuentes'] == ['tickets_pendientes_detalle']
    assert [f['codigo'] for f in segundo['tabla']['filas']] == ['PENDIENTE-AYER']
    assert segundo['contexto_consulta']['argumentos']['modo'] == 'sin_asignar'
    tercero = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={
        'pregunta': '¿Y sin equipo?', 'conversacion_id': segundo['conversacion_id'], 'version': segundo['version'],
    })).json()
    assert tercero['fuentes'] == ['tickets_pendientes_detalle']
    assert tercero['contexto_consulta']['argumentos']['modo'] == 'sin_equipo'
    auditoria = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': '¿Qué cambios se registraron esta semana?'})).json()
    ayer = (await api.post('/api/ia/asistente', headers=mundo['admin'], json={
        'pregunta': '¿Y ayer?', 'conversacion_id': auditoria['conversacion_id'], 'version': auditoria['version'],
    })).json()
    assert ayer['fuentes'] == ['auditoria_cambios']
    assert ayer['filtros_consulta']['desde'] == ayer['filtros_consulta']['hasta'] == (local_date() - timedelta(days=1)).isoformat()
