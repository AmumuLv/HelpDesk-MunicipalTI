"""El listado reutiliza calendario y feriados sin conservar datos obsoletos."""
import asyncio
from collections import Counter
from contextvars import ContextVar
from datetime import datetime

from app.core.time import business_tz
from app.services import config_service, horario_service, sla_service


async def test_lote_evita_lecturas_repetidas_y_la_siguiente_operacion_ve_cambios(monkeypatch):
    llamadas = Counter()
    calendario = {'dias_laborables': [0, 1, 2, 3, 4], 'tramos': [{'entrada': '08:00', 'salida': '16:00'}]}

    async def leer_calendario():
        llamadas['calendario'] += 1
        return calendario

    async def pausa():
        llamadas['pausa'] += 1
        return True

    async def feriado(dia):
        llamadas[dia] += 1
        return False

    monkeypatch.setattr(config_service, 'calendario', leer_calendario)
    monkeypatch.setattr(config_service, 'pausa_fuera_de_horario', pausa)
    monkeypatch.setattr(horario_service, 'es_feriado', feriado)
    inicio = datetime(2026, 3, 2, 8, tzinfo=business_tz())
    fin = inicio.replace(hour=16)
    with sla_service.lote_calculo():
        resultados = [await sla_service.minutos_laborables_entre(inicio, fin) for _ in range(20)]
    assert resultados == [480] * 20
    assert llamadas['calendario'] == llamadas['pausa'] == 1
    assert all(n == 1 for dia, n in llamadas.items() if not isinstance(dia, str))
    calendario = {**calendario, 'tramos': [{'entrada': '08:00', 'salida': '12:00'}]}
    assert await sla_service.minutos_laborables_entre(inicio, fin) == 240
    assert llamadas['calendario'] == llamadas['pausa'] == 2


async def test_calculos_simultaneos_no_mezclan_calendarios(monkeypatch):
    dias = ContextVar('dias_ensayo')

    async def calendario():
        await asyncio.sleep(0)
        return {'dias_laborables': dias.get(), 'tramos': [{'entrada': '08:00', 'salida': '16:00'}]}

    async def pausa():
        return True

    async def feriado(dia):
        await asyncio.sleep(0)
        return False

    monkeypatch.setattr(config_service, 'calendario', calendario)
    monkeypatch.setattr(config_service, 'pausa_fuera_de_horario', pausa)
    monkeypatch.setattr(horario_service, 'es_feriado', feriado)
    inicio = datetime(2026, 3, 2, 8, tzinfo=business_tz())

    async def calcular(laborables):
        dias.set(laborables)
        return await sla_service.minutos_laborables_entre(inicio, inicio.replace(hour=16))

    assert await asyncio.gather(calcular([0]), calcular([1])) == [480, 0]
