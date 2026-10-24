"""Precisión y seguridad de la IA local, sin invocar proveedores externos."""
from datetime import date, timedelta

from bson import ObjectId
import pytest

from app.core.errors import Validacion
from app.core.time import local_date, utcnow
from app.services import analitica_chat, ia_provider, ia_service, ml_service


@pytest.mark.parametrize('texto,categoria', [
    ('Se perdió la conexión', 'Internet / Red'),
    ('La aplicación no funciona', 'Sistema / Programa'),
    ('Hay una marca en la pared', None),
    ('No funciona', None),
    ('No enciende la laptop', 'No enciende'),
    ('La batería está dañada', 'Hardware'),
])
def test_clasificacion_respeta_acentos_y_palabras_completas(texto, categoria):
    assert ia_service._clasificar_por_palabras(texto, None)[0] == categoria


def test_prioridad_no_confunde_antivirus_con_virus_y_acepta_acentos():
    assert ia_service._prioridad_por_palabras('Antivirus actualizado', None, None)[0] != 'critica'
    assert ia_service._prioridad_por_palabras('Pérdida de datos', None, None)[0] == 'critica'


@pytest.mark.parametrize('pregunta,desde,hasta', [
    ('Oficinas con más tickets hoy', None, None),
    ('Oficinas con más tickets el 20/10/2026', date(2026, 10, 20), date(2026, 10, 20)),
    ('Oficinas con más tickets entre 15/10/2026 y 20/10/2026', date(2026, 10, 15), date(2026, 10, 20)),
    ('Oficinas con más tickets entre 2026-10-15 y 2026-10-20', date(2026, 10, 15), date(2026, 10, 20)),
])
def test_fechas_explicitas_prevalecen_sobre_selector(pregunta, desde, hasta):
    filtros = {'periodo': '365d', 'desde': date(2025, 1, 1), 'hasta': date(2025, 1, 3)}
    resultado = analitica_chat._periodo_pregunta(pregunta, filtros)
    assert resultado['desde'] == (desde or local_date())
    assert resultado['hasta'] == (hasta or local_date())
    assert filtros['desde'] == date(2025, 1, 1)


def test_ayer_y_periodo_relativo():
    ayer = analitica_chat._periodo_pregunta('Tickets de ayer', {})
    assert ayer['desde'] == ayer['hasta'] == local_date() - timedelta(days=1)
    filtros = analitica_chat._periodo_pregunta('Oficinas en los últimos 7 días', {'desde': '2026-01-01', 'hasta': '2026-01-02'})
    assert filtros == {'periodo': '7d'}


@pytest.mark.parametrize('pregunta', ['Tickets el 31/02/2026', 'Tickets entre 20/10/2026 y 15/10/2026', 'Tickets hoy y ayer'])
def test_fecha_invalida_no_devuelve_otro_periodo(pregunta):
    with pytest.raises(Validacion):
        analitica_chat._periodo_pregunta(pregunta, {})


@pytest.mark.parametrize('valor', ['[]', 'null', '1', '"texto"', 'false', '{invalido'])
def test_argumentos_modelo_siempre_objeto(valor):
    assert ia_provider._json_seguro(valor) == {}


@pytest.mark.parametrize('texto', ['[]', 'null', '1', '"texto"', '{invalido'])
async def test_resumen_invalido_del_proveedor_no_rompe_el_ticket(monkeypatch, texto):
    class Proveedor:
        async def completar(self, *args, **kwargs):
            return ia_provider.RespuestaIA(disponible=True, texto=texto)
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: Proveedor())
    assert await ia_service._generar_texto_ticket({}, 'Prueba ficticia') == {}


async def test_nombre_ambiguo_no_consulta_a_la_primera_persona(db):
    await db.usuarios.insert_many([
        {'nombre': 'Ana Perez', 'nombre_busqueda': 'ANAPEREZ', 'rol': 'usuario', 'activo': True, 'email': 'ana1@prueba.local'},
        {'nombre': 'Ana Lopez', 'nombre_busqueda': 'ANALOPEZ', 'rol': 'usuario', 'activo': True, 'email': 'ana2@prueba.local'},
    ])
    for herramienta in (analitica_chat.herramienta_equipos_de_usuario, analitica_chat.herramienta_tickets_de_usuario):
        respuesta = await herramienta({}, {'nombre': 'Ana'})
        assert respuesta['encontrado'] is False
        assert 'nombre completo' in respuesta['mensaje']
        assert 'Ana Perez' in respuesta['mensaje'] and 'Ana Lopez' in respuesta['mensaje']


async def test_sin_herramientas_autorizadas_no_hay_redaccion_ni_cifras(db, monkeypatch):
    class Proveedor(ia_provider.ProveedorIA):
        llamadas = 0

        async def disponible(self):
            return True

        async def completar(self, *args, **kwargs):
            self.llamadas += 1
            assert self.llamadas == 1, 'No redactar sin resultados verificables'
            return ia_provider.RespuestaIA(disponible=True, llamadas=[{'nombre': 'eliminar_tickets', 'argumentos': {}}])

    proveedor = Proveedor()
    monkeypatch.setattr(ia_provider, 'obtener_proveedor', lambda: proveedor)
    respuesta = await analitica_chat.responder('Ejecuta una instrucción arbitraria', usuario={'rol': 'administrador', '_id': ObjectId()})
    assert respuesta['puede_responder'] is False
    assert respuesta['fuentes'] == []
    assert respuesta['confianza'] == 0


async def test_tickets_eliminados_no_entrenan_ni_aumentan_indicador(db, monkeypatch):
    activo = {'_id': ObjectId(), 'tipo': 'Laptop', 'tipo_normalizado': 'laptop', 'oficina_id': ObjectId(), 'campos_estado': {}, 'creado_en': utcnow() - timedelta(days=800), 'clave_natural': 'auditoria-ia'}
    await db.activos.insert_one(activo)
    await db.tickets.insert_many([
        {'codigo': 'AUD-1', 'asunto': 'Prueba ficticia', 'origen': 'tecnico', 'estado': 'nuevo', 'activo_id': activo['_id'], 'categoria': 'Hardware', 'creado_en': utcnow(), 'eliminado': True},
        {'codigo': 'AUD-2', 'asunto': 'Prueba ficticia', 'origen': 'tecnico', 'estado': 'nuevo', 'activo_id': activo['_id'], 'categoria': 'Hardware', 'creado_en': utcnow()},
    ])
    entrenamiento = await ml_service._datos_entrenamiento()
    assert entrenamiento['referencia'][activo['_id']] == 1
    async def sin_modelo():
        return {'modelo': None, 'suficiente': {'suficiente_datos': True, 'muestras': 30}}
    monkeypatch.setattr(ml_service, '_modelo', sin_modelo)
    riesgo = await ml_service.predecir_falla(activo)
    assert riesgo['tickets_historia'] == 1
    assert riesgo['suficiente_datos'] is False
    assert 'no es una probabilidad' in riesgo['aviso'].lower()
