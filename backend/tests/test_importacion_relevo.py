"""El cambio de trabajador conserva el patrimonio y la identidad de cada caso."""
from io import BytesIO

from bson import ObjectId
from openpyxl import Workbook
import pytest

from tests.test_tickets_horarios import _mundo


def _excel(zona, filas):
    libro = Workbook()
    hoja = libro.active
    hoja.title = zona
    hoja.append(['AREA', 'Tipo de equipo', 'Dispositivo', 'Código patrimonial',
                 'Nombre equipo', 'Direccion MAC', 'Responsable', 'Marca'])
    for grupo, tipo, codigo, nombre, mac, persona, marca in filas:
        hoja.append(['COMUNA', grupo, tipo, codigo, nombre, mac, persona, marca])
    contenido = BytesIO()
    libro.save(contenido)
    return contenido.getvalue()


async def _previsualizar(api, mundo, filas):
    subida = await api.post('/api/importacion/subir', headers=mundo['admin'], files={
        'archivo': ('relevo.xlsx', _excel(mundo['zona']['nombre'], filas),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    })
    assert subida.status_code == 200, subida.text
    lote = subida.json()['lote_id']
    previa = await api.post(f'/api/importacion/{lote}/previsualizar', headers=mundo['admin'], json={})
    assert previa.status_code == 200, previa.text
    return lote, previa.json()


async def _confirmar(api, mundo, lote, *, crear_perfiles=False):
    respuesta = await api.post(f'/api/importacion/{lote}/confirmar', headers=mundo['admin'],
                               json={'crear_usuarios_faltantes': crear_perfiles})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


async def test_relevo_pc_conserva_ids_tickets_y_crea_un_solo_perfil(db, api):
    m = await _mundo(api, 'relevo')
    anterior = await db.usuarios.find_one({'_id': ObjectId(m['usuario_id'])})
    filas = [('COMPUTADORA N°1', tipo, f'REL-{i}', f'Componente {tipo}', None,
              anterior['nombre'], 'Marca original') for i, tipo in enumerate(('CPU', 'Monitor', 'Teclado', 'Mouse'))]
    lote, previa = await _previsualizar(api, m, filas)
    assert previa['validas'] == 4, previa
    assert (await _confirmar(api, m, lote))['creados'] == 4
    originales = {e['codigo_patrimonial']: e for e in await db.activos.find({}).to_list(None)}
    conjunto = await db.conjuntos.find_one({})
    assert conjunto['responsable_id'] == anterior['_id']
    for equipo in originales.values():
        historia_inicial = await db.historial_responsables.find({'activo_id': equipo['_id']}).to_list(None)
        assert len(historia_inicial) == 1
        assert historia_inicial[0]['responsable_id'] == anterior['_id'] and historia_inicial[0]['fin'] is None
    alta = await api.post('/api/tickets', headers=m['usuario'], json={
        'descripcion': 'Mi computadora presenta un fallo anterior al relevo', 'tipo_problema': 'No enciende',
    })
    assert alta.status_code == 201, alta.text
    ticket_id = ObjectId(alta.json()['ticket']['id'])
    vinculo = await api.patch(f'/api/tickets/{ticket_id}', headers=m['admin'], json={
        'categoria': 'Hardware', 'activo_id': str(originales['REL-0']['_id']),
    })
    assert vinculo.status_code == 200, vinculo.text
    ticket_antes = await db.tickets.find_one({'_id': ticket_id})
    total_personas = await db.usuarios.count_documents({})
    nuevas = [(g, t, c, n, mac, 'Trabajador de reemplazo', 'Marca revisada')
              for g, t, c, n, mac, _, _ in reversed(filas)]
    lote, previa = await _previsualizar(api, m, nuevas)
    assert previa['actualizaria'] == 4 and previa['crearia'] == 0
    assert all(f['cambia_responsable'] and f['responsable_anterior'] == anterior['nombre'] for f in previa['filas'])
    resultado = await _confirmar(api, m, lote, crear_perfiles=True)
    assert resultado['creados'] == 0 and resultado['actualizados'] == 4 and resultado['errores'] == 0, resultado
    assert resultado['usuarios_creados'] == 1
    assert await db.usuarios.count_documents({}) == total_personas + 1
    reemplazo = await db.usuarios.find_one({'nombre': 'Trabajador de reemplazo'})
    assert reemplazo['_id'] != anterior['_id']
    assert reemplazo['rol'] == 'usuario' and reemplazo['email'] is None and reemplazo['password_hash'] is None
    assert (await db.usuarios.find_one({'_id': anterior['_id']}))['nombre'] == anterior['nombre']
    assert await db.tickets.find_one({'_id': ticket_id}) == ticket_antes
    assert await db.activos.count_documents({}) == 4
    assert await db.conjuntos.count_documents({}) == 1
    assert (await db.conjuntos.find_one({'_id': conjunto['_id']}))['responsable_id'] == reemplazo['_id']
    for codigo, original in originales.items():
        equipo = await db.activos.find_one({'codigo_patrimonial': codigo})
        assert equipo['_id'] == original['_id'] and equipo['clave_natural'] == original['clave_natural']
        assert equipo['responsable_id'] == reemplazo['_id']
        historia = await db.historial_responsables.find({'activo_id': equipo['_id']}).sort('inicio').to_list(None)
        assert [h['responsable_id'] for h in historia] == [anterior['_id'], reemplazo['_id']]
        assert historia[0]['fin'] <= historia[1]['inicio'] and historia[1]['fin'] is None
    historial_antes = await db.historial_responsables.find({}).sort('_id').to_list(None)
    lote, _ = await _previsualizar(api, m, nuevas)
    repetido = await _confirmar(api, m, lote, crear_perfiles=True)
    assert repetido['creados'] == repetido['usuarios_creados'] == repetido['errores'] == 0
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historial_antes


async def test_reordenar_e_insertar_equipo_no_cruza_codigos_ni_crea_duplicados(db, api):
    m = await _mundo(api, 'orden')
    filas = [('Laptop', 'Laptop', codigo, nombre, None, None, marca) for codigo, nombre, marca in (
        ('ORD-A', 'Laptop A', 'Marca A'), ('ORD-B', 'Laptop B', 'Marca B'),
    )]
    lote, previa = await _previsualizar(api, m, filas)
    assert previa['validas'] == 2, previa
    assert (await _confirmar(api, m, lote))['creados'] == 2
    originales = {a['codigo_patrimonial']: a['_id'] for a in await db.activos.find({}).to_list(None)}
    nuevas = [('Laptop', 'Laptop', 'ORD-C', 'Laptop C', None, None, 'Marca C'), *reversed(filas)]
    lote, previa = await _previsualizar(api, m, nuevas)
    assert previa['actualizaria'] == 2 and previa['crearia'] == 1, previa
    r = await _confirmar(api, m, lote)
    assert r['actualizados'] == 2 and r['creados'] == 1 and r['errores'] == 0, r
    assert await db.activos.count_documents({}) == 3
    for codigo, id_original in originales.items():
        equipo = await db.activos.find_one({'codigo_patrimonial': codigo})
        assert equipo['_id'] == id_original
        assert equipo['marca'] == ('Marca A' if codigo == 'ORD-A' else 'Marca B')


async def test_mac_reconoce_laptop_aunque_cambie_nombre_y_trabajador(db, api):
    m = await _mundo(api, 'mac_relevo')
    primera = [('Laptop', 'Laptop', None, 'Laptop anterior', '02:11:22:33:44:55', None, None)]
    lote, _ = await _previsualizar(api, m, primera)
    assert (await _confirmar(api, m, lote))['creados'] == 1
    original = await db.activos.find_one({})
    nueva = [('Laptop', 'Laptop', None, 'Laptop renombrada', '02:11:22:33:44:55', 'Nueva persona MAC', None)]
    lote, previa = await _previsualizar(api, m, nueva)
    assert previa['actualizaria'] == 1 and previa['crearia'] == 0
    assert previa['filas'][0]['identificado_por'] == 'Dirección MAC'
    resultado = await _confirmar(api, m, lote, crear_perfiles=True)
    assert resultado['actualizados'] == 1 and resultado['errores'] == 0, resultado
    assert await db.activos.count_documents({}) == 1
    equipo = await db.activos.find_one({'_id': original['_id']})
    assert equipo['nombre_equipo'] == 'Laptop renombrada'
    assert equipo['responsable_id'] != original.get('responsable_id')


async def test_sin_identificador_nombres_unicos_sobreviven_a_otro_orden(db, api):
    m = await _mundo(api, 'nombres')
    filas = [('Impresora', 'Impresora', None, nombre, None, None, marca)
             for nombre, marca in [('Impresora recepción', 'Marca 1'), ('Impresora archivo', 'Marca 2')]]
    lote, previa = await _previsualizar(api, m, filas)
    assert previa['validas'] == 2, previa
    assert (await _confirmar(api, m, lote))['creados'] == 2
    originales = {a['nombre_equipo']: a['_id'] for a in await db.activos.find({}).to_list(None)}
    lote, previa = await _previsualizar(api, m, list(reversed(filas)))
    assert previa['actualizaria'] == 2 and previa['crearia'] == 0, previa
    resultado = await _confirmar(api, m, lote)
    assert resultado['actualizados'] == 2 and resultado['errores'] == 0
    assert {a['nombre_equipo']: a['_id'] for a in await db.activos.find({}).to_list(None)} == originales


async def test_identificador_nuevo_no_sustituye_equipo_sin_codigo_con_nombre_distinto(db, api):
    m = await _mundo(api, 'nuevo_codigo')
    anterior = await db.usuarios.find_one({'_id': ObjectId(m['usuario_id'])})
    alta = await api.post('/api/activos', headers=m['admin'], json={
        'tipo': 'Laptop', 'oficina_id': m['oficina']['id'],
        'responsable_id': m['usuario_id'], 'nombre_equipo': 'Laptop original sin patrimonio',
    })
    assert alta.status_code == 201, alta.text
    id_original = ObjectId(alta.json()['id'])
    equipo_antes = await db.activos.find_one({'_id': id_original})
    historia_antes = await db.historial_responsables.find({}).sort('_id').to_list(None)
    personas_antes = await db.usuarios.count_documents({})
    lote, previa = await _previsualizar(api, m, [(
        'Laptop', 'Laptop', 'PATRIMONIO-NUEVO', 'Otra laptop recién ingresada', None,
        'Persona diferente no debe crearse', None,
    )])
    assert previa['validas'] == 0 and previa['con_error'] == 1, previa
    assert previa['filas'][0]['accion'] == 'omitir'
    resultado = await _confirmar(api, m, lote, crear_perfiles=True)
    assert resultado['creados'] == resultado['actualizados'] == resultado['usuarios_creados'] == 0, resultado
    assert await db.activos.count_documents({}) == 1
    assert await db.activos.find_one({'_id': id_original}) == equipo_antes
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historia_antes
    assert await db.usuarios.count_documents({}) == personas_antes
    # Completar un patrimonio pendiente sí es seguro cuando se conserva el nombre
    # único del equipo: el rechazo no debe impedir esa corrección legítima.
    lote, previa = await _previsualizar(api, m, [(
        'Laptop', 'Laptop', 'PATRIMONIO-NUEVO', 'Laptop original sin patrimonio', None,
        anterior['nombre'], None,
    )])
    assert previa['actualizaria'] == 1 and previa['crearia'] == 0, previa
    assert previa['filas'][0]['existente_id'] == str(id_original)
    resultado = await _confirmar(api, m, lote)
    assert resultado['actualizados'] == 1 and resultado['creados'] == resultado['errores'] == 0, resultado
    equipo = await db.activos.find_one({'_id': id_original})
    assert equipo['responsable_id'] == anterior['_id']
    assert equipo['codigo_patrimonial'] == 'PATRIMONIO-NUEVO'
    assert await db.activos.count_documents({}) == 1
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historia_antes


@pytest.mark.parametrize('caso', ['patrimonio_duplicado', 'patrimonio_mac_cruzados', 'sin_identificacion', 'codigo_repetido_archivo'])
async def test_ambiguedad_no_cambia_equipos_ni_crea_perfiles(db, api, caso):
    m = await _mundo(api, 'ambiguo')
    for nombre, codigo, mac in [('Equipo A', 'AMB-A', '02:11:22:33:44:01'), ('Equipo B', 'AMB-B', '02:11:22:33:44:02')]:
        alta = await api.post('/api/activos', headers=m['admin'], json={
            'tipo': 'Laptop', 'oficina_id': m['oficina']['id'], 'nombre_equipo': nombre,
            'codigo_patrimonial': codigo, 'direccion_mac': mac,
        })
        assert alta.status_code == 201, alta.text
    filas = [('Laptop', 'Laptop', None, None, None, 'Persona no debe crearse', None)]
    if caso == 'patrimonio_duplicado':
        await db.activos.update_many({}, {'$set': {'codigo_patrimonial': 'AMB-DUP'}})
        filas[0] = ('Laptop', 'Laptop', 'AMB-DUP', None, None, 'Persona no debe crearse', None)
    elif caso == 'patrimonio_mac_cruzados':
        filas[0] = ('Laptop', 'Laptop', 'AMB-A', None, '02:11:22:33:44:02', 'Persona no debe crearse', None)
    elif caso == 'codigo_repetido_archivo':
        filas = [('Laptop', 'Laptop', 'AMB-NUEVO', nombre, None, 'Persona no debe crearse', None)
                 for nombre in ('Nombre 1', 'Nombre 2')]
    antes = await db.activos.find({}).sort('_id').to_list(None)
    personas_antes = await db.usuarios.count_documents({})
    lote, previa = await _previsualizar(api, m, filas)
    assert previa['validas'] == 0 and previa['con_error'] == len(filas), previa
    assert all(f['accion'] == 'omitir' and f['errores'] for f in previa['filas'])
    resultado = await _confirmar(api, m, lote, crear_perfiles=True)
    assert resultado['creados'] == resultado['actualizados'] == resultado['usuarios_creados'] == 0, resultado
    assert await db.activos.find({}).sort('_id').to_list(None) == antes
    assert await db.usuarios.count_documents({}) == personas_antes
