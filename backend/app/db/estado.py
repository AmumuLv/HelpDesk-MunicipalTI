"""Estado de la instalacion: que pasos del arranque guiado faltan por completar."""

from __future__ import annotations

from typing import Any
import re

from app.core.db import get_db
from app.domain.constants import ROL_ADMIN, ROL_TECNICO
from app.services import config_service


async def estado_instalacion() -> dict[str, Any]:
    db = get_db()
    hay_admin = await db["usuarios"].count_documents({"rol": ROL_ADMIN, "activo": True}) > 0
    hay_zonas = await db["zonas"].count_documents({"activa": True}) > 0
    hay_oficinas = await db["oficinas"].count_documents({"activa": True}) > 0
    hay_usuarios = await db["usuarios"].count_documents({"rol": "usuario", "activo": True}) > 0
    equipo_ti = await db['usuarios'].find({'rol': {'$in': [ROL_TECNICO, ROL_ADMIN]}, 'activo': True}, {'_id': 1}).to_list(None)
    ids_ti = [u['_id'] for u in equipo_ti]
    hay_tecnicos = bool(ids_ti)
    hay_inventario = await db["activos"].count_documents({"activo": {"$ne": False}}) > 0
    importacion = await db["importaciones"].count_documents({"estado": "confirmado"}) > 0
    perfiles = await db['tecnicos_perfil'].find({'usuario_id': {'$in': ids_ti}}, {'usuario_id': 1, 'horario': 1}).to_list(None)
    horarios = len({p['usuario_id'] for p in perfiles if _horario_util(p.get('horario') or {})})
    horarios_completos = hay_tecnicos and horarios == len(ids_ti)
    ids_usuarios = [u['_id'] async for u in db['usuarios'].find({'activo': True}, {'_id': 1})]
    activos_con_nombre = {'activo': {'$ne': False}, 'responsable_nombre': {'$nin': [None, '']}}
    responsables_total = await db['activos'].count_documents(activos_con_nombre)
    responsables_pendientes = await db['activos'].count_documents({**activos_con_nombre, 'responsable_id': {'$nin': ids_usuarios}})
    responsables_completos = hay_inventario and responsables_pendientes == 0

    pasos = [
        {"clave": "crear_admin", "titulo": "Crear la cuenta de administrador", "hecho": hay_admin},
        {
            "clave": "importar_inventario",
            "titulo": "Importar el inventario (crea zonas y oficinas) o crearlas a mano",
            "hecho": hay_inventario,
            "alternativa": "Si no tienes Excel, crea al menos una zona y una oficina.",
            "alternativa_hecha": hay_oficinas,
        },
        {"clave": "crear_usuarios", "titulo": "Crear las cuentas de los trabajadores", "hecho": hay_usuarios},
        {"clave": "crear_tecnicos", "titulo": "Registrar al equipo de soporte TI", "hecho": hay_tecnicos},
        {"clave": "asignar_responsables", "titulo": "Asignar responsables de los equipos", "hecho": responsables_completos},
        {"clave": "definir_horarios", "titulo": "Definir los horarios del equipo TI", "hecho": horarios_completos},
    ]
    acciones = {
        'crear_admin': ('Crear administrador', '/instalacion', 'La cuenta de administrador permite configurar el sistema.'),
        'importar_inventario': ('Ver inventario', '/panel/equipos', 'Las zonas y oficinas provienen del inventario importado.'),
        'crear_usuarios': ('Registrar trabajador', '/panel/usuarios?crear=usuario', 'Crea las cuentas reales y selecciona su oficina para relacionar sus tickets y equipos.'),
        'crear_tecnicos': ('Registrar técnico', '/panel/usuarios?crear=tecnico', f'{len(ids_ti)} cuentas TI activas, incluidos administradores. Puedes añadir técnicos reales.'),
        'asignar_responsables': ('Vincular responsables', '/panel/equipos?responsables_pendientes=1', f'{responsables_total - responsables_pendientes} de {responsables_total} equipos con responsable identificado están vinculados a una cuenta. Los equipos sin nombre pueden ser de uso común.'),
        'definir_horarios': ('Definir horarios', '/panel/equipo-ti?tab=horarios', f'{horarios} de {len(ids_ti)} integrantes TI tienen un horario laboral válido. Los días libres no cuentan como horario de trabajo.'),
    }
    for paso in pasos:
        accion, ruta, descripcion = acciones[paso['clave']]
        paso.update({'accion': accion, 'ruta': ruta, 'descripcion': descripcion})
    siguiente = next((paso["clave"] for paso in pasos if not paso["hecho"]), "listo")
    config = await config_service.obtener()
    if bool(config.get('sistema', {}).get('primer_arranque_completo')) != (siguiente == 'listo'):
        await db['configuracion'].update_one({'_id': 'config'}, {'$set': {'sistema.primer_arranque_completo': siguiente == 'listo'}}, upsert=True)
    institucion = await config_service.seccion("institucion")
    return {
        "configurado": siguiente == "listo",
        "hay_admin": hay_admin,
        "hay_zonas": hay_zonas,
        "hay_oficinas": hay_oficinas,
        "hay_usuarios": hay_usuarios,
        "hay_tecnicos": hay_tecnicos,
        "hay_inventario": hay_inventario,
        "inventario_importado": importacion,
        "horarios_completos": horarios_completos,
        "pasos": pasos,
        "pasos_completados": [p["clave"] for p in pasos if p["hecho"]],
        "siguiente_paso": siguiente,
        "institucion": institucion.get("nombre", "Municipalidad"),
        'acceso_habilitado': hay_admin,
        'equipo_ti_total': len(ids_ti),
        'horarios_definidos': horarios,
        'responsables_total': responsables_total,
        'responsables_pendientes': responsables_pendientes,
    }


def _horario_util(horario: dict[str, Any]) -> bool:
    for dia, configuracion in (horario.get('dias') or {}).items():
        if str(dia) not in {'0', '1', '2', '3', '4', '5', '6'} or configuracion.get('libre'):
            continue
        for tramo in configuracion.get('tramos') or []:
            entrada, salida = tramo.get('entrada', ''), tramo.get('salida', '')
            patron = r'(?:[01]\d|2[0-3]):[0-5]\d'
            if isinstance(entrada, str) and isinstance(salida, str) and re.fullmatch(patron, entrada) and re.fullmatch(patron, salida) and entrada < salida:
                return True
    return False
