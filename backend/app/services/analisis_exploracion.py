"""Desglose paginado y de solo lectura de las cifras del asistente.

Proyecciones positivas, filtros escalares y autoridad vigente en cada página.
No abre fichas que registren lecturas ni modifica inventario o conversaciones.
"""
from collections import Counter
from datetime import datetime
import math
import re

from app.core.db import get_db
from app.core.errors import Prohibido, Validacion
from app.core.ids import a_id, id_requerido
from app.core.time import business_tz, utcnow
from app.domain.constants import CAMPOS_BASE
from app.domain.permissions import tiene_permiso

INVENTARIO = {'resumen_inventario', 'calidad_inventario', 'equipos_datos_pendientes', 'oficinas_datos_pendientes', 'responsables_inventario'}
HERRAMIENTAS = INVENTARIO | {'auditoria_cambios', 'auditoria_responsables', 'resumen_equipo_ti', 'horarios_manana', 'tickets_pendientes_detalle', 'guias_consultadas', 'guias_valoradas', 'brechas_guias', 'conjuntos_incompletos', 'inventarios_disponibles'}
GRUPOS = {'vinculado': 'Vinculado a una cuenta activa', 'pendiente': 'Responsable pendiente de vincular',
          'compartido': 'Compartido de oficina', 'confirmar': 'Uso por confirmar'}


def tabla(columnas, filas):
    return {'columnas': [{'clave': k, 'titulo': v} for k, v in columnas], 'filas': filas}


def pagina(filas, total, numero=1, indicadores=None, *, validar_pagina=True, **extras):
    if validar_pagina and numero > max(1, math.ceil(total / 20)):
        raise Validacion('Esa página ya no está disponible con los filtros actuales. Vuelve a la primera página.')
    if indicadores is not None:
        filas = {**filas, 'indicadores': indicadores}
    return {'tabla': filas, 'total': total, 'pagina': numero, 'por_pagina': 20,
            'total_paginas': max(1, math.ceil(total / 20)), 'indicadores': indicadores or {},
            'texto': f'Mostrando {len(filas["filas"])} de {total} registros disponibles.' if total else 'No se encontraron registros con los filtros seleccionados.', 'consultado_en': utcnow().isoformat(), **extras}


def seguro(valor, alternativo='Sin registrar'):
    if not isinstance(valor, str) or not valor.strip():
        return alternativo
    if re.search(r'password|contrase|token|bearer|api[_ -]?key|clave\s*[:=]|gsk_|AIza|gh[pousr]_|[\w.+-]+@[\w.-]+', valor, re.I):
        return 'Dato reservado'
    return valor[:180]


def grafico_inventario(nombre, datos):
    if nombre == 'responsables_inventario':
        i = datos['indicadores']
        datos['tabla']['grafico'] = tabla([('relacion', 'Vinculación / uso'), ('total', 'Dispositivos'), ('porcentaje', '% de dispositivos revisados')],
            [{'grupo': g, 'relacion': etiqueta, 'total': i[g], 'porcentaje': round(100 * i[g] / i['dispositivos'], 1) if i['dispositivos'] else None} for g, etiqueta in GRUPOS.items()])
    elif nombre == 'equipos_datos_pendientes':
        datos['tabla']['grafico'] = tabla([('oficina', 'Oficina'), ('total', 'Dispositivos afectados'), ('dispositivos', 'Dispositivos de la oficina'), ('porcentaje', '% de dispositivos afectados')],
            [{'id': f['id'], 'es_oficina': True, 'oficina': f['oficina'], 'total': f['afectados'], 'dispositivos': f['total'], 'porcentaje': round(100 * f['afectados'] / f['total'], 1) if f['total'] else None}
                for f in sorted(datos.get('oficinas', []), key=lambda f: (-f['afectados'], f['oficina'])) if f['afectados']][:20])
    return datos


async def cuentas():
    return {p['_id']: p async for p in get_db().usuarios.find({}, {'nombre': 1, 'activo': 1, 'archivado': 1})}


def grupo(equipo, personas):
    persona = personas.get(a_id(equipo.get('responsable_id')), {})
    if persona.get('activo') is True and not persona.get('archivado'):
        return 'vinculado'
    if equipo.get('responsable_id') or equipo.get('responsable_nombre'):
        return 'pendiente'
    return 'compartido' if equipo.get('uso_comun') is True else 'confirmar'


def consulta_activos(filtros, opciones):
    from app.services.analisis_inventario import _consulta
    consulta = _consulta(filtros)
    if opciones.get('incluir_inactivos') is True:
        consulta.pop('activo', None)
    condiciones = []
    for campo in ('oficina_id', 'responsable_id', 'equipo_id'):
        if opciones.get(campo):
            condiciones.append({'_id' if campo == 'equipo_id' else campo: id_requerido(opciones[campo], campo)})
    for opcion, campo in (('tipo', 'tipo'), ('oficina', 'oficina_nombre'), ('responsable', 'responsable_nombre')):
        if opciones.get(opcion):
            condiciones.append({campo: {'$regex': ('^' + re.escape(opciones[opcion]) + '$') if opcion == 'tipo' else re.escape(opciones[opcion]), '$options': 'i'}})
    if opciones.get('texto'):
        patron = {'$regex': re.escape(opciones['texto']), '$options': 'i'}
        alternativas = [{c: patron} for c in ('nombre_equipo', 'codigo_patrimonial', 'serie')]
        if a_id(opciones['texto']):
            alternativas.append({'_id': a_id(opciones['texto'])})
        condiciones.append({'$or': alternativas})
    if condiciones:
        consulta['$and'] = condiciones
    return consulta


async def inventario(herramienta, filtros, opciones):
    from app.services import inventario_service
    from app.services.analisis_inventario import ETIQUETAS
    consulta = consulta_activos(filtros, opciones)
    campo = opciones.get('campo')
    if campo is not None and (not isinstance(campo, str) or campo not in ETIQUETAS):
        raise Validacion('Selecciona un dato de inventario válido para consultar sus pendientes.')
    personas = await cuentas()
    proyeccion = {c: 1 for c in (*CAMPOS_BASE, 'tipo', 'oficina_id', 'oficina_nombre', 'responsable_id', 'responsable_nombre', 'uso_comun', 'campos_estado', 'opciones_avanzadas', 'serie', 'activo')}
    filas, oficinas, tipos, grupos = [], {}, {}, Counter()
    total = encontrados = esperados = faltantes = completos = sin_nombre = 0
    numero = opciones.get('pagina', 1)
    async for equipo in get_db().activos.find(consulta, proyeccion).sort('_id', 1):
        total += 1
        relacion = grupo(equipo, personas)
        grupos[relacion] += 1
        tipo = equipo.get('tipo') or 'Sin tipo'
        tipo_fila = tipos.setdefault(tipo, {'tipo': tipo, 'total': 0, 'compartidos': 0, 'por_confirmar': 0, 'vinculacion_pendiente': 0})
        tipo_fila['total'] += 1
        tipo_fila['compartidos'] += int(relacion == 'compartido')
        tipo_fila['por_confirmar'] += int(relacion == 'confirmar')
        tipo_fila['vinculacion_pendiente'] += int(relacion == 'pendiente')
        sin_nombre += int(not equipo.get('responsable_id') and not equipo.get('responsable_nombre'))
        calidad = await inventario_service.calcular_completitud(equipo)
        esperados += calidad['esperados']
        faltantes += calidad['faltantes']
        completos += int(not calidad['faltantes'])
        oid = str(equipo['oficina_id']) if equipo.get('oficina_id') else ''
        llave = oid or 'nombre:' + str(equipo.get('oficina_nombre') or '')
        oficina = oficinas.setdefault(llave, {'id': oid, 'oficina': equipo.get('oficina_nombre') or 'Sin oficina registrada', 'total': 0,
            'completos': 0, 'incompletos': 0, 'faltantes': 0, 'esperados': 0, 'afectados': 0, 'responsables_pendientes': 0, 'campos': Counter()})
        oficina['total'] += 1
        oficina['completos'] += int(not calidad['faltantes'])
        oficina['incompletos'] += int(bool(calidad['faltantes']))
        oficina['faltantes'] += calidad['faltantes']
        oficina['esperados'] += calidad['esperados']
        oficina['responsables_pendientes'] += int(relacion == 'pendiente')
        oficina['afectados'] += int(campo in calidad['campos_faltantes'] if campo else bool(calidad['faltantes']))
        oficina['campos'].update(calidad['campos_faltantes'])
        if opciones.get('grupo') == 'sin_cuenta' and relacion == 'vinculado':
            continue
        if opciones.get('grupo') not in (None, '', 'todos', 'sin_cuenta') and opciones['grupo'] != relacion:
            continue
        if campo and campo not in calidad['campos_faltantes']:
            continue
        if herramienta in {'equipos_datos_pendientes', 'calidad_inventario', 'oficinas_datos_pendientes'} and not calidad['faltantes']:
            continue
        encontrados += 1
        if not (numero - 1) * 20 <= encontrados - 1 < numero * 20:
            continue
        responsable = equipo.get('responsable_nombre') or personas.get(a_id(equipo.get('responsable_id')), {}).get('nombre')
        estado_codigo = (equipo.get('campos_estado') or {}).get('codigo_patrimonial')
        if isinstance(estado_codigo, dict): estado_codigo = estado_codigo.get('estado')
        filas.append({'id': str(equipo['_id']), 'nombre': seguro(equipo.get('nombre_equipo') or tipo), 'tipo': tipo,
            'oficina': seguro(equipo.get('oficina_nombre'), 'Sin oficina registrada'), 'oficina_id': oid,
            'equipo_id': str(equipo['_id']), 'responsable': seguro(responsable, 'Responsable no registrado'), 'relacion': GRUPOS[relacion], 'grupo': relacion, 'registro_inventario': 'Inactivo' if equipo.get('activo') is False else 'Activo',
            'codigo': seguro(equipo.get('codigo_patrimonial'), {'no_aplica': 'No aplica', 'no_disponible': 'No disponible'}.get(estado_codigo, 'Código patrimonial pendiente')),
            'estado_codigo': estado_codigo or ('Registrado' if equipo.get('codigo_patrimonial') else 'Pendiente'),
            'faltantes': calidad['faltantes'], 'campos': ', '.join(ETIQUETAS.get(c, c) for c in calidad['campos_faltantes']),
            'aplicables': calidad['esperados'], 'porcentaje_completo': calidad['porcentaje'] if calidad['esperados'] else None})
    for oficina in oficinas.values():
        oficina['porcentaje'] = round(100 * oficina['faltantes'] / oficina['esperados'], 1) if oficina['esperados'] else None
        oficina['porcentaje_completo'] = round(100 - oficina['porcentaje'], 1) if oficina['porcentaje'] is not None else None
        oficina['numerador_completos'] = oficina['esperados'] - oficina['faltantes']
        oficina['principales_pendientes'] = ', '.join(f'{ETIQUETAS.get(c, c)}: {n}' for c, n in oficina.pop('campos').most_common(5))
    indicadores = {'dispositivos': total, 'completos': completos, 'datos_faltantes': faltantes, 'datos_aplicables': esperados,
                  'sin_responsable_registrado': sin_nombre, 'sin_cuenta_activa': total - grupos['vinculado'], **{g: grupos[g] for g in GRUPOS}}
    return pagina(tabla([('nombre', 'Dispositivo'), ('id', 'Identificador interno'), ('tipo', 'Tipo'), ('oficina', 'Oficina'),
        ('responsable', 'Responsable registrado'), ('relacion', 'Vinculación / uso'), ('codigo', 'Código patrimonial'),
        ('estado_codigo', 'Estado del código'), ('faltantes', 'Datos pendientes'), ('campos', 'Qué completar')], filas), encontrados, numero, indicadores,
        validar_pagina=not opciones.get('_candidatos_combinados'),
        oficinas=list(oficinas.values()), tipos=sorted(tipos.values(), key=lambda f: (-f['total'], f['tipo'])))


async def resumen_inventario(filtros, opciones=None):
    opciones = opciones or {}
    datos = await inventario('resumen_inventario', filtros, opciones)
    i = datos['indicadores']
    consulta_pc = {'activo': {'$ne': False}}
    for campo in ('oficina_id', 'zona_id'):
        if filtros.get(campo): consulta_pc[campo] = id_requerido(filtros[campo])
    pcs = await get_db().conjuntos.count_documents(consulta_pc) if not filtros.get('equipo_id') and not filtros.get('tipo_activo') and not any(opciones.get(c) for c in ('texto', 'oficina', 'responsable', 'tipo', 'oficina_id', 'responsable_id', 'equipo_id', 'grupo', 'campo')) else None
    texto = f"El inventario actual tiene {i['dispositivos']} dispositivos físicos activos registrados."
    texto += f"\n\n{i.get('vinculado', 0)} vinculados a cuenta activa; {i.get('pendiente', 0)} con vinculación pendiente; {i.get('compartido', 0)} equipos compartidos; {i.get('confirmar', 0)} con uso por confirmar."
    texto += f"\n\nSin cuenta activa: {i['sin_cuenta_activa']}. Sin responsable registrado: {i['sin_responsable_registrado']}."
    if pcs is not None: texto += f' Hay {pcs} conjuntos de escritorio, contados por separado de sus dispositivos.'
    for fila in datos['tipos']:
        fila['porcentaje'] = round(100 * fila['total'] / i['dispositivos'], 1) if i['dispositivos'] else None
    columnas = [('tipo', 'Tipo de dispositivo'), ('total', 'Equipos activos'), ('porcentaje', '% de dispositivos revisados'), ('compartidos', 'Compartidos'), ('por_confirmar', 'Uso por confirmar'), ('vinculacion_pendiente', 'Vinculación pendiente')]
    return {'texto': texto, 'tabla': tabla(columnas, datos['tipos']), 'total': i['dispositivos'],
            'sin_responsable': i['sin_responsable_registrado'], 'items': datos['tipos'], 'indicadores': {**i, 'conjuntos': pcs}}


async def auditoria(filtros, opciones, *, historial=False):
    from app.core.audit import consulta_movimientos, accion_legible, ACCIONES
    from app.services import analitica_service
    numero = opciones.get('pagina', 1)
    db = get_db()
    equipo_id = a_id(opciones.get('equipo_id'))
    if historial and not equipo_id:
        # Búsqueda parcial, sin exigir que el solicitante memorice un patrimonio.
        opciones['incluir_inactivos'] = True
        opciones['_candidatos_combinados'] = True
        datos = await inventario('resumen_inventario', filtros, opciones)
        for fila in datos['tabla']['filas']:
            fila.update(seleccionable=True, clase='activo')
        consulta_pc = consulta_activos(filtros, opciones)
        # Conjuntos se ofrecen para historial, sin sumarlos a dispositivos físicos.
        if '$and' in consulta_pc:
            consulta_pc['$and'] = [{'$or': [{'nombre' if k == 'nombre_equipo' else k: v} for elemento in c['$or'] for k, v in elemento.items()]} if '$or' in c else c for c in consulta_pc['$and']]
        if opciones.get('tipo'):
            consulta_pc['_id'] = None  # El tipo físico filtra dispositivos, no conjuntos.
        cantidad_pc = await db.conjuntos.count_documents(consulta_pc)
        faltan = 20 - len(datos['tabla']['filas'])
        if faltan:
            pcs = await db.conjuntos.find(consulta_pc, {'nombre': 1, 'oficina_nombre': 1, 'responsable_nombre': 1}).sort('_id', 1).skip(max((numero - 1) * 20 - datos['total'], 0)).limit(faltan).to_list(faltan)
            datos['tabla']['filas'].extend({'id': str(p['_id']), 'nombre': seguro(p.get('nombre')), 'tipo': 'PC de escritorio (conjunto)',
                'oficina': seguro(p.get('oficina_nombre')), 'responsable': seguro(p.get('responsable_nombre'), 'Responsable no registrado'), 'clase': 'conjunto', 'seleccionable': True} for p in pcs)
        datos.update(total=datos['total'] + cantidad_pc, total_paginas=max(1, math.ceil((datos['total'] + cantidad_pc) / 20)))
        if numero > datos['total_paginas']:
            raise Validacion('Esa página ya no está disponible con los filtros actuales. Vuelve a la primera página.')
        datos['tabla']['columnas'] = [{'clave': k, 'titulo': v} for k, v in [('nombre', 'Equipo o conjunto'), ('id', 'Identificador interno'), ('tipo', 'Tipo'), ('oficina', 'Oficina'), ('responsable', 'Responsable registrado'), ('registro_inventario', 'Estado del registro')]]
        datos['texto'] = f"Selecciona un dispositivo o conjunto para consultar su historial de responsables. Mostrando {len(datos['tabla']['filas'])} de {datos['total']} coincidencias."
        datos['vista'] = 'buscar_equipo'
        return datos
    if historial:
        if not tiene_permiso(opciones['_usuario'], 'equipos.ver'):
            raise Prohibido('Necesitas permiso para consultar el inventario de este equipo.')
        filtro_equipo = {'_id': equipo_id}
        for campo in ('oficina_id', 'zona_id'):
            if filtros.get(campo): filtro_equipo[campo] = id_requerido(filtros[campo], campo)
        equipo = await db.activos.find_one(filtro_equipo, {'nombre_equipo': 1, 'oficina_nombre': 1})
        clase = 'activo'
        if not equipo:
            equipo = await db.conjuntos.find_one(filtro_equipo, {'nombre': 1, 'oficina_nombre': 1})
            clase = 'conjunto'
        if not equipo: raise Validacion('El dispositivo seleccionado no existe.')
        consulta = {clase + '_id': equipo_id}
        if filtros.get('desde') or filtros.get('hasta'):
            from app.services import analitica_service
            desde, hasta, _, _ = analitica_service.resolver_periodo(filtros)
            from app.core.time import business_start_of_day
            from datetime import timedelta
            consulta['inicio'] = {'$gte': business_start_of_day(desde), '$lt': business_start_of_day(hasta + timedelta(days=1))}
        # Historial de inventario persistente, distinto de la auditoría de quince días.
        total = await db.historial_responsables.count_documents(consulta)
        if not total:
            datos = await auditoria(filtros, {**opciones, 'equipo_id': str(equipo_id)}, historial=False)
            datos['texto'] = 'No hay entradas en el historial persistente con estos filtros. Se muestran los movimientos de responsable conservados en auditoría. ' + datos['texto']
            datos['vista'] = 'historial_responsables'
            datos['equipo_consulta'] = str(equipo_id)
            return datos
        docs = await db.historial_responsables.find(consulta, {'responsable_nombre': 1, 'fecha': 1, 'inicio': 1, 'motivo': 1, 'usuario_nombre': 1}).sort([('inicio', -1), ('_id', -1)]).skip((numero - 1) * 20).limit(20).to_list(20)
        filas = []
        for doc in docs:
            inicio = doc.get('inicio') or doc.get('fecha')
            anterior = await db.historial_responsables.find_one({clase + '_id': equipo_id, 'inicio': {'$lt': inicio}}, {'responsable_nombre': 1}, sort=[('inicio', -1), ('_id', -1)]) if inicio else None
            filas.append({'id': str(doc['_id']), 'fecha': inicio.astimezone(business_tz()).strftime('%d/%m/%Y %H:%M') if inicio else 'Sin fecha',
                'anterior': seguro((anterior or {}).get('responsable_nombre'), 'No registrado'), 'nuevo': seguro(doc.get('responsable_nombre'), 'Sin responsable'),
                'persona': seguro(doc.get('usuario_nombre'), 'Cuenta no identificada'), 'motivo': seguro(doc.get('motivo'), 'No registrado'),
                'oficina': 'Ubicación histórica no registrada'})
        return pagina(tabla([('fecha', 'Fecha Lima'), ('anterior', 'Responsable anterior'), ('nuevo', 'Responsable nuevo'), ('persona', 'Registró'), ('motivo', 'Motivo registrado'), ('oficina', 'Ubicación histórica'), ('id', 'Referencia')], filas), total, numero,
            texto=f"Historial registrado de {seguro(equipo.get('nombre_equipo') or equipo.get('nombre'))}. Mostrando {len(filas)} de {total} cambios." if total else 'No hay cambios de responsable registrados con estos filtros en el historial de este dispositivo. La auditoría temporal es una fuente distinta.', vista='historial_responsables')
    desde, hasta, _, _ = analitica_service.resolver_periodo(filtros)
    consulta = consulta_movimientos(desde=desde, hasta=hasta)
    consulta['fecha']['$lt'] = min(consulta['fecha']['$lt'], utcnow())
    if opciones.get('equipo_id'):
        eid = id_requerido(opciones['equipo_id'])
        consulta.update({'entidad_id': {'$in': [eid, str(eid)]}, 'accion': {'$in': ['activo.responsable', 'conjunto.responsable']}})
    total = await db.auditoria.count_documents(consulta)
    docs = await db.auditoria.find(consulta, {'fecha': 1, 'accion': 1, 'entidad': 1, 'entidad_id': 1, 'usuario_nombre': 1,
        'antes.oficina_nombre': 1, 'despues.oficina_nombre': 1, 'antes.responsable_nombre': 1, 'despues.responsable_nombre': 1}).sort([('fecha', -1), ('_id', -1)]).skip((numero - 1) * 20).limit(20).to_list(20)
    filas = []
    for doc in docs:
        eid = a_id(doc.get('entidad_id'))
        dispositivo = await db.activos.find_one({'_id': eid}, {'nombre_equipo': 1, 'oficina_nombre': 1}) if eid and doc.get('entidad') in {'activo', 'activos'} else None
        accion = accion_legible(doc.get('accion', ''), doc.get('entidad', '')) if doc.get('accion') in ACCIONES else 'Otro cambio registrado'
        anterior = doc.get('antes') if isinstance(doc.get('antes'), dict) else {}
        posterior = doc.get('despues') if isinstance(doc.get('despues'), dict) else {}
        filas.append({'id': str(doc['_id']), 'fecha': doc['fecha'].astimezone(business_tz()).strftime('%d/%m/%Y %H:%M') if doc.get('fecha') else 'Sin fecha',
            'persona': 'Cuenta TI' if seguro(doc.get('usuario_nombre')) == 'Dato reservado' else seguro(doc.get('usuario_nombre'), 'Cuenta no identificada'), 'accion': accion, 'entidad': seguro(doc.get('entidad')),
            'dispositivo': seguro((dispositivo or {}).get('nombre_equipo'), 'Sin referencia de dispositivo disponible'),
            'oficina': seguro((dispositivo or {}).get('oficina_nombre'), 'Ubicación del movimiento no registrada'),
            'oficina_origen': seguro(anterior.get('oficina_nombre')), 'oficina_destino': seguro(posterior.get('oficina_nombre')),
            'responsable_anterior': seguro(anterior.get('responsable_nombre')), 'responsable_nuevo': seguro(posterior.get('responsable_nombre')),
            'resumen': accion, 'referencia': str(doc.get('entidad_id') or 'Sin referencia')})
    inicio, fin = consulta['fecha']['$gte'], consulta['fecha']['$lt']
    cobertura = f"{inicio.astimezone(business_tz()):%d/%m/%Y %H:%M}–{fin.astimezone(business_tz()):%d/%m/%Y %H:%M}" if inicio < fin else 'Fuera de la retención disponible'
    columnas = [('fecha', 'Fecha Lima'), ('accion', 'Acción'), ('dispositivo', 'Dispositivo actual referenciado'), ('oficina', 'Oficina actual del dispositivo'), ('persona', 'Realizó el cambio'), ('resumen', 'Resumen seguro'), ('referencia', 'Registro afectado'), ('id', 'Referencia de auditoría')]
    for campo, etiqueta in [('oficina_origen', 'Oficina anterior registrada'), ('oficina_destino', 'Oficina nueva registrada'), ('responsable_anterior', 'Responsable anterior registrado'), ('responsable_nuevo', 'Responsable nuevo registrado')]:
        if any(f[campo] != 'Sin registrar' for f in filas): columnas.append((campo, etiqueta))
    return pagina(tabla(columnas, filas), total, numero,
        cobertura=cobertura, solicitado=f'{desde:%d/%m/%Y}–{hasta:%d/%m/%Y}', aviso='La auditoría conserva quince días. La ubicación actual de un dispositivo no acredita su ubicación en la fecha del movimiento; no se publica el payload privado.')


async def explorar(datos, usuario):
    from app.services import analitica_chat, analisis_catalogo
    nombre = datos['herramienta']
    if nombre not in HERRAMIENTAS or usuario.get('rol') not in {'tecnico', 'administrador'} or not analitica_chat._permitida(nombre, usuario):
        raise Prohibido('Tu cuenta no tiene acceso a este desglose.')
    filtros = datos.get('filtros') or {}
    opciones = {k: v for k, v in datos.items() if k not in {'herramienta', 'filtros', 'argumentos'} and v not in (None, '')}
    argumentos = datos.get('argumentos') or {}
    if nombre in analisis_catalogo.CONSULTAS:
        argumentos = analisis_catalogo.argumentos_seguros(nombre, argumentos)
    elif argumentos:
        raise Validacion('El resumen de inventario no admite esos argumentos.')
    if nombre == 'auditoria_responsables' and datos.get('texto') is None and argumentos.get('equipo'):
        opciones['texto'] = argumentos['equipo']
    if nombre == 'responsables_inventario' and not opciones.get('grupo'):
        opciones['grupo'] = argumentos.get('grupo', 'sin_cuenta')
    if nombre == 'oficinas_datos_pendientes' and opciones.get('vista', 'resumen') == 'resumen':
        from app.services.analisis_inventario import oficinas_datos_pendientes
        resultado = await oficinas_datos_pendientes(filtros, opciones)
        return pagina(resultado['tabla'], resultado['total_filas'], opciones.get('pagina', 1), resultado['indicadores'])
    if nombre == 'resumen_inventario' and opciones.get('vista', 'resumen') == 'resumen':
        resultado = await resumen_inventario(filtros, opciones)
        numero = opciones.get('pagina', 1)
        filas = resultado['tabla']['filas']
        return pagina({**resultado['tabla'], 'filas': filas[(numero - 1) * 20:numero * 20], 'indicadores': resultado['indicadores']}, len(filas), numero, resultado['indicadores'])
    if nombre in INVENTARIO:
        if not tiene_permiso(usuario, 'equipos.ver'): raise Prohibido('No tienes acceso al inventario.')
        if (datos.get('argumentos') or {}).get('campo') and not opciones.get('campo'):
            opciones['campo'] = datos['argumentos']['campo']
        resultado = await inventario(nombre, filtros, opciones)
        resultado['tabla']['indicadores'] = resultado['indicadores']
        return grafico_inventario(nombre, resultado)
    if nombre in {'auditoria_cambios', 'auditoria_responsables'}:
        if usuario.get('rol') != 'administrador': raise Prohibido('La auditoría está reservada a administradores.')
        if nombre == 'auditoria_cambios' and (any(filtros.get(c) for c in ('oficina_id', 'zona_id', 'equipo_id', 'categoria', 'tecnico_id', 'tipo_activo')) or any(opciones.get(c) for c in ('texto', 'tipo', 'oficina', 'responsable', 'oficina_id', 'responsable_id', 'equipo_id', 'campo', 'grupo', 'fecha'))):
            raise Validacion('La auditoría general no dispone de esos filtros. Consulta el historial de un equipo para limitar sus movimientos.')
        opciones['_usuario'] = usuario
        return await auditoria(filtros, opciones, historial=nombre == 'auditoria_responsables')
    argumentos = dict(datos.get('argumentos') or {})
    if any(opciones.get(c) for c in ('texto', 'tipo', 'oficina', 'responsable', 'oficina_id', 'responsable_id', 'equipo_id', 'campo', 'grupo')) or opciones.get('orden') == 'porcentaje':
        raise Validacion('Esta consulta no admite esos filtros de inventario.')
    if nombre == 'resumen_equipo_ti' and opciones.get('vista') == 'detalle':
        respuesta = await analitica_chat.ejecutar_herramienta('tickets_pendientes_detalle', {'modo': 'antiguos', 'historial_completo': True, 'pagina': opciones.get('pagina', 1), 'limite': 20}, filtros=filtros, usuario=usuario)
        return pagina(respuesta['tabla'], respuesta['total'], opciones.get('pagina', 1), texto=respuesta['texto'])
    if nombre == 'horarios_manana' and opciones.get('fecha'): argumentos['fecha'] = opciones['fecha']
    argumentos['pagina'] = opciones.get('pagina', 1)
    if nombre in {'tickets_pendientes_detalle', 'resumen_equipo_ti', 'horarios_manana'}:
        argumentos['limite'] = 20
    # El catálogo valida nuevamente argumentos, rol y permiso; nunca ejecuta operadores libres.
    respuesta = await analitica_chat.ejecutar_herramienta(nombre, argumentos, filtros=filtros, usuario=usuario)
    filas = (respuesta.get('tabla') or {}).get('filas', [])
    numero = opciones.get('pagina', 1)
    return pagina(respuesta['tabla'], respuesta.get('total', len(filas)), numero)
