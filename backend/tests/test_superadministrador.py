"""Jerarquía de cuentas contra la API real, incluidos intentos de eludir la interfaz."""

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _sesion


async def mundo(api):
    inicial = await api.post('/api/instalacion/administrador', json={
        'nombre': 'Titular TI', 'email': 'titular@prueba.local', 'password': PASSWORD,
    })
    assert inicial.status_code == 200, inicial.text
    assert inicial.json()['superadministrador'] is True
    titular = await _sesion(api, 'titular@prueba.local')
    cuentas = {}
    for clave, rol in [('admin', 'administrador'), ('otro', 'administrador'), ('tecnico', 'tecnico'), ('persona', 'usuario')]:
        respuesta = await api.post('/api/usuarios', headers=titular, json={
            'nombre': f'Cuenta {clave}', 'email': f'{clave}@prueba.local', 'password': PASSWORD, 'rol': rol,
        })
        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()['superadministrador'] is False
        cuentas[clave] = respuesta.json()['id']
    return inicial.json()['id'], titular, cuentas, await _sesion(api, 'admin@prueba.local')


@pytest.mark.parametrize('objetivo', ['titular', 'otro'])
@pytest.mark.parametrize('accion', ['editar', 'desactivar', 'password', 'foto', 'sesiones'])
async def test_admin_no_puede_intervenir_cuentas_administrativas(db, api, objetivo, accion):
    titular_id, titular, cuentas, admin = await mundo(api)
    objetivo_id = titular_id if objetivo == 'titular' else cuentas['otro']
    base = f'/api/usuarios/{objetivo_id}'
    antes = await db['usuarios'].find_one({'_id': ObjectId(objetivo_id)})
    if accion == 'editar':
        respuesta = await api.patch(base, headers=admin, json={'email': 'usurpado@prueba.local'})
    elif accion == 'desactivar':
        respuesta = await api.post(base + '/desactivar', headers=admin)
    elif accion == 'password':
        respuesta = await api.post(base + '/restablecer-password', headers=admin, json={'password': 'NuevaClave987!'})
    elif accion == 'foto':
        respuesta = await api.delete(base + '/foto', headers=admin)
    else:
        respuesta = await api.delete(base + '/dispositivos/inventada', headers=admin)
    assert respuesta.status_code == 403, respuesta.text
    despues = await db['usuarios'].find_one({'_id': ObjectId(objetivo_id)})
    assert despues == antes
    assert (await api.get('/api/auth/sesion', headers=titular)).status_code == 200


async def test_roles_y_permisos_solo_del_superadmin(db, api):
    _, titular, cuentas, admin = await mundo(api)
    for datos in [{'rol': 'administrador'}, {'permisos': {'usuarios.editar': True}}]:
        respuesta = await api.patch(f"/api/usuarios/{cuentas['tecnico']}", headers=admin, json=datos)
        assert respuesta.status_code == 403, respuesta.text
    alta = await api.post('/api/usuarios', headers=admin, json={
        'nombre': 'Admin no autorizado', 'email': 'nuevo@prueba.local', 'rol': 'administrador', 'password': PASSWORD,
    })
    assert alta.status_code == 403, alta.text
    ruta = f"/api/permisos/tecnicos/{cuentas['tecnico']}"
    assert (await api.put(ruta, headers=admin, json={'cambios': {'usuarios.editar': True}})).status_code == 403
    assert (await api.put(ruta, headers=titular, json={'cambios': {'usuarios.editar': True}})).status_code == 200
    assert (await api.patch(f"/api/usuarios/{cuentas['otro']}", headers=titular, json={'activo': False})).status_code == 200


async def test_admin_conserva_gestion_operativa_y_no_se_asciende(db, api):
    titular_id, titular, cuentas, admin = await mundo(api)
    creado = await api.post('/api/usuarios', headers=admin, json={
        'nombre': 'Usuario nuevo', 'email': 'nuevo@prueba.local', 'rol': 'usuario', 'password': PASSWORD,
        'superadministrador': True,
    })
    assert creado.status_code in (201, 422), creado.text
    if creado.status_code == 201:
        assert creado.json()['superadministrador'] is False
    propio = await api.patch(f"/api/usuarios/{cuentas['admin']}", headers=admin, json={'superadministrador': True, 'cargo': 'Coordinador'})
    assert propio.status_code in (200, 422), propio.text
    documento = await db['usuarios'].find_one({'_id': ObjectId(cuentas['admin'])})
    assert not documento['superadministrador']
    for cambios in [{'activo': False}, {'rol': 'tecnico'}]:
        from app.core.errors import Prohibido
        from app.services import usuario_service
        with pytest.raises(Prohibido):
            await usuario_service.actualizar(ObjectId(titular_id), cambios, usuario=await db['usuarios'].find_one({'_id': ObjectId(titular_id)}))
    usuario = cuentas['persona']
    assert (await api.patch(f'/api/usuarios/{usuario}', headers=admin, json={'cargo': 'Secretaria'})).status_code == 200
    assert (await api.post(f'/api/usuarios/{usuario}/desactivar', headers=admin)).status_code == 200
    assert (await api.patch(f'/api/usuarios/{usuario}', headers=admin, json={'activo': True})).status_code == 200
    assert (await api.get('/api/auth/sesion', headers=titular)).json()['superadministrador'] is True


async def test_indice_impide_dos_superadministradores_y_migracion_no_elige_entre_varios(db, api):
    from app.migrations.m027_superadministrador import aplicar
    _, _, cuentas, _ = await mundo(api)
    with pytest.raises(DuplicateKeyError):
        await db['usuarios'].update_one({'_id': ObjectId(cuentas['admin'])}, {'$set': {'superadministrador': True}})
    await db['usuarios'].update_many({}, {'$unset': {'superadministrador': ''}})
    await aplicar(db)
    assert await db['usuarios'].count_documents({'superadministrador': True}) == 0
    await db['usuarios'].update_many({'rol': 'administrador', '_id': {'$ne': ObjectId(cuentas['admin'])}}, {'$set': {'activo': False}})
    await aplicar(db)
    await aplicar(db)
    assert await db['usuarios'].count_documents({'superadministrador': True}) == 1
    assert (await db['usuarios'].find_one({'_id': ObjectId(cuentas['admin'])}))['superadministrador'] is True


async def test_designacion_por_consola_no_sustituye_titular(db, api):
    from app.core.errors import Prohibido
    from app.scripts.superadmin_designar import designar
    _, _, cuentas, _ = await mundo(api)
    with pytest.raises(Prohibido):
        await designar('admin@prueba.local')
    await db['usuarios'].update_many({}, {'$unset': {'superadministrador': ''}})
    with pytest.raises(Prohibido):
        await designar('tecnico@prueba.local')
    await designar('admin@prueba.local')
    assert (await db['usuarios'].find_one({'_id': ObjectId(cuentas['admin'])}))['superadministrador'] is True
    with pytest.raises(Prohibido):
        await designar('otro@prueba.local')
    assert await db['auditoria'].count_documents({'accion': 'usuario.superadministrador'}) == 1
