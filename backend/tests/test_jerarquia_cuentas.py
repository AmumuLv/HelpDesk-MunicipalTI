"""Escala de roles: las casillas no elevan un técnico ni permiten tomar la cuenta principal."""
import asyncio

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.domain.permissions import CLAVES_PERMISOS
from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _sesion


async def mundo(api):
    inicial = await api.post('/api/instalacion/administrador', json={
        'nombre': 'Titular original', 'email': 'titular@prueba.local', 'password': PASSWORD,
    })
    assert inicial.status_code == 200, inicial.text
    assert inicial.json()['administrador_principal'] is True
    titular = await _sesion(api, 'titular@prueba.local')
    ids = {'principal': inicial.json()['id']}
    for clave, rol in [('admin', 'administrador'), ('tecnico', 'tecnico'), ('otro_tecnico', 'tecnico'), ('persona', 'usuario')]:
        creado = await api.post('/api/usuarios', headers=titular, json={
            'nombre': f'Cuenta {clave}', 'email': f'{clave}@prueba.local', 'password': PASSWORD, 'rol': rol,
        })
        assert creado.status_code == 201, creado.text
        ids[clave] = creado.json()['id']
        assert creado.json()['administrador_principal'] is False
    admin = await _sesion(api, 'admin@prueba.local')
    permiso = await api.put(f"/api/permisos/tecnicos/{ids['tecnico']}", headers=admin,
                            json={'cambios': {p: True for p in CLAVES_PERMISOS}})
    assert permiso.status_code == 200, permiso.text
    tecnico = await _sesion(api, 'tecnico@prueba.local')
    return ids, titular, admin, tecnico


async def accion(api, base, headers, nombre):
    if nombre == 'editar':
        return await api.patch(base, headers=headers, json={'email': 'tomado@prueba.local'})
    if nombre == 'estado':
        return await api.patch(base, headers=headers, json={'activo': False})
    if nombre == 'desactivar':
        return await api.post(base + '/desactivar', headers=headers)
    if nombre == 'password':
        return await api.post(base + '/restablecer-password', headers=headers, json={'password': 'NuevaClave987!'})
    if nombre == 'foto':
        return await api.delete(base + '/foto', headers=headers)
    return await api.delete(base + '/dispositivos/inventada', headers=headers)


@pytest.mark.parametrize('nombre', ['editar', 'estado', 'desactivar', 'password', 'foto', 'sesiones'])
async def test_tecnico_con_todos_los_permisos_no_interviene_cuentas_superiores(db, api, nombre):
    ids, _, _, tecnico = await mundo(api)
    for tipo in ['principal', 'admin', 'otro_tecnico']:
        objetivo = ObjectId(ids[tipo])
        antes = await db.usuarios.find_one({'_id': objetivo})
        respuesta = await accion(api, f'/api/usuarios/{objetivo}', tecnico, nombre)
        assert respuesta.status_code == 403, respuesta.text
        assert await db.usuarios.find_one({'_id': objetivo}) == antes


async def test_tecnico_autorizado_gestiona_solo_usuarios_y_retiro_es_inmediato(db, api):
    ids, _, admin, tecnico = await mundo(api)
    base = f"/api/usuarios/{ids['persona']}"
    assert (await api.patch(base, headers=tecnico, json={'cargo': 'Cargo válido'})).status_code == 200
    persona_headers = await _sesion(api, 'persona@prueba.local')
    assert (await accion(api, base, tecnico, 'password')).status_code == 200
    assert (await api.get('/api/auth/sesion', headers=persona_headers)).status_code == 401
    assert (await accion(api, base, tecnico, 'desactivar')).status_code == 200
    assert (await api.patch(base, headers=tecnico, json={'activo': True})).status_code == 200
    assert (await api.post('/api/usuarios', headers=tecnico, json={
        'nombre': 'Persona nueva', 'email': 'nueva@prueba.local', 'rol': 'usuario', 'password': PASSWORD,
    })).status_code == 201
    for rol in ['tecnico', 'administrador']:
        assert (await api.post('/api/usuarios', headers=tecnico, json={
            'nombre': 'Alta prohibida', 'email': rol + '@no.local', 'rol': rol, 'password': PASSWORD,
        })).status_code == 403
    assert (await api.put(f"/api/permisos/tecnicos/{ids['otro_tecnico']}", headers=tecnico,
                          json={'cambios': {'usuarios.editar': True}})).status_code == 403
    assert (await api.put(f"/api/permisos/tecnicos/{ids['tecnico']}", headers=admin,
                          json={'cambios': {'usuarios.editar': False}})).status_code == 200
    assert (await accion(api, base, tecnico, 'password')).status_code == 403
    assert (await accion(api, base, tecnico, 'editar')).status_code == 403


async def test_administrador_conserva_gestion_y_solo_principal_autoriza_nuevos_admins(db, api):
    ids, principal, admin, _ = await mundo(api)
    for rol in ['usuario', 'tecnico']:
        creado = await api.post('/api/usuarios', headers=admin, json={
            'nombre': f'Nuevo {rol}', 'email': f'nuevo-{rol}@prueba.local', 'rol': rol, 'password': PASSWORD,
        })
        assert creado.status_code == 201, creado.text
    prohibido = await api.post('/api/usuarios', headers=admin, json={
        'nombre': 'Otro administrador', 'email': 'admin2@prueba.local', 'rol': 'administrador', 'password': PASSWORD,
    })
    assert prohibido.status_code == 403
    assert (await api.patch(f"/api/usuarios/{ids['persona']}", headers=admin, json={'rol': 'administrador'})).status_code == 403
    assert (await api.patch(f"/api/usuarios/{ids['persona']}", headers=principal, json={'rol': 'administrador'})).status_code == 200
    # El administrador normal conserva su gestión sobre otro admin secundario.
    base = f"/api/usuarios/{ids['persona']}"
    assert (await api.patch(base, headers=admin, json={'cargo': 'Administrador operativo'})).status_code == 200
    assert (await accion(api, base, admin, 'password')).status_code == 200
    assert (await accion(api, base, admin, 'desactivar')).status_code == 200
    assert (await api.patch(base, headers=admin, json={'activo': True})).status_code == 200
    assert (await api.patch(base, headers=admin, json={'rol': 'tecnico'})).status_code == 200
    # Conserva configuración y permisos, sin confundirlos con crear administradores.
    assert (await api.get('/api/configuracion', headers=admin)).status_code == 200
    assert (await api.put(f"/api/permisos/tecnicos/{ids['otro_tecnico']}", headers=admin,
                          json={'cambios': {'equipos.crear': True}})).status_code == 200


async def test_cuenta_principal_protegida_incluye_credenciales_y_sesiones(db, api):
    ids, titular, admin, _ = await mundo(api)
    base = f"/api/usuarios/{ids['principal']}"
    antes = await db.usuarios.find_one({'_id': ObjectId(ids['principal'])})
    for nombre in ['editar', 'estado', 'desactivar', 'password', 'foto', 'sesiones']:
        assert (await accion(api, base, admin, nombre)).status_code == 403
    assert (await api.patch(base, headers=admin, json={'rol': 'tecnico'})).status_code == 403
    assert (await db.usuarios.find_one({'_id': ObjectId(ids['principal'])})) == antes
    assert (await accion(api, base, titular, 'desactivar')).status_code == 403
    assert (await api.patch('/api/mi-perfil', headers=titular, json={'cargo': 'Titular TI'})).status_code == 200
    assert (await api.post('/api/auth/password', headers=titular,
                           json={'password_actual': PASSWORD, 'password_nuevo': 'PropiaNueva987!'})).status_code == 200


async def test_campos_forjados_y_permisos_no_elevan_roles(db, api):
    ids, _, admin, tecnico = await mundo(api)
    respuesta = await api.patch(f"/api/usuarios/{ids['tecnico']}", headers=tecnico,
                                json={'rol': 'administrador', 'administrador_principal': True, 'permisos': {'*': True}})
    assert respuesta.status_code in (200, 422)
    documento = await db.usuarios.find_one({'_id': ObjectId(ids['tecnico'])})
    assert documento['rol'] == 'tecnico' and documento['administrador_principal'] is False
    # Ni una matriz heredada por error convierte al usuario en técnico.
    await db.usuarios.update_one({'_id': ObjectId(ids['persona'])}, {'$set': {'permisos': {p: True for p in CLAVES_PERMISOS}}})
    persona = await _sesion(api, 'persona@prueba.local')
    assert (await api.get('/api/usuarios', headers=persona)).status_code == 403
    assert (await api.get('/api/permisos/matriz', headers=tecnico)).status_code == 403
    assert (await api.put(f"/api/permisos/tecnicos/{ids['otro_tecnico']}", headers=admin,
                          json={'cambios': {'*': True}})).status_code == 422


@pytest.mark.parametrize('operacion', ['editar', 'password'])
async def test_cambio_simultaneo_de_rol_no_permite_al_tecnico_tomar_cuenta(db, api, monkeypatch, operacion):
    ids, _, _, tecnico = await mundo(api)
    objetivo = ObjectId(ids['persona'])
    antes = await db.usuarios.find_one({'_id': objetivo})
    clase = type(db.usuarios)
    original = clase.update_one
    pendiente = True

    async def interceptar(self, filtro, actualizacion, *args, **kwargs):
        nonlocal pendiente
        campos = actualizacion.get('$set', {})
        if pendiente and self.name == 'usuarios' and filtro.get('_id') == objetivo and ('email' in campos or 'password_hash' in campos):
            pendiente = False
            await original(self, {'_id': objetivo}, {'$set': {'rol': 'administrador'}})
        return await original(self, filtro, actualizacion, *args, **kwargs)

    monkeypatch.setattr(clase, 'update_one', interceptar)
    respuesta = await accion(api, f'/api/usuarios/{objetivo}', tecnico, operacion)
    assert respuesta.status_code == 409, respuesta.text
    despues = await db.usuarios.find_one({'_id': objetivo})
    assert despues['email'] == antes['email'] and despues['password_hash'] == antes['password_hash']


async def test_arranque_simultaneo_solo_crea_un_titular(db, api):
    respuestas = await asyncio.gather(*(api.post('/api/instalacion/administrador', json={
        'nombre': 'Titular ' + str(i), 'email': f'titular{i}@prueba.local', 'password': PASSWORD,
    }) for i in range(2)))
    assert sorted(r.status_code for r in respuestas) in ([200, 403], [200, 409])
    assert await db.usuarios.count_documents({'administrador_principal': True}) == 1
    assert await db.usuarios.count_documents({'rol': 'administrador'}) == 1


async def test_migracion_preserva_primero_y_unicidad(db, api):
    from app.migrations.m027_administrador_principal import aplicar
    ids, _, _, _ = await mundo(api)
    await db.usuarios.update_many({}, {'$unset': {'administrador_principal': ''}})
    await aplicar(db)
    await aplicar(db)
    assert (await db.usuarios.find_one({'_id': ObjectId(ids['principal'])}))['administrador_principal'] is True
    with pytest.raises(DuplicateKeyError):
        await db.usuarios.update_one({'_id': ObjectId(ids['admin'])}, {'$set': {'administrador_principal': True}})
