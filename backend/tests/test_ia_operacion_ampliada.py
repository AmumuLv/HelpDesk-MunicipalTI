"""Listados de trabajo y métricas explicables, sin alterar los registros."""
from datetime import timedelta
from unittest.mock import AsyncMock

from bson import ObjectId
import pytest

from app.core.errors import Prohibido, Validacion
from app.core.time import local_date, utcnow
from app.services import analisis_operacion as operaciones, analitica_service
from tests.test_analisis_flujos import _tickets
from tests.test_gobernanza_y_reportes import _mundo


ADMIN = {'_id': ObjectId(), 'rol': 'administrador'}
TECNICO = {'_id': ObjectId(), 'rol': 'tecnico'}


class TestOperacionSinServicios:
    @pytest.fixture(scope='class', autouse=True)
    @classmethod
    def mongo_replica_set(cls):
        yield None

    @pytest.mark.parametrize('pregunta,esperado', [
        ('Muéstrame los tickets vencidos', ('tickets_pendientes_detalle', {'modo': 'vencidos'})),
        ('Muéstrame los tickets más antiguos', ('tickets_pendientes_detalle', {'modo': 'antiguos'})),
        ('Muéstrame los tickets sin asignar', ('tickets_pendientes_detalle', {'modo': 'sin_asignar'})),
        ('Muéstrame los tickets sin equipo vinculado', ('tickets_pendientes_detalle', {'modo': 'sin_equipo'})),
        ('Muéstrame los tickets con reaperturas', ('tickets_pendientes_detalle', {'modo': 'reabiertos'})),
        ('Muéstrame todos los pendientes más antiguos', ('tickets_pendientes_detalle', {'modo': 'antiguos', 'historial_completo': True})),
        ('¿Cómo está la carga del equipo TI?', ('resumen_equipo_ti', {})),
        ('¿Qué tiempos, valoraciones y reaperturas tiene cada técnico?', ('resumen_equipo_ti', {})),
        ('¿Qué técnicos tienen horario mañana?', ('horarios_manana', {})),
        ('¿Qué técnico estará disponible mañana?', ('horarios_manana', {})),
        ('¿Qué oficina tiene más incidencias?', None),
        ('¿Qué tickets tienen el plazo vencido?', None),
        ('¿Cuántos equipos tenemos?', None),
        ('¿Qué técnico está disponible ahora?', None),
    ])
    def test_deteccion_no_intercepta_consultas_anteriores(self, pregunta, esperado):
        assert operaciones.detectar(pregunta) == esperado

    @pytest.mark.parametrize('funcion', [operaciones.tickets_pendientes, operaciones.resumen_equipo, operaciones.horarios_manana])
    async def test_usuario_sin_acceso_no_consulta_servicios(self, funcion, monkeypatch):
        def prohibido():
            raise AssertionError('No se debe consultar ninguna colección')
        monkeypatch.setattr(operaciones, 'get_db', prohibido)
        for usuario in (None, {'_id': ObjectId(), 'rol': 'usuario', 'permisos': {'analitica.ver': True}}):
            with pytest.raises(Prohibido):
                await funcion({}, {}, usuario=usuario)

    @pytest.mark.parametrize('argumentos', [
        {'limite': 0}, {'limite': 21}, {'limite': True}, {'limite': {'$gt': 1}},
        {'modo': {'$ne': 'vencidos'}}, {'modo': 'borrar'}, {'historial_completo': 'true'},
        {'$where': 'texto'}, {'usuario': {'rol': 'administrador'}},
    ])
    async def test_argumentos_no_admiten_operadores_ni_limites_excesivos(self, argumentos):
        with pytest.raises(Validacion):
            await operaciones.tickets_pendientes({}, argumentos, usuario=ADMIN)

    @pytest.mark.parametrize('filtros', [
        {'oficina_id': {'$ne': None}}, {'categoria': {'$regex': '.*'}},
        {'desde': {'$gt': 0}, 'hasta': local_date()}, {'propiedad': 'Particular'},
        {'periodo': 'todos'},
    ])
    async def test_filtros_invalidos_se_rechazan(self, filtros):
        with pytest.raises(Validacion):
            await operaciones.tickets_pendientes(filtros, {}, usuario=ADMIN)

    @pytest.mark.parametrize('como_texto', [False, True])
    def test_rango_explicito_prevalece_sobre_etiqueta_legible(self, como_texto):
        hoy = local_date()
        valor = hoy.isoformat() if como_texto else hoy
        seguros = operaciones._filtros({'desde': valor, 'hasta': valor, 'periodo': hoy.strftime('%d/%m/%Y') + ' – ' + hoy.strftime('%d/%m/%Y')})
        assert seguros['desde'] == seguros['hasta'] == hoy
        assert analitica_service.resolver_periodo(seguros)[:2] == (hoy, hoy)

    @pytest.mark.parametrize('fechas', [{}, {'desde': local_date()}])
    def test_etiqueta_desconocida_sin_rango_completo_sigue_rechazandose(self, fechas):
        with pytest.raises(Validacion, match='periodo válido'):
            operaciones._filtros({'periodo': 'rango no verificable', **fechas})

    async def test_filtros_contradictorios_no_se_ignoran(self):
        with pytest.raises(Validacion, match='técnico asignado'):
            await operaciones.tickets_pendientes({'tecnico_id': ObjectId()}, {'modo': 'sin_asignar'}, usuario=ADMIN)
        with pytest.raises(Validacion, match='equipo específico'):
            await operaciones.tickets_pendientes({'equipo_id': ObjectId()}, {'modo': 'sin_equipo'}, usuario=ADMIN)

    async def test_manana_usa_horario_previsto_y_oculta_motivos_de_ausencia(self, monkeypatch):
        manana = local_date() + timedelta(days=1)
        identificador = ObjectId()
        calendario = AsyncMock(return_value=[
            {'tecnico_id': identificador, 'tecnico_nombre': 'Técnica Uno', 'fecha': manana,
             'tramos': [{'entrada': '08:00', 'salida': '12:00'}], 'horas_disponibles': 4,
             'carga_pendiente': 3, 'vencimientos': 1},
            {'tecnico_id': ObjectId(), 'tecnico_nombre': 'Técnico Dos', 'fecha': manana,
             'tramos': [], 'horas_disponibles': 0, 'ausencia': 'Tratamiento médico reservado'},
        ])
        monkeypatch.setattr(operaciones.horario_service, 'calendario_equipo', calendario)
        respuesta = await operaciones.horarios_manana({}, {}, usuario=TECNICO)
        calendario.assert_awaited_once_with(manana, manana)
        assert respuesta['tabla']['filas'][0]['horario'] == '08:00–12:00'
        assert respuesta['tabla']['filas'][0]['pendientes_hoy'] == 3
        assert respuesta['tabla']['filas'][1]['estado'] == 'Ausencia registrada'
        assert 'Tratamiento' not in str(respuesta)
        assert 'No garantiza' in respuesta['texto']
        assert 'Los pendientes son los de hoy' in respuesta['texto']
        filtrada = await operaciones.horarios_manana({'tecnico_id': identificador}, {}, usuario=TECNICO)
        assert filtrada['total'] == 1

    @pytest.mark.parametrize('filtros', [{'oficina_id': ObjectId()}, {'tipo_activo': 'Laptop'}, {'desde': local_date(), 'hasta': local_date()}])
    async def test_horario_no_ignora_filtros_de_tickets(self, filtros):
        with pytest.raises(Validacion, match='no admite filtros'):
            await operaciones.horarios_manana(filtros, {}, usuario=ADMIN)


async def test_listados_excluyen_borrados_cerrados_y_respeta_fecha_ubicacion_y_limite(db, api):
    mundo = await _mundo(api, 'operacion-listas')
    oficina = ObjectId(mundo['oficina']['id'])
    ahora = utcnow()
    inicio = analitica_service._a_utc(local_date())
    ids = (await _tickets(db, [
        {'codigo': 'OP-1', 'creado_en': inicio, 'oficina_id': oficina, 'estado': 'nuevo', 'sla_resolver_en': ahora - timedelta(hours=2)},
        {'codigo': 'OP-2', 'creado_en': inicio, 'oficina_id': oficina, 'estado': 'nuevo', 'sla_resolver_en': ahora - timedelta(hours=1)},
        {'codigo': 'OP-SIN-PLAZO', 'creado_en': inicio, 'oficina_id': oficina, 'estado': 'nuevo'},
        {'codigo': 'OP-CERRADO', 'creado_en': inicio, 'oficina_id': oficina, 'estado': 'cerrado', 'sla_resolver_en': ahora - timedelta(hours=3)},
        {'codigo': 'OP-BORRADO', 'creado_en': inicio, 'oficina_id': oficina, 'estado': 'nuevo', 'eliminado': True, 'sla_resolver_en': ahora - timedelta(hours=4)},
        {'codigo': 'OP-ANTERIOR', 'creado_en': inicio - timedelta(days=100), 'oficina_id': oficina, 'estado': 'nuevo', 'sla_resolver_en': ahora - timedelta(hours=5)},
        {'codigo': 'OP-OTRA', 'creado_en': inicio, 'oficina_id': ObjectId(), 'estado': 'nuevo', 'sla_resolver_en': ahora - timedelta(hours=6)},
    ])).inserted_ids
    usuario = {'_id': ObjectId(mundo['tecnico_id']), 'rol': 'tecnico'}
    filtros = {'desde': local_date(), 'hasta': local_date(), 'oficina_id': oficina}
    antes = await db['tickets'].find({}).sort('_id', 1).to_list(None)
    resultado = await operaciones.tickets_pendientes(filtros, {'modo': 'vencidos', 'limite': 1}, usuario=usuario)
    assert resultado['total'] == 2
    assert resultado['mostrados'] == 1
    assert resultado['tabla']['filas'][0]['codigo'] == 'OP-1'
    assert resultado['enlaces'][0]['href'] == '/panel/tickets/' + str(ids[0])
    assert 'Muestro 1 de 2' in resultado['texto']
    assert 'sin fecha límite' in resultado['texto']
    completo = await operaciones.tickets_pendientes(filtros, {'modo': 'vencidos', 'historial_completo': True}, usuario=usuario)
    assert completo['total'] == 3
    assert completo['tabla']['filas'][0]['codigo'] == 'OP-ANTERIOR'
    assert 'Historial completo' in completo['periodo_label']
    despues = await db['tickets'].find({}).sort('_id', 1).to_list(None)
    assert antes == despues


async def test_sin_equipo_distingue_conjunto_y_reaperturas_puede_incluir_cerrados(db):
    ahora = utcnow()
    await _tickets(db, [
        {'codigo': 'SIN-DISPOSITIVO', 'creado_en': ahora, 'estado': 'nuevo'},
        {'codigo': 'CON-PC', 'creado_en': ahora, 'estado': 'nuevo', 'conjunto_id': ObjectId()},
        {'codigo': 'CON-LAPTOP', 'creado_en': ahora, 'estado': 'nuevo', 'activo_id': ObjectId()},
        {'codigo': 'REABIERTO', 'creado_en': ahora, 'estado': 'cerrado', 'veces_reabierto': 2},
    ])
    sin_equipo = await operaciones.tickets_pendientes({}, {'modo': 'sin_equipo'}, usuario=ADMIN)
    assert [fila['codigo'] for fila in sin_equipo['tabla']['filas']] == ['SIN-DISPOSITIVO']
    reabiertos = await operaciones.tickets_pendientes({}, {'modo': 'reabiertos'}, usuario=ADMIN)
    assert reabiertos['total'] == 1
    assert reabiertos['tabla']['filas'][0]['reaperturas'] == 2
    assert 'cerrados actualmente' in reabiertos['texto']


async def test_metricas_equipo_separan_periodo_pendientes_y_muestras(db, api, monkeypatch):
    mundo = await _mundo(api, 'operacion-equipo')
    tecnico = ObjectId(mundo['tecnico_id'])
    oficina = ObjectId(mundo['oficina']['id'])
    hoy = local_date()
    inicio = analitica_service._a_utc(hoy)
    await _tickets(db, [
        {'codigo': 'TI-CON-DATOS', 'creado_en': inicio, 'estado': 'cerrado', 'tecnico_id': tecnico, 'oficina_id': oficina,
         'tiempo_resolucion_min': 40, 'satisfaccion': 4, 'veces_reabierto': 2},
        {'codigo': 'TI-SIN-DATOS', 'creado_en': inicio, 'estado': 'nuevo', 'tecnico_id': tecnico, 'oficina_id': oficina},
        {'codigo': 'TI-HISTORICO', 'creado_en': inicio - timedelta(days=100), 'estado': 'nuevo', 'tecnico_id': tecnico, 'oficina_id': oficina},
        {'codigo': 'TI-OTRA', 'creado_en': inicio, 'estado': 'nuevo', 'tecnico_id': tecnico, 'oficina_id': ObjectId()},
        {'codigo': 'TI-BORRADO', 'creado_en': inicio, 'estado': 'nuevo', 'tecnico_id': tecnico, 'oficina_id': oficina, 'eliminado': True},
    ])
    monkeypatch.setattr(operaciones.horario_service, 'horas_laborables', AsyncMock(return_value=8))
    respuesta = await operaciones.resumen_equipo({'desde': hoy, 'hasta': hoy, 'oficina_id': oficina, 'tecnico_id': tecnico}, {}, usuario=ADMIN)
    assert respuesta['total'] == 1
    fila = respuesta['tabla']['filas'][0]
    assert fila['asignados_periodo'] == 2
    assert fila['cerrados'] == 1
    assert fila['pendientes_actuales'] == 2
    assert fila['tiempo_medio_min'] == 40
    assert fila['registros_tiempo'] == 1
    assert fila['satisfaccion'] == 4
    assert fila['valoraciones'] == 1
    assert fila['reaperturas'] == 2
    assert fila['horas_programadas'] == 8
    assert fila['muestra'] == 'Pocos registros'
    assert 'no miden trabajo real' in respuesta['texto']
    vacia = await operaciones.resumen_equipo({'desde': hoy - timedelta(days=2), 'hasta': hoy - timedelta(days=2), 'tecnico_id': tecnico}, {}, usuario=ADMIN)
    fila_vacia = vacia['tabla']['filas'][0]
    assert fila_vacia['asignados_periodo'] == 0
    assert fila_vacia['tiempo_medio_min'] is None
    assert fila_vacia['satisfaccion'] is None
    assert fila_vacia['registros_tiempo'] == fila_vacia['valoraciones'] == 0
