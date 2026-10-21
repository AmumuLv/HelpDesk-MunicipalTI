"""Recorridos de archivo anual, conexiones, avisos y perfiles."""
from bson import ObjectId
from tests.test_tickets_horarios import _mundo, PASSWORD
from tests.test_inventario_anual import _excel_de_sala


async def test_archivo_anual_independiente_primera_subida_y_comparacion(db, api):
    mundo = await _mundo(api, 'archivo-anual')
    cab = mundo['admin']
    original = await db['activos'].count_documents({})
    filas_a = [['CPU', 'CPU', 'AN-001', 'LENOVO', 'PC PRINCIPAL'], ['Monitor', 'Monitor', 'AN-002', 'LG', 'MONITOR ANTIGUO']]
    filas_b = [['CPU', 'CPU', 'AN-001', 'DELL', 'PC PRINCIPAL'], ['Monitor', 'Monitor', 'AN-003', 'LG', 'MONITOR NUEVO']]
    versiones = []
    for anio, filas in [(2026, filas_a), (2027, filas_b)]:
        archivo = await _excel_de_sala('PALACIO', 'COMUNA' if anio == 2026 else 'SOPORTE', filas)
        carga = await api.post('/api/campanas/anual/importar', headers=cab, data={'anio': str(anio)}, files={'archivo': (f'inventario-{anio}.xlsx', archivo)})
        assert carga.status_code == 201, carga.text
        assert carga.json()['total_items'] == 2
        versiones.append(carga.json()['id'])
        repetida = await api.post('/api/campanas/anual/importar', headers=cab, data={'anio': str(anio)}, files={'archivo': ('mismo.xlsx', archivo)})
        assert repetida.json()['id'] == versiones[-1]
        assert repetida.json()['ya_registrado'] is True
    assert await db['activos'].count_documents({}) == original
    comparacion = await api.get('/api/campanas/versiones/comparar?anio_a=2026&anio_b=2027', headers=cab)
    assert comparacion.status_code == 200, comparacion.text
    datos = comparacion.json()
    assert len(datos['altas']) == len(datos['bajas']) == len(datos['traslados']) == 1
    assert datos['altas'][0]['codigo'] == 'AN-003'
    assert any(d['campo'] == 'marca' and d['despues'] == 'DELL' for d in datos['cambios'][0]['diferencias'])
    assert 0 <= datos['porcentaje_cambio'] <= 100
    assert (await api.get('/api/campanas/versiones/comparar?anio_a=2027&anio_b=2026', headers=cab)).status_code == 422
    pagina = (await api.get(f'/api/campanas/versiones/{versiones[0]}/equipos?por_pagina=1&pagina=2', headers=cab)).json()
    assert pagina['total'] == 2 and len(pagina['items']) == 1
    descarga = await api.get(f'/api/campanas/versiones/{versiones[0]}/excel', headers=cab)
    assert descarga.status_code == 200 and descarga.content.startswith(b'PK')
    from io import BytesIO
    from openpyxl import load_workbook
    hoja = load_workbook(BytesIO(descarga.content), read_only=True)['PALACIO']
    filas_exportadas = list(hoja.values)
    encabezado = next(i for i, fila in enumerate(filas_exportadas) if 'Dispositivo' in fila)
    posiciones = {columna: i for i, columna in enumerate(filas_exportadas[encabezado])}
    primera = filas_exportadas[encabezado + 1]
    assert primera[posiciones['Tipo de equipo']] == 'CPU'
    assert primera[posiciones['Dispositivo']] == 'CPU'
    assert primera[posiciones['Nombre Equipo']] == 'PC PRINCIPAL'
    duplicado = await _excel_de_sala('PALACIO', 'COMUNA', [filas_a[0], filas_a[0]])
    assert (await api.post('/api/campanas/anual/importar', headers=cab, data={'anio': '2028'}, files={'archivo': ('duplicado.xlsx', duplicado)})).status_code == 422
    assert await db['inventario_versiones'].count_documents({'anio': 2028}) == 0


async def test_limite_tres_conexiones_renovacion_y_cambio_password(db, api):
    from app.services import auth_service
    mundo = await _mundo(api, 'dispositivos')
    usuario = await db['usuarios'].find_one({'_id': ObjectId(mundo['usuario_id'])})
    conexiones = [await auth_service._crear_sesion(usuario, None, f'Navegador {i}') for i in range(4)]
    ultimo = conexiones[-1]
    cab = {'Authorization': f"Bearer {ultimo['access_token']}", 'X-CSRF-Token': ultimo['csrf']}
    assert (await api.get('/api/auth/sesion', headers={'Authorization': f"Bearer {conexiones[0]['access_token']}"})).status_code == 401
    dispositivos = (await api.get('/api/auth/dispositivos', headers=cab)).json()
    assert dispositivos['total'] == 3 and dispositivos['limite'] == 3
    renovada = await auth_service.refrescar(refresh_token=ultimo['refresh_token'], csrf_enviado=ultimo['csrf'])
    cab = {'Authorization': f"Bearer {renovada['access_token']}", 'X-CSRF-Token': renovada['csrf']}
    assert (await api.get('/api/auth/dispositivos', headers=cab)).json()['total'] == 3
    cambio = await api.post('/api/auth/password', headers=cab, json={'password_actual': PASSWORD, 'password_nuevo': 'ClaveNueva-2026#'})
    assert cambio.status_code == 403, cambio.text
    cambio = await api.post(f"/api/usuarios/{usuario['_id']}/restablecer-password", headers=mundo['admin'], json={'password': 'ClaveNueva-2026#'})
    assert cambio.status_code == 200, cambio.text
    assert (await api.get('/api/auth/sesion', headers=cab)).status_code == 401
    assert await db['sesiones'].count_documents({'usuario_id': usuario['_id'], 'revocado': False}) == 0


async def test_avisos_se_leen_solo_por_destinatario_y_estado_del_historial(db, api):
    from app.services import notificaciones_service
    mundo = await _mundo(api, 'avisos-historial')
    uid = ObjectId(mundo['usuario_id'])
    aviso = await notificaciones_service.crear(uid, 'Soporte respondió', 'Abre el ticket para revisar.', ticket_id=ObjectId())
    respuesta = await api.post(f"/api/notificaciones/leer?ids={aviso['id']}", headers=mundo['admin'])
    assert respuesta.json()['actualizadas'] == 0
    assert (await api.post('/api/notificaciones/leer?ids=mal', headers=mundo['usuario'])).status_code == 422
    assert (await api.get('/api/notificaciones', headers=mundo['usuario'])).json()['no_leidas'] >= 1
    assert (await api.post(f"/api/notificaciones/leer?ids={aviso['id']}", headers=mundo['usuario'])).json()['actualizadas'] == 1
    await db['tickets'].insert_many([{'codigo': f'FIL-{i}', 'asunto': 'Caso de filtro', 'origen': 'usuario', 'estado': estado, 'reportante_id': uid} for i, estado in enumerate(['en_progreso', 'cerrado'])])
    historial = await api.get(f"/api/usuarios/{uid}/tickets?estado=en_progreso", headers=mundo['admin'])
    assert historial.status_code == 200, historial.text
    assert len(historial.json()['items']) == 1 and historial.json()['items'][0]['estado'] == 'en_progreso'


async def test_migracion_limita_conexiones_anteriores_y_es_repetible(db, api):
    from app.services import auth_service
    from app.migrations.m021_limite_conexiones import aplicar
    mundo = await _mundo(api, 'conexiones-anteriores')
    uid = ObjectId(mundo['usuario_id'])
    usuario = await db['usuarios'].find_one({'_id': uid})
    conexiones = [await auth_service._crear_sesion(usuario, None, 'Navegador antiguo') for _ in range(4)]
    await db['sesiones'].update_many({'usuario_id': uid}, {'$set': {'revocado': False}})
    await db['usuarios'].update_one({'_id': uid}, {'$unset': {'sesiones_activas': ''}})
    for _ in range(2):
        await aplicar(db)
        assert (await auth_service.dispositivos(uid))['total'] == 3
    assert (await api.get('/api/auth/sesion', headers={'Authorization': f"Bearer {conexiones[0]['access_token']}"})).status_code == 401
