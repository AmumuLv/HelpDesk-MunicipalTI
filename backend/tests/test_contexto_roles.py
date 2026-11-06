"""Las ayudas aclaran su alcance sin ocultar permisos ni afirmar que una baja no existe."""
from bson import ObjectId
import pytest

from app.core.errors import Prohibido
from app.services import analitica_chat, consultas_chatbot
from app.services.conocimiento_proyecto import contexto_proyecto


async def test_directorio_del_chatbot_aclara_activos_sin_exponer_bajas(db):
    activo, baja, archivo = ObjectId(), ObjectId(), ObjectId()
    await db.usuarios.insert_many([
        {'_id': activo, 'nombre': 'Persona actual', 'nombre_busqueda': 'persona actual', 'rol': 'usuario', 'activo': True},
        {'_id': baja, 'nombre': 'Persona de baja', 'nombre_busqueda': 'persona de baja', 'rol': 'usuario', 'activo': False},
        {'_id': archivo, 'nombre': 'Persona archivada', 'nombre_busqueda': 'persona archivada', 'rol': 'usuario', 'activo': False, 'archivado': True},
    ])
    antes = await db.usuarios.find({}).sort('_id').to_list(None)
    resultado = await consultas_chatbot.consultar({'recurso': 'usuarios'}, {'rol': 'administrador'})
    assert resultado['total'] == 1
    assert [p['_id'] for p in resultado['items']] == [activo]
    assert 'cuentas activas' in resultado['nota']
    assert 'Usuarios > Estado' in resultado['nota']
    with pytest.raises(Prohibido):
        await consultas_chatbot.consultar({'recurso': 'usuarios'}, {'rol': 'usuario'})
    assert await db.usuarios.find({}).sort('_id').to_list(None) == antes


@pytest.mark.parametrize('archivado', [False, True])
async def test_consulta_local_sin_persona_activa_no_afirma_que_no_exista(db, archivado):
    await db.usuarios.insert_one({'nombre': 'Trabajador anterior', 'nombre_busqueda': 'trabajador anterior', 'rol': 'usuario', 'activo': False, 'archivado': archivado})
    resultado = await analitica_chat.herramienta_equipos_de_usuario({}, {'nombre': 'Trabajador anterior'})
    assert resultado['encontrado'] is False
    assert 'persona activa' in resultado['mensaje']
    assert 'Usuarios > Estado' in resultado['mensaje']
    assert 'No hay ninguna persona' not in resultado['mensaje']


def test_pregunta_sobre_baja_y_rol_incluye_las_politicas_actuales():
    contexto = contexto_proyecto('¿Un técnico con todos los permisos puede desactivar al administrador principal y borrar su cuenta?', [])
    assert 'Solo el principal puede' in contexto
    assert 'Los permisos adicionales no cambian el rol' in contexto
    contexto = contexto_proyecto('¿Dónde encuentro al trabajador archivado y qué pasa al reactivarlo?', [])
    assert '30 días completos' in contexto
    assert 'no la elimina' in contexto
    assert 'Usuarios > Estado' in contexto
