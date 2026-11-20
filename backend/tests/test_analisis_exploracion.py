"""Desgloses verificables, paginados y sin escrituras operativas."""
from datetime import timedelta
import pytest
from bson import ObjectId
from app.core.time import utcnow, local_date
from tests.test_tickets_horarios import _mundo, _sesion
from tests.test_analisis_flujos import _tickets


async def dispositivos(db, mundo, cantidad=47):
    filas = []
    for i in range(cantidad):
        e = {'_id': ObjectId(), 'clave_natural': f'explorar-{i}', 'nombre_equipo': f'Impresora municipal {i:03}',
             'tipo': 'Impresora' if i % 2 else 'Laptop', 'oficina_id': ObjectId(mundo['oficina']['id']), 'oficina_nombre': 'Oficina de prueba',
             'activo': True, 'campos_estado': {}, 'observaciones': 'SECRETO_QUE_NO_DEBE_APARECER'}
        if i < 15: e['responsable_id'] = ObjectId(mundo['usuario_id'])
        elif i < 19: e['responsable_nombre'] = 'Persona pendiente'
        elif i < 27: e['uso_comun'] = True
        if i < 2: e['campos_estado']['codigo_patrimonial'] = {'estado': ['no_aplica', 'no_disponible'][i]}
        filas.append(e)
    await db.activos.insert_many(filas)
    return filas


async def leer(api, mundo, herramienta, **opciones):
    r = await api.post('/api/ia/asistente/explorar', headers=mundo['admin'], json={'herramienta': herramienta, **opciones})
    assert r.status_code == 200, r.text
    assert 'SECRETO_QUE_NO_DEBE_APARECER' not in r.text
    return r.json()


async def test_totales_responsables_y_tres_paginas_corresponden_a_registros_reales(db, api):
    m = await _mundo(api, 'exploracion-totales')
    await dispositivos(db, m)
    colecciones = ('activos', 'usuarios', 'conjuntos', 'historial_responsables', 'auditoria', 'conversaciones_ia')
    antes = {c: await db[c].find({}).sort('_id', 1).to_list(None) for c in colecciones}
    resumen = await leer(api, m, 'resumen_inventario')
    assert sum(f['total'] for f in resumen['tabla']['filas']) == 47
    i = resumen['indicadores']
    assert (i['vinculado'], i['pendiente'], i['compartido'], i['confirmar']) == (15, 4, 8, 20)
    assert i['sin_cuenta_activa'] == 32
    assert i['sin_responsable_registrado'] == 28
    assert sum(f['compartidos'] for f in resumen['tabla']['filas']) == 8
    laptops = await leer(api, m, 'resumen_inventario', filtros={'tipo_activo': 'Laptop'})
    assert laptops['indicadores']['dispositivos'] == 24
    assert sum(f['total'] for f in laptops['tabla']['filas']) == 24
    assert laptops['indicadores']['compartido'] == 4
    ids = []
    for pagina, cantidad in [(1, 20), (2, 20), (3, 7)]:
        datos = await leer(api, m, 'resumen_inventario', vista='detalle', pagina=pagina)
        assert datos['total'] == 47 and len(datos['tabla']['filas']) == cantidad
        ids.extend(f['id'] for f in datos['tabla']['filas'])
    assert len(set(ids)) == 47
    compartidos = await leer(api, m, 'responsables_inventario', grupo='compartido')
    assert compartidos['total'] == 8
    assert all(f['grupo'] == 'compartido' for f in compartidos['tabla']['filas'])
    for c in colecciones:
        assert await db[c].find({}).sort('_id', 1).to_list(None) == antes[c], c
    inexistente = await api.post('/api/ia/asistente/explorar', headers=m['admin'], json={'herramienta': 'resumen_inventario', 'vista': 'detalle', 'pagina': 4})
    assert inexistente.status_code == 422


async def test_codigo_pendiente_excluye_no_aplica_y_no_disponible_y_muestra_responsable(db, api):
    m = await _mundo(api, 'exploracion-codigo')
    await dispositivos(db, m)
    ids = set()
    for numero, cantidad in [(1, 20), (2, 20), (3, 5)]:
        datos = await leer(api, m, 'equipos_datos_pendientes', argumentos={'campo': 'codigo_patrimonial'}, pagina=numero)
        assert datos['total'] == 45
        assert len(datos['tabla']['filas']) == cantidad
        for fila in datos['tabla']['filas']:
            assert fila['codigo'] == 'Código patrimonial pendiente'
            assert fila['responsable'] and fila['oficina']
            ids.add(fila['id'])
    assert len(ids) == 45
    filtro = await leer(api, m, 'equipos_datos_pendientes', texto='municipal 046', argumentos={'campo': 'codigo_patrimonial'})
    assert filtro['total'] == 1 and filtro['tabla']['filas'][0]['nombre'].endswith('046')


async def test_veintiuna_oficinas_numeradores_y_seleccion_consistente(db, api):
    m = await _mundo(api, 'exploracion-oficinas')
    oficinas = [ObjectId() for _ in range(21)]
    await db.activos.insert_many([{'nombre_equipo': f'Dispositivo {i}', 'clave_natural': f'ofi-{i}', 'tipo': 'Mouse', 'oficina_id': oid,
        'oficina_nombre': f'Oficina extensa municipal {i:02}', 'activo': True, 'campos_estado': {}} for i, oid in enumerate(oficinas)])
    p1 = await leer(api, m, 'oficinas_datos_pendientes')
    p2 = await leer(api, m, 'oficinas_datos_pendientes', pagina=2, orden='porcentaje')
    assert p1['total'] == p2['total'] == 21
    assert p1['tabla']['indicadores'] == p1['indicadores']
    assert len(p1['tabla']['filas']) == 20 and len(p2['tabla']['filas']) == 1
    for f in p1['tabla']['filas']:
        assert f['completos'] + f['incompletos'] == f['total']
        assert f['numerador_completos'] + f['faltantes'] == f['esperados']
        assert f['porcentaje_completo'] == round(100 * f['numerador_completos'] / f['esperados'], 1)
    detalle = await leer(api, m, 'oficinas_datos_pendientes', vista='detalle', oficina_id=str(oficinas[0]))
    assert detalle['total'] == 1
    assert detalle['tabla']['filas'][0]['oficina_id'] == str(oficinas[0])


async def test_auditoria_47_movimientos_paginas_y_retencion_sin_payload_privado(db, api):
    m = await _mundo(api, 'exploracion-auditoria')
    # Aislar los eventos de la preparación del mundo de esta cuenta ficticia.
    await db.auditoria.delete_many({})
    ahora = utcnow()
    await db.auditoria.insert_many([{'fecha': ahora - timedelta(minutes=i), 'rol': 'administrador', 'accion': 'activo.editar',
        'usuario_nombre': 'Administrador de prueba', 'entidad': 'activo', 'resumen': 'PAYLOAD_PRIVADO', 'antes': {'password': 'CLAVE_PRIVADA'}} for i in range(47)]
        + [{'fecha': ahora - timedelta(days=30), 'rol': 'administrador', 'accion': 'activo.editar', 'usuario_nombre': 'Evento fuera de retención'}])
    ids = set()
    for numero, cantidad in [(1, 20), (2, 20), (3, 7)]:
        datos = await leer(api, m, 'auditoria_cambios', pagina=numero, filtros={'periodo': '90d'})
        assert datos['total'] == 47 and len(datos['tabla']['filas']) == cantidad
        assert datos['cobertura'] != datos['solicitado']
        assert 'PAYLOAD_PRIVADO' not in str(datos) and 'CLAVE_PRIVADA' not in str(datos)
        ids.update(f['id'] for f in datos['tabla']['filas'])
    assert len(ids) == 47
    antiguo = (local_date() - timedelta(days=40)).isoformat()
    vacio = await leer(api, m, 'auditoria_cambios', filtros={'desde': antiguo, 'hasta': antiguo})
    assert vacio['total'] == 0 and not vacio['tabla']['filas']
    assert 'Fuera de la retención' in vacio['cobertura']
    assert await db.auditoria.count_documents({}) == 48


async def test_busqueda_parcial_seleccion_historial_persistente_y_error_sin_inventar(db, api):
    m = await _mundo(api, 'exploracion-historial')
    equipos = await dispositivos(db, m, 3)
    fecha = utcnow() - timedelta(days=100)
    await db.historial_responsables.insert_many([{'activo_id': equipos[0]['_id'], 'inicio': fecha + timedelta(days=i), 'fecha': fecha + timedelta(days=i),
        'responsable_nombre': f'Persona {i}', 'usuario_nombre': 'TI de prueba', 'motivo': 'Relevo registrado'} for i in range(24)])
    candidatos = await leer(api, m, 'auditoria_responsables', texto='municipal')
    assert candidatos['total'] == 3
    pcs = [ObjectId() for _ in range(24)]
    await db.conjuntos.insert_many([{'_id': oid, 'nombre': f'PC municipal {i}', 'numero': i + 1, 'activo': True} for i, oid in enumerate(pcs)])
    primera = await leer(api, m, 'auditoria_responsables', texto='municipal')
    siguiente = await leer(api, m, 'auditoria_responsables', texto='municipal', pagina=2)
    assert primera['total'] == siguiente['total'] == 27
    assert len(primera['tabla']['filas']) == 20 and len(siguiente['tabla']['filas']) == 7
    assert len({f['id'] for r in (primera, siguiente) for f in r['tabla']['filas']}) == 27
    historial = await leer(api, m, 'auditoria_responsables', equipo_id=str(equipos[0]['_id']))
    assert historial['total'] == 24 and len(historial['tabla']['filas']) == 20
    assert historial['tabla']['filas'][0]['nuevo'] == 'Persona 23'
    assert historial['tabla']['filas'][0]['anterior'] == 'Persona 22'
    segundo = await leer(api, m, 'auditoria_responsables', equipo_id=str(equipos[0]['_id']), pagina=2)
    assert len(segundo['tabla']['filas']) == 4
    error = await api.post('/api/ia/asistente/explorar', headers=m['admin'], json={'herramienta': 'auditoria_responsables', 'equipo_id': str(ObjectId())})
    assert error.status_code == 422
    assert await db.historial_responsables.count_documents({}) == 24


@pytest.mark.parametrize('opciones', [{'pagina': 0}, {'pagina': 501}, {'oficina_id': {'$ne': None}}, {'herramienta': 'borrar'}, {'argumentos': {'campo': {'$ne': None}}}, {'operador': '$where'}])
async def test_operadores_y_paginas_invalidos_no_pasan_al_motor(db, api, opciones):
    m = await _mundo(api, 'exploracion-validacion')
    r = await api.post('/api/ia/asistente/explorar', headers=m['admin'], json={'herramienta': 'equipos_datos_pendientes', **opciones})
    assert r.status_code == 422, r.text


async def test_permisos_vigentes_y_programacion_fecha_lima(db, api):
    m = await _mundo(api, 'exploracion-permisos')
    datos = {'herramienta': 'resumen_inventario'}
    assert (await api.post('/api/ia/asistente/explorar', headers=m['usuario'], json=datos)).status_code == 403
    await api.put('/api/permisos/tecnicos/' + m['tecnico_id'], headers=m['admin'], json={'cambios': {'analitica.ver': True}})
    tecnico = await _sesion(api, 'tecnico-exploracion-permisos@prueba.local')
    assert (await api.post('/api/ia/asistente/explorar', headers=tecnico, json=datos)).status_code == 200
    assert (await api.post('/api/ia/asistente/explorar', headers=tecnico, json={'herramienta': 'auditoria_cambios'})).status_code == 403
    fecha = (local_date() + timedelta(days=3)).isoformat()
    programacion = await leer(api, m, 'horarios_manana', fecha=fecha)
    assert programacion['tabla']['fecha_consulta'] == fecha
    assert all('oficina' in f and 'disponibilidad' in f for f in programacion['tabla']['filas'])
    natural = await api.post('/api/ia/asistente', headers=m['admin'], json={'pregunta': f'Qué técnicos tienen horario el {fecha}'})
    assert natural.status_code == 200, natural.text
    assert natural.json()['fuentes'] == ['horarios_manana']
    assert natural.json()['tabla']['fecha_consulta'] == fecha


async def test_guias_y_pendientes_tienen_segunda_pagina_sin_incrementar_lecturas(db, api):
    m = await _mundo(api, 'exploracion-paginas-extra')
    await db.articulos_kb.insert_many([{'titulo': f'Guia {i:03}', 'categoria': 'Hardware', 'activo': True,
        'visibilidad': 'todos', 'visualizaciones': i, 'actualizado_en': utcnow()} for i in range(23)])
    antes = await db.articulos_kb.find({}).sort('_id', 1).to_list(None)
    primera = await leer(api, m, 'guias_consultadas')
    segunda = await leer(api, m, 'guias_consultadas', pagina=2)
    assert primera['total'] == segunda['total'] == 23
    assert len(primera['tabla']['filas']) == 20 and len(segunda['tabla']['filas']) == 3
    assert not {f['guia'] for f in primera['tabla']['filas']} & {f['guia'] for f in segunda['tabla']['filas']}
    assert await db.articulos_kb.find({}).sort('_id', 1).to_list(None) == antes


async def test_metricas_tecnicos_paginas_estado_vencidos_y_detalle_de_pendientes(db, api):
    m = await _mundo(api, 'exploracion-metricas')
    tid = ObjectId(m['tecnico_id'])
    ahora = utcnow()
    await _tickets(db, [
        {'codigo': 'EXP-PENDIENTE', 'tecnico_id': tid, 'estado': 'en_progreso', 'creado_en': ahora, 'sla_resolver_en': ahora - timedelta(hours=2)},
        {'codigo': 'EXP-CERRADO', 'tecnico_id': tid, 'estado': 'cerrado', 'creado_en': ahora, 'tiempo_resolucion_min': 45, 'satisfaccion': 4},
        {'codigo': 'EXP-ANTIGUO', 'tecnico_id': tid, 'estado': 'en_progreso', 'creado_en': ahora - timedelta(days=100)},
    ])
    datos = await leer(api, m, 'resumen_equipo_ti', filtros={'tecnico_id': str(tid)})
    fila = datos['tabla']['filas'][0]
    assert fila['asignados_periodo'] == 2 and fila['cerrados'] == 1
    assert fila['pendientes_actuales'] == 2 and fila['vencidos_actuales'] == 1
    assert fila['tiempo_medio_min'] == 45 and fila['satisfaccion'] == 4
    assert fila['estado_cuenta'] == 'Activo'
    detalle = await leer(api, m, 'resumen_equipo_ti', filtros={'tecnico_id': str(tid)}, vista='detalle')
    assert detalle['total'] == 2
    assert {f['codigo'] for f in detalle['tabla']['filas']} == {'EXP-PENDIENTE', 'EXP-ANTIGUO'}
    await db.usuarios.insert_many([{'nombre': f'Identidad técnica {i:03}', 'nombre_busqueda': f'IDENTIDAD TECNICA {i:03}', 'rol': 'tecnico', 'activo': True} for i in range(21)])
    primera = await leer(api, m, 'resumen_equipo_ti')
    segunda = await leer(api, m, 'resumen_equipo_ti', pagina=2)
    assert primera['total'] == segunda['total']
    assert len(primera['tabla']['filas']) == 20 and len(segunda['tabla']['filas']) == primera['total'] - 20
    assert not {f['id'] for f in primera['tabla']['filas']} & {f['id'] for f in segunda['tabla']['filas']}
    await db.usuarios.update_one({'_id': tid}, {'$set': {'activo': False, 'archivado': True}})
    archivada = await leer(api, m, 'resumen_equipo_ti', filtros={'tecnico_id': str(tid)})
    assert archivada['tabla']['filas'][0]['estado_cuenta'] == 'Archivado'
