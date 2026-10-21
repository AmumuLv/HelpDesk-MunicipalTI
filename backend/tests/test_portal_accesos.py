import asyncio
import json
from unittest.mock import AsyncMock, patch
from bson import ObjectId

from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _mundo
from app.services import kb_service
from app.api.routes.tiempo_real import ConexionSocket


async def test_companeros_solo_oficina_y_post_no_permite_otras(db, api):
    mundo = await _mundo(api, 'oficina-portal')
    otra = (await api.post('/api/oficinas', headers=mundo['admin'], json={'nombre': 'Otra oficina', 'zona_id': mundo['zona']['id']})).json()
    ajeno = (await api.post('/api/usuarios', headers=mundo['admin'], json={'nombre': 'Persona de otra oficina', 'email': 'ajeno@prueba.local', 'rol': 'usuario', 'password': PASSWORD, 'oficina_id': otra['id']})).json()
    for parametros in ({}, {'otra_oficina': 'true', 'zona_id': mundo['zona']['id']}):
        respuesta = await api.get('/api/usuarios/companeros', headers=mundo['usuario'], params=parametros)
        assert respuesta.status_code == 200
        ids = {p['id'] for p in respuesta.json()['items']}
        assert mundo['companero_id'] in ids
        assert ajeno['id'] not in ids
        assert mundo['usuario_id'] not in ids
        assert respuesta.json()['puede_cambiar_ambito'] is False
    respuesta = await api.post('/api/tickets', headers=mundo['usuario'], json={'tipo_problema': 'Otro', 'descripcion': 'No funciona el programa de la oficina', 'urgencia': 'puede_esperar', 'persona': {'es_para_mi': False, 'afectado_id': ajeno['id']}})
    assert respuesta.status_code == 403
    assert await db.tickets.count_documents({}) == 0


async def test_usuario_no_cambia_password_y_admin_restablace(db, api):
    mundo = await _mundo(api, 'password-gestionada')
    usuario_id = ObjectId(mundo['usuario_id'])
    anterior = await db.usuarios.find_one({'_id': usuario_id})
    resultado = await api.post('/api/auth/password', headers=mundo['usuario'], json={'password_actual': PASSWORD, 'password_nuevo': 'OtraClave123!'})
    assert resultado.status_code == 403
    assert (await db.usuarios.find_one({'_id': usuario_id}))['password_hash'] == anterior['password_hash']
    resultado = await api.post(f'/api/usuarios/{usuario_id}/restablecer-password', headers=mundo['admin'], json={'password': 'NuevaClave123!'})
    assert resultado.status_code == 200
    assert (await api.get('/api/auth/sesion', headers=mundo['usuario'])).status_code == 401
    assert (await api.post('/api/auth/login', json={'correo': 'usuario-password-gestionada@prueba.local', 'password': 'NuevaClave123!'})).status_code == 200


async def test_articulo_ti_no_se_filtra_a_usuario_por_ninguna_ruta(db, api):
    mundo = await _mundo(api, 'kb-privada')
    cuerpo = {'titulo': 'Procedimiento reservado de soporte', 'resumen': 'Instrucciones internas para el equipo de soporte.', 'cuerpo': 'Contenido interno que no deben leer los usuarios.', 'categoria': 'Categoria interna especial', 'visibilidad': 'equipo_ti'}
    respuesta = await api.post('/api/kb/articulos', headers=mundo['admin'], json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    articulo_id = respuesta.json()['id']
    for rol in ['admin', 'tecnico']:
        detalle = await api.get(f'/api/kb/articulos/{articulo_id}', headers=mundo[rol])
        assert detalle.status_code == 200
        assert detalle.json()['visibilidad'] == 'equipo_ti'
    for parametros in ({}, {'texto': 'reservado'}, {'visibilidad': 'equipo_ti'}):
        lista = await api.get('/api/kb/articulos', headers=mundo['usuario'], params=parametros)
        assert lista.status_code == 200
        assert articulo_id not in {a['id'] for a in lista.json()['items']}
    assert (await api.get(f'/api/kb/articulos/{articulo_id}', headers=mundo['usuario'])).status_code == 404
    assert (await api.post(f'/api/kb/articulos/{articulo_id}/valorar', headers=mundo['usuario'], json={'util': True})).status_code == 404
    categorias = (await api.get('/api/kb/categorias', headers=mundo['usuario'])).json()['items']
    assert cuerpo['categoria'] not in categorias
    assert await kb_service.sugerir_para_ticket('reservado soporte', usuario={'rol': 'usuario'}) == []
    assert await kb_service.sugerir_para_ticket('reservado soporte', usuario={'rol': 'tecnico'})
    publico = await api.post('/api/kb/articulos', headers=mundo['admin'], json={**cuerpo, 'titulo': 'Guia publica para trabajadores', 'visibilidad': 'todos'})
    assert (await api.get(f"/api/kb/articulos/{publico.json()['id']}", headers=mundo['usuario'])).status_code == 200
    legado = await db.articulos_kb.insert_one({'titulo': 'Guia anterior', 'categoria': 'General', 'resumen': 'Guia publicada anteriormente.', 'cuerpo': 'Contenido anterior a esta funcion.', 'activo': True})
    assert (await api.get(f'/api/kb/articulos/{legado.inserted_id}', headers=mundo['usuario'])).status_code == 200
    cambio = await api.patch(f'/api/kb/articulos/{articulo_id}', headers=mundo['admin'], json={'visibilidad': 'todos'})
    assert cambio.status_code == 200
    assert (await api.get(f'/api/kb/articulos/{articulo_id}', headers=mundo['usuario'])).status_code == 200
    evento = await db.auditoria.find_one({'entidad_id': articulo_id, 'accion': 'kb.editar'})
    assert evento is not None


async def test_socket_entrega_eventos_y_libera_la_suscripcion_al_salir():
    entradas = asyncio.Queue()
    cierre = asyncio.Queue()
    entregado = asyncio.Event()
    enviados = []
    pubsub = AsyncMock()
    async def escuchar():
        while True:
            yield await entradas.get()
    pubsub.listen = escuchar
    redis = type('RedisSimulado', (), {'pubsub': lambda _: pubsub})()
    async def enviar(dato):
        enviados.append(dato)
        if dato.get('tipo') == 'ticket_estado':
            entregado.set()
    websocket = AsyncMock()
    websocket.send_json.side_effect = enviar
    websocket.receive.side_effect = cierre.get
    with patch('app.api.routes.tiempo_real.get_redis', return_value=redis):
        tarea = asyncio.create_task(ConexionSocket(websocket).run(['ticket:prueba']))
        await entradas.put({'type': 'message', 'data': json.dumps({'tipo': 'ticket_estado', 'datos': {'estado': 'en_progreso'}})})
        await asyncio.wait_for(entregado.wait(), timeout=2)
        assert enviados[0]['tipo'] == 'sincronizacion'
        assert any(evento['tipo'] == 'ticket_estado' for evento in enviados)
        await cierre.put({'type': 'websocket.disconnect'})
        await asyncio.wait_for(tarea, timeout=2)
    pubsub.unsubscribe.assert_awaited_once()
    pubsub.aclose.assert_awaited_once()


async def test_reporte_tiene_titulo_concreto_categoria_y_edicion_ti(db, api):
    mundo = await _mundo(api, 'titulo-categoria')
    descripcion = 'Necesito instalar Office para trabajar con Word y Excel en mi oficina.'
    respuesta = await api.post('/api/tickets', headers=mundo['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': descripcion, 'urgencia': 'puede_esperar', 'persona': {'es_para_mi': True}})
    assert respuesta.status_code == 201, respuesta.text
    ticket = respuesta.json()['ticket']
    detalle = (await api.get(f"/api/tickets/{ticket['id']}", headers=mundo['admin'])).json()
    assert detalle['asunto'] == 'Instalación de Office'
    assert detalle['categoria'] == 'Sistema / Programa'
    assert detalle['descripcion'] == descripcion
    assert 'resumen_automatico' not in detalle
    descripcion_anterior = 'Mi impresora no imprime. ' + 'Necesito ayuda con el equipo. ' * 30
    asunto_anterior = 'Necesito ayuda con la impresora de nuestra oficina porque no podemos continuar con los documentos'
    await db.tickets.update_one({'_id': ObjectId(ticket['id'])}, {'$set': {'descripcion': descripcion_anterior, 'asunto': asunto_anterior, 'tipo_problema': 'Impresora'}})
    legado = (await api.get(f"/api/tickets/{ticket['id']}", headers=mundo['admin'])).json()
    assert legado['asunto'] == 'La impresora no imprime'
    assert 'resumen_automatico' not in legado
    assert legado['descripcion'] == descripcion_anterior
    assert (await db.tickets.find_one({'_id': ObjectId(ticket['id'])}))['asunto'] == asunto_anterior
    await db.tickets.update_one({'_id': ObjectId(ticket['id'])}, {'$set': {'descripcion': descripcion}})
    cambio = {'asunto': 'Instalar Office en el equipo de la oficina', 'categoria': 'Software instalado'}
    assert (await api.patch(f"/api/tickets/{ticket['id']}", headers=mundo['usuario'], json=cambio)).status_code == 403
    actualizado = await api.patch(f"/api/tickets/{ticket['id']}", headers=mundo['admin'], json=cambio)
    assert actualizado.status_code == 200
    assert actualizado.json()['categoria'] == cambio['categoria']
    assert actualizado.json()['asunto'] == cambio['asunto']
    assert actualizado.json()['descripcion'] == descripcion
    from app.services.presentacion_ticket import titulo_reporte
    assert titulo_reporte('Impresora', 'Se atascó la hoja al imprimir') == 'Papel atascado en la impresora'
    assert titulo_reporte('Sistema/programa', 'Office no abre desde ayer') == 'Office no abre'
    assert titulo_reporte('Huella dactilar', 'No puedo registrar la huella de mi compañero') == 'No se puede registrar la huella'
    assert len(titulo_reporte('Otro', 'Un detalle específico ' * 60)) <= 70


async def test_cada_rol_elimina_solo_sus_notificaciones(db, api):
    from app.services import notificaciones_service
    mundo = await _mundo(api, 'eliminar-avisos')
    for rol in ['usuario', 'tecnico', 'admin']:
        sesion = (await api.get('/api/auth/sesion', headers=mundo[rol])).json()
        usuario_id = ObjectId(sesion['id'])
        ajeno = ObjectId()
        propio = await notificaciones_service.crear(usuario_id, 'Aviso propio', 'Contenido')
        otro = await notificaciones_service.crear(ajeno, 'Aviso ajeno', 'Privado')
        assert (await api.delete(f"/api/notificaciones/{otro['id']}", headers=mundo[rol])).status_code == 404
        assert (await api.delete(f"/api/notificaciones/{propio['id']}", headers=mundo[rol])).status_code == 200
        await notificaciones_service.crear(usuario_id, 'Otro aviso', 'Contenido')
        vaciar = await api.delete('/api/notificaciones', headers=mundo[rol])
        assert vaciar.status_code == 200
        assert await db.notificaciones.count_documents({'usuario_id': usuario_id}) == 0
        assert await db.notificaciones.count_documents({'_id': otro['id']}) == 1


async def test_resumen_ia_lee_descripcion_completa_y_respeta_edicion_ti(db):
    from app.services import resumen_ticket_service as servicio
    from app.services.ia_provider import RespuestaIA
    descripcion = 'Buenos días. ' + 'Detalles del problema de la oficina. ' * 50 + 'El sistema SIGA no permite guardar el expediente.'
    documento = {'codigo': 'TKT-RESUMEN', 'asunto': 'Problema reportado', 'estado': 'nuevo', 'origen': 'usuario', 'descripcion': descripcion, 'tipo_problema': 'SIGA/Casita/Servidor'}
    resultado = await db.tickets.insert_one(documento)
    proveedor = AsyncMock()
    proveedor.disponible.return_value = True
    proveedor.completar.return_value = RespuestaIA(disponible=True, texto=json.dumps({'titulo': 'SIGA no permite guardar el expediente', 'resumen': 'No se puede guardar el expediente en SIGA.'}))
    with patch.object(servicio.config_service, 'ia_activada', AsyncMock(return_value=True)), patch.object(servicio.ia_provider, 'obtener_proveedor', return_value=proveedor):
        assert await servicio.resumir(str(resultado.inserted_id))
        mensajes = proveedor.completar.call_args.args[0]
        assert json.loads(mensajes[1]['content'])['descripcion'] == descripcion
        actualizado = await db.tickets.find_one({'_id': resultado.inserted_id})
        assert actualizado['descripcion'] == descripcion
        assert len(actualizado['asunto']) <= 70
        assert 'resumen_automatico' not in actualizado
        await db.tickets.update_one({'_id': resultado.inserted_id}, {'$set': {'asunto': 'Título confirmado por TI', 'asunto_editado_ti': True}})
        assert not await servicio.resumir(str(resultado.inserted_id))
        assert proveedor.completar.await_count == 1
        await db.tickets.update_one({'_id': resultado.inserted_id}, {'$unset': {'asunto_editado_ti': ''}})
        proveedor.completar.return_value = RespuestaIA(disponible=True, texto=json.dumps({'titulo': 'Texto demasiado largo ' * 20}))
        assert not await servicio.resumir(str(resultado.inserted_id))
        proveedor.completar.side_effect = TimeoutError()
        assert not await servicio.resumir(str(resultado.inserted_id))
        assert (await db.tickets.find_one({'_id': resultado.inserted_id}))['asunto'] == 'Título confirmado por TI'


async def test_proveedor_no_confunde_credencial_invalida_con_disponibilidad():
    import httpx
    from app.services.ia_provider import ProveedorOpenAICompatible
    for estado in [200, 401, 403, 500]:
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(lambda peticion: httpx.Response(estado, json={})))
        proveedor = ProveedorOpenAICompatible('https://proveedor.invalid/v1', 'simulada', 'modelo', 2)
        with patch('app.services.ia_provider.httpx.AsyncClient', return_value=cliente):
            assert await proveedor.disponible() is (estado == 200)


async def test_mensajes_llegan_solo_al_tecnico_y_finalizados_incluye_legado(db, api):
    from app.core.time import utcnow
    mundo = await _mundo(api, 'mensajes-destino')
    creado = await api.post('/api/tickets', headers=mundo['usuario'], json={'tipo_problema': 'Otro', 'descripcion': 'Necesito revisar el acceso a la cuenta', 'persona': {'es_para_mi': True}})
    assert creado.status_code == 201, creado.text
    ticket_id = creado.json()['ticket']['id']
    await db.tickets.update_one({'_id': ObjectId(ticket_id)}, {'$set': {'tecnico_id': ObjectId(mundo['tecnico_id'])}})
    await db.notificaciones.delete_many({})
    mensaje = await api.post(f'/api/tickets/{ticket_id}/mensajes', headers=mundo['usuario'], json={'cuerpo': 'Todavía necesito ayuda', 'adjuntos': []})
    assert mensaje.status_code == 201, mensaje.text
    avisos = await db.notificaciones.find({}).to_list(None)
    assert len(avisos) == 1
    assert avisos[0]['usuario_id'] == ObjectId(mundo['tecnico_id'])
    assert avisos[0]['tipo'] == 'mensaje'
    await db.tickets.update_one({'_id': ObjectId(ticket_id)}, {'$set': {'estado': 'cerrado'}})
    assert (await api.post(f'/api/tickets/{ticket_id}/mensajes', headers=mundo['usuario'], json={'cuerpo': 'Me volvió a ocurrir el problema', 'adjuntos': []})).status_code == 201
    cerrado = await db.notificaciones.find_one({'tipo': 'mensaje_cerrado'})
    assert cerrado['usuario_id'] == ObjectId(mundo['tecnico_id'])
    assert await db.notificaciones.count_documents({'usuario_id': {'$ne': ObjectId(mundo['tecnico_id'])}}) == 0
    await db.tickets.insert_one({'codigo': 'TKT-LEGADO', 'asunto': 'Incidencia anterior', 'estado': 'resuelto', 'origen': 'usuario', 'reportante_id': ObjectId(mundo['usuario_id']), 'afectado_id': ObjectId(mundo['usuario_id']), 'creado_en': utcnow(), 'actualizado_en': utcnow()}, bypass_document_validation=True)
    listado = await api.get('/api/tickets?solo_mios=1&estado=cerrado', headers=mundo['usuario'])
    assert listado.status_code == 200, listado.text
    assert listado.json()['total'] == 2


async def test_ti_corrige_vinculo_y_consulta_historial_del_conjunto(db, api):
    mundo = await _mundo(api, 'vinculo-ticket')
    oficina_id = ObjectId(mundo['oficina']['id'])
    conjunto = (await db.conjuntos.insert_one({'nombre': 'Computadora N°1', 'oficina_id': oficina_id})).inserted_id
    equipo = (await db.activos.insert_one({'clave_natural': 'pc-oficina-prueba', 'tipo': 'CPU', 'nombre_equipo': 'PC Oficina', 'oficina_id': oficina_id, 'conjunto_id': conjunto, 'campos_estado': {}, 'activo': True})).inserted_id
    ajeno = (await db.activos.insert_one({'clave_natural': 'pc-ajena-prueba', 'tipo': 'CPU', 'nombre_equipo': 'PC ajena', 'oficina_id': ObjectId(), 'campos_estado': {}, 'activo': True})).inserted_id
    creado = await api.post('/api/tickets', headers=mundo['usuario'], json={'tipo_problema': 'Sistema/programa', 'descripcion': 'Necesito instalar Office en mi computadora', 'persona': {'es_para_mi': True}})
    assert creado.status_code == 201, creado.text
    ticket_id = creado.json()['ticket']['id']
    ruta = f'/api/tickets/{ticket_id}'
    cuerpo = {'alcance_incidencia': 'programa', 'sistema_afectado': 'Office', 'activo_id': str(equipo), 'conjunto_id': None}
    assert (await api.patch(ruta, headers=mundo['usuario'], json=cuerpo)).status_code == 403
    assert (await api.patch(ruta, headers=mundo['admin'], json={**cuerpo, 'activo_id': str(ajeno)})).status_code == 422
    actualizado = await api.patch(ruta, headers=mundo['tecnico'], json=cuerpo)
    assert actualizado.status_code == 200, actualizado.text
    assert actualizado.json()['activo_id'] is None
    assert actualizado.json()['conjunto_id'] == str(conjunto)
    assert actualizado.json()['sistema_afectado'] == 'Office'
    assert (await api.get(f'/api/tickets?conjunto_id={conjunto}', headers=mundo['admin'])).json()['total'] == 1
    assert (await api.get(f'/api/tickets?activo_id={equipo}', headers=mundo['admin'])).json()['total'] == 0
    actualizado = await api.patch(ruta, headers=mundo['admin'], json={**cuerpo, 'activo_id': None, 'conjunto_id': str(conjunto)})
    assert actualizado.status_code == 200
    assert actualizado.json()['activo_id'] is None
    assert (await api.get(f'/api/tickets?activo_id={equipo}', headers=mundo['admin'])).json()['total'] == 0
    assert (await api.get(f'/api/tickets?conjunto_id={conjunto}', headers=mundo['admin'])).json()['total'] == 1
    actualizado = await api.patch(ruta, headers=mundo['admin'], json={**cuerpo, 'sistema_afectado': 'SIGA', 'activo_id': None, 'conjunto_id': str(conjunto)})
    assert actualizado.status_code == 200
    assert actualizado.json()['alcance_incidencia'] == 'programa'
    assert actualizado.json()['conjunto_id'] == str(conjunto)
    assert (await api.get(f'/api/tickets?conjunto_id={conjunto}', headers=mundo['admin'])).json()['total'] == 1
    assert (await api.get('/api/tickets?solo_mios=1', headers=mundo['usuario'])).json()['total'] == 1
    assert (await api.get('/api/tickets?texto=SIGA', headers=mundo['admin'])).json()['total'] == 1
    assert await db.auditoria.count_documents({'accion': 'ticket.actualizar'}) >= 2


async def test_estrellas_se_guardan_una_vez_y_solo_por_participantes(db, api):
    mundo = await _mundo(api, 'calificacion')
    creado = await api.post('/api/tickets', headers=mundo['usuario'], json={'tipo_problema': 'Impresora', 'descripcion': 'La impresora no imprime desde ayer', 'persona': {'es_para_mi': True}})
    ticket_id = creado.json()['ticket']['id']
    ruta = f'/api/tickets/{ticket_id}/valorar'
    assert (await api.post(ruta, headers=mundo['usuario'], json={'valor': 4})).status_code == 422
    assert (await api.post(ruta, headers=mundo['usuario'], json={'puntuacion': 4})).status_code == 403
    await db.tickets.update_one({'_id': ObjectId(ticket_id)}, {'$set': {'estado': 'cerrado', 'tecnico_id': ObjectId(mundo['tecnico_id'])}})
    assert (await api.post(ruta, headers=mundo['tecnico'], json={'puntuacion': 5})).status_code == 403
    assert (await api.post(ruta, headers=mundo['usuario'], json={'puntuacion': 0})).status_code == 422
    assert (await api.post(ruta, headers=mundo['usuario'], json={'puntuacion': 6})).status_code == 422
    respuestas = await asyncio.gather(*(api.post(ruta, headers=mundo['usuario'], json={'puntuacion': n}) for n in [4, 5]))
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    guardado = await db.tickets.find_one({'_id': ObjectId(ticket_id)})
    assert guardado['satisfaccion'] in [4, 5]
    assert guardado['valorado_por'] == ObjectId(mundo['usuario_id'])
    detalle = (await api.get(f'/api/tickets/{ticket_id}', headers=mundo['usuario'])).json()
    assert detalle['satisfaccion'] == guardado['satisfaccion']
    assert (await api.post(ruta, headers=mundo['usuario'], json={'puntuacion': 3})).status_code == 409
    assert await db.notificaciones.count_documents({'tipo': 'satisfaccion'}) == 1


async def test_preferencia_ia_persistente_y_cambios_emitidos_en_vivo(db, api):
    from app.services import notificaciones_service, ia_provider
    mundo = await _mundo(api, 'preferencia-viva')
    with patch.object(notificaciones_service, '_publicar', new_callable=AsyncMock) as publicar, patch.object(ia_provider, 'estado', AsyncMock(return_value={'disponible': False, 'modelo': None})):
        respuesta = await api.post('/api/auth/preferencia-ia', headers=mundo['usuario'], json={'recomendaciones_ia': False})
        assert respuesta.status_code == 200
        assert respuesta.json()['recomendaciones_visibles'] is False
        preferencia = (await api.get('/api/auth/preferencia-ia', headers=mundo['usuario'])).json()
        assert preferencia['recomendaciones_ia'] is False
        assert preferencia['recomendaciones_personales'] is False
        propios = [llamada.args for llamada in publicar.await_args_list if llamada.args[1].get('tipo') == 'ia_preferencia']
        assert propios[-1] == (f"notificaciones:{mundo['usuario_id']}", {'tipo': 'ia_preferencia', 'recomendaciones_ia': False})
        respuesta = await api.patch(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo['admin'], json={'recomendaciones_ia': True})
        assert respuesta.status_code == 200, respuesta.text
        assert (await api.get('/api/auth/preferencia-ia', headers=mundo['usuario'])).json()['recomendaciones_visibles'] is True
        respuesta = await api.patch('/api/configuracion', headers=mundo['admin'], json={'ia': {'global_activa': False}})
        assert respuesta.status_code == 200, respuesta.text
        eventos = [llamada.args for llamada in publicar.await_args_list if llamada.args[1].get('tipo') == 'ia_actualizada']
        assert eventos[-1][0] == 'configuracion:ia'
        assert eventos[-1][1]['global_activa'] is False
        assert set(eventos[-1][1]) == {'tipo', 'global_activa', 'recomendaciones_activas'}
        preferencia = (await api.get('/api/auth/preferencia-ia', headers=mundo['usuario'])).json()
        assert preferencia['ia_global_activa'] is False
        assert preferencia['recomendaciones_ia'] is True
        assert preferencia['recomendaciones_visibles'] is False


async def test_lecturas_y_me_gusta_son_por_persona_con_nombres_y_acceso(db, api):
    mundo = await _mundo(api, 'kb-reacciones')
    creado = await api.post('/api/kb/articulos', headers=mundo['admin'], json={'titulo': 'Impresora de la oficina', 'resumen': 'Comprobaciones para imprimir documentos.', 'cuerpo': 'Revisa la bandeja de papel y la conexión de la impresora.', 'categoria': 'Impresora'})
    assert creado.status_code == 201
    articulo_id = creado.json()['id']
    ruta = f'/api/kb/articulos/{articulo_id}'
    lecturas = await asyncio.gather(*(api.get(ruta, headers=mundo['usuario']) for _ in range(6)))
    assert all(r.status_code == 200 for r in lecturas)
    guardado = await db.articulos_kb.find_one({'_id': ObjectId(articulo_id)})
    assert guardado['visualizaciones'] == 1
    assert len(guardado['lectores_ids']) == 1
    assert (await api.get(ruta, headers=mundo['usuario'])).json()['visualizaciones'] == 1
    assert (await api.get(ruta, headers=mundo['tecnico'])).json()['visualizaciones'] == 2
    respuestas = await asyncio.gather(*(api.post(ruta + '/valorar', headers=mundo['usuario'], json={'util': True}) for _ in range(5)))
    assert all(r.status_code == 200 for r in respuestas)
    detalle = (await api.get(ruta, headers=mundo['usuario'])).json()
    assert detalle['mi_valoracion'] is True
    assert detalle['me_gusta'] == 1
    assert detalle['visualizaciones'] == 2
    assert 'lectores_ids' not in detalle
    await api.post(ruta + '/valorar', headers=mundo['tecnico'], json={'util': True})
    personas = await api.get(ruta + '/me-gusta?por_pagina=1', headers=mundo['usuario'])
    assert personas.status_code == 200
    assert personas.json()['total'] == 2
    assert personas.json()['total_paginas'] == 2
    assert set(personas.json()['items'][0]) == {'usuario_id', 'nombre'}
    segunda = (await api.get(ruta + '/me-gusta?por_pagina=1&pagina=2', headers=mundo['usuario'])).json()
    assert {personas.json()['items'][0]['usuario_id'], segunda['items'][0]['usuario_id']} == {mundo['usuario_id'], mundo['tecnico_id']}
    lista = (await api.get('/api/kb/articulos', headers=mundo['usuario'])).json()
    assert next(a for a in lista['items'] if a['id'] == articulo_id)['me_gusta'] == 2
    quitar = await api.delete(ruta + '/valorar', headers=mundo['usuario'])
    assert quitar.status_code == 200
    assert quitar.json()['me_gusta'] == 1
    assert quitar.json()['mi_valoracion'] is None
    assert (await api.get(ruta, headers=mundo['usuario'])).json()['mi_valoracion'] is None
    await api.patch(ruta, headers=mundo['admin'], json={'visibilidad': 'equipo_ti'})
    assert (await api.get(ruta + '/me-gusta', headers=mundo['usuario'])).status_code == 404
    assert (await api.delete(ruta + '/valorar', headers=mundo['usuario'])).status_code == 404
    assert (await api.get(ruta + '/me-gusta', headers=mundo['tecnico'])).status_code == 200
