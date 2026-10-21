import pytest
from tests.test_tickets_horarios import _mundo


@pytest.mark.parametrize('propiedad', ['Personal', ' personal ', 'PERSONAL'])
async def test_personal_excluye_codigo_patrimonial(db, api, propiedad):
    mundo = await _mundo(api, 'personal')
    respuesta = await api.post('/api/activos', headers=mundo['admin'], json={
        'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id'],
        'propiedad': propiedad, 'codigo_patrimonial': '123456789',
    })
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    detalle = (await api.get(f"/api/activos/{datos['id']}", headers=mundo['admin'])).json()
    assert detalle['codigo_patrimonial'] is None
    assert detalle['campos']['codigo_patrimonial']['estado'] == 'no_aplica'
    assert 'codigo_patrimonial' not in detalle['campos_faltantes']
    otro = await api.post('/api/activos', headers=mundo['admin'], json={
        'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id'],
        'propiedad': 'Institucional', 'codigo_patrimonial': '987654321',
    })
    assert otro.status_code == 201, otro.text
    assert otro.json()['codigo_patrimonial'] == '987654321'
