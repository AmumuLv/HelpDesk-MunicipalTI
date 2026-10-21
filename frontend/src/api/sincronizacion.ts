import type { Query } from '@tanstack/react-query'

const PERSONAS = ['sesion', 'usuarios', 'usuario', 'buscar-usuarios', 'mi-perfil', 'equipo-ti', 'perfil-tecnico-ticket', 'dispositivos', 'permisos', 'borrado']
const INVENTARIO = ['activos', 'activo', 'equipos', 'equipos-de-persona', 'buscar-equipos', 'equipo-por-codigo', 'conjuntos', 'calidad-inventario', 'activos-repetidos', 'destinos-ticket', 'portal-tipos-oficina', 'conjuntos-disponibilidad', 'siguiente-nombre-conjunto', 'sugerencias-campo']
const ORGANIZACION = ['zonas', 'zona', 'oficinas', 'oficina']
const TICKETS = ['tickets', 'mis-tickets', 'ticket', 'activos-tickets', 'analitica', 'reportes', 'auditoria']
const FAMILIAS: Record<string, string[]> = {
  usuarios: [...PERSONAS, ...INVENTARIO, ...ORGANIZACION, 'destinos-ticket'],
  equipos: [...INVENTARIO, ...PERSONAS, ...ORGANIZACION, ...TICKETS, 'campanas', 'campana', 'inventario-anual'],
  organizacion: [...ORGANIZACION, ...PERSONAS, ...INVENTARIO, ...TICKETS],
  tickets: [...TICKETS, ...ORGANIZACION, ...PERSONAS, 'activo', 'activos'],
  'equipo-ti': [...PERSONAS, ...TICKETS, 'ausencias', 'configuracion'],
  conocimiento: ['kb', 'kb-articulo'],
  cuenta: ['sesion', 'dispositivos', 'vistas-guardadas'],
  analitica: ['analitica', 'configuracion'],
  'inventario-anual': ['campanas', 'campana', 'inventario-anual', 'archivo-anual', 'comparar-inventarios', ...INVENTARIO, ...TICKETS],
  importacion: ['importacion', ...INVENTARIO, ...ORGANIZACION, ...PERSONAS, ...TICKETS],
  reportes: ['exportaciones', 'reportes', 'analitica'],
  notificaciones: ['notificaciones'],
  auditoria: ['auditoria'],
}

export function consultaAfectada(consulta: Query, dominios: Set<string>): boolean {
  const clave = consulta.queryKey
  if (clave[0] === 'chatbot-ti' && clave[1] === 'historial') return dominios.has('*') || dominios.has('chatbot')
  // No reiniciar conversaciones locales ni pedir nuevas respuestas a la IA.
  if (typeof consulta.options.queryFn !== 'function' || clave[0] === 'chatbot-ti' || clave[0] === 'sugerencia-reporte' || (clave[0] === 'ticket' && clave[2] === 'ia')) return false
  if (dominios.has('*') || dominios.has('configuracion')) return true
  return [...dominios].some(dominio => FAMILIAS[dominio]?.includes(String(clave[0])))
}
