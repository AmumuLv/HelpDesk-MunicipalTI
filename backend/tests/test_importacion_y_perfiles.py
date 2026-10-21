import io

from openpyxl import Workbook

from app.services import excel_service, import_service, usuario_service


async def test_importacion_excel_con_oficina_nueva_y_datos_pendientes(db):
    admin = await usuario_service.crear(
        {'nombre': 'Admin OTIC', 'rol': 'administrador'},
        usuario={'nombre': 'Test', 'rol': 'sistema'}, es_primer_admin=True,
    )
    w = Workbook()
    s = w.active
    s.title = 'PISCINA MUNICIPAL'
    s.append(['INVENTARIO OTIC 2026'])
    s.append([None, 'Tipo de equipo', 'Dispositivo', 'Código patrimonial', 'Tamaño Pantalla', 'Direccion IP', 'Responsable'])
    s.append(['OFICINA NUEVA', 'COMPUTADORA N°01', 'CPU', 'S/C', '24', '192.168.110', 'Persona del Excel'])
    s.append(['OFICINA NUEVA', 'LAPTOP N°01', None, 'S/C', None, '192.168.0.2', None])
    b = io.BytesIO()
    w.save(b)
    lote = await import_service.subir(b.getvalue(), 'otic.xlsx', usuario=admin)
    previa = await import_service.previsualizar(lote['lote_id'], usuario=admin)
    assert previa['validas'] == 2
    assert previa['con_error'] == 0
    assert previa['filas'][0]['codigo_patrimonial'] is None
    assert previa['filas'][0]['tamano_pantalla'] == '24'
    assert previa['filas'][1]['tipo'] == 'Por identificar'
    resultado = await import_service.confirmar(lote['lote_id'], usuario=admin)
    assert resultado['creados'] == 2
    activo = await db['activos'].find_one({'tipo': 'CPU'})
    assert activo['zona_nombre'] == 'PISCINA MUNICIPAL'
    assert activo['responsable_nombre'] == 'Persona del Excel'
    assert '192.168.110' in activo['observaciones']
    assert await db['usuarios'].count_documents({}) == 1


def test_mapeo_con_tildes_y_codigos_sin_asignar():
    from app.core.ids import limpiar_codigo_patrimonial
    mapeo = import_service.detectar_mapeo(['AREA', 'Dispositivo', 'Código patrimonial', 'Tamaño Pantalla'])
    assert mapeo['codigo_patrimonial']['columna'] == 'Código patrimonial'
    assert mapeo['tamano_pantalla']['columna'] == 'Tamaño Pantalla'
    assert limpiar_codigo_patrimonial('S/C') is None


async def test_ticket_creado_aparece_en_perfil_y_filtros(db, api):
    from tests.test_tickets_horarios import _mundo, _sesion
    mundo = await _mundo(api, 'perfil-creador')
    r = await api.post('/api/tickets', json={
        'tipo_problema': 'No enciende', 'descripcion': 'El equipo no enciende en la oficina',
        'urgencia': 'me_frena', 'persona': {'es_para_mi': True},
    }, headers=mundo['usuario'])
    assert r.status_code == 201, r.text
    ticket = r.json()['ticket']
    assert ticket['id'] and ticket['codigo']
    perfil = await api.get(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo['admin'])
    assert perfil.status_code == 200
    assert any(t['id'] == ticket['id'] for t in perfil.json()['tickets_recientes'])
    perfil_tecnico = await api.get(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo['tecnico'])
    assert perfil_tecnico.status_code == 200
    assert any(t['id'] == ticket['id'] for t in perfil_tecnico.json()['tickets_recientes'])
    cerrados = await api.get('/api/tickets?estado=cerrado', headers=mundo['admin'])
    assert cerrados.status_code == 200
    assert all(t['estado'] == 'cerrado' for t in cerrados.json()['items'])
    companero = await _sesion(api, 'companero-perfil-creador@prueba.local')
    busqueda_ajena = await api.get('/api/tickets?texto=equipo', headers=companero)
    assert busqueda_ajena.status_code == 200
    assert not any(t['id'] == ticket['id'] for t in busqueda_ajena.json()['items'])
