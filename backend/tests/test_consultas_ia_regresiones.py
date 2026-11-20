"""Regresiones de lenguaje común y filtros que no deben desaparecer en la IA."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
import pytest

from app.core.errors import Validacion
from app.core.time import local_date
from app.services import analisis_consultas, analitica_chat, analitica_service, ia_provider
from tests.test_analisis_flujos import _tickets
from tests.test_gobernanza_y_reportes import _mundo


class TestFiltrosSinServicios:
    @pytest.fixture(scope='class', autouse=True)
    @classmethod
    def mongo_replica_set(cls):
        """Sustituye el autouse global para estas pruebas puramente locales."""
        yield None

    @pytest.fixture(autouse=True)
    def no_consultar_servicios(self, monkeypatch):
        def prohibido(*args, **kwargs):
            raise AssertionError('Esta prueba no debe consultar servicios reales')
        monkeypatch.setattr(analisis_consultas, 'get_db', prohibido)
        monkeypatch.setattr(analitica_chat, 'get_db', prohibido)
        monkeypatch.setattr(ia_provider, 'obtener_proveedor', prohibido)

    @pytest.mark.parametrize('pregunta,intencion', [
        ('¿Cuántos equipos hay en el sistema?', 'resumen_inventario'),
        ('¿Cuántos tickets registrados en el sistema hay hoy?', 'metricas_generales'),
        ('¿Cuántos tickets hay en la web?', 'metricas_generales'),
        ('¿Cuántos tickets hay en la mesa de ayuda?', 'metricas_generales'),
        ('¿Cuántos equipos hay en el sistema en la oficina Tesorería?', 'resumen_inventario'),
    ])
    def test_fuente_generica_no_se_confunde_con_oficina(self, pregunta, intencion):
        assert analitica_chat._detectar_intencion(pregunta)[0] == intencion
        analisis_consultas.exigir_ubicacion_explicita(pregunta)

    @pytest.mark.parametrize('pregunta', [
        '¿Cuántos tickets hay en Tesorería?',
        '¿Cuántos equipos hay en Administración?',
        '¿Cuántos tickets hay en el sistema de Tesorería?',
        '¿Cuántos tickets hay en la web para Tesorería?',
        '¿Cuántos equipos hay en el sistema en Tesorería?',
        '¿Cuántos tickets hay en total en Tesorería?',
    ])
    def test_ubicacion_imprecisa_sigue_sin_convertirse_en_total_global(self, pregunta):
        with pytest.raises(Validacion):
            analisis_consultas.exigir_ubicacion_explicita(pregunta)

    async def test_inventario_aplica_tipo_equipo_y_ubicacion_a_ambos_recuentos(self, monkeypatch):
        from app.services import analisis_exploracion
        oficina, zona, equipo = ObjectId(), ObjectId(), ObjectId()
        filtros = {'oficina_id': oficina, 'zona_id': zona, 'tipo_activo': 'Laptop', 'equipo_id': equipo}
        esperado = {'activo': {'$ne': False}, 'oficina_id': oficina, 'zona_id': zona, 'tipo': 'Laptop', '_id': equipo}
        assert analisis_exploracion.consulta_activos(filtros, {}) == esperado
        leer = AsyncMock(return_value={'total': 1, 'sin_responsable': 1})
        monkeypatch.setattr(analisis_exploracion, 'resumen_inventario', leer)
        resultado = await analisis_consultas.inventario(filtros, {'tipo_activo': {'$ne': None}})
        leer.assert_awaited_once_with(filtros)
        assert resultado['total'] == resultado['sin_responsable'] == 1

    @pytest.mark.parametrize('filtros', [{'categoria': 'Impresora'}, {'tecnico_id': ObjectId()}])
    async def test_inventario_rechaza_filtros_de_ticket_que_no_puede_aplicar(self, filtros):
        with pytest.raises(Validacion, match='no admite filtros'):
            await analisis_consultas.inventario(filtros, {})


async def test_consulta_natural_y_filtros_de_inventario_con_api_y_datos_aislados(db, api, monkeypatch):
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: ia_provider.ProveedorDesactivado())
    mundo = await _mundo(api, 'regresion-filtros-ia')
    hoy = analitica_service._a_utc(local_date())
    await _tickets(db, [
        {'codigo': 'regresion-ia-hoy', 'creado_en': hoy, 'estado': 'nuevo'},
        {'codigo': 'regresion-ia-ayer', 'creado_en': hoy - timedelta(hours=1), 'estado': 'nuevo'},
    ])
    laptop, cpu = ObjectId(), ObjectId()
    await db['activos'].insert_many([
        {'_id': equipo_id, 'tipo': tipo, 'activo': True, 'oficina_id': ObjectId(mundo['oficina']['id']),
         'campos_estado': {}, 'clave_natural': 'regresion-ia-' + tipo}
        for equipo_id, tipo in [(laptop, 'Laptop'), (cpu, 'CPU')]
    ])

    async def preguntar(pregunta, filtros=None):
        respuesta = await api.post('/api/ia/asistente', headers=mundo['admin'], json={
            'pregunta': pregunta, 'filtros': filtros or {},
        })
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()

    hoy_datos = await preguntar('¿Cuántos tickets registrados en el sistema hay hoy?')
    assert hoy_datos['fuentes'] == ['metricas_generales']
    assert hoy_datos['tabla']['filas'][0]['total'] == 1
    assert hoy_datos['filtros_consulta']['desde'] == local_date().isoformat()
    solo_laptop = await preguntar('¿Cuántos equipos hay en el sistema?', {'tipo_activo': 'Laptop'})
    assert [(f['tipo'], f['total']) for f in solo_laptop['tabla']['filas']] == [('Laptop', 1)]
    assert solo_laptop['tabla']['filas'][0]['por_confirmar'] == 1
    solo_cpu = await preguntar('¿Cuántos equipos hay en el sistema?', {'equipo_id': str(cpu)})
    assert [(f['tipo'], f['total']) for f in solo_cpu['tabla']['filas']] == [('CPU', 1)]
    sin_coincidencia = await preguntar('¿Cuántos equipos hay en el sistema?', {'equipo_id': str(cpu), 'tipo_activo': 'Laptop'})
    assert sin_coincidencia['tabla']['filas'] == []
    assert '0 dispositivos' in sin_coincidencia['texto']
    oficina = await preguntar('¿Cuántos equipos hay en el sistema en la oficina COMUNA?')
    assert oficina['alcance_consulta'] == 'Oficina: COMUNA'
    assert sum(fila['total'] for fila in oficina['tabla']['filas']) == 2
    for pregunta in ['¿Cuántos tickets hay en Tesorería?', '¿Cuántos equipos hay en el sistema en Tesorería?']:
        imprecisa = await api.post('/api/ia/asistente', headers=mundo['admin'], json={'pregunta': pregunta})
        assert imprecisa.status_code == 422
    assert await db['tickets'].count_documents({}) == 2
    assert await db['activos'].count_documents({}) == 2
