from datetime import datetime, timezone
from tests.test_tickets_horarios import _mundo
from app.services.sla_service import calcular_deadlines


async def test_sla_guardado_validacion_y_plazos_reales(db, api):
    mundo = await _mundo(api, 'sla-personalizado')
    sla = {'reglas': [{'prioridad': p, 'horas_responder': 0.5, 'horas_resolver': 2} for p in ['baja', 'media', 'alta', 'critica']], 'calendario': {'dias_laborables': [0, 1, 2, 3, 4], 'tramos': [{'entrada': '08:00', 'salida': '12:00'}, {'entrada': '13:00', 'salida': '17:00'}]}, 'pausa_fuera_de_horario': True}
    respuesta = await api.patch('/api/configuracion', headers=mundo['admin'], json={'sla': sla})
    assert respuesta.status_code == 200, respuesta.text
    guardado = (await api.get('/api/configuracion', headers=mundo['admin'])).json()['sla']
    assert guardado['reglas'][0]['horas_responder'] == 0.5
    # Lunes 08:00 en Lima; la respuesta vence 08:30 y la resolución 10:00.
    limites = await calcular_deadlines('alta', datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc))
    assert limites['sla_responder_en'].hour == 13 and limites['sla_responder_en'].minute == 30
    assert limites['sla_resolver_en'].hour == 15
    for cambios in [
        {'reglas': [sla['reglas'][0]] * 4},
        {'reglas': [{**r, 'horas_responder': 3} for r in sla['reglas']]},
        {'calendario': {'dias_laborables': [], 'tramos': sla['calendario']['tramos']}},
        {'calendario': {'dias_laborables': [0], 'tramos': [{'entrada': '08:00', 'salida': '13:00'}, {'entrada': '12:00', 'salida': '17:00'}]}},
    ]:
        r = await api.patch('/api/configuracion', headers=mundo['admin'], json={'sla': cambios})
        assert r.status_code == 422, r.text
    assert (await api.patch('/api/configuracion', headers=mundo['usuario'], json={'sla': sla})).status_code == 403
    assert (await api.get('/api/configuracion', headers=mundo['admin'])).json()['sla']['reglas'] == guardado['reglas']
