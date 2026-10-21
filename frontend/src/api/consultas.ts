/**
 * Datos de servidor con TanStack Query.
 *
 * Ninguna pantalla pide datos con `useEffect`: todo pasa por aquí. Así hay caché
 * entre pantallas, se invalida con precisión al guardar y se distingue carga de
 * vacío y de error.
 */

import { QueryClient } from '@tanstack/react-query'

/**
 * Se cambian dos cosas respecto a un cliente por defecto, por cómo son las
 * pantallas de este sistema:
 *
 * - `staleTime` de 30 s: en una mesa de ayuda la gente va y viene entre la
 *   bandeja y el detalle; sin caché cada salto vuelve a pedir todo.
 * - `retry` 1 y sin reintentar errores 4xx: un 403 de permisos no se arregla
 *   reintentando, solo genera ruido en la consola.
 */
export const clienteConsulta = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      // Un 403 de permisos no se arregla reintentando: solo genera ruido
      // Un 403 de permisos no se arregla reintentando: solo genera ruido en consola
      retry: (numeroDeIntentos: number, fallo: Error) => {
        const error = fallo as Error & { estado?: number; status?: number }
        const estado = error.estado ?? error.status
        if (typeof estado === 'number' && estado >= 400 && estado < 500) return false
        return numeroDeIntentos < 1
      },
      // Mientras llega la nueva página se mantiene la anterior en pantalla, para
      // que la tabla no parpadee al cambiar de filtro o de página
      placeholderData: (previo: unknown) => previo,
    },
    mutations: {
      retry: false,
    },
  },
})

/** Claves de consulta centralizadas: invalidar por dominio, no a ciegas. */
export const claves = {
  sesion: ['sesion'] as const,
  preferenciaIa: ['preferencia-ia'] as const,
  instalacion: ['instalacion'] as const,
  zonaHoraria: ['configuracion-publica'] as const,

  tickets: (filtros?: Record<string, unknown>) => ['tickets', filtros ?? {}] as const,
  ticket: (id: string) => ['ticket', id] as const,
  ticketMensajes: (id: string) => ['ticket', id, 'mensajes'] as const,
  ticketNotas: (id: string) => ['ticket', id, 'notas'] as const,
  ticketIa: (id: string) => ['ticket', id, 'ia'] as const,
  resumenTickets: ['tickets', 'resumen'] as const,
  ajustesTicket: ['tickets', 'ajustes'] as const,
  vistasGuardadas: ['vistas-guardadas'] as const,

  activos: (filtros?: Record<string, unknown>) => ['activos', filtros ?? {}] as const,
  activo: (id: string) => ['activo', id] as const,
  conjuntos: (filtros?: Record<string, unknown>) => ['conjuntos', filtros ?? {}] as const,
  equiposCatalogo: ['equipos', 'catalogos'] as const,
  calidad: (filtros?: Record<string, unknown>) => ['calidad-inventario', filtros ?? {}] as const,
  estadosCampo: ['calidad-inventario', 'estados-campo'] as const,
  equiposMis: ['equipos', 'mis'] as const,

  zonas: ['zonas'] as const,
  zona: (id: string) => ['zona', id] as const,
  oficinas: (zonaId?: string) => ['oficinas', zonaId ?? null] as const,
  oficina: (id: string) => ['oficina', id] as const,
  usuarios: (filtros?: Record<string, unknown>) => ['usuarios', filtros ?? {}] as const,
  usuario: (id: string) => ['usuario', id] as const,
  companeros: ['usuarios', 'companeros'] as const,
  miPerfil: ['mi-perfil'] as const,

  panelEquipo: ['equipo-ti', 'panel'] as const,
  tecnico: (id: string) => ['equipo-ti', id] as const,
  calendarioEquipo: (desde: string, hasta: string) => ['equipo-ti', 'calendario', desde, hasta] as const,
  ausencias: (tecnicoId?: string) => ['ausencias', tecnicoId ?? null] as const,
  miHorarioPermiso: ['equipo-ti', 'mi-horario'] as const,

  analiticaResumen: ['analitica', 'resumen'] as const,
  analiticaPanel: (filtros?: Record<string, unknown>) => ['analitica', 'panel', filtros ?? {}] as const,
  prediccion: ['analitica', 'prediccion'] as const,
  conversaciones: ['ia', 'conversaciones'] as const,
  preguntasAsistente: ['ia', 'preguntas'] as const,

  campanas: ['campanas'] as const,
  campanaItems: (id: string, filtros?: Record<string, unknown>) => ['campana', id, 'items', filtros ?? {}] as const,

  kbArticulos: (filtros?: Record<string, unknown>) => ['kb', 'articulos', filtros ?? {}] as const,
  kbArticulo: (id: string) => ['kb', 'articulo', id] as const,
  kbCategorias: ['kb', 'categorias'] as const,

  auditoria: (filtros?: Record<string, unknown>) => ['auditoria', filtros ?? {}] as const,
  permisosMatriz: ['permisos', 'matriz'] as const,
  permisosTecnicos: ['permisos', 'tecnicos'] as const,
  configuracion: ['configuracion'] as const,
  catalogos: ['configuracion', 'catalogos'] as const,
  feriados: ['configuracion', 'feriados'] as const,
  estadoIa: ['configuracion', 'estado-ia'] as const,

  exportaciones: ['exportaciones'] as const,
  notificaciones: ['notificaciones'] as const,
  importacion: (loteId?: string) => ['importacion', loteId ?? 'plantilla'] as const,
} as const