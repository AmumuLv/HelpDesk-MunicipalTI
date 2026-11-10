"""Consultas internas explicables: cifras reproducibles, sin proveedor externo.

No ejecuta instrucciones ni consultas MongoDB aportadas por el usuario.
Los permisos se comprueban en analitica_chat.ejecutar_herramienta.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any
from bson import ObjectId

from app.core.db import agregar, get_db
from app.core.ids import clave
from app.core.errors import Validacion
from app.services import analitica_service


async def resumen(filtros, argumentos):
    filtros = {**filtros, **(argumentos or {})}
    datos = await analitica_service.kpis(filtros)
    _, _, anterior_desde, anterior_hasta = analitica_service.resolver_periodo(filtros)
    return {**datos, 'indicador': (argumentos or {}).get('indicador'), 'anterior': {'desde': anterior_desde.isoformat(), 'hasta': anterior_hasta.isoformat()}}


async def estados(filtros, argumentos):
    filtros = {**filtros, **(argumentos or {})}
    desde, hasta, _, _ = analitica_service.resolver_periodo(filtros)
    filas = await agregar('tickets', [
        {'$match': analitica_service._match(filtros, desde, hasta)},
        {'$group': {'_id': {'$cond': [{'$in': ['$estado', analitica_service.CAMPOS_ESTADO]}, 'cerrado', '$estado']}, 'total': {'$sum': 1}}},
        {'$sort': {'total': -1, '_id': 1}},
    ])
    etiquetas = {'nuevo': 'Nuevos', 'en_progreso': 'En progreso', 'en_espera': 'En espera', 'resuelto': 'Resueltos', 'cerrado': 'Cerrados'}
    return {'items': [{'estado': etiquetas.get(f['_id'], f['_id'] or 'Sin estado'), 'total': f['total']} for f in filas]}


async def plazos(filtros, argumentos):
    return await analitica_service.riesgo_sla({**filtros, **(argumentos or {})}, agrupar_por='oficina')


async def evolucion(filtros, argumentos):
    datos = await analitica_service.tendencia({**filtros, **(argumentos or {})})
    # Se expone solo la serie observada; la proyección no es un hecho.
    return {'serie': datos['serie'], 'total_periodo': datos['total_periodo']}


async def inventario(filtros, argumentos):
    if any(filtros.get(campo) for campo in ('categoria', 'tecnico_id')):
        raise Validacion('El inventario actual no admite filtros por categoría de ticket ni por técnico. Puedes filtrar por oficina, zona, tipo de equipo o equipo específico.')
    consulta = {'activo': {'$ne': False}}
    for campo in ('oficina_id', 'zona_id'):
        if filtros.get(campo):
            consulta[campo] = filtros[campo]
    if filtros.get('tipo_activo'):
        consulta['tipo'] = filtros['tipo_activo']
    if filtros.get('equipo_id'):
        consulta['_id'] = filtros['equipo_id']
    filas = await agregar('activos', [
        {'$match': consulta},
        {'$group': {'_id': '$tipo', 'total': {'$sum': 1}}},
        {'$sort': {'total': -1, '_id': 1}},
    ])
    total = sum(f['total'] for f in filas)
    sin_responsable = await get_db()['activos'].count_documents({**consulta, 'responsable_id': None})
    return {'total': total, 'sin_responsable': sin_responsable,
            'items': [{'tipo': f['_id'] or 'Sin tipo', 'total': f['total']} for f in filas]}


CONSULTAS = {
    'metricas_generales': (resumen, 'Resumen del servicio: tickets creados, cerrados y comparación con el periodo anterior.'),
    'comparacion_periodos': (resumen, 'Compara tickets creados en el periodo elegido con el intervalo anterior de igual duración.'),
    'estados_tickets': (estados, 'Tickets creados en el periodo agrupados por su estado actual.'),
    'plazos_atencion': (plazos, 'Tickets abiertos creados en el periodo, vencidos y sin plazo registrado, agrupados por oficina.'),
    'evolucion_tickets': (evolucion, 'Recuento diario observado de tickets creados, sin pronósticos.'),
    'resumen_inventario': (inventario, 'Equipos activos actuales por tipo; distingue dispositivos físicos de conjuntos.'),
}


async def resolver_ubicacion(pregunta, filtros, contexto=None):
    """Nombres escapados y coincidencia única; nunca sustituye por un total global."""
    resultado = dict(filtros)
    ambito = 'Todas las oficinas'
    if contexto:
        for campo in ('oficina_id', 'zona_id'):
            valor = contexto.get(campo)
            if isinstance(valor, str) and re.fullmatch(r'[a-fA-F0-9]{24}', valor):
                resultado[campo] = ObjectId(valor)
    coincidencia = re.search(r'\b(?:en|para|de)\s+(?:la\s+)?(oficina|zona)\s+(.+)', pregunta, re.I)
    if coincidencia:
        tipo, nombre = coincidencia.groups()
        nombre = re.split(r'\s+(?:durante|hoy|ayer|entre|desde|en el periodo|en los|este mes|este año|el mes pasado)\b', nombre, maxsplit=1, flags=re.I)[0].strip(' ¿?¡!.,')
        if len(nombre) < 2 or len(nombre) > 150:
            raise Validacion('Indica el nombre de la oficina o zona que quieres consultar.')
        coleccion, campo = ('oficinas', 'oficina_id') if tipo.lower() == 'oficina' else ('zonas', 'zona_id')
        filas = await get_db()[coleccion].find({'activo': {'$ne': False}, '$or': [
            {'nombre': {'$regex': re.escape(nombre), '$options': 'i'}}, {'nombre_normalizado': clave(nombre)},
        ]}, {'nombre': 1}).to_list(6)
        exactas = [f for f in filas if clave(f.get('nombre')) == clave(nombre)]
        candidatas = exactas or filas
        if len(candidatas) != 1:
            raise Validacion('No pude identificar una única ' + tipo.lower() + '. Escribe su nombre completo para evitar mezclar ubicaciones.')
        resultado[campo] = candidatas[0]['_id']
        resultado.pop('zona_id' if campo == 'oficina_id' else 'oficina_id', None)
    for campo, coleccion, etiqueta in (('oficina_id', 'oficinas', 'Oficina'), ('zona_id', 'zonas', 'Zona')):
        if resultado.get(campo):
            fila = await get_db()[coleccion].find_one({'_id': resultado[campo]}, {'nombre': 1})
            if not fila:
                raise Validacion('La ubicación de esta consulta ya no está disponible. Indica una ubicación válida.')
            ambito = f"{etiqueta}: {fila['nombre']}"
            break
    return resultado, ambito


def ubicacion_anterior(historial):
    for mensaje in reversed(historial or []):
        if mensaje.get('rol') == 'assistant':
            contexto = mensaje.get('contexto_consulta') or {}
            if isinstance(contexto, dict) and isinstance(contexto.get('ubicacion'), dict):
                return contexto['ubicacion']
    return {}


def detectar(pregunta: str):
    texto = clave(pregunta).lower()
    if re.search(r'que (?:es|significa)|explicame (?:el|la)|como se calcula', texto):
        return None
    if re.search(r'compar|mas o menos|(?:mas|menos).*anterior|subieron|bajaron|aumentaron|disminuyeron', texto) and re.search(r'ticket|incidencia|periodo|mes|semana', texto):
        return 'comparacion_periodos'
    if re.search(r'cumplimiento|porcentaje.*sla|sla.*porcentaje', texto):
        return 'metricas_generales'
    if re.search(r'vencid|fuera de plazo|plazos? (?:de )?atencion|tickets? atrasad|sla.*(?:cumple|cumpli|venci)|que.*atender primero', texto):
        return 'plazos_atencion'
    if re.search(r'por (?:dia|fecha)|evolucion|tendencia|dia.*mas (?:ticket|incidencia)', texto):
        return 'evolucion_tickets'
    if re.search(r'estados? (?:de |del |los )?tickets?|tickets?.*(?:abiertos|cerrados|en espera)|cuantos.*(?:cerrados|abiertos)|^y (?:los |cuantos )?(?:cerrados|abiertos)|^y.*(?:estan|siguen).*(?:abiertos|cerrados|en espera)', texto):
        return 'estados_tickets'
    if re.search(r'resumen.*inventario|cuantos (?:equipos|dispositivos).*(?:hay|tenemos|registrad)|inventario.*por tipo', texto):
        return 'resumen_inventario'
    if not re.search(r'tickets? de ', texto) and re.search(r'resumen (?:del |de |general)|como (?:esta|va|vamos)|cuantos (?:tickets|casos|incidencias)|satisfaccion|tiempo (?:medio|promedio)', texto):
        return 'metricas_generales'
    return None


def exigir_ubicacion_explicita(pregunta):
    for resto in re.findall(r'(?=\ben\s+([^?!.]+))', pregunta, re.I):
        normal = clave(resto).lower()
        # «En el sistema» describe la fuente, no una oficina. Una ubicación
        # agregada con «de/para» todavía requiere la forma explícita de abajo.
        if re.match(r'(?:el sistema|el inventario|la web|la mesa de ayuda)\b(?!\s+(?:de|del|para)\b)', normal):
            continue
        if not re.match(r'(?:la oficina|oficina|la zona|zona|el periodo|el rango|estas fechas|esas fechas|los ultimos|el ultimo|esta semana|la semana pasada|la semana anterior|este mes|este ano|el mes|este momento|espera|progreso|tiempo|total|general|minutos|horas|dias|\d)', normal):
            raise Validacion('Para filtrar por ubicación, escribe «en la oficina [nombre]» o «en la zona [nombre]». Así evito responder con un total de otra ubicación.')


def contexto_completo(historial):
    for mensaje in reversed(historial or []):
        if mensaje.get('rol') == 'assistant':
            contexto = mensaje.get('contexto_consulta') or {}
            if not isinstance(contexto, dict):
                continue
            herramienta = contexto.get('herramienta') or next(iter(mensaje.get('fuentes') or []), None)
            if herramienta not in LECTURAS:
                continue
            argumentos = contexto.get('argumentos') or {}
            if not isinstance(argumentos, dict):
                argumentos = {}
            # Solo se conserva el nombre de una persona; nunca operadores MongoDB.
            seguros = {'nombre': argumentos['nombre']} if isinstance(argumentos.get('nombre'), str) else {}
            if argumentos.get('indicador') in {'satisfaccion', 'tiempo', 'sla'}:
                seguros['indicador'] = argumentos['indicador']
            from app.services import analisis_catalogo
            if herramienta in analisis_catalogo.CONSULTAS:
                seguros = analisis_catalogo.contexto_seguro(herramienta, argumentos)
            return {**contexto, 'herramienta': herramienta, 'argumentos': seguros}
    return {}


def contexto_anterior(historial):
    contexto = contexto_completo(historial)
    return contexto.get('herramienta'), contexto.get('argumentos') or {}


def filtros_del_contexto(contexto):
    """Reconstruye únicamente filtros conocidos; nunca operadores de MongoDB."""
    filtros = contexto.get('filtros')
    if not isinstance(filtros, dict):
        return {}
    seguros = {}
    for campo, valor in filtros.items():
        if campo in {'desde', 'hasta'} and isinstance(valor, str):
            try:
                seguros[campo] = date.fromisoformat(valor)
            except ValueError:
                pass
        elif campo in {'oficina_id', 'zona_id', 'tecnico_id', 'equipo_id'} and isinstance(valor, str) and re.fullmatch(r'[a-fA-F0-9]{24}', valor):
            seguros[campo] = ObjectId(valor)
        elif campo in {'periodo', 'categoria', 'tipo_activo'} and isinstance(valor, str) and len(valor) <= 150:
            seguros[campo] = valor
    return seguros


def es_continuacion(pregunta):
    texto = clave(pregunta).lower()
    return bool(re.fullmatch(r'(?:y |ahora |y en |en )?(?:hoy|ayer|esta semana|semana actual|la semana pasada|semana pasada|semana anterior|este mes|el mes pasado|mes pasado|mes anterior|este ano|el ultimo ano|los ultimos (?:7|30|90|365) dias|ultimos (?:7|30|90|365) dias)', texto)
        or re.fullmatch(r'y (?:los )?(?:sin asignar|sin equipo(?: vinculado)?|mas antiguos|con reaperturas|reabiertos)', texto)
        or re.fullmatch(r'y (?:en|para) (?:la )?(?:oficina|zona) .+', texto)
        or re.fullmatch(r'y (?:los |cuantos )?(?:cerrados|abiertos)(?: (?:hoy|ayer|este mes|el mes pasado))?', texto)
        or re.fullmatch(r'y (?:(?:cuales|cuantos) (?:estan|quedan|hay|siguen) |los )?(?:vencidos|atrasados|abiertos|cerrados|en espera)(?: (?:hoy|ayer|este mes|el mes pasado))?', texto))


def fecha(valor):
    return '/'.join(str(valor).split('-')[::-1])


def tabla(columnas, filas):
    return {'columnas': [{'clave': c, 'titulo': t} for c, t in columnas], 'filas': filas}


def formatear(nombre: str, datos: dict[str, Any]):
    if nombre in {'metricas_generales', 'comparacion_periodos'}:
        total, anterior = datos['tickets_analizados'], datos['tickets_periodo_anterior']
        rango = f"del {fecha(datos['periodo']['desde'])} al {fecha(datos['periodo']['hasta'])}"
        campos = {'satisfaccion': ('satisfaccion_promedio', 'Satisfacción media', '/5', 'muestras_satisfaccion'),
                  'tiempo': ('tiempo_medio_resolucion_min', 'Tiempo medio de resolución', 'minutos', 'muestras_tiempo'),
                  'sla': ('cumplimiento_sla', 'Cumplimiento de SLA', '%', 'cerrados')}
        if datos.get('indicador') in campos:
            campo, etiqueta, unidad, muestra = campos[datos['indicador']]
            valor = datos.get(campo)
            cantidad = datos.get(muestra)
            texto = f"{etiqueta}: {valor} {unidad}, {rango}." if valor is not None else f"No hay datos para calcular «{etiqueta}» {rango}. Esto no significa que el resultado sea cero."
            if valor is not None and cantidad is not None:
                texto += f"\n\nSe basa en {cantidad} registros" + (' de tickets cerrados.' if muestra == 'cerrados' else ' con este dato informado.')
            return texto, tabla([('indicador', 'Indicador'), ('valor', 'Valor'), ('unidad', 'Unidad'), ('muestra', 'Registros usados')], [{'indicador': etiqueta, 'valor': valor, 'unidad': unidad, 'muestra': cantidad}])
        anterior_rango = f"del {fecha(datos['anterior']['desde'])} al {fecha(datos['anterior']['hasta'])}"
        diferencia = total - anterior
        comparacion = (f"Son {abs(diferencia)} tickets {'más' if diferencia > 0 else 'menos'} que en el intervalo anterior ({anterior_rango}), que tuvo {anterior}."
                       if diferencia else f"Es la misma cantidad que en el intervalo anterior ({anterior_rango}).")
        if anterior == 0:
            comparacion += ' No calculo una variación porcentual porque el intervalo anterior tuvo cero tickets.'
        texto = f"Se registraron {total} tickets {rango}.\n\n{comparacion}"
        if nombre == 'metricas_generales':
            texto += f"\n\nDe los tickets creados en estas fechas, {datos['cerrados']} están cerrados."
            tiempo = datos.get('tiempo_medio_resolucion_min')
            texto += f" El tiempo medio registrado de resolución es {tiempo} minutos." if tiempo is not None else ' No hay tiempos de resolución registrados para calcular un promedio.'
        return texto, tabla([('intervalo', 'Intervalo'), ('total', 'Tickets creados')], [
            {'intervalo': rango, 'total': total}, {'intervalo': anterior_rango, 'total': anterior},
        ])
    if nombre == 'estados_tickets':
        filas = datos['items']
        total = sum(f['total'] for f in filas)
        texto = f"Hay {total} tickets creados en el periodo elegido. Su estado actual es:"
        texto += '\n\n' + '\n'.join(f"{f['estado']}: {f['total']} tickets." for f in filas) if filas else ' No hay estados para comparar.'
        return texto, tabla([('estado', 'Estado actual'), ('total', 'Tickets')], filas)
    if nombre == 'plazos_atencion':
        filas = datos.get('items', [])
        vencidos = sum(f['vencidos'] for f in filas)
        sin_plazo = sum(f.get('sin_plazo', 0) for f in filas)
        texto = f"Hay {vencidos} tickets abiertos con el plazo vencido entre los creados en el periodo elegido."
        texto += f"\n\nOtros {sin_plazo} tickets abiertos no tienen fecha límite registrada; no los cuento como cumplidos ni vencidos."
        return texto, tabla([('nombre', 'Oficina'), ('total', 'Abiertos'), ('vencidos', 'Vencidos'), ('sin_plazo', 'Sin plazo')], filas)
    if nombre == 'evolucion_tickets':
        serie = datos['serie']
        total = datos['total_periodo']
        maximo = max((f['valor'] for f in serie), default=0)
        dias = [f for f in serie if f['valor'] == maximo]
        texto = f"Se crearon {total} tickets en el periodo elegido."
        if total:
            texto += f"\n\nLa cantidad diaria más alta fue {maximo}: el {fecha(dias[0]['fecha'])}."
            if len(dias) > 1:
                texto += f" Ese máximo se repitió en {len(dias)} días; no hay un único día líder."
        else:
            texto += ' No hay actividad registrada para comparar días.'
        return texto, tabla([('fecha', 'Fecha'), ('valor', 'Tickets creados')], serie)
    if nombre == 'resumen_inventario':
        texto = f"El inventario actual tiene {datos['total']} dispositivos físicos activos registrados."
        texto += f"\n\n{datos['sin_responsable']} no tienen una persona responsable vinculada. Esto puede incluir equipos compartidos de oficina; no significa que estén sin uso o abandonados."
        texto += '\n\nUn conjunto de escritorio puede incluir varios dispositivos. Una laptop sigue siendo un equipo individual.'
        return texto, tabla([('tipo', 'Tipo de dispositivo'), ('total', 'Equipos activos')], datos['items'])
    return None


LECTURAS = {
    'metricas_generales': ('Resume tickets creados en el intervalo y su estado actual.', 'Revisa plazos vencidos y las oficinas con mayor volumen antes de distribuir trabajo.', 'Los tickets cerrados son parte de los creados en el periodo; no todos los cierres realizados durante esas fechas.'),
    'comparacion_periodos': ('Compara dos intervalos consecutivos con el mismo número de días.', 'Revisa las causas y la distribución por oficina para entender la diferencia.', 'Más tickets no demuestra por sí solo peor atención. Si el periodo anterior tuvo cero, no existe un porcentaje de variación calculable.'),
    'estados_tickets': ('Agrupa por estado actual los tickets creados en las fechas consultadas.', 'Revisa los abiertos y en espera en la lista de tickets.', 'Describe cómo están ahora; no reconstruye el estado que tenían en una fecha pasada.'),
    'plazos_atencion': ('Cuenta abiertos cuya fecha límite ya pasó al momento de consultar.', 'Revisa los vencidos con el equipo TI y verifica los casos sin plazo.', 'Solo incluye tickets creados en el periodo. Los casos sin fecha límite se muestran aparte.'),
    'evolucion_tickets': ('Cada fila cuenta los tickets creados ese día, con horario de la institución.', 'Revisa las fechas con mayor volumen y sus causas antes de planificar recursos.', 'Es un historial observado. Un pico no demuestra una causa ni predice lo que ocurrirá después.'),
    'resumen_inventario': ('Cuenta dispositivos físicos activos por tipo, no personas ni computadoras completas.', 'Verifica responsables y equipos compartidos en Inventario.', 'Es el inventario actual; el filtro de fechas de tickets no reconstruye el inventario pasado.'),
    'ranking_oficinas': ('Cuenta los tickets de cada oficina en las fechas consultadas.', 'Abre la oficina para revisar sus incidencias y causas.', 'Una oficina más grande puede generar más tickets. El volumen no mide por sí solo la gravedad ni el desempeño.'),
    'ranking_zonas': ('Agrupa los tickets por zona de la institución.', 'Revisa las oficinas de la zona con mayor volumen.', 'El tamaño de cada zona puede ser diferente; el ranking no demuestra una causa.'),
    'ranking_conjuntos': ('Agrupa cada ticket una vez en la PC de escritorio vinculada, incluidos sus componentes y programas.', 'Revisa el historial de las computadoras antes de planificar mantenimiento.', 'No incluye como conjuntos las laptops ni los dispositivos independientes.'),
    'causas_recurrentes': ('Agrupa por la categoría y problema registrados en el ticket.', 'Revisa los casos repetidos para preparar una guía o una revisión técnica.', 'La categoría registrada no demuestra por sí sola la causa técnica confirmada.'),
    'equipos_con_fallas': ('El porcentaje indica cuántos equipos tuvieron alguna incidencia en los últimos doce meses.', 'Revisa los dispositivos concretos y sus tickets antes de reemplazar equipos.', 'Varios tickets del mismo equipo no son varios equipos afectados. No es una predicción futura.'),
    'disponibilidad_equipo': ('El estado combina horarios, ausencias y carga de tickets del equipo TI.', 'Confirma la disponibilidad antes de asignar un caso desde Tickets.', 'Es el estado actual; no corresponde al filtro de fechas del historial.'),
    'tecnicos_rendimiento': ('Resume la carga y los tiempos registrados para cada técnico.', 'Considera los horarios y la complejidad de los casos antes de distribuir trabajo.', 'Los recuentos por sí solos no permiten calificar a una persona ni comparar justamente casos diferentes.'),
    'equipos_de_usuario': ('Muestra equipos vinculados a la persona y el uso común de su oficina.', 'Abre Inventario para revisar un dispositivo específico.', 'La asignación es actual; no atribuye al nuevo responsable los tickets antiguos de otra persona.'),
    'tickets_de_usuario': ('Agrupa los tickets reportados por la persona o que la afectan.', 'Consulta cada caso para distinguir quién reportó y quién necesitaba ayuda.', 'Incluye el historial completo; un ticket relacionado no implica que esa persona causara la falla.'),
}


def lectura(nombre, argumentos=None):
    indicadores = {
        'satisfaccion': ('Promedia las valoraciones recibidas, en una escala de 1 a 5.', 'Revisa cuántas personas calificaron antes de interpretar el promedio.', 'Quienes no calificaron no cuentan como cero. Pocas valoraciones pueden ser poco representativas.'),
        'tiempo': ('Promedia los minutos de resolución informados en los tickets del periodo.', 'Revisa el número de tiempos registrados y la complejidad de los casos.', 'Los tickets sin tiempo informado no entran en el promedio. No es una promesa para el siguiente caso.'),
        'sla': ('Calcula qué porcentaje de los cerrados figura sin incumplimiento registrado.', 'Verifica que los plazos y las marcas de incumplimiento estén registrados correctamente.', 'Sin tickets cerrados no hay porcentaje. La ausencia de una marca no demuestra por sí sola una medición completa del plazo.'),
    }
    valores = indicadores.get((argumentos or {}).get('indicador')) if nombre == 'metricas_generales' else None
    valores = valores or LECTURAS.get(nombre)
    return dict(zip(('significado', 'revision', 'limite'), valores)) if valores else None


def seguimientos(nombre):
    preguntas = ['¿Puedes darme un resumen del servicio?', '¿Qué tickets tienen el plazo vencido?', '¿Hay más tickets que en el periodo anterior?', '¿Cuáles son las causas más frecuentes?']
    propia = {'metricas_generales': 0, 'plazos_atencion': 1, 'comparacion_periodos': 2, 'causas_recurrentes': 3}
    return [p for i, p in enumerate(preguntas) if i != propia.get(nombre)][:3]
