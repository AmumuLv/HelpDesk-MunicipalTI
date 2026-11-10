"""Lecturas operativas acotadas para el asistente interno.

Solo devuelve campos publicados en las fichas de TI. No abre el detalle de un
ticket (esa operación marca mensajes como leídos), ni escribe registros.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from app.core.db import agregar, get_db
from app.core.errors import Prohibido, Validacion
from app.core.ids import clave, id_requerido
from app.core.time import local_date, to_utc, utcnow
from app.domain.constants import ESTADOS_CERRADOS
from app.domain.permissions import tiene_permiso
from app.services import analitica_service, horario_service, ticket_service


LIMITE = 10
MAXIMO = 20
MODOS = {'vencidos', 'antiguos', 'sin_asignar', 'sin_equipo', 'reabiertos'}
FILTROS = {'periodo', 'desde', 'hasta', 'oficina_id', 'zona_id', 'tecnico_id', 'equipo_id', 'categoria', 'tipo_activo'}


def _autorizar(usuario, permiso):
    if not usuario or usuario.get('rol') not in {'administrador', 'tecnico'} or not tiene_permiso(usuario, permiso):
        raise Prohibido('Tu cuenta no tiene acceso a esta consulta operativa.')


def _argumentos(argumentos, admitidos):
    if not isinstance(argumentos, dict) or set(argumentos) - set(admitidos):
        raise Validacion('Esta consulta recibió opciones que no admite. Elige una pregunta sugerida.')
    limite = argumentos.get('limite', LIMITE)
    if type(limite) is not int or not 1 <= limite <= MAXIMO:
        raise Validacion(f'Puedes consultar entre 1 y {MAXIMO} resultados a la vez.')
    return limite


def _filtros(filtros):
    if not isinstance(filtros, dict) or set(filtros) - FILTROS:
        raise Validacion('La consulta no admite alguno de los filtros seleccionados.')
    seguros = dict(filtros)
    for campo in ('oficina_id', 'zona_id', 'tecnico_id', 'equipo_id'):
        if seguros.get(campo):
            seguros[campo] = id_requerido(seguros[campo], campo)
    for campo in ('categoria', 'tipo_activo'):
        if seguros.get(campo) and (not isinstance(seguros[campo], str) or len(seguros[campo]) > 150):
            raise Validacion('El filtro de categoría o tipo de equipo no es válido.')
    for campo in ('desde', 'hasta'):
        valor = seguros.get(campo)
        if valor is not None:
            if isinstance(valor, str):
                try:
                    seguros[campo] = date.fromisoformat(valor)
                except ValueError as exc:
                    raise Validacion('Las fechas del periodo no son válidas.') from exc
            elif not isinstance(valor, date) or isinstance(valor, datetime):
                raise Validacion('Las fechas del periodo no son válidas.')
    # El parser conversacional acompaña un rango explícito con su etiqueta
    # legible. Igual que resolver_periodo, las dos fechas prevalecen sobre ella.
    rango_explicito = isinstance(seguros.get('desde'), date) and isinstance(seguros.get('hasta'), date)
    if not rango_explicito and seguros.get('periodo') not in (None, '', '7d', '30d', '90d', '365d', 'mes', 'mes_anterior', 'anio'):
        raise Validacion('Selecciona un periodo válido.')
    return seguros


def _tabla(columnas, filas):
    return {'columnas': [{'clave': clave_, 'titulo': titulo} for clave_, titulo in columnas], 'filas': filas}


def _fecha(dia):
    return dia.strftime('%d/%m/%Y')


def _texto(valor, alternativa='Sin registrar'):
    return str(valor)[:180] if valor is not None and str(valor).strip() else alternativa


async def tickets_pendientes(filtros, argumentos, *, usuario=None):
    _autorizar(usuario, 'tickets.ver_propios')
    limite = _argumentos(argumentos, {'modo', 'limite', 'historial_completo'})
    modo = argumentos.get('modo', 'vencidos')
    if not isinstance(modo, str) or modo not in MODOS:
        raise Validacion('Elige vencidos, antiguos, sin asignar, sin equipo o reabiertos.')
    completo = argumentos.get('historial_completo', False)
    if type(completo) is not bool:
        raise Validacion('Indica si deseas todo el historial con una opción válida.')
    seguros = _filtros(filtros)
    desde, hasta, _, _ = analitica_service.resolver_periodo(seguros)
    # Mantiene el mismo alcance de lectura de la bandeja, sin llamadas de detalle.
    consulta = ticket_service.consulta_listado({}, usuario=usuario)
    consulta.update(analitica_service._match(seguros, desde, hasta))
    if completo:
        consulta.pop('creado_en', None)
    if modo != 'reabiertos':
        consulta['estado'] = {'$nin': list(ESTADOS_CERRADOS)}
    ahora = utcnow()
    orden = [('creado_en', 1), ('_id', 1)]
    if modo == 'vencidos':
        consulta['sla_resolver_en'] = {'$lt': ahora}
        orden = [('sla_resolver_en', 1), ('creado_en', 1), ('_id', 1)]
    elif modo == 'sin_asignar':
        if seguros.get('tecnico_id'):
            raise Validacion('Un listado sin asignar no puede filtrar por un técnico asignado.')
        consulta['tecnico_id'] = None
    elif modo == 'sin_equipo':
        if seguros.get('equipo_id'):
            raise Validacion('Un listado sin equipo no puede filtrar por un equipo específico.')
        consulta['activo_id'] = None
        consulta['conjunto_id'] = None
    elif modo == 'reabiertos':
        consulta['veces_reabierto'] = {'$gt': 0}
        orden = [('veces_reabierto', -1), ('creado_en', 1), ('_id', 1)]
    db = get_db()
    total = await db['tickets'].count_documents(consulta)
    documentos = await db['tickets'].find(consulta, {
        'codigo': 1, 'asunto': 1, 'estado': 1, 'prioridad': 1, 'creado_en': 1,
        'oficina_nombre': 1, 'tecnico_nombre': 1, 'sla_resolver_en': 1,
        'veces_reabierto': 1, 'reportante_id': 1, 'afectado_id': 1,
    }).sort(orden).limit(limite).to_list(limite)
    filas, enlaces = [], []
    for documento in documentos:
        ticket_service._verificar_acceso(documento, usuario)
        creado = documento.get('creado_en')
        filas.append({
            'codigo': _texto(documento.get('codigo'), 'Sin código'),
            'asunto': _texto(documento.get('asunto')),
            'estado': 'cerrado' if documento.get('estado') in ESTADOS_CERRADOS else _texto(documento.get('estado')),
            'oficina': _texto(documento.get('oficina_nombre')),
            'tecnico': _texto(documento.get('tecnico_nombre'), 'Sin asignar'),
            'antiguedad_dias': max(0, (ahora - to_utc(creado)).days) if isinstance(creado, datetime) else None,
            'reaperturas': documento.get('veces_reabierto', 0),
        })
        enlaces.append({'texto': filas[-1]['codigo'], 'href': f"/panel/tickets/{documento['_id']}"})
    etiquetas = {'vencidos': 'con plazo vencido', 'antiguos': 'pendientes, del más antiguo al más reciente',
                 'sin_asignar': 'sin técnico asignado', 'sin_equipo': 'sin dispositivo ni conjunto vinculado',
                 'reabiertos': 'con reaperturas registradas'}
    fechas = 'de todo el historial' if completo else f'creados del {_fecha(desde)} al {_fecha(hasta)}'
    texto = f"Hay {total} tickets {etiquetas[modo]} {fechas}. Muestro {len(filas)} de {total}."
    texto += (' Los reabiertos pueden estar cerrados actualmente; el orden usa la cantidad de reaperturas.'
              if modo == 'reabiertos' else ' Se incluyen únicamente los que siguen abiertos al consultar.')
    if modo == 'vencidos':
        texto += ' Los abiertos sin fecha límite no se consideran vencidos.'
    if modo == 'sin_equipo':
        texto += ' Puede ser intencional: TI identifica el dispositivo cuando corresponde.'
    return {'texto': texto, 'tabla': _tabla([
        ('codigo', 'Ticket'), ('asunto', 'Incidencia'), ('estado', 'Estado actual'), ('oficina', 'Oficina'),
        ('tecnico', 'Técnico'), ('antiguedad_dias', 'Días desde su creación'), ('reaperturas', 'Reaperturas'),
    ], filas), 'enlaces': enlaces, 'total': total, 'mostrados': len(filas),
        'periodo_label': 'Historial completo · estado actual' if completo else f'{_fecha(desde)}–{_fecha(hasta)} · estado actual',
        'seguimientos': ['Muéstrame los tickets sin asignar', 'Muéstrame los tickets más antiguos']}


async def resumen_equipo(filtros, argumentos, *, usuario=None):
    _autorizar(usuario, 'equipo_ti.ver')
    limite = _argumentos(argumentos, {'limite'})
    seguros = _filtros(filtros)
    desde, hasta, _, _ = analitica_service.resolver_periodo(seguros)
    consulta = analitica_service._match(seguros, desde, hasta)
    consulta.setdefault('$and', []).append({'tecnico_id': {'$ne': None}})
    tiempo_valido = {'$and': [{'$isNumber': '$tiempo_resolucion_min'}, {'$gte': ['$tiempo_resolucion_min', 0]}]}
    valoracion_valida = {'$and': [{'$isNumber': '$satisfaccion'}, {'$gte': ['$satisfaccion', 1]}, {'$lte': ['$satisfaccion', 5]}]}
    reapertura_valida = {'$and': [{'$isNumber': '$veces_reabierto'}, {'$gte': ['$veces_reabierto', 0]}]}
    grupos = await agregar('tickets', [
        {'$match': consulta}, {'$group': {
            '_id': '$tecnico_id', 'asignados': {'$sum': 1},
            'cerrados': {'$sum': {'$cond': [{'$in': ['$estado', list(ESTADOS_CERRADOS)]}, 1, 0]}},
            'muestras_tiempo': {'$sum': {'$cond': [tiempo_valido, 1, 0]}},
            'suma_tiempo': {'$sum': {'$cond': [tiempo_valido, '$tiempo_resolucion_min', 0]}},
            'muestras_valoracion': {'$sum': {'$cond': [valoracion_valida, 1, 0]}},
            'suma_valoracion': {'$sum': {'$cond': [valoracion_valida, '$satisfaccion', 0]}},
            'reaperturas': {'$sum': {'$cond': [reapertura_valida, '$veces_reabierto', 0]}},
        }},
    ])
    actual = {**consulta, 'estado': {'$nin': list(ESTADOS_CERRADOS)}}
    actual.pop('creado_en', None)
    pendientes = await agregar('tickets', [{'$match': actual}, {'$group': {'_id': '$tecnico_id', 'total': {'$sum': 1}}}])
    ids = {fila['_id'] for fila in grupos + pendientes}
    consulta_usuarios = {'rol': {'$in': ['administrador', 'tecnico']}, '$or': [{'activo': True}, {'_id': {'$in': list(ids)}}]}
    if seguros.get('tecnico_id'):
        consulta_usuarios['_id'] = seguros['tecnico_id']
    personas = await get_db()['usuarios'].find(consulta_usuarios, {'nombre': 1, 'activo': 1}).to_list(None)
    por_periodo = {fila['_id']: fila for fila in grupos}
    por_actual = {fila['_id']: fila['total'] for fila in pendientes}
    # Los casos ligados a una identidad técnica que ya no existe siguen contados.
    conocidos = {p['_id'] for p in personas}
    personas.extend({'_id': identificador, 'nombre': 'Cuenta técnica no disponible'} for identificador in ids - conocidos)
    personas.sort(key=lambda p: (-por_actual.get(p['_id'], 0), -por_periodo.get(p['_id'], {}).get('asignados', 0), p.get('nombre') or ''))
    filas, enlaces = [], [{'texto': 'Ver equipo TI', 'href': '/panel/equipo-ti'}]
    for persona in personas[:limite]:
        identificador = persona['_id']
        dato = por_periodo.get(identificador, {})
        muestras_t = dato.get('muestras_tiempo', 0)
        muestras_v = dato.get('muestras_valoracion', 0)
        horas = await horario_service.horas_laborables(identificador, desde, hasta)
        filas.append({
            'tecnico': _texto(persona.get('nombre')), 'pendientes_actuales': por_actual.get(identificador, 0),
            'asignados_periodo': dato.get('asignados', 0), 'cerrados': dato.get('cerrados', 0),
            'tiempo_medio_min': round(dato.get('suma_tiempo', 0) / muestras_t, 1) if muestras_t else None,
            'registros_tiempo': muestras_t,
            'satisfaccion': round(dato.get('suma_valoracion', 0) / muestras_v, 2) if muestras_v else None,
            'valoraciones': muestras_v, 'reaperturas': dato.get('reaperturas', 0),
            'horas_programadas': horas, 'muestra': 'Pocos registros' if muestras_t < 3 or muestras_v < 3 else 'Ver muestras',
        })
    texto = f"Resumen de {len(personas)} identidades técnicas; muestro {len(filas)}. Los casos del periodo fueron creados del {_fecha(desde)} al {_fecha(hasta)}."
    texto += '\n\nLos pendientes actuales abarcan todo el historial y respetan los mismos filtros de ubicación, categoría y equipo. Las horas son jornadas programadas descontando ausencias y feriados; no miden trabajo real dedicado a tickets. Sin tiempos o valoraciones se muestra «Sin datos».'
    texto += ' Pocas muestras o casos de distinta complejidad no permiten calificar automáticamente a una persona.'
    return {'texto': texto, 'tabla': _tabla([
        ('tecnico', 'Técnico'), ('pendientes_actuales', 'Pendientes actuales'), ('asignados_periodo', 'Creados en periodo · asignación actual'),
        ('cerrados', 'De ellos, cerrados ahora'), ('tiempo_medio_min', 'Tiempo medio registrado (min)'), ('registros_tiempo', 'Tiempos usados'),
        ('satisfaccion', 'Valoración media /5'), ('valoraciones', 'Valoraciones usadas'), ('reaperturas', 'Reaperturas acumuladas'),
        ('horas_programadas', 'Horas programadas del periodo'), ('muestra', 'Interpretación'),
    ], filas), 'enlaces': enlaces, 'total': len(personas), 'mostrados': len(filas),
        'seguimientos': ['¿Qué técnico está disponible ahora?', '¿Qué técnicos tienen horario mañana?']}


async def horarios_manana(filtros, argumentos, *, usuario=None):
    _autorizar(usuario, 'horarios.ver_todos')
    limite = _argumentos(argumentos, {'limite'})
    seguros = _filtros(filtros)
    if any(seguros.get(campo) for campo in ('oficina_id', 'zona_id', 'categoria', 'tipo_activo', 'equipo_id', 'desde', 'hasta')):
        raise Validacion('La programación de mañana no admite filtros de tickets, oficinas ni otras fechas. Puedes seleccionar un técnico.')
    manana = local_date() + timedelta(days=1)
    calendario = await horario_service.calendario_equipo(manana, manana)
    if seguros.get('tecnico_id'):
        calendario = [fila for fila in calendario if fila['tecnico_id'] == seguros['tecnico_id']]
    calendario.sort(key=lambda fila: (-float(fila.get('horas_disponibles') or 0), fila.get('tecnico_nombre') or ''))
    filas = []
    for fila in calendario[:limite]:
        tramos = fila.get('tramos') or []
        horario = ', '.join(f"{tramo.get('entrada', '?')}–{tramo.get('salida', '?')}" for tramo in tramos)
        estado = 'Ausencia registrada' if fila.get('ausencia') else 'Feriado' if fila.get('feriado') else 'Sin jornada programada' if not tramos else 'Jornada programada'
        filas.append({'tecnico': _texto(fila.get('tecnico_nombre')), 'fecha': _fecha(manana),
                      'horario': horario or 'Sin jornada programada', 'estado': estado,
                      'horas_programadas': round(float(fila.get('horas_disponibles') or 0), 2),
                      'pendientes_hoy': fila.get('carga_pendiente', 0), 'vencimientos': fila.get('vencimientos', 0)})
    texto = f"Programación registrada para mañana, {_fecha(manana)}. Muestro {len(filas)} de {len(calendario)} técnicos."
    texto += '\n\nEs el horario previsto, con ausencias y feriados registrados. No garantiza que el técnico esté libre mañana. Los pendientes son los de hoy; los vencimientos son fechas límite ya registradas. El periodo de tickets seleccionado no cambia esta fecha.'
    return {'texto': texto, 'tabla': _tabla([
        ('tecnico', 'Técnico'), ('fecha', 'Fecha'), ('horario', 'Horario programado'), ('estado', 'Programación'),
        ('horas_programadas', 'Horas programadas'), ('pendientes_hoy', 'Pendientes actuales'), ('vencimientos', 'Vencimientos registrados'),
    ], filas), 'enlaces': [{'texto': 'Ver equipo TI', 'href': '/panel/equipo-ti'}], 'total': len(calendario), 'mostrados': len(filas),
        'periodo_label': f'Programación del {_fecha(manana)}',
        'seguimientos': ['¿Qué técnico está disponible ahora?', '¿Cómo está la carga del equipo TI?']}


CONSULTAS = {
    'tickets_pendientes_detalle': {
        'funcion': tickets_pendientes, 'descripcion': 'Listados acotados de tickets vencidos, antiguos, sin asignar, sin equipo o con reaperturas; códigos, estado, antigüedad y enlaces.',
        'permiso': 'tickets.ver_propios', 'grupo': 'Tickets', 'ambito': 'periodo',
        'esquema': {'type': 'object', 'additionalProperties': False, 'properties': {
            'modo': {'type': 'string', 'enum': sorted(MODOS)}, 'limite': {'type': 'integer', 'minimum': 1, 'maximum': MAXIMO},
            'historial_completo': {'type': 'boolean'},
        }},
        'lectura': ('Lista tickets que cumplen el filtro y muestra cuántos existen en total.', 'Abre el código del ticket para revisar el caso con sus datos completos.', 'El estado se consulta ahora. Por defecto limita la creación al periodo; «historial completo» quita ese límite. Reaperturas puede incluir casos ya cerrados.'),
        'preguntas': ['Muéstrame los tickets vencidos', 'Muéstrame los tickets más antiguos', 'Muéstrame los tickets sin asignar', 'Muéstrame los tickets sin equipo vinculado', 'Muéstrame los tickets con reaperturas'],
    },
    'resumen_equipo_ti': {
        'funcion': resumen_equipo, 'descripcion': 'Carga actual y métricas del periodo por técnico, con tamaños de muestra, reaperturas y horas programadas; no mide horas realmente trabajadas.',
        'permiso': 'equipo_ti.ver', 'grupo': 'Equipo TI', 'ambito': 'periodo',
        'esquema': {'type': 'object', 'additionalProperties': False, 'properties': {'limite': {'type': 'integer', 'minimum': 1, 'maximum': MAXIMO}}},
        'lectura': ('Distingue los pendientes actuales de los tickets creados en el periodo y sus métricas.', 'Revisa los tamaños de muestra, la complejidad del trabajo y los horarios antes de distribuir casos.', 'Las horas programadas no son tiempo efectivo de atención. Una muestra pequeña no permite valorar el desempeño de una persona.'),
        'preguntas': ['¿Cómo está la carga del equipo TI?', '¿Qué tiempos, valoraciones y reaperturas tiene cada técnico?'],
    },
    'horarios_manana': {
        'funcion': horarios_manana, 'descripcion': 'Horarios programados para mañana, ausencias sin motivos privados y vencimientos conocidos; no predice disponibilidad.',
        'permiso': 'horarios.ver_todos', 'grupo': 'Equipo TI', 'ambito': 'actual',
        'esquema': {'type': 'object', 'additionalProperties': False, 'properties': {'limite': {'type': 'integer', 'minimum': 1, 'maximum': MAXIMO}}},
        'lectura': ('Consulta la programación de mañana y los vencimientos ya registrados para esa fecha.', 'Confirma los cambios de horario y la carga antes de asignar una incidencia.', 'No garantiza disponibilidad futura; no publica motivos privados de ausencia ni predice casos nuevos.'),
        'preguntas': ['¿Qué técnicos tienen horario mañana?'],
    },
}


def detectar(pregunta):
    texto = clave(pregunta).lower()
    if re.search(r'\bmanana\b', texto) and re.search(r'tecnic|equipo ti|horario|jornada|turno|disponib', texto):
        return 'horarios_manana', {}
    if re.search(r'tecnic|equipo ti', texto) and re.search(r'carga|reapertur|valoraciones|tiempos.*cada|mas pendientes|rendimiento detallado', texto):
        return 'resumen_equipo_ti', {}
    if not re.search(r'ticket|caso|incidencia|pendiente', texto):
        return None
    opciones = {'historial_completo': True} if re.search(r'historial completo|sin limitar (?:por )?fecha|todos los pendientes', texto) else {}
    modo = None
    if re.search(r'sin asignar|sin tecnico|no tienen tecnico|sin responsable', texto):
        modo = 'sin_asignar'
    elif re.search(r'sin equipo|sin dispositivo|equipo sin identificar|sin identificar (?:el )?equipo|no tienen equipo', texto):
        modo = 'sin_equipo'
    elif re.search(r'reabiert|reapertur|reabrieron|volvieron a abrir', texto):
        modo = 'reabiertos'
    elif re.search(r'mas antiguos|mas tiempo|antiguedad|hace mas tiempo', texto):
        modo = 'antiguos'
    elif re.search(r'muestr|lista|listar|dame|ver ', texto) and re.search(r'vencid|atrasad|fuera de plazo', texto):
        modo = 'vencidos'
    return ('tickets_pendientes_detalle', {'modo': modo, **opciones}) if modo else None
