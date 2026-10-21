"""Registro de auditoria append-only.

Ninguna pantalla modifica la coleccion ``auditoria``: solo existe esta funcion
y las escrituras de negocio que la llaman.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from app.core.db import get_db
from app.core.time import business_start_of_day, utcnow
from app.core.errors import Validacion

logger = logging.getLogger(__name__)

# Acciones relevantes registradas obligatoriamente
ACCIONES = {
    'inventario.anual': 'Registro de inventario anual',
    'inventario.anual.eliminar': 'Eliminación de versión anual',
    "auth.login": "Inicio de sesion",
    "auth.logout": "Cierre de sesion",
    "auth.login_fallido": "Intento de acceso fallido",
    "auth.bloqueo": "Cuenta bloqueada por intentos",
    "usuario.crear": "Creacion de usuario",
    "usuario.editar": "Edicion de usuario",
    "usuario.desactivar": "Desactivacion de usuario",
    "usuario.reactivar": "Reactivacion de usuario",
    "usuario.password": "Cambio de contrasena",
    "zona.crear": "Creacion de zona",
    "zona.editar": "Edicion de zona",
    "zona.eliminar": "Eliminacion de zona",
    "oficina.crear": "Creacion de oficina",
    "oficina.editar": "Edicion de oficina",
    "oficina.eliminar": "Eliminacion de oficina",
    "activo.crear": "Alta de equipo",
    "activo.editar": "Edicion de equipo",
    "activo.eliminar": "Baja de equipo",
    "activo.masivo": "Cambio masivo de equipos",
    "activo.campo_estado": "Cambio de estado de campo",
    "activo.opciones_avanzadas": "Opciones avanzadas",
    "activo.componente": "Cambio de componente interno",
    "activo.responsable": "Cambio de responsable",
    "conjunto.crear": "Alta de conjunto",
    "conjunto.editar": "Edicion de conjunto",
    "importacion.subir": "Carga de archivo de importacion",
    "importacion.confirmar": "Importacion confirmada",
    "importacion.deshacer": "Deshacer importacion",
    "campana.crear": "Creacion de campana de inventario",
    "campana.cerrar": "Cierre de campana de inventario",
    "campana.item": "Actualizacion de campana",
    "ticket.crear": "Creacion de ticket",
    "ticket.actualizar": "Actualizacion de ticket",
    "ticket.asignar": "Asignacion de ticket",
    "ticket.estado": "Cambio de estado de ticket",
    "ticket.cerrar": "Cierre de ticket",
    "ticket.reabrir": "Reapertura de ticket",
    "ticket.eliminar": "Eliminacion de ticket",
    "ticket.chat": "Mensaje en el chat del ticket",
    "ticket.nota": "Nota interna",
    "ticket.adjunto": "Adjunto en ticket",
    "ticket.encuesta": "Valoracion de atencion",
    "kb.crear": "Creacion de articulo",
    "kb.editar": "Edicion de articulo",
    "kb.eliminar": "Eliminacion de articulo",
    "config.actualizar": "Cambio de configuracion",
    "permiso.cambiar": "Cambio de permiso delegable",
    "ia.preferencia": "Cambio de preferencia de recomendaciones IA",
    "ia.global": "Cambio del interruptor global de IA",
    "ia.aplicar": "Aplicacion de sugerencia de IA",
    "ia.descartar": "Descarte de sugerencia de IA",
    "ia.consulta": "Consulta al asistente de analisis",
    "exportacion.pdf": "Exportacion PDF",
    "exportacion.excel": "Exportacion Excel/CSV",
    "demo.cargar": "Carga de datos de demostracion",
}

# El chat y las notas conservan su historial en el ticket. La auditoría central
# destaca cambios de negocio y seguridad, sin duplicar la actividad cotidiana.
ACCIONES_COTIDIANAS = {
    "auth.login", "auth.logout", "ticket.chat", "ticket.nota", "ticket.adjunto",
    "ticket.encuesta", "ia.consulta", "ia.preferencia", "ia.descartar",
    "exportacion.pdf", "exportacion.excel",
}
RESULTADOS_ALERTA = ["error", "fallido", "denegado", "bloqueado"]


def accion_legible(accion: str, entidad: str = "") -> str:
    if entidad == "respuesta_rapida":
        return {"kb.crear": "Creación de respuesta rápida", "kb.editar": "Edición de respuesta rápida", "kb.eliminar": "Eliminación de respuesta rápida"}.get(accion, ACCIONES.get(accion, accion))
    return ACCIONES.get(accion, accion)


def consulta_movimientos(*, desde: date | None = None, hasta: date | None = None,
                         accion: str | None = None, entidad: str | None = None,
                         usuario_id: Any = None, resultado: str | None = None) -> dict[str, Any]:
    if desde and hasta and hasta < desde:
        raise Validacion("La fecha final debe ser igual o posterior a la inicial.")
    consulta: dict[str, Any] = {"rol": {"$in": ["administrador", "tecnico"]}, "$or": [
        {"accion": {"$nin": sorted(ACCIONES_COTIDIANAS)}},
        {"resultado": {"$in": RESULTADOS_ALERTA}},
    ]}
    for campo, valor in (("accion", accion), ("entidad", entidad), ("usuario_id", usuario_id), ("resultado", resultado)):
        if valor:
            consulta[campo] = valor
    rango = {'$gte': utcnow() - timedelta(days=15)}
    if desde:
        rango['$gte'] = max(rango['$gte'], business_start_of_day(desde))
    if hasta:
        rango['$lt'] = business_start_of_day(hasta + timedelta(days=1))
    if rango:
        consulta['fecha'] = rango
    return consulta


async def registrar(
    accion: str,
    *,
    usuario_id: Any = None,
    usuario_nombre: str = "",
    rol: str = "",
    entidad: str = "",
    entidad_id: Any = None,
    resultado: str = "ok",
    resumen: str = "",
    antes: Any = None,
    despues: Any = None,
    contexto: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Escribe una entrada de auditoria. Nunca lanza excepcion hacia el negocio."""
    if not rol and usuario_id:
        try:
            persona = await get_db()['usuarios'].find_one({'_id': usuario_id}, {'rol': 1})
            rol = (persona or {}).get('rol', '')
        except Exception:
            return
    if rol not in {'administrador', 'tecnico'}:
        return
    if accion in ACCIONES_COTIDIANAS and resultado not in RESULTADOS_ALERTA:
        return
    if antes is not None and despues is not None and antes == despues and resultado == 'ok':
        return
    documento = {
        "fecha": utcnow(),
        "accion": accion,
        "accion_texto": accion_legible(accion, entidad),
        "usuario_id": usuario_id,
        "usuario_nombre": usuario_nombre,
        "rol": rol,
        "entidad": entidad,
        "entidad_id": str(entidad_id) if entidad_id is not None else None,
        "resultado": resultado,
        "resumen": resumen,
        "antes": antes,
        "despues": despues,
        "contexto": contexto or {},
        "ip": ip,
        "user_agent": user_agent,
    }
    try:
        await get_db()["auditoria"].insert_one(documento)
    except Exception as exc:  # pragma: no cover
        logger.error("No se pudo escribir la auditoria (%s): %s", accion, exc)


async def diff_antes_despues(
    antes: dict[str, Any] | None, despues: dict[str, Any] | None, *, omitir: set[str] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Devuelve solo los campos que cambiaron, para auditoria legible."""
    omitir = omitir or set()
    anterior = {k: v for k, v in (antes or {}).items() if k not in omitir}
    nuevo = {k: v for k, v in (despues or {}).items() if k not in omitir}
    cambios_antes: dict[str, Any] = {}
    cambios_despues: dict[str, Any] = {}
    for campo in set(anterior) | set(nuevo):
        valor_antes = anterior.get(campo)
        valor_despues = nuevo.get(campo)
        if valor_antes != valor_despues:
            cambios_antes[campo] = valor_antes
            cambios_despues[campo] = valor_despues
    return cambios_antes, cambios_despues
