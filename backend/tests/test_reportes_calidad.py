"""Archivos reales de los nueve reportes, con datos ficticios y almacenamiento temporal."""
import csv
import io
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from openpyxl import load_workbook
from pypdf import PdfReader

from app.core.config import settings
from app.core.time import local_date
from app.services import export_service
from tests.conftest import equipo_para_persona
from tests.test_gobernanza_y_reportes import _mundo
from tests.test_reportes_flujos import _exportar


PRINCIPALES = ('tickets', 'inventario', 'carga_equipo', 'analitica', 'auditoria')


def comprobar_archivo(respuesta, formato, *, horizontal=False):
    if formato == 'pdf':
        pdf = PdfReader(io.BytesIO(respuesta.content))
        texto = '\n'.join(p.extract_text() for p in pdf.pages)
        assert 'MESA DE AYUDA' in texto
        assert 'Generado el' in texto
        assert pdf.metadata.title
        if horizontal:
            assert all(float(p.mediabox.width) > float(p.mediabox.height) for p in pdf.pages)
        return texto
    if formato == 'excel':
        libro = load_workbook(io.BytesIO(respuesta.content))
        assert libro.sheetnames
        for hoja in libro:
            assert hoja.max_column >= 2
            assert hoja.freeze_panes == 'A2'
            assert hoja.auto_filter.ref
        return libro
    filas = list(csv.reader(io.StringIO(respuesta.content.decode('utf-8-sig')), delimiter=';'))
    assert filas and len(filas[0]) >= 2
    assert all(len(f) == len(filas[0]) for f in filas)
    return filas


@pytest.mark.parametrize('tipo', (*PRINCIPALES, 'pendientes_calidad', 'equipo', 'ticket_individual', 'campana'))
async def test_cada_reporte_descarga_archivos_validos(db, api, monkeypatch, tmp_path, tipo):
    monkeypatch.setattr(settings, 'export_dir', str(tmp_path))
    mundo = await _mundo(api, 'calidad-' + tipo)
    formatos = ('pdf',) if tipo == 'ticket_individual' else ('pdf', 'excel', 'csv')
    filtros = {'fecha_desde': local_date().isoformat(), 'fecha_hasta': local_date().isoformat()}
    cabeceras_vacias = None
    if tipo in PRINCIPALES:
        for formato in formatos:
            vacio = await _exportar(api, mundo['admin'], tipo, formato, filtros)
            resultado = comprobar_archivo(vacio, formato, horizontal=formato == 'pdf')
            if tipo == 'tickets' and formato == 'csv':
                cabeceras_vacias = resultado[0]
    equipo_id = await equipo_para_persona(api, mundo['admin'], mundo['tecnico_id'])
    ticket = await api.post('/api/tickets/manual', headers=mundo['admin'], json={
        'persona': {'afectado_id': mundo['tecnico_id']}, 'activo_id': equipo_id,
        'asunto': 'Incidencia ficticia para validar documentos', 'prioridad': 'media',
    })
    assert ticket.status_code == 201, ticket.text
    extras = {}
    if tipo == 'equipo':
        filtros = {'activo_id': equipo_id}
    elif tipo == 'ticket_individual':
        extras = {'ids': [ticket.json()['ticket']['id']]}
        filtros = {}
    elif tipo == 'campana':
        dia = local_date()
        campana = await api.post('/api/campanas', headers=mundo['admin'], json={
            'nombre': 'Verificación ficticia', 'anio': dia.year,
            'fecha_inicio': f'{dia.year}-01-01', 'fecha_fin': f'{dia.year}-12-31',
        })
        assert campana.status_code == 201, campana.text
        filtros = {'campana_id': campana.json()['id']}
        await db.campana_items.insert_one({
            'campana_id': ObjectId(campana.json()['id']), 'activo_id': ObjectId(equipo_id),
            'activo_nombre': 'CPU ficticio', 'activo_tipo': 'CPU', 'estado_item': 'verificado',
        })
    for formato in formatos:
        archivo = await _exportar(api, mundo['admin'], tipo, formato, filtros, **extras)
        resultado = comprobar_archivo(archivo, formato, horizontal=tipo in PRINCIPALES or tipo == 'pendientes_calidad')
        if tipo == 'tickets' and formato == 'csv':
            assert resultado[0] == cabeceras_vacias
            assert ticket.json()['ticket']['codigo'] in archivo.text
        if tipo == 'campana' and formato == 'pdf':
            assert 'CPU ficticio' in resultado
        if tipo == 'pendientes_calidad' and formato == 'pdf':
            assert 'Situación actual' in resultado
            assert 'Código patrimonial' in resultado
            assert 'codigo_patrimonial' not in resultado


async def test_resumen_pdf_incluye_todas_las_oficinas_y_solo_atencion(db, monkeypatch):
    panel = {
        'kpis': {'tickets_analizados': 21, 'tickets_periodo_anterior': 0, 'variacion': None,
                 'tiempo_medio_resolucion_min': None, 'cumplimiento_sla': None, 'satisfaccion_promedio': None,
                 'periodo': {'desde': '2026-10-01', 'hasta': '2026-10-21'}},
        'ranking_oficinas': {'items': [{'oficina': f'OFICINA FICTICIA {i:02}', 'zona': 'Zona ficticia', 'total': 1,
                                       'por_equipo': 1, 'por_usuario': 1, 'criticas': 0} for i in range(1, 22)]},
        'riesgo_sla_categoria': {'items': [{'nombre': 'Hardware', 'total': 7, 'seguro': 1, 'atencion': 1, 'critico': 4, 'vencidos': 3, 'sin_plazo': 1}]}, 'carga_tecnicos': {'items': []},
        'ranking_zonas': {'items': []}, 'causas': {'items': []},
    }
    monkeypatch.setattr(export_service.analitica_service, 'panel_completo', AsyncMock(return_value=panel))
    render = export_service.pdf_service.informe_consolidado
    observado = {}
    async def capturar(**datos):
        observado.update(datos)
        return await render(**datos)
    monkeypatch.setattr(export_service.pdf_service, 'informe_consolidado', capturar)
    contenido = await export_service._generar_analitica({}, 'pdf', {'nombre': 'TI ficticio'})
    texto = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(contenido)).pages)
    assert 'Resumen de atención de tickets' in texto
    for i in range(1, 22):
        assert f'OFICINA FICTICIA {i:02}' in texto
    assert 'Confianza media' not in texto and 'Calidad de recomendaciones de IA' not in texto
    plazos = next(t for t in observado['tablas'] if t['titulo'] == 'Estado de los plazos por categoría')
    fila = plazos['filas'][0]
    assert fila == ['Hardware', 7, 1, 1, 1, 3, 1]
    assert sum(fila[2:]) == fila[1], 'Los vencidos no se cuentan otra vez como casos por vencer'


async def test_campana_exporta_todas_las_paginas(monkeypatch):
    monkeypatch.setattr(export_service.campana_service, 'obtener', AsyncMock(return_value={'anio': 2026}))
    filas = [{'activo_nombre': f'Equipo ficticio {i}'} for i in range(2001)]
    paginas = AsyncMock(side_effect=[{'items': filas[:2000], 'total_paginas': 2}, {'items': filas[2000:]}])
    monkeypatch.setattr(export_service.campana_service, 'items', paginas)
    contenido = await export_service._generar_campana(ObjectId(), 'csv', {'nombre': 'TI ficticio'})
    resultado = list(csv.reader(io.StringIO(contenido.decode('utf-8-sig')), delimiter=';'))
    assert len(resultado) == 2002
    assert 'Equipo ficticio 2000' in contenido.decode('utf-8-sig')


async def test_ficha_no_corta_ni_escapa_dos_veces_detalles(db):
    from app.services import pdf_service
    detalle = ('Detalle técnico ficticio. ' * 30) + 'FIN DEL DETALLE & revisión <completa>'
    contenido = await pdf_service.ficha_equipo({
        'tipo': 'CPU', 'nombre_equipo': 'Equipo ficticio', 'campos': {},
        'opciones_avanzadas': True, 'detalle_avanzado': {'observaciones': detalle},
    }, generado_por='TI ficticio')
    texto = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(contenido)).pages)
    assert 'FIN DEL DETALLE & revisión <completa>' in ' '.join(texto.split())
    assert '&amp;' not in texto
