"""Lecturas de conocimiento y auditoría con resultados verificables y acotados.

No abre artículos mediante ``kb.obtener`` (esa operación registra una lectura),
no escribe registros y nunca devuelve el contenido privado de una auditoría.
"""
from __future__ import annotations

import re
from typing import Any

from bson import ObjectId

from app.core.audit import ACCIONES, accion_legible, consulta_movimientos
from app.core.db import agregar, get_db
from app.core.errors import Prohibido, Validacion
from app.core.ids import a_id, clave
from app.core.time import business_tz
from app.domain.permissions import tiene_permiso
from app.services import analitica_service, kb_service

LIMITE = 10


def _tabla(columnas, filas):
    return {'columnas': [{'clave': c, 'titulo': t} for c, t in columnas], 'filas': filas}


def _autorizar(usuario, permiso, *, solo_admin=False):
    if (usuario or {}).get('rol') not in {'tecnico', 'administrador'} or not tiene_permiso(usuario, permiso):
        raise Prohibido('Tu cuenta no tiene permiso para esta consulta.')
    if solo_admin and usuario.get('rol') != 'administrador':
        raise Prohibido('La auditoría está reservada a administradores.')


def _argumentos(argumentos, permitidos):
    if (argumentos is not None and not isinstance(argumentos, dict)) or set(argumentos or {}) - set(permitidos):
        raise Validacion('La consulta contiene argumentos no admitidos.')
    argumentos = argumentos or {}
    for campo in ('periodo_explicito',):
        if campo in argumentos and not isinstance(argumentos[campo], bool):
            raise Validacion('El periodo indicado no es válido.')
    return argumentos


def _sin_filtros(filtros, campos, mensaje):
    if any(filtros.get(campo) not in (None, '') for campo in campos):
        raise Validacion(mensaje)


def _consulta_guias(filtros, usuario, argumentos):
    _autorizar(usuario, 'kb.ver')
    _sin_filtros(filtros, ('oficina_id', 'zona_id', 'tecnico_id', 'tipo_activo', 'equipo_id'),
                 'Las guías no están asignadas a una oficina, zona, técnico ni equipo. Consulta sin esos filtros.')
    if argumentos.get('periodo_explicito') or filtros.get('desde') or filtros.get('hasta'):
        raise Validacion('Las lecturas y valoraciones de guías son acumuladas. No hay una serie histórica de lecturas para calcularlas solo en esas fechas.')
    consulta = {'activo': True, **kb_service._filtro_acceso(usuario)}
    if filtros.get('categoria'):
        if not isinstance(filtros['categoria'], str):
            raise Validacion('La categoría no es válida.')
        consulta['categoria'] = filtros['categoria']
    return consulta


def _unificar_guias(consulta):
    # La misma unificación de títulos/categorías/visibilidad que la pantalla KB.
    return [
        {'$match': consulta}, {'$sort': {'actualizado_en': -1, '_id': -1}},
        {'$group': {'_id': {campo: {'$toLower': {'$trim': {'input': {'$ifNull': [f'${campo}', 'todos' if campo == 'visibilidad' else '']}}}}
                            for campo in ('titulo', 'categoria', 'visibilidad')}, 'articulo': {'$first': '$$ROOT'}}},
        {'$replaceRoot': {'newRoot': '$articulo'}},
    ]


async def guias_consultadas(filtros, argumentos, *, usuario=None):
    argumentos = _argumentos(argumentos, {'periodo_explicito'})
    consulta = _consulta_guias(filtros, usuario, argumentos)
    resultado = await agregar('articulos_kb', _unificar_guias(consulta) + [
        {'$facet': {'items': [
            {'$sort': {'visualizaciones': -1, '_id': -1}}, {'$limit': LIMITE},
            {'$project': {'titulo': 1, 'categoria': 1, 'visualizaciones': {'$ifNull': ['$visualizaciones', 0]}}},
        ], 'conteo': [{'$count': 'total'}]}},
    ])
    bloque = resultado[0] if resultado else {}
    items = bloque.get('items', [])
    total = (bloque.get('conteo') or [{}])[0].get('total', 0)
    filas = [{'guia': f.get('titulo') or 'Sin título', 'categoria': f.get('categoria') or 'Sin categoría',
              'lecturas': f.get('visualizaciones', 0)} for f in items]
    return {'texto': f'Hay {total} guías activas y visibles. Muestro hasta {LIMITE}, ordenadas por sus lecturas acumuladas.'
                    '\n\nLas lecturas no equivalen a problemas resueltos ni al número de visitas repetidas de una persona.',
            'tabla': _tabla([('guia', 'Guía'), ('categoria', 'Categoría'), ('lecturas', 'Lecturas acumuladas')], filas),
            'enlaces': [{'texto': f.get('titulo') or 'Abrir guía', 'href': f"/panel/ayuda/{f['_id']}"} for f in items],
            'alcance': 'Guías activas visibles para tu cuenta', 'periodo_label': 'Lecturas acumuladas',
            'seguimientos': ['¿Qué guías están mejor valoradas?', '¿Qué problemas frecuentes no tienen una guía?']}


async def guias_valoradas(filtros, argumentos, *, usuario=None):
    argumentos = _argumentos(argumentos, {'periodo_explicito'})
    consulta = _consulta_guias(filtros, usuario, argumentos)
    resultado = await agregar('articulos_kb', _unificar_guias(consulta) + [
        {'$lookup': {'from': 'articulos_kb_valoraciones', 'let': {'articulo': '$_id'}, 'pipeline': [
            {'$match': {'$expr': {'$eq': ['$articulo_id', '$$articulo']}}},
            {'$sort': {'fecha': 1, 'formato': 1, '_id': 1}},
            {'$group': {'_id': '$usuario_id', 'util': {'$last': '$util'}}},
            {'$group': {'_id': None, 'votos': {'$sum': 1}, 'utiles': {'$sum': {'$cond': ['$util', 1, 0]}}}},
        ], 'as': 'estadistica'}},
        {'$unwind': '$estadistica'},
        {'$set': {'porcentaje': {'$round': [{'$multiply': [100, {'$divide': ['$estadistica.utiles', '$estadistica.votos']}]}, 1]}}},
        {'$facet': {'items': [
            {'$sort': {'porcentaje': -1, 'estadistica.votos': -1, '_id': -1}}, {'$limit': LIMITE},
            {'$project': {'titulo': 1, 'porcentaje': 1, 'votos': '$estadistica.votos', 'utiles': '$estadistica.utiles'}},
        ], 'conteo': [{'$count': 'total'}]}},
    ])
    bloque = resultado[0] if resultado else {}
    items = bloque.get('items', [])
    total = (bloque.get('conteo') or [{}])[0].get('total', 0)
    filas = [{'guia': f.get('titulo') or 'Sin título', 'porcentaje_util': f['porcentaje'], 'valoraciones': f['votos'],
              'utiles': f['utiles'], 'muestra': 'Pocas valoraciones' if f['votos'] < 5 else '5 o más valoraciones'} for f in items]
    return {'texto': (f'{total} guías activas y visibles tienen valoraciones. Muestro hasta {LIMITE}, ordenadas por el porcentaje de votos útiles.' if total else
                     'No hay valoraciones registradas en las guías activas y visibles. Esto no equivale a una valoración de cero.')
                    + '\n\nUna valoración por persona y guía: se toma su decisión más reciente. Con pocas valoraciones el porcentaje puede ser poco representativo.',
            'tabla': _tabla([('guia', 'Guía'), ('porcentaje_util', 'Utilidad (%)'), ('valoraciones', 'Valoraciones'), ('utiles', 'Votos útiles'), ('muestra', 'Muestra')], filas),
            'enlaces': [{'texto': f.get('titulo') or 'Abrir guía', 'href': f"/panel/ayuda/{f['_id']}"} for f in items],
            'alcance': 'Guías activas visibles para tu cuenta', 'periodo_label': 'Valoraciones acumuladas',
            'suficiente_datos': bool(items), 'seguimientos': ['¿Qué guías son las más consultadas?']}


async def brechas_guias(filtros, argumentos, *, usuario=None):
    _autorizar(usuario, 'analitica.ver')
    _autorizar(usuario, 'kb.ver')
    _argumentos(argumentos, set())
    desde, hasta, _, _ = analitica_service.resolver_periodo(filtros)
    categorias = await agregar('tickets', [
        {'$match': analitica_service._match(filtros, desde, hasta)},
        {'$group': {'_id': '$categoria', 'total': {'$sum': 1}}},
        {'$sort': {'total': -1, '_id': 1}}, {'$limit': 501},
    ])
    guias = await agregar('articulos_kb', [
        {'$match': {'activo': True, **kb_service._filtro_acceso(usuario)}},
        {'$group': {'_id': '$categoria'}}, {'$limit': 501},
    ])
    if len(categorias) > 500 or len(guias) > 500:
        raise Validacion('Hay demasiadas categorías para contrastarlas en una sola consulta. Reduce el periodo o la categoría.')
    cubiertas = {clave(f['_id']) for f in guias if f.get('_id')}
    pendientes = [f for f in categorias if not f.get('_id') or clave(f['_id']) not in cubiertas]
    filas = [{'categoria': f['_id'] or 'Sin clasificar', 'total': f['total'],
              'revision': 'Falta clasificar los tickets' if not f.get('_id') else 'Sin guía activa visible en esta categoría'} for f in pendientes[:20]]
    total = sum(f['total'] for f in categorias)
    return {'texto': f'Se revisaron {total} tickets creados en el periodo. Hay {len(pendientes)} categorías o grupos pendientes; muestro hasta 20.'
                    '\n\nLa comparación usa la categoría registrada. Una guía de otra categoría podría cubrir el problema; esto no analiza su contenido ni confirma la causa de la incidencia.',
            'tabla': _tabla([('categoria', 'Categoría'), ('total', 'Tickets del periodo'), ('revision', 'Qué revisar')], filas),
            'enlaces': [{'texto': 'Revisar la base de conocimiento', 'href': '/panel/conocimiento'}],
            'seguimientos': ['¿Cuáles son las causas más frecuentes?', '¿Qué guías son las más consultadas?']}


async def _equipo_auditoria(filtros, argumentos):
    db = get_db()
    identificador = filtros.get('equipo_id')
    nombre = argumentos.get('equipo')
    if identificador is not None:
        identificador = a_id(identificador)
        if not identificador:
            raise Validacion('El identificador del equipo no es válido.')
        consulta: dict[str, Any] = {'_id': identificador}
    elif isinstance(nombre, str) and 2 <= len(nombre.strip()) <= 160:
        patron = {'$regex': '^' + re.escape(nombre.strip()) + '$', '$options': 'i'}
        consulta = {'$or': [{'nombre_equipo': patron}, {'nombre': patron}, {'codigo_patrimonial': patron}]}
    else:
        raise Validacion('Indica el nombre exacto o código patrimonial del equipo para revisar sus cambios de responsable.')
    for campo in ('oficina_id', 'zona_id'):
        if filtros.get(campo):
            consulta[campo] = filtros[campo]
    encontrados = []
    for coleccion in ('activos', 'conjuntos'):
        encontrados.extend(await db[coleccion].find(consulta, {'nombre': 1, 'nombre_equipo': 1}).limit(2).to_list(2))
    if len(encontrados) != 1:
        raise Validacion('No encontré un equipo único con ese nombre o código. Indica su código patrimonial o precisa la oficina.')
    return encontrados[0]


def _nombre_actor(nombre):
    if not isinstance(nombre, str) or '@' in nombre or re.search(r'password|contrase|token|api[_ -]?key|bearer|clave\s*[:=]', nombre, re.I):
        return 'Cuenta TI'
    return nombre[:160] or 'Cuenta no identificada'


async def _auditoria(filtros, argumentos, usuario, *, responsables=False):
    _autorizar(usuario, 'auditoria.ver', solo_admin=True)
    argumentos = _argumentos(argumentos, {'equipo'} if responsables else set())
    _sin_filtros(filtros, ('categoria', 'tecnico_id', 'tipo_activo'),
                 'La auditoría no admite filtros de categoría de ticket, técnico asignado ni tipo de equipo.')
    if not responsables:
        _sin_filtros(filtros, ('oficina_id', 'zona_id', 'equipo_id'),
                     'La auditoría general no tiene ubicación de todos los eventos. Para un equipo, pide sus cambios de responsable indicando el nombre exacto.')
    desde, hasta, _, _ = analitica_service.resolver_periodo(filtros)
    consulta = consulta_movimientos(desde=desde, hasta=hasta)
    equipo = await _equipo_auditoria(filtros, argumentos) if responsables else None
    if equipo:
        consulta.update({'accion': 'activo.responsable', 'entidad_id': str(equipo['_id'])})
    inicio = consulta['fecha']['$gte'].astimezone(business_tz())
    fin = consulta['fecha'].get('$lt')
    fuera_retencion = bool(fin and fin <= consulta['fecha']['$gte'])
    db = get_db()
    total = await db['auditoria'].count_documents(consulta)
    # Proyección positiva. No se leen resumen, antes/después, contexto, IP o UA.
    documentos = await db['auditoria'].find(consulta, {
        'fecha': 1, 'accion': 1, 'entidad': 1, 'usuario_nombre': 1,
    }).sort([('fecha', -1), ('_id', -1)]).limit(20).to_list(20)
    entidades = {'activo': 'Equipo', 'activos': 'Equipo', 'conjunto': 'Conjunto', 'conjuntos': 'Conjunto',
                 'ticket': 'Ticket', 'usuario': 'Cuenta', 'oficina': 'Oficina', 'zona': 'Zona',
                 'articulo': 'Guía', 'configuracion': 'Configuración', 'importacion': 'Importación',
                 'campana': 'Campaña', 'inventario': 'Inventario', 'permiso': 'Permisos'}
    filas = [{'fecha': f['fecha'].astimezone(business_tz()).strftime('%d/%m/%Y %H:%M') if f.get('fecha') else 'Sin fecha',
              'persona': _nombre_actor(f.get('usuario_nombre')),
              'accion': accion_legible(f.get('accion', ''), f.get('entidad', '')) if f.get('accion') in ACCIONES else 'Otro cambio registrado',
              'entidad': entidades.get(f.get('entidad'), 'Registro del sistema')} for f in documentos]
    rango = f"del {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
    texto = (f'El periodo solicitado ({rango}) queda fuera de los 15 días de auditoría conservados. No puedo reconstruir esos cambios.' if fuera_retencion else
             f'Hay {total} movimientos relevantes conservados para la consulta ({rango}). Muestro hasta 20, del más reciente al más antiguo.')
    texto += f"\n\nLa auditoría conserva 15 días; la lectura disponible empieza el {inicio.strftime('%d/%m/%Y %H:%M')} (hora de Lima) o la fecha inicial solicitada si es posterior. No se muestran valores privados de los cambios."
    if responsables:
        texto += '\n\nSolo se incluyen eventos registrados como cambio de responsable de este equipo; no se infieren cambios de otros flujos sin ese registro.'
    return {'texto': texto, 'tabla': _tabla([('fecha', 'Fecha (Lima)'), ('persona', 'Quién realizó el cambio'), ('accion', 'Acción'), ('entidad', 'Registro afectado')], filas),
            'enlaces': [{'texto': 'Abrir auditoría', 'href': '/panel/auditoria'}],
            'alcance': ('Cambios del equipo identificado' if equipo else 'Movimientos relevantes de administradores y técnicos'),
            'periodo_label': 'Auditoría conservada (máximo 15 días)', 'suficiente_datos': not fuera_retencion}


async def auditoria_cambios(filtros, argumentos, *, usuario=None):
    return await _auditoria(filtros, argumentos, usuario)


async def auditoria_responsables(filtros, argumentos, *, usuario=None):
    return await _auditoria(filtros, argumentos, usuario, responsables=True)


def detectar(pregunta):
    texto = clave(pregunta).lower()
    if re.search(r'quien.*(?:cambio|modifico|asigno).*responsable|cambios? de responsable|historial de responsables', texto):
        encontrado = re.search(r'(?:equipo|dispositivo)\s+[«"“](.+?)[»"”]', pregunta, re.I)
        if not encontrado:
            encontrado = re.search(r'(?:equipo|dispositivo)\s+(.+?)(?:\s+(?:hoy|ayer|esta semana|en la oficina|en la zona|entre|desde)\b|[?!.]|$)', pregunta, re.I)
        argumentos = {'equipo': encontrado[1].strip()} if encontrado else {}
        return 'auditoria_responsables', argumentos
    if re.search(r'auditoria|(?:que|cuales).*cambios.*(?:hubo|hicieron|registr|realiza)|movimientos.*(?:registr|sistema|periodo)', texto):
        return 'auditoria_cambios', {}
    if re.search(r'(?:problemas?|categorias?|incidencias?).*(?:(?:sin|no tienen?|no cuentan con) (?:una )?(?:guia|articulo)|necesitan? (?:una )?guia)|(?:faltan|falta).*guias', texto):
        return 'brechas_guias', {}
    if re.search(r'guias?|articulos?', texto):
        explicito = bool(re.search(r'\b(?:hoy|ayer|este mes|mes pasado|este ano|esta semana|periodo seleccionado|ultimos? \d+ dias|entre \d|desde \d)\b', texto))
        argumentos = {'periodo_explicito': True} if explicito else {}
        if re.search(r'valorad|valoracion|mas utiles|mejor|mas ayudan|me gusta', texto):
            return 'guias_valoradas', argumentos
        if re.search(r'mas (?:consult|leid|visit)|lecturas|mas se (?:leen|consultan)', texto):
            return 'guias_consultadas', argumentos
    return None


CONSULTAS = {
    'guias_consultadas': {
        'funcion': guias_consultadas, 'descripcion': 'Guías activas visibles, ordenadas por lecturas acumuladas, sin registrar nuevas lecturas.',
        'permiso': 'kb.ver', 'esquema': {'type': 'object', 'properties': {'periodo_explicito': {'type': 'boolean'}}},
        'lectura': ('Ordena guías activas y visibles por sus lecturas acumuladas.', 'Abre las guías y revisa si necesitan actualizarse.', 'Las lecturas no miden problemas resueltos ni tienen un desglose histórico por día.'),
        'preguntas': ['¿Qué guías son las más consultadas?'], 'grupo': 'Entender', 'ambito': 'actual',
    },
    'guias_valoradas': {
        'funcion': guias_valoradas, 'descripcion': 'Utilidad de guías según la última valoración por persona, mostrando tamaño de muestra.',
        'permiso': 'kb.ver', 'esquema': {'type': 'object', 'properties': {'periodo_explicito': {'type': 'boolean'}}},
        'lectura': ('Compara el porcentaje de valoraciones útiles, incluyendo cuántas personas valoraron.', 'Revisa especialmente las guías con pocas valoraciones antes de concluir.', 'Una guía sin votos no tiene una valoración de cero. La utilidad percibida no demuestra resolución de tickets.'),
        'preguntas': ['¿Qué guías están mejor valoradas?'], 'grupo': 'Entender', 'ambito': 'actual',
    },
    'brechas_guias': {
        'funcion': brechas_guias, 'descripcion': 'Contrasta categorías de tickets del periodo con categorías de guías activas visibles.',
        'permiso': 'analitica.ver', 'esquema': {'type': 'object', 'properties': {}},
        'lectura': ('Muestra categorías con incidencias y sin guías activas visibles de la misma categoría.', 'Revisa el contenido existente antes de crear una guía para esos problemas.', 'La coincidencia es por categoría normalizada, no por análisis del contenido ni por causa técnica confirmada.'),
        'preguntas': ['¿Qué problemas frecuentes no tienen una guía?'], 'grupo': 'Entender', 'ambito': 'periodo',
    },
    'auditoria_cambios': {
        'funcion': auditoria_cambios, 'descripcion': 'Movimientos relevantes conservados en auditoría, sin payload de cambios ni credenciales.',
        'permiso': 'auditoria.ver', 'solo_admin': True, 'esquema': {'type': 'object', 'properties': {}},
        'lectura': ('Muestra quién realizó cambios relevantes y cuándo, dentro de la auditoría conservada.', 'Abre Auditoría para una revisión autorizada de los movimientos.', 'Solo se conservan 15 días de auditoría; la ausencia de registros antiguos no demuestra que no hubiera cambios.'),
        'preguntas': ['¿Qué cambios se registraron en el periodo?'], 'grupo': 'Entender', 'ambito': 'periodo',
    },
    'auditoria_responsables': {
        'funcion': auditoria_responsables, 'descripcion': 'Actor y fecha de cambios de responsable registrados para un equipo identificado de manera única.',
        'permiso': 'auditoria.ver', 'solo_admin': True, 'esquema': {'type': 'object', 'properties': {'equipo': {'type': 'string', 'minLength': 2, 'maxLength': 160}}},
        'lectura': ('Identifica quién registró un cambio de responsable de un equipo concreto.', 'Indica su nombre exacto, código patrimonial o precisa la oficina si hay coincidencias.', 'Solo se muestran eventos activo.responsable conservados en los últimos 15 días; no se reconstruyen cambios ausentes.'),
        'preguntas': ['¿Quién cambió el responsable de un equipo?'], 'grupo': 'Entender', 'ambito': 'periodo',
    },
}
