"""Contrato completo de las sugerencias nuevas, sin servidor ni proveedor."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.core.errors import Prohibido, Validacion
from app.services import analisis_catalogo, analisis_consultas, analitica_chat


@pytest.fixture(scope='session', autouse=True)
def mongo_replica_set():
    yield None


ADMIN = {'_id': ObjectId(), 'nombre': 'Administradora ficticia', 'rol': 'administrador'}
TECNICO = {'_id': ObjectId(), 'rol': 'tecnico', 'permisos': {'analitica.ver': True}}


@pytest.mark.parametrize('pregunta,nombre,grupo', analisis_catalogo.preguntas())
async def test_cada_sugerencia_nueva_consulta_su_herramienta_sin_modelo(pregunta, nombre, grupo, monkeypatch):
    assert analitica_chat._detectar_intencion(pregunta)[0] == nombre
    proveedor = MagicMock()
    proveedor.disponible = AsyncMock(side_effect=AssertionError('No debe llamar al modelo'))
    monkeypatch.setattr(analitica_chat.ia_provider, 'obtener_proveedor', lambda: proveedor)
    monkeypatch.setattr(analitica_chat, 'get_db', MagicMock())
    monkeypatch.setattr(analitica_chat, 'ia_service_registrar', AsyncMock())
    lectura = AsyncMock(return_value={'texto': 'Resultado ficticio comprobado.', 'tabla': {'columnas': [], 'filas': []},
                                     'periodo_label': 'Fuente de prueba', 'alcance': 'Solo registros ficticios'})
    monkeypatch.setitem(analitica_chat.HERRAMIENTAS, nombre, {**analitica_chat.HERRAMIENTAS[nombre], 'funcion': lectura})
    resultado = await analitica_chat.responder(pregunta, usuario=ADMIN)
    assert resultado['fuentes'] == [nombre]
    assert resultado['texto'] == 'Resultado ficticio comprobado.'
    assert resultado['periodo'] == 'Fuente de prueba'
    assert resultado['alcance_consulta'] == 'Solo registros ficticios'
    assert analisis_consultas.contexto_completo([{'rol': 'assistant', **resultado}])['herramienta'] == nombre
    assert analitica_chat.preguntas_disponibles(ADMIN)['grupos'][pregunta] == grupo
    proveedor.disponible.assert_not_awaited()
    lectura.assert_awaited_once()


def test_sugerencias_y_contexto_no_revelan_opciones_reservadas():
    tecnico = analitica_chat.preguntas_disponibles(TECNICO)
    admin = analitica_chat.preguntas_disponibles(ADMIN)
    assert '¿Qué cambios se registraron en el periodo?' not in tecnico['preguntas']
    assert '¿Qué cambios se registraron en el periodo?' in admin['preguntas']
    assert 'Compara dos inventarios anuales' not in tecnico['preguntas']
    assert 'Muéstrame los tickets sin asignar' in tecnico['preguntas']
    contexto = {'rol': 'assistant', 'contexto_consulta': {'herramienta': 'tickets_pendientes_detalle',
                'argumentos': {'modo': 'sin_asignar', 'limite': 5, 'historial_completo': True}}}
    assert analisis_consultas.contexto_completo([contexto])['argumentos'] == contexto['contexto_consulta']['argumentos']
    contexto['contexto_consulta']['argumentos']['$where'] = 'operador no permitido'
    assert analisis_consultas.contexto_completo([contexto])['argumentos'] == {}


@pytest.mark.parametrize('argumentos', [{'modo': {'$ne': ''}}, {'$where': 'x'}, {'limite': True}, {'limite': 1000}, {'modo': 'borrar'}, {'historial_completo': 'si'}])
def test_argumentos_de_consulta_solo_admiten_esquema_tipado(argumentos):
    with pytest.raises(Validacion):
        analisis_catalogo.argumentos_seguros('tickets_pendientes_detalle', argumentos)


async def test_tecnico_no_puede_pedir_auditoria_aunque_envie_la_pregunta_manualmente(monkeypatch):
    funcion = AsyncMock(side_effect=AssertionError('No debe leer auditoría'))
    monkeypatch.setitem(analitica_chat.HERRAMIENTAS, 'auditoria_cambios', {**analitica_chat.HERRAMIENTAS['auditoria_cambios'], 'funcion': funcion})
    with pytest.raises(Prohibido):
        await analitica_chat.ejecutar_herramienta('auditoria_cambios', {}, filtros={}, usuario=TECNICO)
    funcion.assert_not_awaited()


def test_semana_y_continuacion_conservan_herramienta_sin_bloquear_cambio_a_ayer(monkeypatch):
    monkeypatch.setattr(analitica_chat, 'local_date', lambda: date(2026, 11, 11))
    actual = analitica_chat._periodo_pregunta('Cambios de esta semana hasta hoy', {'periodo': '30d'})
    assert (actual['desde'], actual['hasta']) == (date(2026, 11, 9), date(2026, 11, 11))
    pasada = analitica_chat._periodo_pregunta('¿Y la semana pasada?', actual)
    assert (pasada['desde'], pasada['hasta']) == (date(2026, 11, 2), date(2026, 11, 8))
    ayer = analitica_chat._periodo_pregunta('¿Y ayer?', actual)
    assert ayer['desde'] == ayer['hasta'] == date(2026, 11, 10)
    assert analisis_consultas.es_continuacion('¿Y la semana pasada?')
    assert analisis_consultas.es_continuacion('¿Y sin equipo?')


def test_fuentes_genericas_y_ubicaciones_ambiguas_no_se_mezclan():
    analisis_consultas.exigir_ubicacion_explicita('¿Qué datos faltan en el inventario?')
    analisis_consultas.exigir_ubicacion_explicita('¿Qué datos faltan en el inventario en la oficina Caja?')
    with pytest.raises(Validacion):
        analisis_consultas.exigir_ubicacion_explicita('¿Qué datos faltan en el inventario en Caja?')
