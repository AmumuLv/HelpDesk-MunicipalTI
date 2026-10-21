/**
 * Menos, estados y permisos de la navegación.
 *
 * El menú se construye con los permisos delegables, no con el rol. Un técnico
 * sin `equipos.importar` no ve el enlace, y si escribe la URL recibe una
 * pantalla de "sin permisos" en lugar de un error.
 */

import type { LucideIcon } from 'lucide-react'

export type EntradaMenu = {
  clave: string
  texto: string
  ruta: string
  icono: LucideIcon
  /** Permiso que hay que tener para que el enlace exista. */
  permiso?: string
  /** Número que se muestra junto al texto; lo da la API. */
  contador?: number
  /** Coloca la entrada después de un separador. */
  separadorAntes?: boolean
}

export type GrupoMenu = {
  clave: string
  texto: string
  entradas: EntradaMenu[]
}

/** Los 20 permisos delegables que publica `GET /permisos/matriz`. */
export const PERMISOS = [
  'tickets.operar',
  'tickets.crear',
  'tickets.asignar',
  'tickets.notas_internas',
  'tickets.exportar',
  'equipos.ver',
  'equipos.crear',
  'equipos.editar',
  'equipos.importar',
  'equipos.campanas',
  'equipos.masivo',
  'org.ver',
  'org.editar',
  'usuarios.ver',
  'usuarios.editar',
  'horarios.ver',
  'horarios.editar_propio',
  'horarios.editar_todos',
  'analitica.ver',
  'kb.ver',
  'kb.editar',
  'configuracion.ver',
  'configuracion.editar',
  'permisos.ver',
  'permisos.editar',
  'auditoria.ver',
  'reportes.ver',
  'exportar',
  'vistas.compartidas',
] as const

/** Módulos del panel y el permiso que los abre. */
export const MODULOS_PANEL: Record<string, string | undefined> = {
  resumen: undefined,
  tickets: 'tickets.operar',
  inventario: 'equipos.ver',
  organizacion: 'org.ver',
  usuarios: 'usuarios.ver',
  equipo: 'horarios.ver',
  analisis: 'analitica.ver',
  reportes: 'reportes.ver',
  conocimiento: 'kb.ver',
  auditoria: 'auditoria.ver',
  configuracion: 'configuracion.ver',
}

/** Navegación inferior del portal del usuario, en el orden en que se usa. */
export const NAVEGACION_PORTAL = [
  { clave: 'inicio', texto: 'Inicio', ruta: '/' },
  { clave: 'tickets', texto: 'Mis reportes', ruta: '/mis-tickets' },
  { clave: 'perfil', texto: 'Mi cuenta', ruta: '/perfil' },
] as const
