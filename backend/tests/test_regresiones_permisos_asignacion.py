"""Regresiones de autorización y bajas detectadas en la revisión del 04/11/2026."""
from bson import ObjectId
import pytest

from app.core.errors import Prohibido
from app.domain.permissions import CLAVES_PERMISOS
from app.services import usuario_service
from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _mundo


async def _post(api, ruta, datos, headers):
    respuesta = await api.post('/api' + ruta, json=datos, headers=headers)
    assert respuesta.status_code in (200, 201), respuesta.text
    return respuesta.json()


@pytest.mark.parametrize('rol', ['usuario', 'tecnico', 'tecnico_con_permisos'])
async def test_ubicacion_propia_no_elude_la_jerarquia(db, api, rol):
    mundo = await _mundo(api, 'ubicacion_segura')
    if rol == 'tecnico_con_permisos':
        respuesta = await api.put(f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
            headers=mundo['admin'], json={'cambios': {p: True for p in CLAVES_PERMISOS}})
        assert respuesta.status_code == 200
    clave = 'usuario' if rol == 'usuario' else 'tecnico'
    objetivo = ObjectId(mundo[clave + '_id'])
    headers = mundo[clave]
    zona = await _post(api, '/zonas', {'nombre': 'Zona ajena'}, mundo['admin'])
    oficina = await _post(api, '/oficinas', {'nombre': 'Oficina ajena', 'zona_id': zona['id']}, mundo['admin'])
    vecino = await _post(api, '/usuarios', {'nombre': 'Persona de otra oficina', 'rol': 'usuario',
        'oficina_id': oficina['id']}, mundo['admin'])
    antes = await db.usuarios.find_one({'_id': objetivo})
    for cambios in ({'oficina_id': oficina['id']}, {'zona_id': zona['id']},
                    {'oficina_id': None, 'zona_id': None}):
        respuesta = await api.patch(f'/api/usuarios/{objetivo}', json=cambios, headers=headers)
        assert respuesta.status_code == 403, respuesta.text
        assert await db.usuarios.find_one({'_id': objetivo}) == antes
        # La ruta de perfil existente ignora los datos institucionales.
        respuesta = await api.patch('/api/mi-perfil', json=cambios, headers=headers)
        assert respuesta.status_code == 200, respuesta.text
        assert await db.usuarios.find_one({'_id': objetivo}) == antes
    with pytest.raises(Prohibido):
        await usuario_service.actualizar(objetivo, {'oficina_id': ObjectId(oficina['id'])}, usuario=antes)
    if rol == 'usuario':
        companeros = await api.get('/api/usuarios/companeros', headers=headers)
        assert vecino['id'] not in {p['id'] for p in companeros.json()['items']}
    respuesta = await api.patch('/api/mi-perfil', json={'anexo': '456'}, headers=headers)
    assert respuesta.status_code == 200
    assert (await db.usuarios.find_one({'_id': objetivo}))['anexo'] == '456'


@pytest.mark.parametrize('rol', ['admin', 'tecnico'])
async def test_gestion_autorizada_conserva_cambio_de_oficina(db, api, rol):
    mundo = await _mundo(api, 'ubicacion_autorizada')
    respuesta = await api.put(f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
        headers=mundo['admin'], json={'cambios': {'usuarios.editar': True}})
    assert respuesta.status_code == 200
    oficina = await _post(api, '/oficinas', {'nombre': 'Nueva oficina', 'zona_id': mundo['zona']['id']}, mundo['admin'])
    respuesta = await api.patch(f"/api/usuarios/{mundo['usuario_id']}",
        headers=mundo[rol], json={'oficina_id': oficina['id']})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['oficina_id'] == oficina['id']
    if rol == 'admin':
        titular = await db.usuarios.find_one({'administrador_principal': True})
        respuesta = await api.patch(f"/api/usuarios/{titular['_id']}",
            headers=mundo['admin'], json={'oficina_id': oficina['id']})
        assert respuesta.status_code == 200, respuesta.text


@pytest.mark.parametrize('rol', ['tecnico', 'tecnico_autorizado', 'admin'])
async def test_ticket_no_crea_cuentas_ni_deja_altas_parciales(db, api, rol):
    mundo = await _mundo(api, 'alta_indirecta')
    if rol == 'tecnico_autorizado':
        respuesta = await api.put(f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
            headers=mundo['admin'], json={'cambios': {'usuarios.editar': True}})
        assert respuesta.status_code == 200
    headers = mundo['admin' if rol == 'admin' else 'tecnico']
    usuarios_antes = await db.usuarios.count_documents({})
    auditoria_antes = await db.auditoria.count_documents({'accion': 'usuario.crear'})
    alta = {'nombre': 'Cuenta que no debe aparecer', 'email': 'indirecta@prueba.local',
            'password': PASSWORD, 'crear_usuario': True, 'oficina_id': mundo['oficina']['id']}
    for persona in ({'persona_no_registrada': alta},
                    {'afectado_id': mundo['usuario_id'], 'persona_no_registrada': alta}):
        respuesta = await api.post('/api/tickets/manual', headers=headers, json={
            'asunto': 'Alta indirecta rechazada', 'categoria': 'Hardware', 'persona': persona})
        assert respuesta.status_code == (403 if rol == 'tecnico' else 422), respuesta.text
        assert await db.usuarios.count_documents({}) == usuarios_antes
        assert await db.usuarios.find_one({'email_normalizado': alta['email']}) is None
        assert await db.tickets.count_documents({}) == 0
        assert await db.auditoria.count_documents({'accion': 'usuario.crear'}) == auditoria_antes
    if rol == 'tecnico':
        actor = await db.usuarios.find_one({'_id': ObjectId(mundo['tecnico_id'])})
        with pytest.raises(Prohibido):
            await usuario_service.resolver_solicitante_no_registrado(alta, usuario=actor)
        respuesta = await api.post('/api/usuarios', headers=headers, json={
            'nombre': alta['nombre'], 'email': alta['email'], 'password': PASSWORD, 'rol': 'usuario'})
        assert respuesta.status_code == 403
    else:
        creada = await _post(api, '/usuarios', {'nombre': 'Alta por la ruta autorizada',
            'email': 'autorizada@prueba.local', 'password': PASSWORD, 'rol': 'usuario'}, headers)
        assert creada['rol'] == 'usuario'
    # El técnico sigue registrando tickets de personas y equipos existentes.
    equipo = await _post(api, '/activos', {'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id'],
        'responsable_id': mundo['usuario_id'], 'nombre_equipo': 'Laptop de prueba'}, mundo['admin'])
    respuesta = await api.post('/api/tickets/manual', headers=headers, json={
        'asunto': 'Problema en laptop registrada', 'categoria': 'Hardware', 'activo_id': equipo['id'],
        'persona': {'afectado_id': mundo['usuario_id']}})
    assert respuesta.status_code == 201, respuesta.text


@pytest.mark.parametrize('estado', ['desactivado', 'archivado', 'marca_archivado'])
async def test_bajas_rechazan_asignaciones_y_conservan_historial(db, api, estado):
    mundo = await _mundo(api, 'asignacion_baja')
    admin = mundo['admin']
    ubicacion = {'oficina_id': mundo['oficina']['id']}
    propio = await _post(api, '/activos', {**ubicacion, 'tipo': 'Laptop',
        'responsable_id': mundo['usuario_id'], 'nombre_equipo': 'Equipo histórico'}, admin)
    libre = await _post(api, '/activos', {**ubicacion, 'tipo': 'CPU', 'nombre_equipo': 'Equipo libre'}, admin)
    conjunto = await _post(api, '/conjuntos', {**ubicacion, 'nombre': 'Computadora de la persona',
        'responsable_id': mundo['usuario_id']}, admin)
    conjunto_libre = await _post(api, '/conjuntos', {**ubicacion, 'nombre': 'Computadora compartida'}, admin)
    respuesta = await api.post(f"/api/usuarios/{mundo['usuario_id']}/desactivar", headers=admin)
    assert respuesta.status_code == 200
    await db.usuarios.update_one({'_id': ObjectId(mundo['usuario_id'])}, {'$set': {
        'activo': estado == 'marca_archivado', 'archivado': estado != 'desactivado'}})
    responsable = {'responsable_id': mundo['usuario_id']}
    activos_antes = await db.activos.find({}).sort('_id').to_list(None)
    conjuntos_antes = await db.conjuntos.find({}).sort('_id').to_list(None)
    historial_antes = await db.historial_responsables.find({}).sort('_id').to_list(None)
    intentos = [
        ('post', '/activos', {**ubicacion, **responsable, 'tipo': 'Laptop'}),
        ('post', '/conjuntos', {**ubicacion, **responsable, 'nombre': 'Conjunto rechazado'}),
        ('post', f"/activos/{libre['id']}/responsable", responsable),
        ('post', f"/conjuntos/{conjunto_libre['id']}/responsable", responsable),
        ('patch', f"/activos/{libre['id']}", {**responsable, 'nombre_equipo': 'No guardar parcialmente'}),
        ('patch', f"/conjuntos/{conjunto_libre['id']}", {**responsable, 'notas': 'No guardar parcialmente'}),
        ('post', '/activos/cambio-masivo', {**responsable, 'activo_ids': [libre['id'], propio['id']], 'estado': 'Inoperativo'}),
        ('post', '/activos', {**ubicacion, 'tipo': 'Teclado', 'conjunto_id': conjunto['id']}),
        ('post', '/activos', {**ubicacion, 'tipo': 'Teclado', 'conjunto_id': conjunto['id'],
                              'responsable_id': mundo['companero_id']}),
        ('patch', f"/activos/{libre['id']}", {'conjunto_id': conjunto['id']}),
        ('patch', f"/activos/{libre['id']}", {'conjunto_id': conjunto['id'], 'responsable_id': None}),
    ]
    for metodo, ruta, cuerpo in intentos:
        respuesta = await api.request(metodo, '/api' + ruta, headers=admin, json=cuerpo)
        assert respuesta.status_code == 422, (ruta, respuesta.text)
        assert await db.activos.find({}).sort('_id').to_list(None) == activos_antes
        assert await db.conjuntos.find({}).sort('_id').to_list(None) == conjuntos_antes
        assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historial_antes
    # El responsable histórico sigue visible y no impide corregir otros datos.
    respuesta = await api.patch(f"/api/activos/{propio['id']}", headers=admin,
        json={**responsable, 'observaciones': 'Inventario histórico revisado'})
    assert respuesta.status_code == 200, respuesta.text
    assert (await db.activos.find_one({'_id': ObjectId(propio['id'])}))['responsable_id'] == ObjectId(mundo['usuario_id'])
    respuesta = await api.patch(f"/api/conjuntos/{conjunto['id']}", headers=admin,
        json={**responsable, 'notas': 'Conservar su historial'})
    assert respuesta.status_code == 200, respuesta.text
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historial_antes
    assert (await api.get(f"/api/usuarios/{mundo['usuario_id']}", headers=admin)).status_code == 200
    # Un cambio masivo de estado no debe borrar responsables omitidos del formulario.
    respuesta = await api.post('/api/activos/cambio-masivo', headers=admin,
        json={'activo_ids': [propio['id']], 'estado': 'En reparación'})
    assert respuesta.status_code == 200, respuesta.text
    assert (await db.activos.find_one({'_id': ObjectId(propio['id'])}))['responsable_id'] == ObjectId(mundo['usuario_id'])
    assert await db.historial_responsables.find({}).sort('_id').to_list(None) == historial_antes
    # Reenviar el responsable actual no asigna componentes pendientes al archivado.
    await db.activos.update_one({'_id': ObjectId(libre['id'])}, {'$set': {'conjunto_id': ObjectId(conjunto['id'])}})
    respuesta = await api.post(f"/api/conjuntos/{conjunto['id']}/responsable", headers=admin, json=responsable)
    assert respuesta.status_code == 200
    assert (await db.activos.find_one({'_id': ObjectId(libre['id'])})).get('responsable_id') is None
    respuesta = await api.patch(f"/api/activos/{libre['id']}", headers=admin, json={'conjunto_id': conjunto['id']})
    assert respuesta.status_code == 422
    # La reasignación al reemplazo activo y la liberación de equipos siguen disponibles.
    for destino in (None, mundo['companero_id']):
        respuesta = await api.post(f"/api/activos/{propio['id']}/responsable",
            headers=admin, json={'responsable_id': destino})
        assert respuesta.status_code == 200, respuesta.text
    for anterior in historial_antes:
        conservado = await db.historial_responsables.find_one({'_id': anterior['_id']})
        assert conservado and conservado['responsable_id'] == anterior['responsable_id']
    respuesta = await api.patch(f"/api/usuarios/{mundo['usuario_id']}", headers=admin, json={'activo': True})
    assert respuesta.status_code == 200
    respuesta = await api.post(f"/api/conjuntos/{conjunto['id']}/responsable", headers=admin, json=responsable)
    assert respuesta.status_code == 200
    assert (await db.activos.find_one({'_id': ObjectId(libre['id'])}))['responsable_id'] == ObjectId(mundo['usuario_id'])
    nuevo = await _post(api, '/activos', {**ubicacion, **responsable, 'tipo': 'Laptop'}, admin)
    assert nuevo['responsable_id'] == mundo['usuario_id']
