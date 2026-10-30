"""Permisos: base por rol + matriz delegable por administrador.

Principio: el frontend oculta controles por comodidad, pero TODA autorizacion se
resuelve aqui, en el backend, a partir del documento del usuario.
"""

from __future__ import annotations

from typing import Any

from app.domain.constants import (
    ROL_ADMIN,
    ROL_TECNICO,
    ROL_USUARIO,
    ROLES,
)

# ── Permisos base (no delegables; definen el rol) ────────────
# Un administrador tiene todos ("*").
PERMISOS_BASE: dict[str, set[str]] = {
    ROL_USUARIO: {
        "perfil.ver",
        "perfil.editar",
        "tickets.ver_propios",
        "tickets.crear",
        "tickets.responder",
        "tickets.adjuntar",
        "tickets.valorar",
        "tickets.reabrir_propios",
        "kb.ver",
        "equipos.ver_sus_equipos",
        "equipos.ver_oficina",
        "ia.preferencia",
    },
    ROL_TECNICO: {
        "perfil.ver",
        "perfil.editar",
        "tickets.ver_propios",
        "tickets.crear",
        "tickets.operar",
        "tickets.asignar_si_mismo",
        "tickets.cambiar_estado",
        "tickets.notas_internas",
        "tickets.resolver",
        "tickets.responder",
        "tickets.adjuntar",
        "tickets.valorar",
        "tickets.reabrir_propios",
        "kb.ver",
        "kb.crear_articulo",
        "equipos.ver_sus_equipos",
        "equipos.ver",
        "equipos.ver_oficina",
        "org.ver",
        "usuarios.ver",
        "equipo_ti.ver",
        "horarios.ver",
        "horarios.ver_todos",
        "ia.preferencia",
    },
    ROL_ADMIN: {"*"},
}

# ── Matriz delegable (todo desactivado por defecto) ──────────
# clave -> (etiqueta, descripcion, grupo)
PERMISOS_DELEGABLES: dict[str, dict[str, str]] = {
    "equipos.crear": {
        "etiqueta": "Crear equipos",
        "descripcion": "Registrar conjuntos y equipos nuevos en el inventario.",
        "grupo": "Equipos e inventario",
    },
    "equipos.editar": {
        "etiqueta": "Editar equipos",
        "descripcion": "Modificar los datos de conjuntos y equipos existentes.",
        "grupo": "Equipos e inventario",
    },
    "equipos.eliminar": {
        "etiqueta": "Eliminar equipos",
        "descripcion": "Dar de baja equipos del inventario. Accion destructiva.",
        "grupo": "Equipos e inventario",
    },
    "equipos.importar": {
        "etiqueta": "Importar inventario",
        "descripcion": "Subir y confirmar importaciones desde Excel.",
        "grupo": "Equipos e inventario",
    },
    "equipos.acciones_masivas": {
        "etiqueta": "Acciones masivas sobre equipos",
        "descripcion": "Cambiar estado, oficina o responsable de varios equipos a la vez.",
        "grupo": "Equipos e inventario",
    },
    "equipos.opciones_avanzadas": {
        "etiqueta": "Activar y editar opciones avanzadas",
        "descripcion": "Encender el interruptor de detalle tecnico y registrar componentes internos.",
        "grupo": "Equipos e inventario",
    },
    "equipos.marcar_no_aplica": {
        "etiqueta": "Marcar campos como No aplica",
        "descripcion": "Indicar que un dato no aplica o no esta disponible, en un equipo o en varios.",
        "grupo": "Equipos e inventario",
    },
    "equipos.campanas": {
        "etiqueta": "Ejecutar campanas de inventario",
        "descripcion": "Crear, actualizar y cerrar las campanas de inventario anual.",
        "grupo": "Equipos e inventario",
    },
    "org.editar": {
        "etiqueta": "Crear y editar zonas y oficinas",
        "descripcion": "Administrar la jerarquia Zona > Oficina.",
        "grupo": "Organizacion",
    },
    "usuarios.editar": {
        "etiqueta": "Crear y editar usuarios",
        "descripcion": "Alta, edicion y desactivacion de cuentas del directorio.",
        "grupo": "Organizacion",
    },
    "tickets.reasignar": {
        "etiqueta": "Reasignar tickets a otros tecnicos",
        "descripcion": "Mover un ticket a una persona distinto de quien lo tiene asignado.",
        "grupo": "Tickets",
    },
    "tickets.cerrar_reabrir": {
        "etiqueta": "Cerrar y reabrir tickets",
        "descripcion": "Cerrar tickets de otros o reabrir tickets ya cerrados.",
        "grupo": "Tickets",
    },
    "tickets.eliminar": {
        "etiqueta": "Eliminar tickets, notas y adjuntos",
        "descripcion": "Borrar tickets o sus notas y adjuntos. Accion destructiva.",
        "grupo": "Tickets",
    },
    "kb.editar": {
        "etiqueta": "Editar base de conocimiento",
        "descripcion": "Administrar categorias, plantillas, respuestas rapidas y articulos.",
        "grupo": "Conocimiento",
    },
    "reportes.ver": {
        "etiqueta": "Ver Reportes, Tickets cerrados y Auditoria",
        "descripcion": "Acceder a los apartados de reportes, historial cerrado y auditoria.",
        "grupo": "Analisis",
    },
    "exportar": {
        "etiqueta": "Exportar PDF y Excel",
        "descripcion": "Descargar informes, fichas e inventarios en PDF o Excel.",
        "grupo": "Analisis",
    },
    "analitica.ver": {
        "etiqueta": "Ver Analisis IA",
        "descripcion": "Acceder al panel analitico y al asistente de consulta.",
        "grupo": "Analisis",
    },
    "horarios.editar_propio": {
        "etiqueta": "Editar el propio horario",
        "descripcion": "Modificar el horario y las ausencias del propio tecnico.",
        "grupo": "Equipo TI",
    },
    "horarios.editar_todos": {
        "etiqueta": "Editar horarios de otros tecnicos",
        "descripcion": "Modificar el horario, dias libres y ausencias de cualquier tecnico.",
        "grupo": "Equipo TI",
    },
    "vistas.compartidas": {
        "etiqueta": "Personalizar vistas guardadas compartidas",
        "descripcion": "Editar los filtros guardados que ve todo el equipo de soporte.",
        "grupo": "Equipo TI",
    },
}

CLAVES_PERMISOS = tuple(PERMISOS_DELEGABLES)
GRUPOS_PERMISOS: list[str] = []
for _d in PERMISOS_DELEGABLES.values():
    if _d["grupo"] not in GRUPOS_PERMISOS:
        GRUPOS_PERMISOS.append(_d["grupo"])


def es_admin(usuario: dict[str, Any] | None) -> bool:
    return bool(usuario) and usuario.get("rol") == ROL_ADMIN


def es_tecnico(usuario: dict[str, Any] | None) -> bool:
    return bool(usuario) and usuario.get("rol") in (ROL_TECNICO, ROL_ADMIN)


def es_usuario(usuario: dict[str, Any] | None) -> bool:
    return bool(usuario) and usuario.get("rol") in ROLES


def permisos_del_usuario(usuario: dict[str, Any] | None) -> set[str]:
    """Conjunto completo de permisos efectivos de una persona."""
    if not usuario:
        return set()
    rol = usuario.get("rol")
    base = set(PERMISOS_BASE.get(rol, set()))
    if "*" in base:
        return set(CLAVES_PERMISOS) | base
    delegables = usuario.get("permisos") or {}
    efectivos = base | {k for k, v in delegables.items() if v and k in PERMISOS_DELEGABLES}
    return efectivos


def tiene_permiso(usuario: dict[str, Any] | None, permiso: str) -> bool:
    if not usuario:
        return False
    if usuario.get("rol") == ROL_ADMIN:
        return True
    return permiso in permisos_del_usuario(usuario)


def matriz_inicial() -> dict[str, dict[str, bool]]:
    """Matriz de la configuracion: todo delegable arranca en False."""
    return {clave: False for clave in CLAVES_PERMISOS}