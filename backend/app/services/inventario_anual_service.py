"""Archivo anual independiente del inventario operativo y comparación reproducible."""
from __future__ import annotations

import hashlib
import re
from typing import Any
from bson import ObjectId, BSON
from pymongo.errors import DuplicateKeyError
from app.core.db import get_db
from app.core.errors import NoEncontrado, Validacion
from app.core.ids import clave, normalizar_texto, limpiar_codigo_patrimonial, mcp_ip, mcp_mac
from app.core.time import utcnow
from app.core.audit import registrar
from app.domain.constants import CAMPOS_BASE
from app.services import excel_service, import_service, catalogo_service


def identidad(item: dict) -> str:
    codigo = limpiar_codigo_patrimonial(item.get('codigo'))
    if codigo:
        return 'patrimonio:' + clave(codigo)
    if item.get('activo_id'):
        return 'activo:' + str(item['activo_id'])
    grupo = item.get('conjunto_nombre') or (item.get('campos') or {}).get('tipo_equipo') or ''
    patron = import_service._patron_conjunto(grupo)
    if patron:
        grupo = f"{patron['base']} {int(patron['numero'])}"
    return 'sin-codigo:' + '|'.join(clave(str(item.get(c) or '')) for c in ('zona', 'oficina', 'tipo', 'nombre')) + '|' + clave(grupo)


async def importar(anio: int, contenido: bytes, nombre: str, zona_csv: str | None, usuario: dict) -> dict:
    if not 2000 <= anio <= 2100:
        raise Validacion('Selecciona un año entre 2000 y 2100.')
    if not contenido or len(contenido) > 20 * 1024 * 1024:
        raise Validacion('Selecciona un archivo de hasta 20 MB.')
    db = get_db()
    es_csv = nombre.lower().endswith('.csv')
    zona_csv = normalizar_texto(zona_csv)
    if es_csv and not zona_csv:
        raise Validacion('Indica la zona a la que pertenece el CSV. Para varias zonas usa Excel con una hoja por zona.')
    huella_contenido = hashlib.sha256(contenido).hexdigest()
    # La zona no está dentro de un CSV: también forma parte de su versión.
    huella = hashlib.sha256(contenido + b'\x00zona-csv:' + clave(zona_csv).encode('utf-8')).hexdigest() if es_csv else huella_contenido
    previo = await db['inventario_versiones'].find_one({'anio': anio, 'archivo_hash': huella}, {'instantanea': 0})
    if not previo and es_csv:
        # Compatibilidad con CSV anteriores, cuya huella solo incluía los bytes.
        previo = await db['inventario_versiones'].find_one({'anio': anio, 'archivo_hash': huella_contenido,
            'archivo_nombre': {'$regex': r'\.csv$', '$options': 'i'},
            'instantanea.0.zona': {'$regex': '^' + re.escape(zona_csv) + '$', '$options': 'i'}}, {'instantanea': 0})
    if previo:
        return {**previo, 'id': str(previo['_id']), 'ya_registrado': True}
    hojas = excel_service.leer_archivo(contenido, nombre)
    if es_csv:
        if not normalizar_texto(zona_csv):
            raise Validacion('Indica la zona a la que pertenece el CSV. Para varias zonas usa Excel con una hoja por zona.')
        hojas = {normalizar_texto(zona_csv): next(iter(hojas.values()))}
    filas: list[dict] = []
    vistos: dict[str, str] = {}
    redes: dict[tuple[str, str], str] = {}
    errores: list[str] = []
    sinonimos = await catalogo_service.mapa_sinonimos()
    tipos = {clave(t): t for t in await catalogo_service.tipos_existentes()}
    sin_codigo = 0
    for zona, hoja in hojas.items():
        if clave(zona) == 'DETALLE AVANZADO':
            continue
        cabeceras, registros = excel_service.hoja_a_registros(hoja)
        mapeo = import_service.detectar_mapeo(cabeceras)
        oficina_anterior = ''
        grupo_anterior = ''
        def valor(registro, campo):
            columna = (mapeo.get(campo) or {}).get('columna')
            return normalizar_texto(registro.get(columna, '')) if columna else ''
        for registro in registros:
            campos = {c: valor(registro, c) or None for c in CAMPOS_BASE}
            campos.update({c: valor(registro, c) or None for c in ('tipo_equipo', 'dispositivo')})
            oficina = valor(registro, 'area') or oficina_anterior
            if clave(oficina) != clave(oficina_anterior):
                grupo_anterior = ''
            grupo = valor(registro, 'tipo_equipo') or grupo_anterior
            oficina_anterior, grupo_anterior = oficina, grupo
            tipo = import_service._resolver_tipo(valor(registro, 'dispositivo') or grupo, sinonimos, tipos)
            nombre_equipo = campos.get('nombre_equipo') or tipo
            campos['tipo_equipo'] = grupo or None
            campos['dispositivo'] = tipo
            campos['codigo_patrimonial'] = limpiar_codigo_patrimonial(campos.get('codigo_patrimonial'))
            personal = clave(campos.get('propiedad') or '') == 'PERSONAL'
            if personal:
                campos['codigo_patrimonial'] = None
            origen = f'{zona}, fila {registro.get("__fila__", "?")}'
            for campo, validar in [('direccion_ip', mcp_ip), ('direccion_mac', mcp_mac)]:
                crudo = campos.get(campo)
                if not crudo or import_service._es_texto_sin_dato(crudo) or clave(crudo) in {'NO APLICA', 'NO DISPONIBLE'}:
                    campos[campo] = None
                    continue
                if campo == 'direccion_ip' and clave(tipo or '') == 'IMPRESORA' and clave(crudo) in {'USB', 'CABLE USB'}:
                    campos[campo] = 'Cable USB'
                    continue
                normalizado = validar(crudo)
                if not normalizado:
                    errores.append(f'{origen}: {campo} inválida: {crudo}.')
                else:
                    llave_red = (campo, normalizado)
                    if llave_red in redes:
                        errores.append(f'{origen}: {campo} repetida ({normalizado}); primera aparición: {redes[llave_red]}.')
                    redes[llave_red] = origen
                    campos[campo] = normalizado
            if not nombre_equipo or not oficina:
                raise Validacion(f'Hoja «{zona}», fila {registro.get("__fila__", "?")}: faltan el equipo o el área/oficina.')
            fila = {'activo_id': None, 'codigo': campos.get('codigo_patrimonial'), 'nombre': nombre_equipo,
                    'tipo': tipo or 'Equipo', 'oficina': oficina, 'zona': zona, 'responsable': valor(registro, 'responsable') or None,
                    'conjunto_nombre': grupo or None, 'uso_comun': not bool(valor(registro, 'responsable')), 'estado_item': 'archivo_anual', 'campos': campos}
            llave = identidad(fila)
            if llave in vistos:
                errores.append(f'{origen}: equipo repetido: {fila["codigo"] or nombre_equipo} ({grupo or "sin conjunto"}). Primera aparición: {vistos[llave]}.')
            vistos[llave] = f'{zona}, fila {registro.get("__fila__", "?")}'
            sin_codigo += not bool(fila['codigo'])
            filas.append(fila)
    if errores:
        raise Validacion('Revisa el Excel antes de registrar:\n' + '\n'.join(errores[:25]) + (f'\nY {len(errores)-25} errores más.' if len(errores) > 25 else ''))
    if not filas:
        raise Validacion('El archivo no contiene equipos. Usa las cabeceras de la plantilla de inventario.')
    ahora = utcnow()
    documento = {'anio': anio, 'campana_id': None, 'codigo_campana': f'ANUAL-{anio}-{ObjectId().__str__()[-6:].upper()}',
                 'fuente': 'archivo_anual', 'archivo_nombre': nombre, 'archivo_hash': huella,
                 'archivo_hash_contenido': huella_contenido, 'zona_csv': zona_csv if es_csv else None,
                 'cerrado_en': ahora, 'cerrado_por': usuario.get('nombre', ''), 'total_items': len(filas),
                 'sin_codigo': sin_codigo, 'instantanea': filas}
    if len(BSON.encode(documento)) > 14 * 1024 * 1024:
        raise Validacion('El inventario supera el tamaño admitido por versión. Reduce columnas o texto innecesario.')
    try:
        resultado = await db['inventario_versiones'].insert_one(documento)
        documento['_id'] = resultado.inserted_id
    except DuplicateKeyError:
        documento = await db['inventario_versiones'].find_one({'anio': anio, 'archivo_hash': huella})
    await registrar('inventario.anual', usuario_id=usuario['_id'], usuario_nombre=usuario.get('nombre', ''), rol=usuario.get('rol', ''), entidad='inventario_anual', entidad_id=documento['_id'], resumen=f'Inventario de {anio} registrado: {len(filas)} equipos', despues={'anio': anio, 'equipos': len(filas), 'archivo': nombre})
    return {k: v for k, v in {**documento, 'id': str(documento['_id'])}.items() if k != 'instantanea'}


async def equipos(version_id: ObjectId, pagina: int, por_pagina: int, texto: str = '') -> dict:
    version = await get_db()['inventario_versiones'].find_one({'_id': version_id})
    if not version:
        raise NoEncontrado('La versión del inventario no existe.')
    termino = clave(texto)
    filas = [i for i in version.get('instantanea', []) if not termino or termino in clave(' '.join(str(i.get(c) or '') for c in ('nombre', 'codigo', 'tipo', 'zona', 'oficina', 'responsable', 'conjunto_nombre')))]
    total = len(filas)
    paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(pagina, paginas)
    return {'items': filas[(pagina - 1) * por_pagina:pagina * por_pagina], 'total': total, 'pagina': pagina, 'por_pagina': por_pagina, 'total_paginas': paginas}


async def eliminar(version_id: ObjectId, usuario: dict) -> dict:
    """Borra una copia anual independiente; nunca elimina activos operativos."""
    db = get_db()
    version = await db['inventario_versiones'].find_one_and_delete({
        '_id': version_id, 'fuente': 'archivo_anual', 'campana_id': None,
    })
    if not version:
        raise NoEncontrado('El archivo anual no existe o pertenece a una campaña.')
    await registrar('inventario.anual.eliminar', usuario_id=usuario['_id'],
                    usuario_nombre=usuario.get('nombre', ''), rol=usuario.get('rol', ''),
                    entidad='inventario_anual', entidad_id=version_id,
                    resumen=f"Versión del inventario {version['anio']} eliminada",
                    antes={'anio': version['anio'], 'archivo': version.get('archivo_nombre'), 'equipos': version.get('total_items')})
    return {'eliminada': True}


async def comparar(anio_a: int, anio_b: int) -> dict:
    if anio_a >= anio_b:
        raise Validacion('El año de origen debe ser anterior al año de destino.')
    db = get_db()
    versiones = []
    for anio in (anio_a, anio_b):
        version = await db['inventario_versiones'].find_one({'anio': anio, 'fuente': 'archivo_anual'}, sort=[('cerrado_en', -1), ('_id', -1)])
        version = version or await db['inventario_versiones'].find_one({'anio': anio}, sort=[('cerrado_en', -1), ('_id', -1)])
        if not version:
            return {'suficiente_datos': False, 'mensaje': f'Registra el inventario de {anio} para comparar.'}
        versiones.append(version)
    mapas = [{identidad(i): i for i in v.get('instantanea', [])} for v in versiones]
    a, b = mapas
    altas = [b[k] for k in sorted(b.keys() - a.keys())]
    bajas = [a[k] for k in sorted(a.keys() - b.keys())]
    cambios, traslados, responsables = [], [], []
    alterados = set()
    for llave in sorted(a.keys() & b.keys()):
        antes, despues = a[llave], b[llave]
        campos_a = {**(antes.get('campos') or {}), **{c: antes.get(c) for c in ('zona', 'oficina', 'responsable', 'tipo')}}
        campos_b = {**(despues.get('campos') or {}), **{c: despues.get(c) for c in ('zona', 'oficina', 'responsable', 'tipo')}}
        diferencias = [{'campo': c, 'antes': campos_a.get(c), 'despues': campos_b.get(c)} for c in sorted(campos_a.keys() | campos_b.keys()) if (campos_a.get(c) or None) != (campos_b.get(c) or None)]
        if diferencias:
            alterados.add(llave)
            cambios.append({'codigo': despues.get('codigo'), 'nombre': despues.get('nombre'), 'diferencias': diferencias})
        if (antes.get('zona'), antes.get('oficina')) != (despues.get('zona'), despues.get('oficina')):
            traslados.append({'codigo': despues.get('codigo'), 'nombre': despues.get('nombre'), 'de': f'{antes.get("zona")} · {antes.get("oficina")}', 'a': f'{despues.get("zona")} · {despues.get("oficina")}'})
        if antes.get('responsable') != despues.get('responsable'):
            responsables.append({'codigo': despues.get('codigo'), 'nombre': despues.get('nombre'), 'de': antes.get('responsable'), 'a': despues.get('responsable')})
    universo = len(a.keys() | b.keys())
    return {'suficiente_datos': True, 'anios': [anio_a, anio_b], 'versiones': [{'id': str(v['_id']), 'codigo': v.get('codigo_campana'), 'archivo': v.get('archivo_nombre'), 'fuente': v.get('fuente', 'verificacion')} for v in versiones],
            'totales': {str(anio_a): len(a), str(anio_b): len(b)}, 'altas': altas, 'bajas': bajas, 'traslados': traslados, 'cambios_responsable': responsables, 'cambios': cambios,
            'comunes': len(a.keys() & b.keys()), 'sin_cambios': len(a.keys() & b.keys()) - len(alterados),
            'porcentaje_cambio': round(100 * (len(altas) + len(bajas) + len(alterados)) / universo, 1) if universo else 0,
            'criterio': 'Se identifica por código patrimonial. Sin código se usan zona, oficina, conjunto, tipo y nombre; un traslado sin código puede aparecer como salida y alta. Las salidas de esta comparación no dan de baja equipos del inventario operativo.'}
