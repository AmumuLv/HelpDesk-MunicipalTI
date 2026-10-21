"""Auditoría del archivo anual actual, sin mezclarlo con el inventario operativo."""
import asyncio
from io import BytesIO

import pytest
import pytest_asyncio
from bson import ObjectId
from openpyxl import Workbook, load_workbook

from app.services import usuario_service
from tests.test_tickets_horarios import _sesion, PASSWORD

COLUMNAS = ['AREA', 'Tipo de equipo', 'Dispositivo', 'Código patrimonial', 'Marca', 'Nombre Equipo', 'Estado', 'Responsable', 'Direccion IP', 'Direccion MAC', 'Propiedad']


def excel(filas, zona='PALACIO'):
    libro = Workbook()
    hoja = libro.active
    hoja.title = zona
    hoja.append(COLUMNAS)
    for fila in filas:
        hoja.append(fila)
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def fila(codigo='AN-001', nombre='Laptop de revisión', oficina='SOPORTE', marca='LENOVO', responsable='Persona de prueba', ip='', mac=''):
    return [oficina, 'Laptop', 'Laptop', codigo, marca, nombre, 'OPERATIVO', responsable, ip, mac, 'MUNICIPAL']


@pytest_asyncio.fixture
async def admin_anual(api, db):
    await usuario_service.crear({'nombre': 'Admin archivo', 'email': 'archivo@prueba.local', 'password': PASSWORD, 'rol': 'administrador'}, usuario={'nombre': 'Pruebas', 'rol': 'sistema'}, es_primer_admin=True)
    return await _sesion(api, 'archivo@prueba.local')


async def subir(api, headers, contenido, anio=2030, nombre='revision.xlsx', zona=None):
    datos = {'anio': str(anio)}
    if zona is not None:
        datos['zona_csv'] = zona
    return await api.post('/api/campanas/anual/importar', headers=headers, data=datos, files={'archivo': (nombre, contenido)})


async def test_eliminar_version_solo_admin_con_csrf_conserva_operativo_y_otras_copias(api, db, admin_anual):
    await db.activos.insert_one({'tipo': 'Laptop', 'oficina_id': ObjectId(), 'campos_estado': {}, 'nombre_equipo': 'Conservar'})
    original = await db.activos.find({}).to_list(None)
    primera = (await subir(api, admin_anual, excel([fila()]), anio=2030)).json()
    segunda = (await subir(api, admin_anual, excel([fila(nombre='Otra revisión')]), anio=2030)).json()
    await subir(api, admin_anual, excel([fila()]), anio=2031)
    ruta = f"/api/campanas/versiones/{segunda['id']}"
    assert (await api.delete(ruta)).status_code == 401
    assert (await api.delete(ruta, headers={'Authorization': admin_anual['Authorization']})).status_code == 403
    tecnico = await usuario_service.crear({'nombre': 'Técnico delegado', 'email': 'delegado@prueba.local', 'password': PASSWORD, 'rol': 'tecnico'}, usuario={'rol': 'administrador', 'nombre': 'Pruebas'})
    await api.put(f"/api/permisos/tecnicos/{tecnico['_id']}", headers=admin_anual, json={'cambios': {'equipos.campanas': True}})
    assert (await api.delete(ruta, headers=await _sesion(api, 'delegado@prueba.local'))).status_code == 403
    assert (await api.delete(ruta, headers=admin_anual)).status_code == 200
    assert (await api.delete(ruta, headers=admin_anual)).status_code == 404
    assert await db.activos.find({}).to_list(None) == original
    assert await db.inventario_versiones.count_documents({'anio': 2030}) == 1
    assert await db.inventario_versiones.count_documents({'anio': 2031}) == 1
    assert await db.auditoria.find_one({'accion': 'inventario.anual.eliminar', 'entidad_id': segunda['id']})
    # Las versiones de campañas no se borran por este endpoint.
    protegida = await db.inventario_versiones.find_one({'_id': ObjectId(primera['id'])})
    protegida.pop('_id')
    protegida.update(fuente='verificacion', campana_id=ObjectId(), archivo_hash='version-campana')
    id_campana = (await db.inventario_versiones.insert_one(protegida)).inserted_id
    assert (await api.delete(f'/api/campanas/versiones/{id_campana}', headers=admin_anual)).status_code == 404
    assert await db.inventario_versiones.find_one({'_id': id_campana})


async def test_registro_busqueda_paginacion_y_descarga_sin_tocar_operativo(api, db, admin_anual):
    await db['activos'].insert_one({'nombre_equipo': 'No modificar', 'activo': True, 'tipo': 'Laptop', 'oficina_id': ObjectId(), 'campos_estado': {}})
    antes = await db['activos'].find({}).to_list(None)
    carga = await subir(api, admin_anual, excel([fila(f'AN-{i:03}', f'Laptop {i:02}') for i in range(35)]))
    assert carga.status_code == 201, carga.text
    version = carga.json()['id']
    assert carga.json()['total_items'] == 35
    base = f'/api/campanas/versiones/{version}/equipos'
    primera = (await api.get(base, headers=admin_anual)).json()
    assert len(primera['items']) == 25 and primera['total_paginas'] == 2
    segunda = (await api.get(base, params={'pagina': 2}, headers=admin_anual)).json()
    assert len(segunda['items']) == 10
    fuera = (await api.get(base, params={'pagina': 99}, headers=admin_anual)).json()
    assert fuera['pagina'] == 2
    for termino in ['Laptop 34', 'AN-034']:
        buscado = (await api.get(base, params={'texto': termino}, headers=admin_anual)).json()
        assert buscado['total'] == 1
    vacio = (await api.get(base, params={'texto': 'No existe'}, headers=admin_anual)).json()
    assert vacio['items'] == [] and vacio['total'] == 0
    for params in [{'pagina': 0}, {'por_pagina': 101}, {'por_pagina': 0}]:
        assert (await api.get(base, params=params, headers=admin_anual)).status_code == 422
    descarga = await api.get(f'/api/campanas/versiones/{version}/excel', headers=admin_anual)
    assert descarga.status_code == 200 and 'attachment' in descarga.headers['content-disposition']
    libro = load_workbook(BytesIO(descarga.content), read_only=True)
    assert 'PALACIO' in libro.sheetnames
    assert 'Laptop 34' in str(list(libro['PALACIO'].values))
    assert await db['activos'].find({}).to_list(None) == antes


@pytest.mark.parametrize('caso', ['vacio', 'corrupto', 'sin_equipos', 'sin_area', 'duplicado', 'ip_invalida', 'ip_repetida', 'mac_invalida', 'anio_menor', 'anio_mayor'])
async def test_archivos_invalidos_no_crean_version_parcial(api, db, admin_anual, caso):
    contenido, anio = excel([fila()]), 2030
    if caso == 'vacio': contenido = b''
    elif caso == 'corrupto': contenido = b'Esto no es un Excel'
    elif caso == 'sin_equipos': contenido = excel([])
    elif caso == 'sin_area': contenido = excel([fila(oficina='')])
    elif caso == 'duplicado': contenido = excel([fila(), fila(nombre='Otro equipo')])
    elif caso == 'ip_invalida': contenido = excel([fila(ip='999.999.1.1')])
    elif caso == 'ip_repetida': contenido = excel([fila(ip='192.168.1.2'), fila('AN-002', ip='192.168.1.2')])
    elif caso == 'mac_invalida': contenido = excel([fila(mac='esto no es una MAC')])
    elif caso == 'anio_menor': anio = 1999
    elif caso == 'anio_mayor': anio = 2101
    respuesta = await subir(api, admin_anual, contenido, anio)
    assert respuesta.status_code == 422, respuesta.text
    assert await db['inventario_versiones'].count_documents({}) == 0


async def test_csv_zona_obligatoria_y_duplicados_concurrentes(api, db, admin_anual):
    csv = ('AREA;Tipo de equipo;Dispositivo;Código patrimonial;Nombre Equipo\nSOPORTE;Laptop;Laptop;CSV-001;Portátil CSV\n').encode('utf-8')
    assert (await subir(api, admin_anual, csv, nombre='revision.csv')).status_code == 422
    valida = await subir(api, admin_anual, csv, nombre='revision.csv', zona='PALACIO')
    assert valida.status_code == 201, valida.text
    ident = valida.json()['id']
    repetida = await subir(api, admin_anual, csv, nombre='copia.csv', zona='PALACIO')
    assert repetida.json()['id'] == ident and repetida.json()['ya_registrado']
    contenido = excel([fila()])
    respuestas = await asyncio.gather(*(subir(api, admin_anual, contenido, 2031) for _ in range(3)))
    assert all(r.status_code == 201 for r in respuestas)
    assert len({r.json()['id'] for r in respuestas}) == 1
    assert await db['inventario_versiones'].count_documents({'anio': 2031}) == 1


async def test_csv_mismo_contenido_con_zona_corregida_crea_otra_revision(api, db, admin_anual):
    csv = b'AREA;Tipo de equipo;Dispositivo;Codigo patrimonial;Nombre Equipo\nSOPORTE;Laptop;Laptop;CSV-001;Portatil\n'
    primera = await subir(api, admin_anual, csv, nombre='revision.csv', zona='PALACIO')
    corregida = await subir(api, admin_anual, csv, nombre='revision.csv', zona='OTRA SEDE')
    assert primera.status_code == corregida.status_code == 201
    assert primera.json()['id'] != corregida.json()['id'], 'La zona es parte del contenido de una versión CSV.'
    filas = (await api.get(f"/api/campanas/versiones/{corregida.json()['id']}/equipos", headers=admin_anual)).json()['items']
    assert filas[0]['zona'] == 'OTRA SEDE'


async def test_comparacion_altas_salidas_traslados_responsables_y_revision_reciente(api, db, admin_anual):
    a = excel([fila('A-001', 'Laptop trasladada'), fila('B-001', 'Sin cambios'), fila('C-001', 'Solo en origen')])
    b = excel([fila('A-001', 'Laptop trasladada', oficina='CAJA', marca='DELL', responsable='Otra persona'), fila('B-001', 'Sin cambios'), fila('D-001', 'Solo en destino')])
    for anio, contenido in [(2030, a), (2031, b)]:
        assert (await subir(api, admin_anual, contenido, anio)).status_code == 201
    datos = (await api.get('/api/campanas/versiones/comparar', params={'anio_a': 2030, 'anio_b': 2031}, headers=admin_anual)).json()
    assert datos['suficiente_datos'] and datos['sin_cambios'] == 1
    assert [i['codigo'] for i in datos['altas']] == ['D-001']
    assert [i['codigo'] for i in datos['bajas']] == ['C-001']
    assert [i['codigo'] for i in datos['traslados']] == ['A-001']
    assert [i['codigo'] for i in datos['cambios_responsable']] == ['A-001']
    assert datos['porcentaje_cambio'] == 75
    ultima = await subir(api, admin_anual, excel([fila('E-001', 'Última revisión')]), 2031, 'ultima.xlsx')
    nueva = (await api.get('/api/campanas/versiones/comparar', params={'anio_a': 2030, 'anio_b': 2031}, headers=admin_anual)).json()
    assert nueva['versiones'][1]['id'] == ultima.json()['id']
    assert nueva['totales']['2031'] == 1
    assert await db['activos'].count_documents({}) == 0


async def test_rangos_versiones_inexistentes_y_eliminacion_anual(api, db, admin_anual):
    for origen, destino in [(2030, 2030), (2031, 2030)]:
        assert (await api.get('/api/campanas/versiones/comparar', params={'anio_a': origen, 'anio_b': destino}, headers=admin_anual)).status_code == 422
    faltante = (await api.get('/api/campanas/versiones/comparar', params={'anio_a': 2030, 'anio_b': 2031}, headers=admin_anual)).json()
    assert not faltante['suficiente_datos']
    inexistente = str(ObjectId())
    for sufijo in ['equipos', 'excel']:
        assert (await api.get(f'/api/campanas/versiones/{inexistente}/{sufijo}', headers=admin_anual)).status_code == 404
        assert (await api.get(f'/api/campanas/versiones/invalido/{sufijo}', headers=admin_anual)).status_code == 422
    version = (await subir(api, admin_anual, excel([fila()]))).json()['id']
    # El administrador puede retirar su copia anual independiente.
    assert (await api.delete(f'/api/campanas/versiones/{version}', headers=admin_anual)).status_code == 200
    assert await db['inventario_versiones'].count_documents({}) == 0


async def test_acceso_restringido_y_csrf_en_registro(api, db, admin_anual):
    for rol in ['usuario', 'tecnico']:
        await usuario_service.crear({'nombre': f'Cuenta {rol}', 'email': f'{rol}@prueba.local', 'password': PASSWORD, 'rol': rol}, usuario={'nombre': 'Admin', 'rol': 'administrador'})
        cab = await _sesion(api, f'{rol}@prueba.local')
        assert (await api.get('/api/campanas/versiones/historico', headers=cab)).status_code == 403
        assert (await subir(api, cab, excel([fila()]))).status_code == 403
    sin_csrf = {'Authorization': admin_anual['Authorization']}
    assert (await subir(api, sin_csrf, excel([fila()]))).status_code == 403
    assert (await api.get('/api/campanas/versiones/historico')).status_code == 401
    assert await db['inventario_versiones'].count_documents({}) == 0
    tecnico = await db['usuarios'].find_one({'email': 'tecnico@prueba.local'}, {'_id': 1})
    permiso = await api.put(f"/api/permisos/tecnicos/{tecnico['_id']}", headers=admin_anual, json={'cambios': {'equipos.campanas': True}})
    assert permiso.status_code == 200, permiso.text
    delegado = await _sesion(api, 'tecnico@prueba.local')
    assert (await api.get('/api/campanas/versiones/historico', headers=delegado)).status_code == 200
    assert (await subir(api, delegado, excel([fila()]))).status_code == 201
