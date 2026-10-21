"""Avisos de invalidación sin documentos ni datos personales en el canal común."""
import asyncio
import contextlib
import json
import logging

from app.core.db import get_db, get_redis

CANAL = 'sincronizacion:datos'
logger = logging.getLogger(__name__)
DOMINIOS = {
    'usuarios': 'usuarios', 'tecnicos_perfil': 'equipo-ti', 'sesiones': 'cuenta',
    'zonas': 'organizacion', 'oficinas': 'organizacion',
    'activos': 'equipos', 'conjuntos': 'equipos', 'historial_responsables': 'equipos',
    'activos_cambios_componentes': 'equipos', 'valores_inventario': 'equipos',
    'tickets': 'tickets', 'ticket_eventos': 'tickets', 'ticket_mensajes': 'tickets',
    'notas_internas': 'tickets', 'adjuntos': 'tickets',
    'articulos_kb': 'conocimiento', 'articulos_kb_valoraciones': 'conocimiento',
    'respuestas_rapidas': 'conocimiento', 'configuracion': 'configuracion',
    'catalogos': 'configuracion', 'esquemas_tipos': 'configuracion',
    'ausencias': 'equipo-ti', 'feriados': 'equipo-ti',
    'campanas_inventario': 'inventario-anual', 'campana_items': 'inventario-anual',
    'inventario_versiones': 'inventario-anual', 'importaciones': 'importacion',
    'exportaciones': 'reportes', 'notificaciones': 'notificaciones', 'auditoria': 'auditoria',
    'ia_eventos': 'analitica', 'vistas_guardadas': 'cuenta',
    'chatbot_conversaciones': 'chatbot',
}


def aviso_cambio(cambio):
    coleccion = cambio.get('ns', {}).get('coll')
    dominio = DOMINIOS.get(coleccion)
    if not dominio:
        return None
    operacion = cambio.get('operationType')
    actualizacion = cambio.get('updateDescription') or {}
    campos = set(actualizacion.get('updatedFields') or {}) | set(actualizacion.get('removedFields') or [])
    raices = {campo.split('.')[0] for campo in campos}
    # No propagar lecturas como ediciones: evita ciclos de refresco y descargas.
    if operacion == 'update':
        if coleccion == 'articulos_kb' and raices <= {'lectores_ids', 'visualizaciones', 'popularidad'}:
            return None
        if coleccion == 'sesiones' and raices <= {'ultimo_uso'}:
            return None
        if coleccion == 'usuarios' and raices <= {'ultimo_acceso', 'sesiones_activas'}:
            return None
    foto = None
    if coleccion == 'usuarios' and (operacion in {'replace', 'delete'} or 'foto' in raices):
        foto = str((cambio.get('documentKey') or {}).get('_id') or '') or None
    return dominio, foto


async def vigilar_cambios(listo=None):
    """Change stream del replica set: también capta importaciones y trabajos del worker.

    Agrupa ráfagas de escrituras; las sesiones solo reciben dominios e IDs de
    fotos a invalidar. Cada lectura HTTP vuelve a comprobar sus permisos.
    """
    demora = 1
    while True:
        tareas = []
        try:
            pipeline = [{'$match': {'ns.coll': {'$in': list(DOMINIOS)}, 'operationType': {'$in': ['insert', 'update', 'replace', 'delete']}}}]
            async with await get_db().watch(pipeline, max_await_time_ms=1000) as stream:
                dominios, fotos = set(), set()
                fotos_todas = False
                pendiente = asyncio.Event()

                async def escuchar():
                    nonlocal fotos_todas
                    async for cambio in stream:
                        aviso = aviso_cambio(cambio)
                        if not aviso:
                            continue
                        dominio, foto = aviso
                        dominios.add(dominio)
                        if foto and not fotos_todas:
                            fotos.add(foto)
                            if len(fotos) > 200:
                                fotos.clear()
                                fotos_todas = True
                        pendiente.set()

                async def emitir():
                    nonlocal fotos_todas
                    while True:
                        await pendiente.wait()
                        await asyncio.sleep(0.2)
                        payload = {'tipo': 'datos_actualizados', 'dominios': sorted(dominios), 'fotos': sorted(fotos), 'fotos_todas': fotos_todas}
                        dominios.clear(); fotos.clear(); fotos_todas = False; pendiente.clear()
                        await get_redis().publish(CANAL, json.dumps(payload))

                await get_redis().publish(CANAL, json.dumps({'tipo': 'sincronizacion'}))
                logger.info('Sincronización de datos activa')
                demora = 1
                if listo:
                    listo.set()
                tareas = [asyncio.create_task(escuchar()), asyncio.create_task(emitir())]
                terminadas, _ = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
                for tarea in terminadas:
                    tarea.result()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning('Reconectando sincronización de datos (%s)', type(exc).__name__)
        finally:
            for tarea in tareas:
                tarea.cancel()
            for tarea in tareas:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await tarea
        await asyncio.sleep(demora)
        demora = min(30, demora * 2)
