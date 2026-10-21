"""Datos y presentación de informes: filas completas, filtros comunes y alcance explícito."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from app.core.audit import accion_legible, consulta_movimientos
from app.core.db import get_db
from app.core.errors import Validacion
from app.core.ids import id_requerido
from app.core.time import business_tz, local_date
from app.services import analitica_service, excel_service, inventario_service, pdf_service, ticket_service


async def preparar_filtros(tipo: str, originales: dict[str, Any]) -> dict[str, Any]:
    filtros = {k: v for k, v in originales.items() if v not in (None, '', [], {})}
    for campo in ('desde', 'hasta', 'fecha_desde', 'fecha_hasta'):
        if campo in filtros:
            try:
                valor = filtros[campo]
                filtros[campo] = valor if isinstance(valor, date) else date.fromisoformat(valor)
            except (ValueError, TypeError):
                raise Validacion('Las fechas del reporte no son válidas.')
    desde = filtros.get('fecha_desde') or filtros.get('desde')
    hasta = filtros.get('fecha_hasta') or filtros.get('hasta')
    if desde and hasta and hasta < desde:
        raise Validacion('La fecha final debe ser igual o posterior a la inicial.')
    for campo in ('zona_id', 'oficina_id', 'tecnico_id', 'activo_id', 'responsable_id', 'usuario_id', 'campana_id', 'equipo_id'):
        if campo in filtros:
            filtros[campo] = id_requerido(filtros[campo], campo.removesuffix('_id'))
    if tipo == 'tickets':
        filtros['fecha_desde'], filtros['fecha_hasta'] = desde, hasta
        for campo in ('estado', 'prioridad', 'categoria', 'origen'):
            if isinstance(filtros.get(campo), str):
                filtros[campo] = [filtros[campo]]
    elif tipo in {'analitica', 'carga_equipo', 'auditoria'}:
        filtros['desde'], filtros['hasta'] = desde, hasta
        if tipo != 'auditoria' and bool(desde) != bool(hasta):
            raise Validacion('Indica las dos fechas del periodo.')
    db = get_db()
    zona = await db['zonas'].find_one({'_id': filtros['zona_id']}) if filtros.get('zona_id') else None
    oficina = await db['oficinas'].find_one({'_id': filtros['oficina_id']}) if filtros.get('oficina_id') else None
    if filtros.get('zona_id') and not zona:
        raise Validacion('La zona seleccionada ya no existe.')
    if filtros.get('oficina_id') and not oficina:
        raise Validacion('La oficina seleccionada ya no existe.')
    if zona and oficina and oficina.get('zona_id') != zona['_id']:
        raise Validacion('La oficina no pertenece a la zona seleccionada.')
    if zona:
        filtros['_zona_nombre'] = zona['nombre']
    if oficina:
        filtros['_oficina_nombre'] = oficina['nombre']
    return filtros


def valor_excel(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.astimezone(business_tz()).replace(tzinfo=None)
    return valor


def texto_filtros(filtros: dict[str, Any], *, inventario: bool = False) -> str:
    partes = []
    desde = filtros.get('fecha_desde') or filtros.get('desde')
    hasta = filtros.get('fecha_hasta') or filtros.get('hasta')
    if inventario:
        partes.append(f'Situación actual al {local_date():%d/%m/%Y}')
    elif desde or hasta:
        partes.append(f"Periodo: {desde.strftime('%d/%m/%Y') if desde else 'sin inicio'} al {hasta.strftime('%d/%m/%Y') if hasta else 'sin fin'}")
    else:
        partes.append('Todo el historial' if not filtros.get('periodo') else f"Periodo: {filtros['periodo']}")
    partes.append(f"Zona: {filtros.get('_zona_nombre') or 'todas'}")
    partes.append(f"Oficina: {filtros.get('_oficina_nombre') or 'todas'}")
    for campo, etiqueta in (('estado', 'Estado'), ('tipo', 'Tipo'), ('accion', 'Acción')):
        if filtros.get(campo):
            valor = filtros[campo]
            partes.append(f"{etiqueta}: {', '.join(valor) if isinstance(valor, list) else valor}")
    return ' · '.join(partes)


def archivo_tabular(filas: list[dict[str, Any]], columnas: list[str], formato: str, nombre: str) -> bytes:
    if formato == 'csv':
        fechas = [{k: v.strftime('%d/%m/%Y %H:%M') if isinstance(v, datetime) else v.strftime('%d/%m/%Y') if isinstance(v, date) else v for k, v in fila.items()} for fila in filas]
        return excel_service.a_csv(fechas, columnas)
    return excel_service.escribir_tablas({nombre: filas}, {nombre: columnas})


async def tickets(filtros: dict[str, Any], formato: str, usuario: dict[str, Any], *, incluir_notas: bool = False) -> bytes:
    db = get_db()
    consulta = ticket_service.consulta_listado(filtros, usuario=usuario)
    items = await db['tickets'].find(consulta).sort([('creado_en', 1), ('_id', 1)]).to_list(None)
    ids = list({i['activo_id'] for i in items if i.get('activo_id')})
    equipos = {e['_id']: e for e in await db['activos'].find({'_id': {'$in': ids}}, {'tipo': 1, 'nombre_equipo': 1, 'codigo_patrimonial': 1, 'marca': 1, 'modelo': 1}).to_list(None)} if ids else {}
    notas: dict[Any, list[str]] = defaultdict(list)
    if incluir_notas:
        for nota in await db['notas_internas'].find({'ticket_id': {'$in': [i['_id'] for i in items]}}).sort('creado_en', 1).to_list(None):
            notas[nota['ticket_id']].append(f"{pdf_service._formatear_fecha(nota.get('creado_en'))} · {nota.get('autor_nombre') or 'TI'}: {nota.get('cuerpo') or ''}")
    filas = []
    for i in items:
        equipo = equipos.get(i.get('activo_id'), {})
        fila = {
            'Ticket': i.get('codigo'), 'Asunto': i.get('asunto'),
            'Zona': i.get('zona_nombre') or 'Sin zona', 'Oficina': i.get('oficina_nombre') or 'Sin oficina',
            'Tipo de equipo': i.get('activo_tipo') or equipo.get('tipo') or 'Sin equipo registrado',
            'Equipo': i.get('activo_nombre') or equipo.get('nombre_equipo') or 'Sin equipo vinculado',
            'Código patrimonial': equipo.get('codigo_patrimonial') or 'Sin código', 'Conjunto': i.get('conjunto_nombre'),
            'Estado': pdf_service.ETIQUETAS_ESTADO.get(i.get('estado'), i.get('estado')),
            'Prioridad': pdf_service.ETIQUETAS_PRIORIDAD.get(i.get('prioridad'), i.get('prioridad')),
            'Categoría': i.get('categoria'), 'Problema': i.get('tipo_problema'),
            'Persona afectada': i.get('afectado_nombre'), 'Reportado por': i.get('reportante_nombre'),
            'Técnico': i.get('tecnico_nombre') or 'Sin asignar',
            'Creado': valor_excel(i.get('creado_en')), 'Cerrado': valor_excel(i.get('cerrado_en') or i.get('resuelto_en')),
            'Resolución': pdf_service._formatear_minutos(i.get('tiempo_resolucion_min')),
            'Resolución (min)': i.get('tiempo_resolucion_min'),
            'Incumplió SLA': 'Sí' if i.get('sla_incumplido') else 'No', 'Satisfacción (1–5)': i.get('satisfaccion'),
        }
        if incluir_notas:
            fila['Notas internas'] = '\n'.join(notas[i['_id']])
        filas.append(fila)
    columnas = ['Ticket', 'Asunto', 'Zona', 'Oficina', 'Tipo de equipo', 'Equipo', 'Código patrimonial', 'Conjunto', 'Estado', 'Prioridad', 'Categoría', 'Problema', 'Persona afectada', 'Reportado por', 'Técnico', 'Creado', 'Cerrado', 'Resolución', 'Resolución (min)', 'Incumplió SLA', 'Satisfacción (1–5)']
    if incluir_notas:
        columnas.append('Notas internas')
    if formato != 'pdf':
        return archivo_tabular(filas, columnas, formato, 'Tickets')
    tablas = [{
        'titulo': 'Detalle completo de tickets',
        'cabeceras': ['Ticket / asunto', 'Equipo', 'Zona / oficina', 'Persona / técnico', 'Estado / prioridad', 'Fechas', 'Tiempo'],
        'anchos': [20, 18, 17, 15, 10, 12, 8],
        'filas': [[f"{f['Ticket']}\n{f['Asunto']}", f"{f['Tipo de equipo']}\n{f['Equipo']}\nPatrimonio: {f['Código patrimonial']}", f"{f['Zona']}\n{f['Oficina']}", f"{f['Persona afectada'] or 'Sin persona'}\nTI: {f['Técnico']}", f"{f['Estado']}\n{f['Prioridad']}", f"Alta: {pdf_service._formatear_fecha(f['Creado']).split(' ')[0]}\nCierre: {pdf_service._formatear_fecha(f['Cerrado']).split(' ')[0]}", f['Resolución']] for f in filas],
        'vacio': 'No hay tickets que cumplan los filtros.',
    }]
    if incluir_notas:
        tablas.append({'titulo': 'Notas internas · uso exclusivo del equipo TI', 'cabeceras': ['Ticket', 'Notas'], 'anchos': [20, 80],
                       'filas': [[f['Ticket'], f['Notas internas']] for f in filas if f['Notas internas']]})
    return await pdf_service.informe_consolidado(titulo='Informe de tickets', subtitulo='Casos creados en el periodo indicado',
        kpis=[('Total', len(items)), ('Cerrados', sum(i.get('estado') == 'cerrado' for i in items)), ('Abiertos', sum(i.get('estado') != 'cerrado' for i in items))],
        tablas=tablas, filtros_texto=texto_filtros(filtros), generado_por=usuario.get('nombre', ''))


async def inventario(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    consulta = {**filtros, 'pagina': 1, 'por_pagina': 100, 'orden': 'ubicacion'}
    datos = await inventario_service.listar(consulta)
    items = list(datos['items'])
    for pagina in range(2, datos['total_paginas'] + 1):
        items.extend((await inventario_service.listar({**consulta, 'pagina': pagina}))['items'])
    if formato == 'pdf':
        return await pdf_service.inventario(items, generado_por=usuario.get('nombre', ''), filtros_texto=texto_filtros(filtros, inventario=True))
    campos = [('Zona', 'zona_nombre'), ('Oficina', 'oficina_nombre'), ('Conjunto', 'conjunto_nombre'), ('Tipo de equipo', 'tipo'), ('Equipo', 'nombre_equipo'),
              ('Código patrimonial', 'codigo_patrimonial'), ('Marca', 'marca'), ('Modelo', 'modelo'), ('Estado', 'estado'), ('Responsable', 'responsable_nombre'),
              ('Procesador', 'procesador'), ('RAM', 'memoria_ram'), ('Almacenamiento', 'almacenamiento'), ('IP', 'direccion_ip'), ('MAC', 'direccion_mac'), ('Propiedad', 'propiedad'), ('Datos completos (%)', 'completitud'), ('Datos faltantes', 'faltantes')]
    columnas = [etiqueta for etiqueta, _ in campos]
    filas = [{etiqueta: i.get(campo) for etiqueta, campo in campos} for i in items]
    for f in filas:
        f['Zona'] = f['Zona'] or 'Sin zona'
        f['Oficina'] = f['Oficina'] or 'Sin oficina'
        f['Responsable'] = f['Responsable'] or 'Uso común'
    if formato == 'csv':
        return archivo_tabular(filas, columnas, formato, 'Inventario')
    hojas: dict[str, list[dict[str, Any]]] = {}
    for fila in filas:
        hojas.setdefault(fila['Zona'], []).append(fila)
    if not hojas:
        hojas['Inventario'] = []
    return excel_service.escribir_tablas(hojas, {nombre: columnas for nombre in hojas})


async def carga_equipo(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    datos = await analitica_service.carga_tecnicos(filtros)
    desde, hasta, _, _ = analitica_service.resolver_periodo(filtros)
    filas = [{
        'Técnico': t['tecnico'], 'Casos del periodo': t['asignados'], 'Finalizados de esos casos': t['resueltos'],
        'Pendientes actuales': t['carga_actual'], 'Disponibilidad actual': t['disponibilidad'] or 'No aplica',
        'Resolución media': pdf_service._formatear_minutos(t['tiempo_medio_resolucion_min']),
        'Resolución media (min)': t['tiempo_medio_resolucion_min'], 'Horas laborables': t['horas_laborables'],
        'Cerrados por hora': t['tickets_por_hora'],
    } for t in datos['items'] if t['asignados'] or t['carga_actual']]
    columnas = ['Técnico', 'Casos del periodo', 'Finalizados de esos casos', 'Pendientes actuales', 'Disponibilidad actual', 'Resolución media', 'Resolución media (min)', 'Horas laborables', 'Cerrados por hora']
    if formato != 'pdf':
        return archivo_tabular(filas, columnas, formato, 'Equipo TI')
    columnas_pdf = ['Técnico', 'Casos del periodo', 'Finalizados de esos casos', 'Pendientes actuales', 'Disponibilidad actual', 'Resolución media']
    return await pdf_service.informe_consolidado(titulo='Informe del equipo TI', subtitulo='Casos creados en el periodo y carga actual al generar el informe',
        kpis=[('Técnicos con casos del periodo', sum(t['tecnico_id'] is not None and bool(t['asignados']) for t in datos['items'])), ('Casos del periodo', sum(t['asignados'] for t in datos['items']))],
        tablas=[{'titulo': 'Carga y atención', 'descripcion': 'Casos creados dentro del periodo, agrupados por el técnico asignado actualmente. Finalizados indica cuántos de esos casos están cerrados al generar el informe; no mide todos los cierres realizados en esas fechas. Los pendientes actuales abarcan todo el historial del técnico, sin limitarse a la zona u oficina elegidas.', 'cabeceras': columnas_pdf, 'filas': [[f[c] for c in columnas_pdf] for f in filas]}],
        filtros_texto=texto_filtros({**filtros, 'desde': desde, 'hasta': hasta}), generado_por=usuario.get('nombre', ''))


async def auditoria(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    consulta = consulta_movimientos(desde=filtros.get('desde'), hasta=filtros.get('hasta'), accion=filtros.get('accion'), entidad=filtros.get('entidad'), usuario_id=filtros.get('usuario_id'), resultado=filtros.get('resultado'))
    entradas = await get_db()['auditoria'].find(consulta).sort([('fecha', 1), ('_id', 1)]).to_list(None)
    filas = [{'Fecha': valor_excel(e.get('fecha')), 'Persona': e.get('usuario_nombre') or 'Sistema', 'Rol': e.get('rol'),
              'Acción': accion_legible(e.get('accion', ''), e.get('entidad', '')), 'Entidad': e.get('entidad'), 'Identificador': e.get('entidad_id'),
              'Resultado': e.get('resultado'), 'Detalle': e.get('resumen') or 'Sin detalle registrado'} for e in entradas]
    columnas = ['Fecha', 'Persona', 'Rol', 'Acción', 'Entidad', 'Identificador', 'Resultado', 'Detalle']
    if formato != 'pdf':
        return archivo_tabular(filas, columnas, formato, 'Auditoría')
    return await pdf_service.informe_consolidado(titulo='Informe de movimientos importantes', subtitulo='Cambios en cuentas, permisos, inventario, tickets y seguridad',
        kpis=[('Movimientos', len(filas))], tablas=[{'titulo': 'Registro cronológico', 'cabeceras': ['Fecha', 'Persona', 'Acción', 'Entidad', 'Detalle'], 'anchos': [13, 17, 20, 12, 38],
        'filas': [[pdf_service._formatear_fecha(f['Fecha']), f['Persona'], f['Acción'], f['Entidad'], f['Detalle']] for f in filas]}],
        filtros_texto=texto_filtros(filtros), generado_por=usuario.get('nombre', ''))
