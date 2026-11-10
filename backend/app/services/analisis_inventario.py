"""Lecturas explicables de inventario: datos actuales e instantáneas anuales.

No escribe registros, no envía datos a proveedores y nunca mezcla las fechas de
los tickets con la fecha del inventario. La autorización la aplica el catálogo
del asistente antes de invocar cada función.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.core.db import get_db
from app.core.errors import Validacion
from app.core.ids import clave, id_requerido
from app.domain.constants import CAMPOS_BASE, COMPONENTES_CONJUNTO_POR_DEFECTO
from app.services import inventario_anual_service, inventario_service

LIMITE = 20
ETIQUETAS = {
    'codigo_patrimonial': 'Código patrimonial', 'nombre_equipo': 'Nombre del equipo',
    'marca': 'Marca', 'modelo': 'Modelo', 'tamano_pantalla': 'Tamaño de pantalla',
    'procesador': 'Procesador', 'memoria_ram': 'Memoria RAM', 'almacenamiento': 'Almacenamiento',
    'direccion_ip': 'Dirección IP', 'direccion_mac': 'Dirección MAC',
    'propiedad': 'Propiedad', 'estado': 'Estado', 'observaciones': 'Observaciones',
}


def _tabla(columnas, filas):
    return {'columnas': [{'clave': k, 'titulo': t} for k, t in columnas], 'filas': filas}


def _nombre(activo):
    return activo.get('nombre_equipo') or activo.get('tipo') or 'Equipo sin nombre'


def _consulta(filtros):
    if any(filtros.get(c) for c in ('categoria', 'tecnico_id')):
        raise Validacion('Esta consulta de inventario no admite categoría de ticket ni técnico. Puedes filtrar por oficina, zona, tipo o equipo.')
    consulta: dict[str, Any] = {'activo': {'$ne': False}}
    for campo in ('oficina_id', 'zona_id'):
        if filtros.get(campo):
            consulta[campo] = id_requerido(filtros[campo], campo)
    if filtros.get('tipo_activo'):
        consulta['tipo'] = filtros['tipo_activo']
    if filtros.get('equipo_id'):
        consulta['_id'] = id_requerido(filtros['equipo_id'], 'equipo')
    return consulta


def _enlaces(filas):
    return [{'texto': f['nombre'], 'href': '/panel/equipos/' + str(f['id'])} for f in filas if f.get('id')]


async def _calidad(filtros, campo=None):
    consulta = _consulta(filtros)
    # Se proyectan TODOS los datos que usa calcular_completitud. Proyectar solo
    # marca/modelo produciría falsos faltantes en RAM, procesador, IP, etc.
    proyeccion = {c: 1 for c in CAMPOS_BASE}
    proyeccion.update({c: 1 for c in ('tipo', 'oficina_id', 'oficina_nombre', 'campos_estado', 'opciones_avanzadas')})
    total = esperados = faltantes = incompletos = pendientes_total = 0
    por_campo: Counter = Counter()
    oficinas: dict[str, dict[str, Any]] = {}
    pendientes = []
    async for activo in get_db()['activos'].find(consulta, proyeccion).sort('_id', 1):
        info = await inventario_service.calcular_completitud(activo)
        total += 1
        esperados += info['esperados']
        faltantes += info['faltantes']
        incompletos += int(info['faltantes'] > 0)
        por_campo.update(info['campos_faltantes'])
        llave = str(activo['oficina_id']) if activo.get('oficina_id') else 'sin-id:' + str(activo.get('oficina_nombre') or '')
        oficina = oficinas.setdefault(llave, {'id': str(activo['oficina_id']) if activo.get('oficina_id') else None,
            'oficina': activo.get('oficina_nombre') or 'Sin oficina registrada', 'total': 0, 'incompletos': 0, 'faltantes': 0, 'esperados': 0})
        oficina['total'] += 1
        oficina['incompletos'] += int(info['faltantes'] > 0)
        oficina['faltantes'] += info['faltantes']
        oficina['esperados'] += info['esperados']
        if info['faltantes'] and (not campo or campo in info['campos_faltantes']):
            pendientes_total += 1
            pendientes.append({'id': str(activo['_id']), 'nombre': _nombre(activo), 'tipo': activo.get('tipo') or 'Sin tipo',
                'oficina': activo.get('oficina_nombre') or 'Sin oficina registrada', 'faltantes': info['faltantes'],
                'porcentaje': info['porcentaje'], 'campos': ', '.join(ETIQUETAS.get(c, c.replace('_', ' ')) for c in info['campos_faltantes'])})
            pendientes.sort(key=lambda f: (-f['faltantes'], f['nombre'], f['id']))
            del pendientes[LIMITE:]
    return {'total': total, 'esperados': esperados, 'faltantes': faltantes, 'incompletos': incompletos,
            'por_campo': por_campo, 'oficinas': list(oficinas.values()), 'pendientes': pendientes, 'pendientes_total': pendientes_total}


async def calidad_inventario(filtros, argumentos, *, usuario=None):
    info = await _calidad(filtros)
    porcentaje = round(100 * info['faltantes'] / info['esperados'], 1) if info['esperados'] else None
    texto = f"Revisé {info['total']} dispositivos activos. {info['incompletos']} tienen datos por completar."
    texto += (f"\n\nFaltan {info['faltantes']} de {info['esperados']} datos aplicables ({porcentaje}%)." if porcentaje is not None
              else '\n\nNo hay datos aplicables para calcular un porcentaje; no lo presento como 0%.')
    texto += '\n\nLos datos marcados como No aplica o No disponible se excluyen. Un equipo puede tener varios datos pendientes; esto no indica una avería.'
    filas = [{'campo': ETIQUETAS.get(c, c.replace('_', ' ')), 'total': n,
              'porcentaje': round(100 * n / info['total'], 1)} for c, n in sorted(info['por_campo'].items(), key=lambda p: (-p[1], p[0]))]
    return {'texto': texto, 'tabla': _tabla([('campo', 'Dato pendiente'), ('total', 'Equipos'), ('porcentaje', '% de equipos revisados')], filas),
            'enlaces': [{'texto': 'Revisar calidad del inventario', 'href': '/panel/equipos/calidad'}], 'periodo_label': 'Inventario actual'}


async def equipos_datos_pendientes(filtros, argumentos, *, usuario=None):
    campo = (argumentos or {}).get('campo')
    if campo is not None and (not isinstance(campo, str) or campo not in ETIQUETAS):
        raise Validacion('Selecciona un dato de inventario admitido para consultar sus pendientes.')
    info = await _calidad(filtros, campo)
    asunto = ' con ' + ETIQUETAS[campo].lower() + ' pendiente' if campo else ' con datos por completar'
    texto = f"Hay {info['pendientes_total']} equipos{asunto} entre los {info['total']} dispositivos activos revisados."
    texto += f"\n\nMuestro hasta {LIMITE}, empezando por los que tienen más datos pendientes. No aplica y No disponible no cuentan como pendientes."
    return {'texto': texto, 'tabla': _tabla([('nombre', 'Equipo'), ('tipo', 'Tipo'), ('oficina', 'Oficina'), ('faltantes', 'Datos pendientes'), ('campos', 'Qué completar')], info['pendientes']),
            'enlaces': _enlaces(info['pendientes']), 'periodo_label': 'Inventario actual'}


async def oficinas_datos_pendientes(filtros, argumentos, *, usuario=None):
    info = await _calidad(filtros)
    filas = sorted(info['oficinas'], key=lambda f: (-f['faltantes'], f['oficina']))
    for fila in filas:
        fila['porcentaje'] = round(100 * fila['faltantes'] / fila['esperados'], 1) if fila['esperados'] else None
    texto = f"Revisé {info['total']} dispositivos activos de {len(filas)} ubicaciones de inventario."
    texto += f"\n\nMuestro hasta {LIMITE} oficinas, ordenadas por cantidad de datos pendientes. El porcentaje usa solo los datos aplicables de esa oficina."
    texto += '\n\nUna oficina con más equipos puede tener más pendientes; el recuento por sí solo no mide su calidad.'
    return {'texto': texto, 'tabla': _tabla([('oficina', 'Oficina'), ('total', 'Equipos'), ('incompletos', 'Equipos incompletos'), ('faltantes', 'Datos pendientes'), ('porcentaje', '% de datos faltantes')], filas[:LIMITE]),
            'enlaces': [{'texto': f['oficina'], 'href': '/panel/oficinas/' + f['id']} for f in filas[:LIMITE] if f['id']], 'periodo_label': 'Inventario actual'}


async def responsables_inventario(filtros, argumentos, *, usuario=None):
    consulta = _consulta(filtros)
    db = get_db()
    activos = {u['_id'] async for u in db['usuarios'].find({'activo': True}, {'_id': 1})}
    categorias: Counter = Counter()
    filas = []
    total = 0
    proyeccion = {c: 1 for c in ('nombre_equipo', 'tipo', 'oficina_nombre', 'responsable_id', 'responsable_nombre', 'uso_comun')}
    async for equipo in db['activos'].find(consulta, proyeccion).sort('_id', 1):
        total += 1
        if equipo.get('responsable_id') in activos:
            categorias['Vinculado a una cuenta activa'] += 1
            continue
        if equipo.get('responsable_nombre') or equipo.get('responsable_id'):
            estado = 'Responsable pendiente de vincular'
        elif equipo.get('uso_comun') is True:
            estado = 'Compartido de oficina'
        else:
            estado = 'Sin persona vinculada; uso por confirmar'
        categorias[estado] += 1
        if len(filas) < LIMITE:
            filas.append({'id': str(equipo['_id']), 'nombre': _nombre(equipo), 'tipo': equipo.get('tipo') or 'Sin tipo',
                'oficina': equipo.get('oficina_nombre') or 'Sin oficina registrada', 'relacion': estado,
                'responsable': equipo.get('responsable_nombre') or 'Sin nombre registrado'})
    texto = f"Revisé {total} equipos activos: {categorias['Vinculado a una cuenta activa']} están vinculados a una cuenta activa."
    texto += f"\n\n{categorias['Responsable pendiente de vincular']} tienen responsable pendiente de vincular; {categorias['Compartido de oficina']} están marcados como compartidos y {categorias['Sin persona vinculada; uso por confirmar']} requieren confirmar su uso."
    texto += f"\n\nMuestro hasta {LIMITE} sin vínculo activo. No tener una persona asignada no significa abandono: puede ser uso común. No reasigno equipos ni cambio historiales."
    return {'texto': texto, 'tabla': _tabla([('nombre', 'Equipo'), ('tipo', 'Tipo'), ('oficina', 'Oficina'), ('relacion', 'Situación'), ('responsable', 'Responsable registrado')], filas),
            'enlaces': _enlaces(filas), 'periodo_label': 'Inventario actual'}


async def conjuntos_incompletos(filtros, argumentos, *, usuario=None):
    consulta = _consulta(filtros)
    if filtros.get('tipo_activo'):
        raise Validacion('La revisión de PC de escritorio compara CPU, monitor, teclado y mouse. Consulta sin filtro de tipo para revisar conjuntos completos.')
    consulta.pop('_id', None)
    if filtros.get('equipo_id'):
        equipo = await get_db()['activos'].find_one({'_id': id_requerido(filtros['equipo_id']), 'activo': {'$ne': False}}, {'conjunto_id': 1})
        if not equipo or not equipo.get('conjunto_id'):
            raise Validacion('El equipo seleccionado no pertenece a una PC de escritorio. Las laptops y equipos independientes se revisan por separado.')
        consulta['_id'] = equipo['conjunto_id']
    conjuntos = await get_db()['conjuntos'].find(consulta, {'nombre': 1, 'oficina_nombre': 1, 'responsable_nombre': 1}).sort('_id', 1).to_list(None)
    ids = [c['_id'] for c in conjuntos]
    componentes: dict[Any, set[str]] = {}
    if ids:
        async for componente in get_db()['activos'].find({'activo': {'$ne': False}, 'conjunto_id': {'$in': ids}}, {'conjunto_id': 1, 'tipo': 1}):
            componentes.setdefault(componente['conjunto_id'], set()).add(clave(componente.get('tipo')))
    filas = []
    for conjunto in conjuntos:
        presentes = componentes.get(conjunto['_id'], set())
        faltan = [t for t in COMPONENTES_CONJUNTO_POR_DEFECTO if clave(t) not in presentes]
        if faltan:
            filas.append({'nombre': conjunto.get('nombre') or 'PC de escritorio', 'oficina': conjunto.get('oficina_nombre') or 'Sin oficina registrada',
                'responsable': conjunto.get('responsable_nombre') or 'Sin responsable vinculado', 'faltantes': ', '.join(faltan)})
    texto = f"De {len(conjuntos)} PC de escritorio registradas, {len(filas)} no tienen registrados todos los componentes básicos activos."
    texto += f"\n\nMuestro hasta {LIMITE}. Compruebo CPU, monitor, teclado y mouse; las laptops e impresoras son dispositivos independientes. Un componente sin registrar no demuestra que falte físicamente."
    return {'texto': texto, 'tabla': _tabla([('nombre', 'PC de escritorio'), ('oficina', 'Oficina'), ('responsable', 'Responsable actual'), ('faltantes', 'Componentes no registrados')], filas[:LIMITE]),
            'enlaces': [{'texto': 'Revisar computadoras e inventario', 'href': '/panel/equipos'}], 'periodo_label': 'Inventario actual'}


def _sin_filtros_anuales(filtros):
    if any(filtros.get(c) for c in ('oficina_id', 'zona_id', 'tipo_activo', 'equipo_id', 'categoria', 'tecnico_id')):
        raise Validacion('Los archivos anuales se consultan completos por año. Esta comparación no admite los filtros de tickets, oficina, zona, tipo ni equipo; quítalos para no confundir una cifra global con una filtrada.')


async def inventarios_disponibles(filtros, argumentos, *, usuario=None):
    _sin_filtros_anuales(filtros)
    por_anio: dict[int, dict[str, Any]] = {}
    async for version in get_db()['inventario_versiones'].find({}, {'anio': 1, 'total_items': 1}).sort([('anio', -1), ('_id', -1)]):
        anio = version.get('anio')
        if type(anio) is not int or not 2000 <= anio <= 2100:
            continue
        fila = por_anio.setdefault(anio, {'anio': anio, 'versiones': 0})
        fila['versiones'] += 1
    filas = list(por_anio.values())
    texto = f"Hay {len(filas)} años con inventarios guardados. Muestro hasta {LIMITE}; cada año puede tener varias versiones."
    texto += '\n\nLa comparación utiliza la versión anual de archivo más reciente y, si no existe, la última versión disponible de ese año. Necesitas dos años distintos.'
    anios = sorted(por_anio)
    seguimientos = [f'Compara los inventarios de {anios[-2]} y {anios[-1]}'] if len(anios) >= 2 else []
    return {'texto': texto, 'tabla': _tabla([('anio', 'Año'), ('versiones', 'Versiones guardadas')], filas[:LIMITE]),
            'enlaces': [{'texto': 'Abrir inventario anual', 'href': '/panel/inventario-anual'}], 'periodo_label': 'Archivos anuales guardados', 'seguimientos': seguimientos}


async def comparar_inventarios(filtros, argumentos, *, usuario=None):
    _sin_filtros_anuales(filtros)
    a, b = (argumentos or {}).get('anio_a'), (argumentos or {}).get('anio_b')
    if type(a) is not int or type(b) is not int or not 2000 <= a < b <= 2100:
        disponibles = await inventarios_disponibles(filtros, {})
        disponibles['texto'] = 'Indica dos años distintos en orden cronológico, por ejemplo «Compara los inventarios de 2025 y 2026».\n\n' + disponibles['texto']
        disponibles['suficiente_datos'] = False
        return disponibles
    datos = await inventario_anual_service.comparar(a, b)
    if not datos.get('suficiente_datos'):
        return {'texto': datos.get('mensaje') or 'Falta uno de los inventarios para comparar.', 'tabla': _tabla([], []),
                'enlaces': [{'texto': 'Revisar inventarios guardados', 'href': '/panel/inventario-anual'}], 'suficiente_datos': False,
                'periodo_label': f'Inventarios {a} y {b}'}
    grupos = [('altas', 'Incorporaciones'), ('bajas', 'Ausencias en el archivo nuevo'), ('traslados', 'Cambios de ubicación'), ('cambios_responsable', 'Cambios de responsable'), ('cambios', 'Equipos con diferencias de datos')]
    filas = [{'movimiento': etiqueta, 'total': len(datos.get(campo, []))} for campo, etiqueta in grupos]
    texto = f"Comparé los inventarios de {a} ({datos['totales'][str(a)]} equipos) y {b} ({datos['totales'][str(b)]} equipos)."
    texto += '\n\n' + '; '.join(f"{f['movimiento']}: {f['total']}" for f in filas) + '.'
    texto += f"\n\n{datos.get('sin_cambios', 0)} equipos comunes no presentan cambios. Un mismo equipo puede figurar en varias clases de diferencia."
    texto += '\n\n' + datos.get('criterio', 'Son diferencias entre archivos guardados; no se modifica el inventario operativo.')
    return {'texto': texto, 'tabla': _tabla([('movimiento', 'Diferencia entre archivos'), ('total', 'Equipos')], filas),
            'enlaces': [{'texto': 'Ver comparación en Inventario anual', 'href': '/panel/inventario-anual'}], 'periodo_label': f'Inventarios {a} y {b}'}


def detectar(pregunta):
    texto = clave(pregunta).lower()
    if re.search(r'que (?:es|significa|hace)|para que sirve|como (?:funciona|se calcula|comparo|comparar|importo|registro|asigno)', texto):
        return None
    if re.search(r'\bquien\b.*\b(?:cambio|modifico|asigno|reasigno|traslado|desactivo|elimino)\b', texto):
        return None
    if re.search(r'inventari', texto) and re.search(r'anual|\banos?\b|\b(?:20\d{2}|2100)\b|compar', texto):
        anios = sorted({int(a) for a in re.findall(r'\b(?:20\d{2}|2100)\b', texto)})
        if re.search(r'compar|cambio|diferencia|entre|traslad|responsable', texto):
            return 'comparar_inventarios', {'anio_a': anios[0], 'anio_b': anios[1]} if len(anios) == 2 else {}
        return 'inventarios_disponibles', {}
    if re.search(r'(?:conjuntos?|pc de escritorio|computadoras?).*(?:incomplet|componente.*(?:falt|pendient)|falt.*componente)|(?:falt|pendient).*componentes?.*(?:pc|conjunto|computadora)', texto):
        return 'conjuntos_incompletos', {}
    if re.search(r'(?:equipos?|dispositivos?|inventario).*(?:sin responsable|responsable.*(?:pendiente|vincul|archivad)|sin persona)', texto):
        return 'responsables_inventario', {}
    if re.search(r'oficinas?.*(?:datos.*(?:falt|pendient|completar)|inventario.*(?:incomplet|pendient|completar))|(?:datos|inventario).*pendient.*oficinas?', texto):
        return 'oficinas_datos_pendientes', {}
    if re.search(r'(?:equipos?|dispositivos?).*(?:datos.*(?:falt|pendient|completar)|incomplet|sin (?:codigo|patrimonio)|no tienen (?:codigo|patrimonio)|pendiente.*(?:codigo|patrimonio))', texto):
        return 'equipos_datos_pendientes', {'campo': 'codigo_patrimonial'} if re.search(r'patrimonial|patrimonio|codigo', texto) else {}
    if re.search(r'calidad.*inventario|(?:datos|campos).*(?:faltan|faltantes|pendientes)|inventario.*(?:completo|incompleto|completitud)', texto):
        return 'calidad_inventario', {}
    return None


def _definicion(funcion, descripcion, pregunta, lectura, *, permiso='equipos.ver', ambito='actual', esquema=None):
    return {'funcion': funcion, 'descripcion': descripcion, 'permiso': permiso,
            'esquema': esquema or {'type': 'object', 'properties': {}, 'additionalProperties': False},
            'lectura': lectura, 'preguntas': [pregunta] if isinstance(pregunta, str) else list(pregunta), 'grupo': 'Equipos', 'ambito': ambito}


CONSULTAS = {
    'calidad_inventario': _definicion(calidad_inventario, 'Datos aplicables pendientes del inventario activo, con porcentajes y campos.', '¿Qué datos faltan en el inventario?',
        ('Calcula faltantes sobre los datos aplicables de los equipos activos.', 'Completa los campos que aplican antes de comparar la calidad entre oficinas.', 'No aplica y No disponible se excluyen. Los datos incompletos no son fallas físicas.')),
    'equipos_datos_pendientes': _definicion(equipos_datos_pendientes, 'Equipos activos con datos pendientes y enlaces, hasta veinte.', ('¿Qué equipos tienen datos por completar?', '¿Qué equipos no tienen código patrimonial?'),
        ('Lista dispositivos con campos esperados pendientes.', 'Abre el equipo para completar sus datos.', 'Muestra hasta veinte; los totales incluyen todo el inventario filtrado.'),
        esquema={'type': 'object', 'properties': {'campo': {'type': 'string', 'enum': list(ETIQUETAS)}}, 'additionalProperties': False}),
    'oficinas_datos_pendientes': _definicion(oficinas_datos_pendientes, 'Pendientes de inventario por oficina, con denominadores.', '¿Qué oficinas tienen más datos pendientes?',
        ('Agrupa equipos y datos pendientes de las oficinas.', 'Considera el tamaño de la oficina y el porcentaje de datos aplicables.', 'Una oficina con más equipos puede tener más pendientes en números absolutos.')),
    'responsables_inventario': _definicion(responsables_inventario, 'Equipos compartidos, sin vínculo y con responsable pendiente de vincular.', '¿Qué equipos están sin responsable?',
        ('Distingue vínculos a cuentas activas de uso común y vínculos pendientes.', 'Revisa el responsable registrado y el uso del dispositivo.', 'No modifica responsables ni atribuye tickets antiguos a personas nuevas.')),
    'conjuntos_incompletos': _definicion(conjuntos_incompletos, 'PC de escritorio sin CPU, monitor, teclado o mouse activos registrados.', '¿Qué PC de escritorio tienen componentes pendientes?',
        ('Compara los conjuntos registrados con los cuatro componentes básicos.', 'Verifica el registro y la existencia física antes de tomar medidas.', 'Una laptop es independiente y un componente sin registrar no demuestra que no exista.')),
    'inventarios_disponibles': _definicion(inventarios_disponibles, 'Años de inventario guardados y número de versiones.', '¿Qué inventarios anuales están guardados?',
        ('Lista los años con archivos o versiones de inventario guardadas.', 'Elige dos años distintos para compararlos.', 'El inventario actual y los archivos anuales son registros diferentes.'), permiso='equipos.campanas', ambito='anual'),
    'comparar_inventarios': _definicion(comparar_inventarios, 'Diferencias reproducibles entre dos inventarios anuales guardados.', 'Compara dos inventarios anuales',
        ('Compara instantáneas guardadas de dos años explícitos.', 'Revisa los archivos de origen y los identificadores antes de confirmar un traslado.', 'Una salida entre archivos no equivale a dar de baja un equipo operativo. Sin identificadores estables un traslado puede parecer salida y alta.'),
        permiso='equipos.campanas', ambito='anual', esquema={'type': 'object', 'properties': {'anio_a': {'type': 'integer', 'minimum': 2000, 'maximum': 2100}, 'anio_b': {'type': 'integer', 'minimum': 2000, 'maximum': 2100}}, 'additionalProperties': False}),
}
