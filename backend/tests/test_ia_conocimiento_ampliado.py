"""Guías y auditoría: consultas acotadas, permisos y ausencia de escrituras."""
from datetime import timedelta
from unittest.mock import AsyncMock

from bson import ObjectId
import pytest

from app.core.errors import Prohibido, Validacion
from app.core.time import local_date, utcnow
from app.services import analisis_conocimiento as consultas
from app.services import analitica_service
from tests.test_analisis_flujos import _tickets

ADMIN = {'_id': ObjectId(), 'rol': 'administrador', 'nombre': 'Admin ficticio'}
TECNICO = {'_id': ObjectId(), 'rol': 'tecnico', 'nombre': 'Técnico ficticio', 'permisos': {'analitica.ver': True}}


class TestSinServicios:
    @pytest.fixture(scope='class', autouse=True)
    @classmethod
    def mongo_replica_set(cls):
        yield None

    @pytest.fixture(autouse=True)
    def impedir_servicios(self, monkeypatch):
        def prohibido(*args, **kwargs):
            raise AssertionError('No debe consultar servicios reales')
        monkeypatch.setattr(consultas, 'get_db', prohibido)
        monkeypatch.setattr(consultas, 'agregar', prohibido)

    @pytest.mark.parametrize('pregunta,herramienta', [
        ('¿Qué guías son las más consultadas?', 'guias_consultadas'),
        ('¿Qué guías están mejor valoradas?', 'guias_valoradas'),
        ('¿Qué problemas frecuentes no tienen una guía?', 'brechas_guias'),
        ('¿Qué cambios se registraron en el periodo?', 'auditoria_cambios'),
        ('¿Quién cambió el responsable del equipo «CPU-01»?', 'auditoria_responsables'),
    ])
    def test_preguntas_canonicas_y_nombres(self, pregunta, herramienta):
        resultado = consultas.detectar(pregunta)
        assert resultado and resultado[0] == herramienta
        assert herramienta in consultas.CONSULTAS

    def test_detecta_nombre_exacto_sin_interpretarlo_como_consulta(self):
        nombre, argumentos = consultas.detectar('¿Quién cambió el responsable del equipo «CPU.$-01» esta semana?')
        assert nombre == 'auditoria_responsables'
        assert argumentos == {'equipo': 'CPU.$-01'}
        assert consultas.detectar('¿Cuántos equipos hay en el sistema?') is None

    @pytest.mark.parametrize('herramienta', ['guias_consultadas', 'guias_valoradas', 'brechas_guias', 'auditoria_cambios', 'auditoria_responsables'])
    async def test_usuario_final_no_obtiene_consultas_ti(self, herramienta):
        with pytest.raises(Prohibido):
            await consultas.CONSULTAS[herramienta]['funcion']({}, {}, usuario={'rol': 'usuario'})

    @pytest.mark.parametrize('herramienta', ['auditoria_cambios', 'auditoria_responsables'])
    async def test_tecnico_con_todos_los_delegables_no_obtiene_auditoria(self, herramienta):
        with pytest.raises(Prohibido):
            await consultas.CONSULTAS[herramienta]['funcion']({}, {}, usuario={**TECNICO, 'permisos': {'reportes.ver': True, 'auditoria.ver': True}})

    async def test_brecha_exige_permiso_de_analisis(self):
        with pytest.raises(Prohibido):
            await consultas.brechas_guias({}, {}, usuario={**TECNICO, 'permisos': {}})

    @pytest.mark.parametrize('filtros', [{'oficina_id': ObjectId()}, {'equipo_id': ObjectId()}, {'tecnico_id': ObjectId()}, {'tipo_activo': 'Laptop'}])
    async def test_guias_no_fingen_aplicar_filtros_de_ubicacion_o_dispositivo(self, filtros):
        with pytest.raises(Validacion, match='no están asignadas'):
            await consultas.guias_consultadas(filtros, {}, usuario=ADMIN)

    @pytest.mark.parametrize('pregunta', ['¿Qué guías son las más consultadas hoy?', '¿Qué guías están mejor valoradas este mes?'])
    async def test_no_confunde_contador_acumulado_con_lecturas_del_dia(self, pregunta):
        nombre, argumentos = consultas.detectar(pregunta)
        assert argumentos == {'periodo_explicito': True}
        with pytest.raises(Validacion, match='acumuladas'):
            await consultas.CONSULTAS[nombre]['funcion']({}, argumentos, usuario=ADMIN)

    @pytest.mark.parametrize('argumentos', [{'semana_actual': {'$ne': True}}, {'$where': 'cualquier cosa'}])
    async def test_argumentos_de_herramienta_no_aceptan_operadores(self, argumentos):
        with pytest.raises(Validacion):
            await consultas.auditoria_cambios({}, argumentos, usuario=ADMIN)

    @pytest.mark.parametrize('filtros', [{'oficina_id': ObjectId()}, {'categoria': 'Impresora'}, {'tipo_activo': 'CPU'}, {'tecnico_id': ObjectId()}])
    async def test_auditoria_rechaza_filtros_sin_fuente_confiable(self, filtros):
        with pytest.raises(Validacion):
            await consultas.auditoria_cambios(filtros, {}, usuario=ADMIN)

    @pytest.mark.parametrize('nombre', ['correo@example.invalid', 'Bearer secreto ficticio', 'token=reservado', None])
    def test_actor_no_filtra_correos_o_credenciales(self, nombre):
        assert consultas._nombre_actor(nombre) == 'Cuenta TI'

    async def test_guia_sin_valoraciones_no_se_presenta_con_cero_de_utilidad(self, monkeypatch):
        consulta = AsyncMock(return_value=[{'items': [], 'conteo': []}])
        monkeypatch.setattr(consultas, 'agregar', consulta)
        respuesta = await consultas.guias_valoradas({'periodo': '30d'}, {}, usuario=ADMIN)
        assert respuesta['tabla']['filas'] == []
        assert respuesta['suficiente_datos'] is False
        assert 'no equivale' in respuesta['texto']
        assert 'acumuladas' in respuesta['periodo_label']


async def test_guias_usan_lecturas_y_votos_reales_sin_incrementarlos(db):
    ahora = utcnow()
    articulo_a, articulo_b, viejo, retirado = [ObjectId() for _ in range(4)]
    await db.articulos_kb.insert_many([
        {'_id': articulo_a, 'titulo': 'Guía red', 'categoria': 'Internet / Red', 'activo': True, 'visibilidad': 'todos', 'visualizaciones': 7, 'actualizado_en': ahora, 'cuerpo': 'CUERPO_PRIVADO_NO_DEVOLVER'},
        {'_id': articulo_b, 'titulo': 'Guía hardware', 'categoria': 'Hardware', 'activo': True, 'visibilidad': 'equipo_ti', 'visualizaciones': 10, 'actualizado_en': ahora},
        {'_id': viejo, 'titulo': 'Guía red', 'categoria': 'Internet / Red', 'activo': True, 'visibilidad': 'todos', 'visualizaciones': 999, 'actualizado_en': ahora - timedelta(days=1)},
        {'_id': retirado, 'titulo': 'Guía retirada', 'categoria': 'Correo', 'activo': False, 'visualizaciones': 9999, 'actualizado_en': ahora},
    ])
    u1, u2, u3 = ObjectId(), ObjectId(), ObjectId()
    await db.articulos_kb_valoraciones.insert_many([
        {'articulo_id': articulo_b, 'usuario_id': u1, 'util': False, 'fecha': ahora - timedelta(days=1)},
        {'articulo_id': articulo_b, 'usuario_id': u1, 'util': True, 'fecha': ahora, 'formato': 2},
        {'articulo_id': articulo_b, 'usuario_id': u2, 'util': True, 'fecha': ahora},
        {'articulo_id': articulo_a, 'usuario_id': u3, 'util': False, 'fecha': ahora},
    ])
    antes = await db.articulos_kb.find({}).sort('_id').to_list(None)
    lecturas = await consultas.guias_consultadas({'periodo': '30d'}, {}, usuario=TECNICO)
    assert [(f['guia'], f['lecturas']) for f in lecturas['tabla']['filas']] == [('Guía hardware', 10), ('Guía red', 7)]
    assert all(e['href'].startswith('/panel/ayuda/') for e in lecturas['enlaces'])
    assert 'CUERPO_PRIVADO_NO_DEVOLVER' not in str(lecturas)
    valoradas = await consultas.guias_valoradas({}, {}, usuario=TECNICO)
    assert valoradas['tabla']['filas'][0] == {'guia': 'Guía hardware', 'porcentaje_util': 100.0, 'valoraciones': 2, 'utiles': 2, 'muestra': 'Pocas valoraciones'}
    assert valoradas['tabla']['filas'][1]['porcentaje_util'] == 0
    assert await db.articulos_kb.find({}).sort('_id').to_list(None) == antes
    assert await db.articulos_kb_valoraciones.count_documents({}) == 4


async def test_brechas_respetan_periodo_oficina_y_categoria_sin_inventar_causas(db):
    hoy = analitica_service._a_utc(local_date())
    oficina, otra = ObjectId(), ObjectId()
    await _tickets(db, [
        {'creado_en': hoy, 'oficina_id': oficina, 'categoria': 'Hardware'},
        {'creado_en': hoy, 'oficina_id': oficina, 'categoria': 'Hardware'},
        {'creado_en': hoy, 'oficina_id': oficina, 'categoria': 'Correo'},
        {'creado_en': hoy, 'oficina_id': oficina, 'categoria': None},
        {'creado_en': hoy - timedelta(days=10), 'oficina_id': oficina, 'categoria': 'Impresora'},
        {'creado_en': hoy, 'oficina_id': otra, 'categoria': 'Impresora'},
        {'creado_en': hoy, 'oficina_id': oficina, 'categoria': 'Impresora', 'eliminado': True},
    ])
    await db.articulos_kb.insert_many([
        {'titulo': 'Guía de hardware', 'categoria': 'HARDWARE', 'activo': True, 'visibilidad': 'equipo_ti'},
        {'titulo': 'Guía de correo retirada', 'categoria': 'Correo', 'activo': False},
    ])
    respuesta = await consultas.brechas_guias({'desde': local_date(), 'hasta': local_date(), 'oficina_id': oficina}, {}, usuario=TECNICO)
    filas = respuesta['tabla']['filas']
    assert {f['categoria'] for f in filas} == {'Correo', 'Sin clasificar'}
    assert sum(f['total'] for f in filas) == 2
    assert '4 tickets' in respuesta['texto']
    assert 'no analiza su contenido' in respuesta['texto']
    assert await db.tickets.count_documents({}) == 7


async def test_auditoria_proyecta_solo_actor_fecha_accion_entidad_y_conserva_retencion(db):
    ahora = utcnow()
    eventos = [
        {'fecha': ahora, 'rol': 'administrador', 'accion': 'activo.editar', 'usuario_nombre': 'Admin ficticio', 'entidad': 'activo', 'antes': {'password': 'SECRETO_SIMULADO'}, 'despues': {'token': 'TOKEN_SIMULADO'}, 'resumen': 'RESUMEN_PRIVADO', 'contexto': {'email': 'privado@example.invalid'}, 'ip': 'IP_PRIVADA'},
        {'fecha': ahora, 'rol': 'tecnico', 'accion': 'ticket.estado', 'usuario_nombre': 'tecnico@example.invalid', 'entidad': 'ticket'},
        {'fecha': ahora, 'rol': 'administrador', 'accion': 'auth.login', 'usuario_nombre': 'Login ordinario'},
        {'fecha': ahora - timedelta(days=20), 'rol': 'administrador', 'accion': 'activo.editar', 'usuario_nombre': 'Antiguo'},
        {'fecha': ahora, 'rol': 'usuario', 'accion': 'activo.editar', 'usuario_nombre': 'No TI'},
    ]
    await db.auditoria.insert_many(eventos)
    conservados = {'fecha': {'$gte': ahora - timedelta(days=14)}}
    antes = await db.auditoria.count_documents(conservados)
    respuesta = await consultas.auditoria_cambios({'periodo': '30d'}, {}, usuario=ADMIN)
    assert len(respuesta['tabla']['filas']) == 2
    assert {f['persona'] for f in respuesta['tabla']['filas']} == {'Admin ficticio', 'Cuenta TI'}
    for reservado in ['SECRETO_SIMULADO', 'TOKEN_SIMULADO', 'RESUMEN_PRIVADO', 'privado@example.invalid', 'IP_PRIVADA', 'tecnico@example.invalid']:
        assert reservado not in str(respuesta)
    assert '15 días' in respuesta['texto']
    anterior = local_date() - timedelta(days=40)
    fuera = await consultas.auditoria_cambios({'desde': anterior, 'hasta': anterior + timedelta(days=1)}, {}, usuario=ADMIN)
    assert fuera['suficiente_datos'] is False
    assert 'No puedo reconstruir' in fuera['texto']
    assert await db.auditoria.count_documents(conservados) == antes


async def test_responsable_exige_equipo_unico_y_excluye_otros_equipos(db):
    ahora = utcnow()
    oficina, otra = ObjectId(), ObjectId()
    equipo, segundo = ObjectId(), ObjectId()
    await db.activos.insert_many([
        {'_id': equipo, 'tipo': 'CPU', 'oficina_id': oficina, 'campos_estado': {}, 'nombre_equipo': 'CPU-01', 'codigo_patrimonial': '740000001', 'clave_natural': 'auditoria-cpu-1'},
        {'_id': segundo, 'tipo': 'CPU', 'oficina_id': otra, 'campos_estado': {}, 'nombre_equipo': 'CPU-01', 'codigo_patrimonial': '740000002', 'clave_natural': 'auditoria-cpu-2'},
    ])
    await db.auditoria.insert_many([
        {'fecha': ahora, 'rol': 'administrador', 'accion': 'activo.responsable', 'usuario_nombre': 'Actor del primero', 'entidad': 'activos', 'entidad_id': str(equipo)},
        {'fecha': ahora, 'rol': 'administrador', 'accion': 'activo.responsable', 'usuario_nombre': 'Actor del segundo', 'entidad': 'activos', 'entidad_id': str(segundo)},
    ])
    coincidencias = await consultas.auditoria_responsables({}, {'equipo': 'CPU-01'}, usuario=ADMIN)
    assert coincidencias['total'] == 2
    assert {f['id'] for f in coincidencias['tabla']['filas']} == {str(equipo), str(segundo)}
    respuesta = await consultas.auditoria_responsables({'oficina_id': oficina}, {'equipo': 'CPU-01'}, usuario=ADMIN)
    assert [f['persona'] for f in respuesta['tabla']['filas']] == ['Actor del primero']
    por_codigo = await consultas.auditoria_responsables({}, {'equipo': '740000002'}, usuario=ADMIN)
    assert [f['persona'] for f in por_codigo['tabla']['filas']] == ['Actor del segundo']
    por_id = await consultas.auditoria_responsables({'equipo_id': equipo}, {}, usuario=ADMIN)
    assert [f['persona'] for f in por_id['tabla']['filas']] == ['Actor del primero']
    assert await db.auditoria.count_documents({}) == 2
