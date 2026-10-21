"""Verifica datos completos y archivos reales, no capturas de la página."""
import csv
import io
from datetime import timedelta

from bson import ObjectId
from openpyxl import load_workbook
from pypdf import PdfReader

from app.core import audit
from app.core.config import settings
from app.core.time import business_start_of_day, local_date, utcnow
from app.services import excel_service, export_service
from tests.test_gobernanza_y_reportes import _mundo
from tests.conftest import equipo_para_persona


async def _exportar(api, headers, tipo, formato, filtros=None, **extras):
    respuesta = await api.post('/api/exportaciones', headers=headers, json={'tipo': tipo, 'formato': formato, 'filtros': filtros or {}, **extras})
    assert respuesta.status_code == 200, respuesta.text
    archivo = await api.get('/api' + respuesta.json()['descarga_url'], headers=headers)
    assert archivo.status_code == 200, archivo.text
    return archivo


async def test_tickets_exporta_mas_de_500_con_equipo_fechas_y_notas(db, api, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'export_dir', str(tmp_path))
    mundo = await _mundo(api, 'filas-reporte')
    activo_id = ObjectId()
    await db['activos'].insert_one({'_id': activo_id, 'tipo': 'Monitor', 'oficina_id': ObjectId(mundo['oficina']['id']), 'campos_estado': {}, 'clave_natural': 'monitor-reporte', 'nombre_equipo': 'Monitor de recepción', 'codigo_patrimonial': 'PAT-0123'})
    ahora = utcnow()
    filas = [{'_id': ObjectId(), 'codigo': f'REP-{i:04}', 'asunto': 'Pantalla sin imagen', 'origen': 'tecnico', 'estado': 'cerrado', 'prioridad': 'media',
              'creado_en': ahora, 'cerrado_en': ahora, 'activo_id': activo_id, 'zona_id': ObjectId(mundo['zona']['id']), 'oficina_id': ObjectId(mundo['oficina']['id']),
              'zona_nombre': mundo['zona']['nombre'], 'oficina_nombre': 'COMUNA', 'tiempo_resolucion_min': 60, 'afectado_nombre': 'Persona de prueba'} for i in range(505)]
    await db['tickets'].insert_many(filas + [{'codigo': 'ELIMINADO', 'asunto': 'No incluir', 'origen': 'tecnico', 'estado': 'nuevo', 'creado_en': ahora, 'eliminado': True}])
    await db['notas_internas'].insert_one({'ticket_id': filas[0]['_id'], 'cuerpo': 'Nota exclusiva TI', 'autor_nombre': 'Soporte', 'creado_en': ahora})
    filtros = {'zona_id': mundo['zona']['id'], 'fecha_desde': local_date().isoformat(), 'fecha_hasta': local_date().isoformat()}
    archivo = await _exportar(api, mundo['admin'], 'tickets', 'csv', filtros)
    registros = list(csv.DictReader(io.StringIO(archivo.content.decode('utf-8-sig')), delimiter=';'))
    assert len(registros) == 505
    assert registros[-1]['Ticket'] == 'REP-0504'
    assert registros[0]['Tipo de equipo'] == 'Monitor'
    assert registros[0]['Código patrimonial'] == 'PAT-0123'
    assert registros[0]['Resolución'] == '1 hora'
    assert 'Notas internas' not in registros[0]
    excel = await _exportar(api, mundo['admin'], 'tickets', 'excel', filtros, incluir_notas_internas=True)
    assert excel.headers['content-type'].startswith('application/vnd.openxmlformats')
    hoja = load_workbook(io.BytesIO(excel.content)).active
    assert hoja.max_row == 506
    cabeceras = [c.value for c in hoja[1]]
    assert hoja.cell(2, cabeceras.index('Resolución (min)') + 1).value == 60
    assert hoja.cell(2, cabeceras.index('Creado') + 1).number_format == 'dd/mm/yyyy hh:mm'
    assert 'Nota exclusiva TI' in hoja.cell(2, cabeceras.index('Notas internas') + 1).value
    assert hoja.freeze_panes == 'A2' and hoja.auto_filter.ref.endswith('506')


async def test_pdf_horizontal_legible_identifica_equipo_y_filtros(db, api, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'export_dir', str(tmp_path))
    mundo = await _mundo(api, 'pdf-informe')
    ticket = (await api.post('/api/tickets/manual', headers=mundo['tecnico'], json={'persona': {'afectado_id': mundo['tecnico_id']}, 'asunto': 'Equipo de prueba del informe', 'prioridad': 'media', 'activo_id': await equipo_para_persona(api, mundo['admin'], mundo['tecnico_id'], tipo='Monitor')})).json()['ticket']
    archivo = await _exportar(api, mundo['admin'], 'tickets', 'pdf', {'zona_id': mundo['zona']['id'], 'fecha_desde': local_date().isoformat(), 'fecha_hasta': local_date().isoformat()})
    pdf = PdfReader(io.BytesIO(archivo.content))
    assert all(float(p.mediabox.width) > float(p.mediabox.height) for p in pdf.pages)
    texto = '\n'.join(p.extract_text() for p in pdf.pages)
    assert ticket['codigo'] in texto and 'Monitor' in texto
    assert mundo['zona']['nombre'] in texto
    assert mundo['zona']['id'] not in texto
    assert local_date().strftime('%d/%m/%Y') in texto
    assert '{{institucion}}' not in texto
    (tmp_path / 'tickets-informe.pdf').write_bytes(archivo.content)


async def test_inventario_completo_en_hojas_por_zona_y_paginas_pdf(db, api, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'export_dir', str(tmp_path))
    mundo = await _mundo(api, 'inventario-reporte')
    zona2 = (await api.post('/api/zonas', headers=mundo['admin'], json={'nombre': 'Zona Norte'})).json()
    oficina2 = (await api.post('/api/oficinas', headers=mundo['admin'], json={'nombre': 'ALMACEN', 'zona_id': zona2['id']})).json()
    filas = []
    for i in range(102):
        zona, oficina = (mundo['zona'], mundo['oficina']) if i < 101 else (zona2, oficina2)
        filas.append({'tipo': 'Monitor', 'nombre_equipo': f'Monitor {i:03}', 'oficina_id': ObjectId(oficina['id']), 'oficina_nombre': oficina['nombre'], 'zona_id': ObjectId(zona['id']), 'zona_nombre': zona['nombre'], 'campos_estado': {}, 'clave_natural': f'inv-{i}', 'estado': 'Operativo'})
    await db['activos'].insert_many(filas)
    archivo = await _exportar(api, mundo['admin'], 'inventario', 'excel')
    libro = load_workbook(io.BytesIO(archivo.content))
    assert set(libro.sheetnames) == {mundo['zona']['nombre'], zona2['nombre']}
    assert sum(h.max_row - 1 for h in libro) == 102
    for hoja in libro:
        assert hoja.freeze_panes == 'A2'
        assert hoja.page_setup.orientation == 'landscape'
        assert hoja.print_title_rows == '$1:$1'
    pdf = PdfReader(io.BytesIO((await _exportar(api, mundo['admin'], 'inventario', 'pdf')).content))
    assert len(pdf.pages) >= 2
    paginas_por_zona = {nombre: [i for i, p in enumerate(pdf.pages) if nombre in p.extract_text()] for nombre in libro.sheetnames}
    assert all(paginas_por_zona.values())
    assert set(paginas_por_zona[zona2['nombre']]).isdisjoint(paginas_por_zona[mundo['zona']['nombre']])
    assert all(float(p.mediabox.width) > float(p.mediabox.height) for p in pdf.pages)


async def test_auditoria_importante_fecha_final_y_exportacion_coinciden(db, api, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'export_dir', str(tmp_path))
    mundo = await _mundo(api, 'auditoria-reporte')
    dia = local_date() - timedelta(days=3)
    inicio = business_start_of_day(dia)
    await db['auditoria'].insert_many([
        {'fecha': inicio, 'accion': 'activo.editar', 'accion_texto': 'Edición de equipo', 'usuario_nombre': 'Soporte', 'resultado': 'ok', 'resumen': 'CAMBIO IMPORTANTE'},
        {'fecha': inicio + timedelta(days=1) - timedelta(milliseconds=1), 'accion': 'permiso.cambiar', 'resultado': 'ok', 'resumen': 'FIN DEL DIA'},
        {'fecha': inicio + timedelta(days=1), 'accion': 'activo.editar', 'resultado': 'ok', 'resumen': 'DIA SIGUIENTE'},
        {'fecha': inicio, 'accion': 'auth.login', 'resultado': 'ok', 'resumen': 'RUTINA'},
        {'fecha': inicio, 'accion': 'auth.login_fallido', 'resultado': 'fallido', 'resumen': 'ALERTA DE SEGURIDAD'},
    ])
    await db['auditoria'].update_many({'rol': {'$exists': False}}, {'$set': {'rol': 'administrador'}})
    conteo = await db['auditoria'].count_documents({})
    await audit.registrar('ticket.chat', resumen='No duplicar el chat')
    assert await db['auditoria'].count_documents({}) == conteo
    await audit.registrar('activo.editar', antes={'estado': 'Operativo'}, despues={'estado': 'Operativo'})
    assert await db['auditoria'].count_documents({}) == conteo
    await audit.registrar('activo.responsable', resumen='Cambio importante de responsable', rol='administrador')
    assert await db['auditoria'].count_documents({}) == conteo + 1
    vista = await api.get(f'/api/auditoria?desde={dia}&hasta={dia}', headers=mundo['admin'])
    assert vista.status_code == 200, vista.text
    assert vista.json()['total'] == 3
    assert not any(a['clave'] == 'auth.login' for a in vista.json()['acciones'])
    filtrado = await api.get(f'/api/auditoria?desde={dia}&hasta={dia}&accion=activo.editar', headers=mundo['admin'])
    assert filtrado.json()['total'] == 1
    archivo = await _exportar(api, mundo['admin'], 'auditoria', 'csv', {'fecha_desde': str(dia), 'fecha_hasta': str(dia)})
    texto = archivo.content.decode('utf-8-sig')
    assert 'CAMBIO IMPORTANTE' in texto and 'FIN DEL DIA' in texto and 'ALERTA DE SEGURIDAD' in texto
    assert 'RUTINA' not in texto and 'DIA SIGUIENTE' not in texto


async def test_carga_y_analitica_exportan_su_formato_real_y_validan_filtros(db, api, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'export_dir', str(tmp_path))
    mundo = await _mundo(api, 'tipos-reporte')
    await api.post('/api/tickets', headers=mundo['tecnico'], json={'tipo_problema': 'Internet/red', 'urgencia': 'puede_esperar'})
    filtros = {'fecha_desde': local_date().isoformat(), 'fecha_hasta': local_date().isoformat()}
    for formato in ('pdf', 'excel', 'csv'):
        contenido = (await _exportar(api, mundo['admin'], 'carga_equipo', formato, filtros)).content
        assert contenido.startswith(b'%PDF' if formato == 'pdf' else b'PK' if formato == 'excel' else b'\xef\xbb\xbf')
    csv_analitica = await _exportar(api, mundo['admin'], 'analitica', 'csv', filtros)
    assert not csv_analitica.content.startswith(b'PK')
    assert 'Seccion' in csv_analitica.text
    for filtros_invalidos in ({'fecha_desde': 'ayer'}, {'fecha_desde': '2026-10-20', 'fecha_hasta': '2026-10-01'}):
        respuesta = await api.post('/api/exportaciones', headers=mundo['admin'], json={'tipo': 'tickets', 'formato': 'csv', 'filtros': filtros_invalidos})
        assert respuesta.status_code == 422, respuesta.text
    assert (await api.post('/api/exportaciones', headers=mundo['tecnico'], json={'tipo': 'auditoria', 'formato': 'csv'})).status_code == 403


async def test_excel_nombres_de_hoja_seguros_y_celdas_son_datos(db):
    contenido = excel_service.escribir_tablas({'Zona/Norte': [{'Equipo': '=1+1', 'Cantidad': 0}], 'Zona:Norte': [{'Equipo': 'Monitor', 'Cantidad': 1}]})
    libro = load_workbook(io.BytesIO(contenido))
    assert libro.sheetnames == ['Zona Norte', 'Zona Norte (2)']
    assert libro.worksheets[0]['A2'].data_type != 'f'
    assert libro.worksheets[0]['B2'].value == 0
