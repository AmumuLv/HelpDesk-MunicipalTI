"""Biblioteca y configuración: contratos reales usados por la interfaz."""
from tests.test_gobernanza_y_reportes import _mundo


async def test_paginas_de_cuatro_articulos_sin_huecos_por_duplicados(db, api):
    mundo = await _mundo(api, 'paginas-kb')
    cabeceras = mundo['admin']
    for indice in [0, 0, 0, 1, 2, 3, 4, 5, 6, 7]:
        respuesta = await api.post('/api/kb/articulos', headers=cabeceras, json={'titulo': f'Paginacion tutorial {indice}', 'categoria': 'Tutoriales', 'resumen': 'Resumen para probar las paginas.', 'cuerpo': 'Contenido de una guia de prueba.'})
        assert respuesta.status_code == 201, respuesta.text
    identidades = set()
    for pagina in [1, 2]:
        respuesta = await api.get('/api/kb/articulos', headers=cabeceras, params={'texto': 'Paginacion', 'pagina': pagina, 'por_pagina': 4})
        assert respuesta.status_code == 200, respuesta.text
        datos = respuesta.json()
        assert len(datos['items']) == 4
        assert datos['total'] == 8 and datos['total_paginas'] == 2
        identidades.update(a['id'] for a in datos['items'])
    assert len(identidades) == 8


async def test_auditoria_evitar_guardados_sin_cambios_y_exportaciones_comunes(db, api):
    from app.core.audit import registrar
    from bson import ObjectId
    mundo = await _mundo(api, 'audit-clara')
    cabeceras = mundo['admin']
    datos = {'titulo': 'Articulo para auditoria', 'categoria': 'Tutoriales', 'resumen': 'Resumen del articulo de prueba.', 'cuerpo': 'Contenido del articulo de prueba.'}
    articulo = (await api.post('/api/kb/articulos', headers=cabeceras, json=datos)).json()
    antes = await db['auditoria'].count_documents({'accion': 'kb.editar'})
    assert (await api.patch(f"/api/kb/articulos/{articulo['id']}", headers=cabeceras, json=datos)).status_code == 200
    assert await db['auditoria'].count_documents({'accion': 'kb.editar'}) == antes
    await registrar('exportacion.pdf', resumen='Descarga corriente')
    await registrar('exportacion.pdf', resumen='Error que debe conservarse', resultado='error', rol='administrador')
    listado = (await api.get('/api/auditoria', headers=cabeceras)).json()['items']
    assert not any(e.get('resumen') == 'Descarga corriente' for e in listado)
    assert any(e.get('resumen') == 'Error que debe conservarse' for e in listado)
    await db['usuarios'].update_one({'_id': ObjectId(mundo['tecnico_id'])}, {'$set': {'permisos': {'reportes.ver': True}}})
    assert (await api.get('/api/auditoria', headers=mundo['tecnico'])).status_code == 403


async def test_avisos_en_pagina_respetan_destinatarios_sin_necesitar_correo(db, api):
    from bson import ObjectId
    from app.services import config_service, notificaciones_service
    mundo = await _mundo(api, 'avisos-pagina')
    persona = ObjectId(mundo['tecnico_id'])
    ticket = {'_id': ObjectId(), 'afectado_id': persona, 'reportante_id': persona}
    await config_service.actualizar({'notificaciones': {'email_activo': False, 'avisar_al_afectado': True, 'avisar_al_reportante': True}})
    await notificaciones_service.avisar_participantes(ticket, titulo='Ticket actualizado', mensaje='El ticket cambió de estado.')
    assert await db['notificaciones'].count_documents({'ticket_id': ticket['_id'], 'usuario_id': persona}) == 1
    await config_service.actualizar({'notificaciones': {'avisar_al_afectado': False, 'avisar_al_reportante': False}})
    await notificaciones_service.avisar_participantes(ticket, titulo='Sin duplicado', mensaje='Avisos desactivados.')
    assert await db['notificaciones'].count_documents({'ticket_id': ticket['_id']}) == 1


async def test_biblioteca_crear_leer_editar_filtrar_y_archivar(db, api):
    mundo = await _mundo(api, 'biblioteca')
    cabeceras = mundo['admin']
    datos = {'titulo': 'Tutorial de monitor', 'categoria': 'Tutoriales', 'resumen': 'Revisar el cable de video.', 'cuerpo': 'Conectar el monitor y comprobar la entrada de video.'}
    creado = await api.post('/api/kb/articulos', headers=cabeceras, json=datos)
    assert creado.status_code == 201, creado.text
    identidad = creado.json()['id']
    detalle = await api.get(f'/api/kb/articulos/{identidad}', headers=cabeceras)
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()['cuerpo'] == datos['cuerpo']
    editado = await api.patch(f'/api/kb/articulos/{identidad}', headers=cabeceras, json={'titulo': 'Tutorial actualizado'})
    assert editado.status_code == 200, editado.text
    assert (await api.get('/api/kb/articulos', headers=cabeceras, params={'texto': '['})).status_code == 200
    assert 'Tutoriales' in (await api.get('/api/kb/categorias', headers=cabeceras)).json()['items']
    assert (await api.patch(f'/api/kb/articulos/{identidad}', headers=cabeceras, json={'titulo': ' '})).status_code == 422
    for util in [True, True, False]:
        valoracion = await api.post(f'/api/kb/articulos/{identidad}/valorar', headers=cabeceras, json={'util': util})
        assert valoracion.status_code == 200, valoracion.text
        assert valoracion.json()['valoraciones'] == 1
    assert valoracion.json()['utiles'] == 0
    assert (await api.delete(f'/api/kb/articulos/{identidad}', headers=cabeceras)).status_code == 200
    assert (await api.get(f'/api/kb/articulos/{identidad}', headers=cabeceras)).status_code == 404


async def test_plantillas_crear_editar_y_eliminar(db, api):
    mundo = await _mundo(api, 'plantillas')
    cabeceras = mundo['admin']
    creado = await api.post('/api/kb/respuestas-rapidas', headers=cabeceras, json={'titulo': 'Solicitar información', 'cuerpo': 'Indica el código patrimonial del equipo.'})
    assert creado.status_code == 200, creado.text
    identidad = creado.json()['id']
    editado = await api.patch(f'/api/kb/respuestas-rapidas/{identidad}', headers=cabeceras, json={'titulo': 'Datos del equipo', 'cuerpo': 'Indica el código y la oficina del equipo.'})
    assert editado.status_code == 200, editado.text
    assert any(p['id'] == identidad for p in (await api.get('/api/kb/respuestas-rapidas', headers=cabeceras)).json()['items'])
    assert (await api.delete(f'/api/kb/respuestas-rapidas/{identidad}', headers=cabeceras)).status_code == 200


async def test_configuracion_parcial_preserva_ajustes_no_enviados(db, api):
    mundo = await _mundo(api, 'ajustes')
    cabeceras = mundo['admin']
    await api.patch('/api/configuracion', headers=cabeceras, json={'ia': {'valor_por_defecto': False}, 'notificaciones': {'email_activo': True}})
    guardado = await api.patch('/api/configuracion', headers=cabeceras, json={'negocio': {'institucion_nombre': 'Municipalidad de prueba'}, 'ia': {'confianza_minima': 0.7}, 'notificaciones': {'avisar_al_afectado': False}})
    assert guardado.status_code == 200, guardado.text
    datos = guardado.json()
    assert datos['institucion']['nombre'] == 'Municipalidad de prueba'
    assert datos['notificaciones']['email_activo'] is True
    assert datos['notificaciones']['avisar_al_afectado'] is False
    assert datos['ia']['valor_por_defecto'] is False
    assert (await api.patch('/api/configuracion', headers=cabeceras, json={'ia': {'confianza_minima': 2}})).status_code == 422
