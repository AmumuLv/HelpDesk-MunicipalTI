"""La importación normal no concede permisos para crear perfiles de personas."""

from io import BytesIO
from unittest.mock import AsyncMock

from bson import ObjectId
from openpyxl import Workbook
import pytest

from app.core.errors import Prohibido
from app.services import import_service
from tests.test_tickets_horarios import _mundo


async def _preparar(api, *, gestionar_usuarios=False):
    mundo = await _mundo(api, 'imp_perfiles')
    permisos = await api.put(
        f"/api/permisos/tecnicos/{mundo['tecnico_id']}", headers=mundo['admin'],
        json={'cambios': {'equipos.importar': True, 'usuarios.editar': gestionar_usuarios}},
    )
    assert permisos.status_code == 200, permisos.text

    libro = Workbook()
    hoja = libro.active
    hoja.title = mundo['zona']['nombre']
    hoja.append(['AREA', 'Tipo de equipo', 'Dispositivo', 'Código patrimonial', 'Nombre equipo', 'Responsable'])
    hoja.append(['COMUNA', 'Laptop', 'Laptop', 'PERF-001', 'Laptop de inventario', 'Responsable Excel Prueba'])
    contenido = BytesIO()
    libro.save(contenido)
    subida = await api.post('/api/importacion/subir', headers=mundo['tecnico'], files={
        'archivo': ('perfiles.xlsx', contenido.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    })
    assert subida.status_code == 200, subida.text
    lote = subida.json()['lote_id']
    previa = await api.post(f'/api/importacion/{lote}/previsualizar', headers=mundo['tecnico'], json={})
    assert previa.status_code == 200, previa.text
    assert previa.json()['validas'] == 1, previa.text
    assert previa.json()['filas'][0]['responsable_estado'] == 'no_encontrado', previa.text
    return mundo, lote


async def _estado(db):
    return {
        nombre: await db[nombre].find({}).sort('_id').to_list(None)
        for nombre in ('usuarios', 'activos', 'conjuntos', 'zonas', 'oficinas', 'importaciones')
    }


async def test_crear_perfiles_exige_permiso_antes_de_reservar_o_escribir(db, api, monkeypatch):
    mundo, lote = await _preparar(api)
    actor = await db.usuarios.find_one({'_id': ObjectId(mundo['tecnico_id'])})
    antes = await _estado(db)
    altas_antes = await db.auditoria.count_documents({'accion': 'usuario.crear'})
    operacion = AsyncMock(wraps=import_service._ejecutar_operacion)
    monkeypatch.setattr(import_service, '_ejecutar_operacion', operacion)

    respuesta = await api.post(f'/api/importacion/{lote}/confirmar', headers=mundo['tecnico'],
                               json={'crear_usuarios_faltantes': True})
    assert respuesta.status_code == 403, respuesta.text
    assert await _estado(db) == antes
    operacion.assert_not_awaited()

    with pytest.raises(Prohibido):
        await import_service.confirmar(lote, crear_usuarios_faltantes=True, usuario=actor)
    operacion.assert_not_awaited()
    assert await _estado(db) == antes
    assert await db.auditoria.count_documents({'accion': 'usuario.crear'}) == altas_antes


@pytest.mark.parametrize('cuerpo', [{}, {'crear_usuarios_faltantes': False}])
async def test_importador_sigue_importando_sin_crear_perfiles(db, api, cuerpo):
    mundo, lote = await _preparar(api)
    personas_antes = await db.usuarios.count_documents({})
    respuesta = await api.post(f'/api/importacion/{lote}/confirmar', headers=mundo['tecnico'], json=cuerpo)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['creados'] == 1, respuesta.text
    assert respuesta.json()['errores'] == 0, respuesta.text
    assert await db.usuarios.count_documents({}) == personas_antes
    equipo = await db.activos.find_one({'codigo_patrimonial': 'PERF-001'})
    assert equipo and equipo.get('responsable_id') is None
    assert equipo['responsable_nombre'] == 'Responsable Excel Prueba'


@pytest.mark.parametrize('rol', ['admin', 'tecnico'])
async def test_autorizado_conserva_alta_de_perfiles_sin_credenciales(db, api, rol):
    mundo, lote = await _preparar(api, gestionar_usuarios=rol == 'tecnico')
    personas_antes = await db.usuarios.count_documents({})
    respuesta = await api.post(f'/api/importacion/{lote}/confirmar', headers=mundo[rol],
                               json={'crear_usuarios_faltantes': True})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['creados'] == 1, respuesta.text
    assert respuesta.json()['errores'] == 0, respuesta.text
    assert await db.usuarios.count_documents({}) == personas_antes + 1
    persona = await db.usuarios.find_one({'nombre': 'Responsable Excel Prueba'})
    assert persona and persona['rol'] == 'usuario'
    assert persona['email'] is None and persona['password_hash'] is None
    assert not persona.get('administrador_principal')
    equipo = await db.activos.find_one({'codigo_patrimonial': 'PERF-001'})
    assert equipo and equipo['responsable_id'] == persona['_id']
