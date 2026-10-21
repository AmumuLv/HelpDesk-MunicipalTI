import pytest
from tests.test_tickets_horarios import _mundo


async def test_importar_excel_usb_sin_advertencia_y_reimportar(db, api):
    from io import BytesIO
    from openpyxl import Workbook
    mundo = await _mundo(api, 'excel-usb')
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Zona USB'
    hoja.append(['AREA', 'TIPO DE EQUIPO', 'DISPOSITIVO', 'CODIGO PATRIMONIAL', 'IP'])
    for i, conexion in enumerate(['CABLE USB', 'Cable USB', 'usb']):
        hoja.append(['COMUNA', f'Impresora {i}', 'Impresora', f'1234500{i}', conexion])
    hoja.append(['COMUNA', 'CPU red', 'CPU', '12345999', '999.1.1.1'])
    archivo = BytesIO()
    libro.save(archivo)
    for intento in range(2):
        subida = await api.post('/api/importacion/subir', headers=mundo['admin'], files={'archivo': ('usb.xlsx', archivo.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert subida.status_code == 200, subida.text
        lote = subida.json()['lote_id']
        respuesta = await api.post(f'/api/importacion/{lote}/previsualizar', headers=mundo['admin'], json={})
        assert respuesta.status_code == 200, respuesta.text
        filas = respuesta.json()['filas']
        impresoras = [f for f in filas if f['tipo'] == 'Impresora']
        assert len(impresoras) == 3
        for fila in impresoras:
            assert fila['direccion_ip'] == 'Cable USB'
            assert fila['campos_estado']['direccion_ip'] == 'no_aplica'
            assert not any('IP' in a and 'invalida' in a for a in fila['advertencias'])
        assert any('IP invalida' in a for f in filas if f['tipo'] == 'CPU' for a in f['advertencias'])
        confirmado = await api.post(f'/api/importacion/{lote}/confirmar', headers=mundo['admin'], json={})
        assert confirmado.status_code == 200, confirmado.text
        assert confirmado.json()['errores'] == 0
        assert await db.activos.count_documents({'tipo': 'Impresora'}) == 3
        async for equipo in db.activos.find({'tipo': 'Impresora'}):
            assert equipo['direccion_ip'] is None
            assert equipo['campos_estado']['direccion_ip']['motivo'] == 'Cable USB'


@pytest.mark.parametrize('conexion', ['Cable USB', 'CABLE USB', 'usb'])
async def test_impresora_usb_y_vuelta_a_red(db, api, conexion):
    mundo = await _mundo(api, 'usb')
    cuerpo = {'tipo': 'Impresora', 'oficina_id': mundo['oficina']['id'], 'direccion_ip': conexion}
    respuesta = await api.post('/api/activos', headers=mundo['admin'], json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    ruta = f"/api/activos/{respuesta.json()['id']}"
    detalle = (await api.get(ruta, headers=mundo['admin'])).json()
    assert detalle['direccion_ip'] is None
    assert detalle['campos']['direccion_ip']['estado'] == 'no_aplica'
    assert detalle['campos']['direccion_ip']['motivo'] == 'Cable USB'
    assert 'direccion_ip' not in detalle['campos_faltantes']
    red = await api.patch(ruta, headers=mundo['admin'], json={'direccion_ip': '192.168.1.25'})
    assert red.status_code == 200, red.text
    detalle = (await api.get(ruta, headers=mundo['admin'])).json()
    assert detalle['direccion_ip'] == '192.168.1.25'
    assert detalle['campos']['direccion_ip']['estado'] != 'no_aplica'
    usb = await api.patch(ruta, headers=mundo['admin'], json={'direccion_ip': 'Cable USB'})
    assert usb.status_code == 200, usb.text
    assert (await api.get(ruta, headers=mundo['admin'])).json()['direccion_ip'] is None
    for tipo, ip in [('CPU', 'Cable USB'), ('Impresora', '999.1.1.1')]:
        invalida = await api.post('/api/activos', headers=mundo['admin'], json={**cuerpo, 'tipo': tipo, 'direccion_ip': ip})
        assert invalida.status_code == 422, invalida.text
