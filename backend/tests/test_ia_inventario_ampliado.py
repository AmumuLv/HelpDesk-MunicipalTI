"""Consultas de inventario de la IA: cálculos trazables, filtros y solo lectura."""
from copy import deepcopy
from unittest.mock import AsyncMock

from bson import ObjectId
import pytest

from app.core.errors import Validacion
from app.services import analisis_inventario as consultas
from app.services import catalogo_service


class TestSinServicios:
    @pytest.fixture(scope='class', autouse=True)
    @classmethod
    def mongo_replica_set(cls):
        yield None

    @pytest.fixture(autouse=True)
    def no_consultar_servicios(self, monkeypatch):
        def prohibido(*args, **kwargs):
            raise AssertionError('Esta prueba no debe leer la base de datos')
        monkeypatch.setattr(consultas, 'get_db', prohibido)

    @pytest.mark.parametrize('nombre', list(consultas.CONSULTAS))
    def test_cada_pregunta_canonica_tiene_consulta_real_y_lectura(self, nombre):
        definicion = consultas.CONSULTAS[nombre]
        assert definicion['lectura'] and all(definicion['lectura'])
        assert callable(definicion['funcion'])
        assert definicion['grupo'] == 'Equipos'
        assert all(consultas.detectar(p)[0] == nombre for p in definicion['preguntas'])

    @pytest.mark.parametrize('pregunta', [
        '¿Qué equipos no tienen código patrimonial?',
        '¿Qué dispositivos no tienen patrimonio?',
    ])
    def test_equipos_sin_patrimonio_aplica_el_campo_explicito(self, pregunta):
        assert consultas.detectar(pregunta) == ('equipos_datos_pendientes', {'campo': 'codigo_patrimonial'})
        assert any('patrimonial' in p for p in consultas.CONSULTAS['equipos_datos_pendientes']['preguntas'])

    @pytest.mark.parametrize('pregunta', [
        '¿Para qué sirve el inventario anual?', '¿Cómo comparo dos inventarios anuales?',
        '¿Qué significa el porcentaje de datos faltantes?', '¿Cómo importo un inventario anual?',
    ])
    def test_ayuda_funcional_no_se_convierte_en_un_recuento(self, pregunta):
        assert consultas.detectar(pregunta) is None

    @pytest.mark.parametrize('pregunta', [
        '¿Quién cambió el responsable de un equipo?',
        '¿Quién asignó un equipo sin responsable?',
        '¿Quién modificó el responsable vinculado de este equipo?',
        '¿Qué cambios se hicieron en el inventario?',
    ])
    def test_auditoria_no_se_confunde_con_inventario_actual_o_anual(self, pregunta):
        assert consultas.detectar(pregunta) is None

    @pytest.mark.parametrize('pregunta', [
        'Compara los inventarios de 2025 y 2026',
        '¿Qué cambió entre los inventarios de 2026 y 2025?',
    ])
    def test_comparar_reconoce_ambos_anios_sin_inventar_el_orden(self, pregunta):
        assert consultas.detectar(pregunta) == ('comparar_inventarios', {'anio_a': 2025, 'anio_b': 2026})

    def test_tres_anios_no_se_reducen_silenciosamente_a_dos(self):
        assert consultas.detectar('Compara los inventarios de 2024, 2025 y 2026') == ('comparar_inventarios', {})

    @pytest.mark.parametrize('campo', ['oficina_id', 'zona_id', 'tipo_activo', 'equipo_id', 'categoria', 'tecnico_id'])
    async def test_anual_rechaza_filtros_no_soportados_antes_de_leer(self, campo):
        with pytest.raises(Validacion, match='archivos anuales'):
            await consultas.comparar_inventarios({campo: 'no-importa'}, {'anio_a': 2025, 'anio_b': 2026})

    @pytest.mark.parametrize('funcion', [consultas.calidad_inventario, consultas.equipos_datos_pendientes, consultas.responsables_inventario])
    async def test_inventario_no_ignora_un_filtro_de_tickets(self, funcion):
        with pytest.raises(Validacion, match='no admite'):
            await funcion({'categoria': 'Impresora'}, {})

    async def test_tipo_no_cambia_el_significado_de_conjunto(self):
        with pytest.raises(Validacion, match='sin filtro de tipo'):
            await consultas.conjuntos_incompletos({'tipo_activo': 'Laptop'}, {})

    async def test_campo_operador_no_se_usa_como_consulta_mongo(self):
        with pytest.raises(Validacion, match='dato de inventario'):
            await consultas.equipos_datos_pendientes({}, {'campo': {'$ne': None}})

    def test_anual_exige_permiso_de_campanas_y_otros_usan_inventario(self):
        for nombre, definicion in consultas.CONSULTAS.items():
            assert definicion['permiso'] == ('equipos.campanas' if definicion['ambito'] == 'anual' else 'equipos.ver')


def _activo(oficina, **valores):
    return {'tipo': 'CPU', 'oficina_id': oficina, 'oficina_nombre': 'OFICINA A',
            'activo': True, 'campos_estado': {}, 'clave_natural': str(ObjectId()), **valores}


async def test_calidad_usa_valores_reales_excluye_no_aplica_filtra_y_no_escribe(db, monkeypatch):
    esquema = AsyncMock(return_value={'esperados': ['codigo_patrimonial', 'procesador'], 'opcionales': []})
    monkeypatch.setattr(catalogo_service, 'esquema', esquema)
    oficina_a, oficina_b = ObjectId(), ObjectId()
    ids = (await db['activos'].insert_many([
        _activo(oficina_a, nombre_equipo='CPU completo', codigo_patrimonial='IA-CAL-1', procesador='Intel i7'),
        _activo(oficina_a, tipo='Laptop', nombre_equipo='Laptop pendiente', procesador='Intel i5'),
        _activo(oficina_b, tipo='Monitor', oficina_nombre='OFICINA B', nombre_equipo='No aplica',
                campos_estado={'codigo_patrimonial': {'estado': 'no_aplica'}, 'procesador': {'estado': 'no_disponible'}}),
        _activo(oficina_a, nombre_equipo='CPU pendiente'),
        _activo(oficina_a, activo=False, nombre_equipo='No contar'),
    ])).inserted_ids
    antes = await db['activos'].find({}).sort('_id').to_list(None)

    respuesta = await consultas.calidad_inventario({}, {})
    assert '4 dispositivos' in respuesta['texto']
    assert '3 de 6 datos' in respuesta['texto']
    assert '(50.0%)' in respuesta['texto']
    assert next(f['total'] for f in respuesta['tabla']['filas'] if f['campo'] == 'Procesador') == 1
    pendientes = await consultas.equipos_datos_pendientes({'oficina_id': oficina_a}, {'campo': 'codigo_patrimonial'})
    assert {f['nombre'] for f in pendientes['tabla']['filas']} == {'Laptop pendiente', 'CPU pendiente'}
    assert len(pendientes['enlaces']) == 2
    assert all(e['href'].startswith('/panel/equipos/') for e in pendientes['enlaces'])
    assert 'CPU completo' not in str(pendientes)
    assert (await consultas.equipos_datos_pendientes({'equipo_id': ids[0]}, {}))['tabla']['filas'] == []
    laptop = await consultas.equipos_datos_pendientes({'tipo_activo': 'Laptop'}, {})
    assert [f['nombre'] for f in laptop['tabla']['filas']] == ['Laptop pendiente']

    oficinas = await consultas.oficinas_datos_pendientes({}, {})
    assert next(f['porcentaje'] for f in oficinas['tabla']['filas'] if f['oficina'] == 'OFICINA B') is None
    assert next(f['faltantes'] for f in oficinas['tabla']['filas'] if f['oficina'] == 'OFICINA A') == 3
    assert await db['activos'].find({}).sort('_id').to_list(None) == antes


async def test_pendientes_acota_listado_pero_informa_total_y_sin_datos_no_es_cero(db, monkeypatch):
    monkeypatch.setattr(catalogo_service, 'esquema', AsyncMock(return_value={'esperados': ['codigo_patrimonial'], 'opcionales': []}))
    vacia = await consultas.calidad_inventario({}, {})
    assert 'No hay datos aplicables' in vacia['texto']
    oficina = ObjectId()
    await db['activos'].insert_many([_activo(oficina, nombre_equipo=f'CPU {i:02}') for i in range(25)])
    respuesta = await consultas.equipos_datos_pendientes({}, {})
    assert 'Hay 25 equipos' in respuesta['texto']
    assert len(respuesta['tabla']['filas']) == consultas.LIMITE == 20
    assert len(respuesta['enlaces']) == 20


async def test_responsables_distingue_compartido_uso_incierto_y_cuenta_archivada(db):
    activo, archivado = ObjectId(), ObjectId()
    await db['usuarios'].insert_many([
        {'_id': activo, 'nombre': 'Persona actual', 'nombre_busqueda': 'PERSONA ACTUAL', 'rol': 'usuario', 'activo': True},
        {'_id': archivado, 'nombre': 'Persona anterior', 'nombre_busqueda': 'PERSONA ANTERIOR', 'rol': 'usuario', 'activo': False},
    ])
    oficina = ObjectId()
    await db['activos'].insert_many([
        _activo(oficina, nombre_equipo='Propio actual', responsable_id=activo),
        _activo(oficina, nombre_equipo='Pendiente anterior', responsable_id=archivado, responsable_nombre='Persona anterior'),
        _activo(oficina, nombre_equipo='Nuevo perfil pendiente', responsable_nombre='Persona nueva'),
        _activo(oficina, nombre_equipo='Impresora compartida', tipo='Impresora', uso_comun=True),
        _activo(oficina, nombre_equipo='No identificado'),
    ])
    antes = await db['activos'].find({}).sort('_id').to_list(None)
    respuesta = await consultas.responsables_inventario({}, {})
    filas = {f['nombre']: f['relacion'] for f in respuesta['tabla']['filas']}
    assert 'Propio actual' not in filas
    assert filas['Impresora compartida'] == 'Compartido de oficina'
    assert filas['Pendiente anterior'] == filas['Nuevo perfil pendiente'] == 'Responsable pendiente de vincular'
    assert filas['No identificado'] == 'Uso por confirmar'
    assert '2 tienen responsable pendiente' in respuesta['texto']
    assert await db['activos'].find({}).sort('_id').to_list(None) == antes


async def test_conjuntos_no_agrupa_laptops_ni_cuenta_componentes_inactivos(db):
    oficina, primero, segundo = ObjectId(), ObjectId(), ObjectId()
    await db['conjuntos'].insert_many([
        {'_id': primero, 'activo': True, 'oficina_id': oficina, 'numero': 1, 'nombre': 'PC completa'},
        {'_id': segundo, 'activo': True, 'oficina_id': oficina, 'numero': 2, 'nombre': 'PC pendiente'},
    ])
    documentos = [_activo(oficina, tipo=t, conjunto_id=primero) for t in ('CPU', 'Monitor', 'Teclado', 'Mouse')]
    documentos += [_activo(oficina, tipo=t, conjunto_id=segundo) for t in ('CPU', 'Monitor', 'Mouse')]
    documentos += [_activo(oficina, tipo='Teclado', conjunto_id=segundo, activo=False),
                   _activo(oficina, tipo='Laptop', nombre_equipo='Laptop independiente')]
    ids = (await db['activos'].insert_many(documentos)).inserted_ids
    respuesta = await consultas.conjuntos_incompletos({}, {})
    assert len(respuesta['tabla']['filas']) == 1
    assert respuesta['tabla']['filas'][0]['nombre'] == 'PC pendiente'
    assert respuesta['tabla']['filas'][0]['faltantes'] == 'Teclado'
    assert 'De 2 PC de escritorio' in respuesta['texto']
    with pytest.raises(Validacion, match='independientes'):
        await consultas.conjuntos_incompletos({'equipo_id': ids[-1]}, {})


async def test_inventarios_requiere_dos_anos_usa_version_reciente_y_no_modifica(db):
    oficina = ObjectId()
    await db['activos'].insert_one(_activo(oficina, nombre_equipo='Operativo conservar'))
    comun = {'codigo': 'CP-IA-1', 'tipo': 'Laptop', 'nombre': 'Equipo conservado', 'oficina': 'OFICINA A', 'zona': 'PALACIO', 'responsable': 'Persona anterior'}
    cambiado = {**comun, 'oficina': 'OFICINA B', 'responsable': 'Persona nueva'}
    nuevo = {**comun, 'codigo': 'CP-IA-2', 'nombre': 'Equipo nuevo'}
    await db['inventario_versiones'].insert_many([
        {'anio': 2025, 'fuente': 'archivo_anual', 'instantanea': [comun]},
        {'anio': 2026, 'fuente': 'archivo_anual', 'instantanea': [comun]},
        {'anio': 2026, 'fuente': 'archivo_anual', 'instantanea': [cambiado, nuevo]},
    ])
    antes_activos = await db['activos'].find({}).to_list(None)
    antes_versiones = deepcopy(await db['inventario_versiones'].find({}).sort('_id').to_list(None))
    disponibles = await consultas.inventarios_disponibles({}, {})
    assert disponibles['tabla']['filas'] == [{'anio': 2026, 'versiones': 2}, {'anio': 2025, 'versiones': 1}]
    assert disponibles['seguimientos'] == ['Compara los inventarios de 2025 y 2026']
    sin_anios = await consultas.comparar_inventarios({}, {})
    assert sin_anios['suficiente_datos'] is False
    assert sin_anios['tabla']['filas'] == disponibles['tabla']['filas']
    resultado = await consultas.comparar_inventarios({}, {'anio_a': 2025, 'anio_b': 2026})
    filas = {f['movimiento']: f['total'] for f in resultado['tabla']['filas']}
    assert filas['Incorporaciones'] == filas['Cambios de ubicación'] == filas['Cambios de responsable'] == 1
    assert resultado['periodo_label'] == 'Inventarios 2025 y 2026'
    assert 'no dan de baja' in resultado['texto']
    faltante = await consultas.comparar_inventarios({}, {'anio_a': 2025, 'anio_b': 2027})
    assert faltante['suficiente_datos'] is False
    assert '2027' in faltante['texto']
    assert await db['activos'].find({}).to_list(None) == antes_activos
    assert await db['inventario_versiones'].find({}).sort('_id').to_list(None) == antes_versiones
