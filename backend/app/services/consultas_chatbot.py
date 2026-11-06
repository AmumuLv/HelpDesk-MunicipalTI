"""Lecturas acotadas para el chatbot. Sin Mongo arbitrario ni operaciones de escritura."""
import json
import re
import unicodedata
from datetime import date, datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError

from app.core.db import get_db
from app.core.errors import AppError, Prohibido, Validacion
from app.core.time import business_tz
from app.domain.permissions import tiene_permiso
from app.services import analitica_service, ticket_service
from app.services.conocimiento_proyecto import ALCANCE_DIRECTORIO


def ajustar_intencion(argumentos, pregunta):
    """No aceptar un ranking deducido de una página de tickets ni un estado inventado."""
    if not isinstance(argumentos, dict):
        return argumentos
    argumentos = dict(argumentos)
    texto = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if not unicodedata.combining(c))
    ranking_equipo = (re.search(r'equipo|impresora|laptop|computadora', texto)
                      and re.search(r'\bmas\b|mayor|ranking|afectad', texto)
                      and re.search(r'incidencia|ticket|falla|afectad', texto))
    if ranking_equipo and argumentos.get('recurso') in ('tickets', 'ranking_equipos'):
        argumentos['recurso'] = 'ranking_equipos'
    if argumentos.get('recurso') in ('tickets', 'ranking_equipos', 'ranking_oficinas', 'ranking_estados'):
        if not re.search(r'cerrad|finalizad|resuelt|abiert|pendiente|nuevo|progreso|espera', texto):
            argumentos.pop('estado', None)
    return argumentos


def resumen_ranking_equipos(datos):
    """Conservar cifras y cobertura exactas al responder un ranking sencillo."""
    desde, hasta = (datos[c].strftime('%d/%m/%Y') for c in ('desde', 'hasta'))
    items = datos.get('items') or []
    total = datos['total_tickets']
    sin_vinculo = datos['sin_vinculo']
    if not total:
        return f'No hay tickets creados entre el {desde} y el {hasta} con esos filtros.'
    if not items:
        return f'Entre el {desde} y el {hasta} hay {total} tickets, pero ninguno tiene un equipo concreto vinculado. Con esos registros no se puede identificar qué equipo tuvo más incidencias.'
    maximo = items[0]['total']
    empatados = [json.loads(datos_json({'nombre': item.get('nombre') or 'Equipo sin nombre'}))['nombre'] for item in items if item['total'] == maximo]
    nombres = ', '.join(empatados[:4])
    if len(empatados) > 4:
        nombres += f' y otros {len(empatados) - 4} equipos del listado'
    principal = (f'**{nombres}** tiene el mayor número de incidencias: **{maximo}**.' if len(empatados) == 1 else f'**{nombres}** empatan con **{maximo} incidencias por equipo**.')
    cobertura = f'Hay {total} tickets en el rango; {sin_vinculo} no tienen equipo vinculado y no se pueden atribuir a uno concreto.'
    return f'Entre el {desde} y el {hasta}, {principal} {cobertura}'


def resumen_total_equipos(datos, pregunta):
    """Answer only a simple inventory count, from the authorized full total.

    Never infer a total from the limited sample, answer a compound question,
    or turn a denied read into a successful response.
    """
    texto = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if not unicodedata.combining(c))
    total = datos.get('total')
    if (datos.get('error') or datos.get('recurso') != 'equipos'
            or not isinstance(total, int) or isinstance(total, bool) or total < 0):
        return None
    if not re.search(r'\b(?:cuantos equipos(?: activos)? (?:hay|estan registrados)|total (?:actual )?de equipos|cantidad (?:actual )?de equipos)\b', texto):
        return None
    # A deliberately small vocabulary keeps this fast path from answering a
    # historical, conditional or compound request with the current global total.
    permitidas = set('consulta consultar el la los las inventario actual actuales actualmente y dime exactamente cuantos equipos activos hay estan registrados registradas necesito total real no una estimacion estimaciones cantidad numero de en sistema nuestro nuestra mi base datos por favor web proyecto mesa ayuda municipalidad municipal provincial casma'.split())
    if (re.search(r'\d|\bpor\b(?!\s+favor\b)|\bno\b(?!\s+(?:una\s+)?estimaci(?:on|ones)\b)', texto)
            or set(re.findall(r'[a-z]+', texto)) - permitidas):
        return None
    equipo = 'equipo activo registrado' if total == 1 else 'equipos activos registrados'
    return f'Hay **{total} {equipo}** en la consulta actual.'


class Lectura(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recurso: str
    consulta: str = Field(default='', max_length=100)
    desde: date | None = None
    hasta: date | None = None
    estado: str | None = Field(default=None, max_length=30)
    oficina_id: str | None = Field(default=None, max_length=24)
    zona_id: str | None = Field(default=None, max_length=24)
    equipo_id: str | None = Field(default=None, max_length=24)
    conjunto_id: str | None = Field(default=None, max_length=24)
    tecnico_id: str | None = Field(default=None, max_length=24)
    registro_id: str | None = Field(default=None, max_length=24)
    usar_filtros_pagina: bool = True


# Proyección inclusiva: nunca enviar documentos completos, mensajes, notas,
# contraseñas, hashes, tokens, sesiones, correos personales o archivos adjuntos.
RECURSOS = {
    'equipos': ('activos', 'equipos.ver', ['nombre_equipo', 'tipo', 'marca', 'modelo', 'estado', 'codigo_patrimonial', 'serie', 'procesador', 'memoria_ram', 'almacenamiento', 'oficina_nombre', 'zona_nombre', 'responsable_nombre', 'conjunto_nombre'], ['nombre_equipo', 'tipo', 'responsable_nombre', 'oficina_nombre']),
    'conjuntos': ('conjuntos', 'equipos.ver', ['nombre', 'oficina_nombre', 'zona_nombre', 'responsable_nombre'], ['nombre', 'responsable_nombre', 'oficina_nombre']),
    'usuarios': ('usuarios', 'usuarios.ver', ['nombre', 'rol', 'cargo', 'oficina_nombre', 'zona_nombre'], ['nombre', 'oficina_nombre']),
    'oficinas': ('oficinas', 'org.ver', ['nombre', 'zona_nombre'], ['nombre']),
    'zonas': ('zonas', 'org.ver', ['nombre'], ['nombre']),
    'reportes': ('exportaciones', 'exportar', ['tipo', 'estado', 'formato', 'creado_en'], ['tipo']),
    'campanas': ('campanas_inventario', 'equipos.campanas', ['nombre', 'anio', 'estado', 'creado_en'], ['nombre']),
    'ausencias': ('ausencias', 'horarios.ver', ['tecnico_id', 'inicio', 'fin'], []),
    'conocimiento': ('articulos_kb', 'kb.ver', ['titulo', 'categoria', 'resumen', 'visibilidad'], ['titulo', 'categoria']),
}

ESQUEMA = {
    'type': 'function', 'function': {
        'name': 'consultar_sistema',
        'description': 'Consulta datos reales de solo lectura. Usa esta función para cifras, listados y rankings; nunca alegues no tener acceso sin consultar. Tickets y rankings se filtran por fecha de creación, días completos de Lima. Ranking de equipos incluye equipos individuales; conjuntos agrupa la PC. Datos actuales de inventario/directorio no son históricos. Máximo 20 registros por consulta; total es el recuento completo.',
        'parameters': {'type': 'object', 'properties': {
            'recurso': {'type': 'string', 'enum': ['tickets', 'ranking_equipos', 'ranking_oficinas', 'ranking_estados', 'configuracion', *RECURSOS]},
            'consulta': {'type': 'string', 'description': 'Texto literal para buscar nombre, equipo, asunto o código de ticket. Vacío para todos.'},
            'usar_filtros_pagina': {'type': 'boolean', 'description': 'False para una consulta general, de otra sección o si piden ignorar los filtros actuales. True para consultar el contexto visible.'},
            'desde': {'type': 'string', 'description': 'Fecha inicial ISO AAAA-MM-DD. Interpreta fechas en español; hoy usa la fecha local del contexto.'},
            'hasta': {'type': 'string', 'description': 'Fecha final ISO AAAA-MM-DD inclusiva. No inviertas día y mes.'},
            'estado': {'type': 'string', 'enum': ['nuevo', 'en_progreso', 'en_espera', 'cerrado', 'resuelto']},
            **{campo: {'type': 'string', 'description': 'Identificador real obtenido de la ruta de pantalla o de otra consulta; nunca inventarlo. registro_id busca el registro exacto.'} for campo in ('oficina_id', 'zona_id', 'equipo_id', 'conjunto_id', 'tecnico_id', 'registro_id')},
        }, 'required': ['recurso'], 'additionalProperties': False},
    },
}


def serializar(valor):
    if isinstance(valor, datetime):
        return valor.astimezone(business_tz()).strftime('%d/%m/%Y %H:%M')
    if isinstance(valor, date):
        return valor.strftime('%d/%m/%Y')
    return str(valor)


def datos_json(datos):
    # Defensa adicional para texto de campos libres, incluso de nombres/asuntos.
    def limpiar(valor):
        if isinstance(valor, dict):
            return {k: limpiar(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [limpiar(v) for v in valor]
        if isinstance(valor, str):
            valor = re.sub(r'(?i)(?:gsk_|sk-|AIza)[A-Za-z0-9_-]{15,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[credencial omitida]', valor)
            return re.sub(r'(?im)^.*(?:contrase[ñn]a|password|api[_ -]?key|secret|token|clave)\s*[:=].*$', '[dato reservado]', valor)[:350]
        return valor
    return json.dumps(limpiar(datos), default=serializar, ensure_ascii=False)


async def consultar(argumentos, usuario, filtros_pagina=None):
    """Validación independiente de lo que solicite el modelo o envíe el navegador."""
    if usuario.get('rol') not in ('administrador', 'tecnico'):
        raise Prohibido('Solo el equipo TI puede consultar.')
    datos = Lectura.model_validate(argumentos)
    filtros_pagina = filtros_pagina if datos.usar_filtros_pagina else {}
    db = get_db()
    if datos.recurso == 'configuracion':
        if usuario.get('rol') != 'administrador':
            raise Prohibido('La configuración está reservada al administrador.')
        # No llamar config_service.obtener(): puede inicializar un documento.
        doc = await db['configuracion'].find_one({'_id': 'config'}, {
            '_id': 0, 'institucion.nombre': 1, 'negocio.zona_horaria': 1,
            'sla.activo': 1, 'sla.reglas': 1, 'sla.calendario.dias_laborables': 1,
            'sla.calendario.tramos': 1, 'sla.pausa_fuera_de_horario': 1,
            'ia.global_activa': 1, 'ia.recomendaciones_activas': 1,
        })
        return {'recurso': 'configuracion', 'configuracion': doc or {}, 'nota': 'Configuración guardada; solo lectura, sin credenciales.'}
    filtros = {}
    for campo in ('oficina_id', 'zona_id', 'equipo_id', 'conjunto_id', 'tecnico_id', 'registro_id'):
        valor = getattr(datos, campo) or (filtros_pagina or {}).get('activo_id' if campo == 'equipo_id' else campo)
        if valor:
            if not ObjectId.is_valid(valor):
                raise Validacion('El identificador solicitado no es válido.')
            filtros[{'equipo_id': 'activo_id', 'registro_id': '_id'}.get(campo, campo)] = ObjectId(valor)
    if datos.recurso in RECURSOS:
        coleccion, permiso, campos, buscables = RECURSOS[datos.recurso]
        if not tiene_permiso(usuario, permiso):
            raise Prohibido('Tu cuenta no puede consultar este recurso.')
        consulta = {'activo': {'$ne': False}}
        if datos.recurso == 'reportes' and usuario.get('rol') != 'administrador':
            consulta['usuario_id'] = usuario['_id']
        if datos.recurso == 'ausencias':
            if not tiene_permiso(usuario, 'horarios.ver_todos'):
                consulta['tecnico_id'] = usuario['_id']
            elif filtros.get('tecnico_id'):
                consulta['tecnico_id'] = filtros['tecnico_id']
        if '_id' in filtros:
            consulta['_id'] = filtros['_id']
        for campo in ('oficina_id', 'zona_id'):
            if campo in filtros:
                consulta[campo] = filtros[campo]
        if datos.consulta and buscables:
            consulta['$or'] = [{c: {'$regex': re.escape(datos.consulta), '$options': 'i'}} for c in buscables]
        proyeccion = {campo: 1 for campo in campos}
        items = await db[coleccion].find(consulta, proyeccion).sort('_id', -1).limit(20).max_time_ms(5000).to_list(20)
        nota = ALCANCE_DIRECTORIO if datos.recurso == 'usuarios' else 'Registros actuales, no una fotografía histórica.'
        return {'recurso': datos.recurso, 'total': await db[coleccion].count_documents(consulta, maxTimeMS=5000), 'items': items, 'limite': 20, 'nota': nota}
    if datos.recurso not in ('tickets', 'ranking_equipos', 'ranking_oficinas', 'ranking_estados'):
        raise Validacion('Consulta no disponible.')
    if not tiene_permiso(usuario, 'tickets.ver_propios'):
        raise Prohibido('Tu cuenta no puede consultar tickets.')
    # El modelo interpreta la fecha pedida; si no pide otra, hereda el periodo visible.
    pagina = filtros_pagina or {}
    periodo = {'periodo': pagina.get('periodo', '30d')}
    if datos.desde or datos.hasta:
        if not datos.desde or not datos.hasta:
            raise Validacion('Indica las dos fechas del rango.')
        periodo = {'desde': datos.desde, 'hasta': datos.hasta}
    elif pagina.get('desde') and pagina.get('hasta'):
        periodo = {'desde': pagina['desde'], 'hasta': pagina['hasta']}
    desde, hasta, _, _ = analitica_service.resolver_periodo(periodo)
    filtros.update(fecha_desde=desde, fecha_hasta=hasta)
    if datos.estado:
        filtros['estado'] = [datos.estado]
    elif pagina.get('estado'):
        estados = pagina['estado'].split(',')
        if any(e not in {'nuevo', 'en_progreso', 'en_espera', 'cerrado', 'resuelto'} for e in estados):
            raise Validacion('El filtro visible de estados no es válido.')
        filtros['estado'] = estados
    if datos.consulta:
        filtros['texto'] = datos.consulta
    consulta = ticket_service.consulta_listado(filtros, usuario=usuario)
    if '_id' in filtros:
        consulta['_id'] = filtros['_id']
        if not datos.desde and not datos.hasta:
            consulta.pop('creado_en', None)
    total = await db['tickets'].count_documents(consulta, maxTimeMS=5000)
    base = {'recurso': datos.recurso, 'desde': desde, 'hasta': hasta, 'zona_horaria': 'America/Lima', 'total_tickets': total, 'criterio': 'Fecha de creación; incluye ambos días completos', 'filtros': argumentos}
    if 'creado_en' not in consulta:
        base.update(desde=None, hasta=None, criterio='Registro exacto, sin restricción de fecha')
    if datos.recurso == 'tickets':
        campos = ['codigo', 'asunto', 'estado', 'prioridad', 'categoria', 'afectado_nombre', 'tecnico_nombre', 'oficina_nombre', 'activo_nombre', 'conjunto_nombre', 'creado_en']
        base['items'] = await db['tickets'].find(consulta, {c: 1 for c in campos}).sort('creado_en', -1).limit(20).max_time_ms(5000).to_list(20)
        base['lista_parcial'] = total > 20
        base['nota'] = 'Esta lista limitada NO permite calcular rankings. Para saber qué equipo tuvo más incidencias consulta ranking_equipos, que agrega todos los tickets del rango.'
    else:
        campo, nombre = {'ranking_equipos': ('activo_id', 'activo_nombre'), 'ranking_oficinas': ('oficina_id', 'oficina_nombre'), 'ranking_estados': ('estado', 'estado')}[datos.recurso]
        base['sin_vinculo'] = await db['tickets'].count_documents({'$and': [consulta, {campo: None}]}, maxTimeMS=5000)
        cursor = await db['tickets'].aggregate([
            {'$match': {'$and': [consulta, {campo: {'$ne': None}}]}},
            {'$group': {'_id': '$' + campo, 'nombre': {'$first': '$' + nombre}, 'total': {'$sum': 1}}},
            {'$sort': {'total': -1, '_id': 1}}, {'$limit': 20},
        ], maxTimeMS=5000)
        base['items'] = await cursor.to_list(20)
        base['nota'] = 'Cuenta tickets vinculados al recurso; los no vinculados no permiten atribuir una falla a un equipo. No son predicciones.'
    return base


async def ejecutar_seguro(argumentos, usuario, filtros_pagina=None):
    try:
        return await consultar(argumentos, usuario, filtros_pagina)
    except AppError as fallo:
        return {'error': fallo.mensaje}
    except (ValueError, TypeError):
        return {'error': 'Argumentos inválidos. Corrige las fechas, el recurso o los filtros.'}
    except PyMongoError:
        return {'error': 'No se pudo completar la lectura en este momento. No hay datos verificados para esta consulta.'}
