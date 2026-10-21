"""Correcciones solicitadas en samples/Correcciones funcionales.pdf."""
from datetime import timedelta
from io import BytesIO
from bson import ObjectId
from openpyxl import load_workbook
from app.core.time import utcnow
from tests.test_tickets_horarios import _mundo


async def test_conjuntos_numerados_sugerencias_reales_y_campos_unicos(db, api):
    mundo = await _mundo(api, 'pdf-conjuntos')
    cab = mundo['admin']
    oficina = mundo['oficina']['id']
    conjunto = await api.post('/api/conjuntos', headers=cab, json={'nombre': 'Computadora N°2', 'oficina_id': oficina})
    assert conjunto.status_code == 201, conjunto.text
    assert conjunto.json()['numero'] == 2
    duplicado = await api.post('/api/conjuntos', headers=cab, json={'nombre': 'PC N°2', 'oficina_id': oficina})
    assert duplicado.status_code == 409, duplicado.text
    mal = await api.post('/api/conjuntos', headers=cab, json={'nombre': 'Computadora N°3', 'numero': 4, 'oficina_id': oficina})
    assert mal.status_code == 422
    activo = await api.post('/api/activos', headers=cab, json={'tipo': 'CPU', 'oficina_id': oficina, 'conjunto_id': conjunto.json()['id'], 'nombre_equipo': 'CPU de prueba', 'procesador': 'Ryzen 7 PDF', 'memoria_ram': '32 GB PDF', 'almacenamiento': '1 TB SSD PDF', 'tamano_pantalla': '24 PDF'})
    assert activo.status_code == 201, activo.text
    for campo, esperado in [('procesador', 'Ryzen 7 PDF'), ('memoria_ram', '32 GB PDF'), ('almacenamiento', '1 TB SSD PDF'), ('tamano_pantalla', '24 PDF')]:
        respuesta = await api.get(f'/api/equipos/sugerencias?campo={campo}', headers=cab)
        assert respuesta.status_code == 200
        assert any(v['valor'] == esperado and v['frecuencia'] == 1 for v in respuesta.json()['valores'])
    for campo in ['codigo_patrimonial', 'direccion_ip']:
        assert (await api.get(f'/api/equipos/sugerencias?campo={campo}', headers=cab)).status_code == 422
    lista = (await api.get(f'/api/conjuntos?oficina_id={oficina}', headers=cab)).json()['items']
    assert lista[0]['numero'] == 2 and lista[0]['componentes'][0]['tipo'] == 'CPU'
    otro = await api.post('/api/conjuntos', headers=cab, json={'nombre': 'Computadora N°3', 'oficina_id': oficina})
    assert otro.status_code == 201
    ruta = f"/api/conjuntos/{conjunto.json()['id']}"
    assert (await api.patch(ruta, headers=cab, json={'nombre': 'PC N°3'})).status_code == 409
    renombrado = await api.patch(ruta, headers=cab, json={'nombre': 'PC N°4'})
    assert renombrado.status_code == 200 and renombrado.json()['numero'] == 4
    ficha = (await api.get(f"/api/activos/{activo.json()['id']}", headers=cab)).json()
    assert ficha['conjunto_nombre'] == 'PC N°4'


async def test_criticos_e_historial_separados_y_mas_recientes_primero(db, api):
    mundo = await _mundo(api, 'pdf-cerrados')
    ahora = utcnow()
    for i, (estado, prioridad, dias, vencido) in enumerate([
        ('cerrado', 'critica', 2, True), ('cerrado', 'media', 1, False),
        ('nuevo', 'critica', 3, False), ('en_progreso', 'media', 0, True), ('nuevo', 'media', 0, False),
    ]):
        await db['tickets'].insert_one({'codigo': f'PDF-{i}', 'asunto': 'Caso PDF', 'origen': 'usuario', 'estado': estado, 'prioridad': prioridad, 'creado_en': ahora - timedelta(days=dias), 'sla_resolver_en': ahora + timedelta(days=-1 if vencido else 1)})
    criticos = (await api.get('/api/tickets?vista=criticos', headers=mundo['admin'])).json()['items']
    assert [t['codigo'] for t in criticos] == ['PDF-3', 'PDF-2']
    cerrados = (await api.get('/api/tickets?vista=cerrados', headers=mundo['admin'])).json()['items']
    assert [t['codigo'] for t in cerrados] == ['PDF-1', 'PDF-0']
    imposible = (await api.get('/api/tickets?vista=criticos&estado=cerrado', headers=mundo['admin'])).json()
    assert imposible['total'] == 0


async def test_limpiezas_respetan_equipos_propietario_y_tareas_en_curso(db, api, monkeypatch, tmp_path):
    from app.services import export_service
    from app.core.config import settings
    mundo = await _mundo(api, 'pdf-limpieza')
    monkeypatch.setattr(export_service.settings, 'export_dir', str(tmp_path))
    cantidad = await db['activos'].count_documents({})
    for lote, estado in [('viejo', 'confirmado'), ('vista-vieja', 'analizado'), ('actual', 'analizado'), ('ocupado', 'confirmando')]:
        await db['importaciones'].insert_one({'lote_id': lote, 'estado': estado, 'creado_en': utcnow()})
    assert (await api.delete('/api/importacion', headers=mundo['usuario'])).status_code == 403
    limpio = await api.delete('/api/importacion?conservar_lote=actual', headers=mundo['admin'])
    assert limpio.status_code == 200 and limpio.json()['eliminados'] == 2
    assert await db['importaciones'].count_documents({}) == 2
    assert await db['activos'].count_documents({}) == cantidad
    propietarios = [ObjectId(mundo['tecnico_id']), ObjectId(mundo['usuario_id'])]
    for i, usuario in enumerate(propietarios):
        archivo = tmp_path / f'archivo-{i}.xlsx'; archivo.write_bytes(b'datos')
        await db['exportaciones'].insert_one({'tipo': 'tickets', 'formato': 'excel', 'estado': 'listo', 'usuario_id': usuario, 'ruta': str(archivo), 'creado_en': utcnow()})
    await db['exportaciones'].insert_one({'tipo': 'tickets', 'formato': 'excel', 'estado': 'en_proceso', 'usuario_id': propietarios[0], 'creado_en': utcnow()})
    assert (await export_service.eliminar_archivos({'_id': propietarios[0], 'rol': 'tecnico'}))['eliminados'] == 1
    assert not (tmp_path / 'archivo-0.xlsx').exists() and (tmp_path / 'archivo-1.xlsx').exists()
    assert (await api.delete('/api/exportaciones', headers=mundo['admin'])).json()['eliminados'] == 1
    assert await db['exportaciones'].count_documents({'estado': 'en_proceso'}) == 1


async def test_auditoria_solo_equipo_ti_retencion_y_vaciado(db, api):
    from app.core.audit import registrar
    from app.migrations.m022_retencion_auditoria import aplicar
    mundo = await _mundo(api, 'pdf-auditoria')
    for rol in ['usuario', 'administrador', 'tecnico', 'sistema']:
        await registrar('equipo.editar', rol=rol, resumen=f'Prueba rol {rol}')
    guardados = await db['auditoria'].find({'resumen': {'$regex': '^Prueba rol'}}).to_list(None)
    assert {e['rol'] for e in guardados} == {'administrador', 'tecnico'}
    await db['auditoria'].insert_one({'rol': 'administrador', 'fecha': utcnow() - timedelta(days=16), 'accion': 'equipo.editar'})
    await aplicar(db)
    assert await db['auditoria'].count_documents({'fecha': {'$lt': utcnow() - timedelta(days=15)}}) == 0
    indices = await db['auditoria'].index_information()
    assert any(i.get('expireAfterSeconds') == 15 * 86400 for i in indices.values())
    assert (await api.delete('/api/auditoria', headers=mundo['tecnico'])).status_code == 403
    assert (await api.delete('/api/auditoria', headers=mundo['admin'])).status_code == 200
    assert await db['auditoria'].count_documents({}) == 0


async def test_resumen_ejecutivo_excel_etiquetas_unidades_y_ceros(db, api, monkeypatch):
    from app.services import analitica_service, export_service
    mundo = await _mundo(api, 'pdf-ejecutivo')
    panel = await analitica_service.panel_completo({})
    panel['kpis'].update({'tiempo_medio_resolucion_min': 735.9, 'confianza_media_modelo': 0.715, 'satisfaccion_promedio': 0})
    async def datos(_): return panel
    monkeypatch.setattr(analitica_service, 'panel_completo', datos)
    contenido = await export_service._generar_analitica({}, 'excel', {'nombre': 'Persona de prueba'})
    hoja = load_workbook(BytesIO(contenido))['Resumen de atención']
    filas = list(hoja.values)
    etiquetas = {f[1]: f for f in filas[1:] if len(f) >= 4}
    assert etiquetas['Tiempo medio de resolución'][2:] == (12.27, 'horas')
    assert etiquetas['Confianza media de las sugerencias'][2] == 71.5
    assert etiquetas['Satisfacción media'][2] == 0
    assert etiquetas['Cumplimiento del plazo de atención'][2] == 'N/A'
    assert 'tiempo_medio_resolucion_min' not in str(filas)


async def test_importacion_no_se_puede_limpiar_ni_confirmar_dos_veces_a_la_vez(db, api, monkeypatch):
    import asyncio
    from app.services import import_service
    from app.core.errors import Conflicto
    mundo = await _mundo(api, 'pdf-reserva')
    await db['importaciones'].insert_one({'lote_id': 'ocupacion-pdf', 'estado': 'analizado', 'creado_en': utcnow()})
    iniciada, terminar = asyncio.Event(), asyncio.Event()
    async def operacion(lote_id, **opciones):
        iniciada.set()
        await terminar.wait()
        return {'lote_id': lote_id}
    monkeypatch.setattr(import_service, '_confirmar_lote', operacion)
    tarea = asyncio.create_task(import_service.confirmar('ocupacion-pdf', usuario={}))
    try:
        await asyncio.wait_for(iniciada.wait(), 5)
        assert (await api.delete('/api/importacion', headers=mundo['admin'])).json()['eliminados'] == 0
        import pytest
        with pytest.raises(Conflicto):
            await import_service.confirmar('ocupacion-pdf', usuario={})
    finally:
        terminar.set()
        await tarea
    assert (await api.delete('/api/importacion', headers=mundo['admin'])).json()['eliminados'] == 1
