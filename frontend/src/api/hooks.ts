/**
 * Hooks de datos: el único lugar donde la interfaz pide algo a la API.
 *
 * Ninguna pantalla usa `useEffect` para traer datos. Cada hook declara su
 * `queryKey`, lo que permite invalidar exactamente lo que cambió al guardar y
 * distinguir "cargando" de "vacío" de "error" sin lógica repetida.
 *
 * Regla de los permisos: si la consulta falla con 403, la pantalla muestra
 * NoPermission y no reintenta. El backend es la autoridad.
 */

import { useMutation, useQuery, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { api, consulta } from './cliente'
import { claves } from './consultas'
import type {
  UsuarioSesion,
  ActivoDetalle,
  AjustesTicket,
  ArticuloKb,
  ArticuloKbDetalle,
  Ausencia,
  AuditoriaRespuesta,
  CalendarioEquipo,
  CampanasRespuesta,
  CalidadInventario,
  CatalogoEquipos,
  CatalogosConfiguracion,
  CompanerosRespuesta,
  ConfiguracionPublica,
  ConjuntosRespuesta,
  Conversaciones,
  EstadoCampoCatalogo,
  EsquemaEquipo,
  EstadoIa,
  EstadoInstalacion,
  EstadoLote,
  EquiposDePersona,
  ExportacionesRespuesta,
  FeriadosRespuesta,
  FiltrosActivos,
  FiltrosAnalitica,
  FiltrosArticulos,
  FiltrosAuditoria,
  FiltrosAusencias,
  FiltrosBusquedaEquipo,
  FiltrosCalendario,
  FiltrosCalidad,
  FiltrosConjuntos,
  FiltrosItemsCampana,
  FiltrosMisTickets,
  FiltrosNombreConjunto,
  FiltrosNotificaciones,
  FiltrosOficinas,
  FiltrosPorCodigo,
  FiltrosSugerenciaReporte,
  FiltrosSugerenciasCampo,
  FiltrosTicket,
  FiltrosUsuarios,
  FiltrosZonas,
  HistoricoCampanas,
  ListaActivos,
  ListaEquiposBuscados,
  ListaTickets,
  MatrizPermisos,
  MiHorarioPermiso,
  MiPerfil,
  NotificacionesRespuesta,
  OficinasRespuesta,
  PanelAnalitica,
  PanelConfiguracion,
  PanelEquipo,
  PermisosTecnicos,
  PrediccionEquipos,
  PreguntasAsistente,
  RespuestasRapidasRespuesta,
  ResumenAnalitica,
  ResumenTickets,
  Salud,
  SugerenciaCampo,
  SugerenciaNombreConjunto,
  SugerenciaReporte,
  SugerenciasTicket,
  TecnicoDetalle,
  TecnicosRespuesta,
  TicketDetalle,
  UsuariosRespuesta,
  VistaGuardada,
  ZonasRespuesta,
} from './tipos'

/* ══ Sesión e instalación ══ */

export function useConfiguracionPublica() {
  return useQuery({
    queryKey: claves.zonaHoraria,
    queryFn: () => api.obtener<ConfiguracionPublica>('/publico/configuracion'),
    staleTime: 10 * 60_000,
    retry: false,
  })
}

export function useEstadoInstalacion() {
  return useQuery({
    queryKey: claves.instalacion,
    queryFn: () => api.obtener<EstadoInstalacion>('/instalacion'),
    retry: false,
  })
}

export function useMiPerfil() {
  return useQuery({ queryKey: claves.miPerfil, queryFn: () => api.obtener<MiPerfil>('/mi-perfil'), retry: false })
}

export function usePreferenciaIa() {
  return useQuery({
    queryKey: claves.preferenciaIa,
    queryFn: () => api.obtener<PreferenciaIaShape>('/auth/preferencia-ia'),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
    retry: false,
  })
}

export function useGuardarPreferenciaIa(): UseMutationResult<PreferenciaIaShape, Error, boolean> {
  const invalidate = useQueryClient()
  return useMutation({
    mutationFn: (activo: boolean) =>
      api.crear<PreferenciaIaShape>('/auth/preferencia-ia', { recomendaciones_ia: activo }),
    onSuccess: (datos) => {
      invalidate.setQueryData(claves.preferenciaIa, datos)
      invalidate.setQueryData<UsuarioSesion | null>(claves.sesion, anterior => anterior ? { ...anterior, recomendaciones_ia: datos.recomendaciones_ia } : anterior)
      void invalidate.cancelQueries({ queryKey: ['sugerencia-reporte'] })
      void invalidate.invalidateQueries({ queryKey: ['sugerencia-reporte'], refetchType: 'none' })
      invalidate.invalidateQueries({ queryKey: claves.sesion })
    },
  })
}

export function useSalud() {
  return useQuery({
    queryKey: ['salud'],
    queryFn: () => api.obtener<Salud>('/salud'),
    staleTime: 60_000,
    retry: false,
  })
}

/* ══ Tickets ══ */

export function useResumenTickets() {
  return useQuery({
    queryKey: claves.resumenTickets,
    queryFn: () => api.obtener<ResumenTickets>('/tickets/resumen'),
    retry: false,
  })
}

export function useAjustesTicket() {
  return useQuery({
    queryKey: claves.ajustesTicket,
    queryFn: () => api.obtener<AjustesTicket>('/tickets/ajustes-crear'),
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function useTickets(filtros: FiltrosTicket = {}, enabled = true) {
  return useQuery({
    queryKey: claves.tickets(filtros),
    enabled,
    queryFn: () => api.obtener<ListaTickets>(`/tickets${consulta(filtros)}`),
    retry: false,
  })
}

export function useMisTickets(filtros: FiltrosMisTickets = {}) {
  return useQuery({
    queryKey: ['mis-tickets', filtros],
    queryFn: () => api.obtener<ListaTickets>(`/tickets${consulta({ ...filtros, solo_mios: 1 })}`),
    refetchInterval: 30_000,
    retry: false,
  })
}

export function useTicket(id: string | undefined) {
  return useQuery({
    queryKey: claves.ticket(id ?? ''),
    queryFn: () => api.obtener<TicketDetalle>(`/tickets/${id}`),
    enabled: Boolean(id),
    retry: false,
  })
}

export function useMensajesTicket(id: string | undefined, habilitado: boolean) {
  return useQuery({
    queryKey: claves.ticketMensajes(id ?? ''),
    queryFn: () => api.obtener<ConversacionTicket>(`/tickets/${id}/mensajes`),
    // El chat solo se pide si la API dice que este ticket lo tiene
    enabled: Boolean(id) && habilitado,
    retry: false,
  })
}

export function useNotasTicket(id: string | undefined) {
  return useQuery({
    queryKey: claves.ticketNotas(id ?? ''),
    queryFn: () => api.obtener<ConversacionTicket>(`/tickets/${id}/notas`),
    enabled: Boolean(id),
    retry: false,
  })
}

export function useSugerenciasTicket(id: string | undefined, habilitado: boolean) {
  return useQuery({
    queryKey: claves.ticketIa(id ?? ''),
    queryFn: () => api.obtener<SugerenciasTicket>(`/tickets/${id}/ia`),
    enabled: Boolean(id) && habilitado,
    retry: false,
  })
}

export function useSugerenciaReporte(filtros: FiltrosSugerenciaReporte, habilitado: boolean) {
  return useQuery({
    queryKey: ['sugerencia-reporte', filtros],
    queryFn: () => api.obtener<SugerenciaReporte>(`/ia/sugerencias-reporte${consulta(filtros)}`),
    enabled: habilitado,
    retry: false,
  })
}

export function useVistasGuardadas() {
  return useQuery({
    queryKey: claves.vistasGuardadas,
    queryFn: () => api.obtener<{ items: VistaGuardada[] }>('/vistas-guardadas'),
    retry: false,
  })
}

/* ══ Inventario ══ */

export function useActivos(filtros: FiltrosActivos = {}) {
  return useQuery({
    queryKey: claves.activos(filtros),
    queryFn: () => api.obtener<ListaActivos>(`/activos${consulta(filtros)}`),
    retry: false,
  })
}

export function useActivo(id: string | undefined) {
  return useQuery({
    queryKey: claves.activo(id ?? ''),
    queryFn: () => api.obtener<ActivoDetalle>(`/activos/${id}`),
    enabled: Boolean(id),
    retry: false,
  })
}

export function useEquiposDePersona() {
  return useQuery({
    queryKey: claves.equiposMis,
    queryFn: () => api.obtener<EquiposDePersona>('/equipos/mis'),
    retry: false,
  })
}

/**
 * Los equipos de **otra** persona, para registrarle un caso.
 *
 * El portal usa `useEquiposDePersona`, que es la de quien pregunta. Al registrar
 * un caso de otra persona hace falta lo mismo para ella, y elegir de una lista
 * es lo que evita tener que escribir el nombre del equipo.
 */
export function useEquiposDe(usuarioId: string | null | undefined) {
  return useQuery({
    queryKey: ['equipos-de-persona', usuarioId],
    queryFn: () => api.obtener<EquiposDePersona>(`/equipos/de-persona/${usuarioId}`),
    enabled: Boolean(usuarioId),
    retry: false,
  })
}

export function useCatalogoEquipos() {
  return useQuery({
    queryKey: claves.equiposCatalogo,
    queryFn: () => api.obtener<CatalogoEquipos>('/equipos/catalogos'),
    staleTime: 10 * 60_000,
    retry: false,
  })
}

export function useSugerenciasCampo(campo: string, marca: string | null, habilitado: boolean) {
  const filtros: FiltrosSugerenciasCampo = { campo, ...(marca ? { marca } : {}) }
  return useQuery({
    queryKey: ['sugerencias-campo', filtros],
    queryFn: () => api.obtener<SugerenciaCampo>(`/equipos/sugerencias${consulta(filtros)}`),
    enabled: habilitado && Boolean(campo),
    retry: false,
  })
}

export function useEquipoPorCodigo(texto: string, habilitado: boolean) {
  // El endpoint busca por texto o código patrimonial; se llama igual que
  // `buscar`, que es lo mismo con más campos de filtrado
  const filtros: FiltrosPorCodigo = { texto }
  return useQuery({
    queryKey: ['equipo-por-codigo', filtros],
    queryFn: () => api.obtener<ActivoDetalle | null>(`/equipos/por-codigo${consulta(filtros)}`),
    enabled: habilitado && texto.trim().length > 2,
    retry: false,
  })
}

export function useBuscarEquipos(filtros: FiltrosBusquedaEquipo, habilitado: boolean) {
  return useQuery({
    queryKey: ['buscar-equipos', filtros],
    queryFn: () => api.obtener<ListaEquiposBuscados>(`/equipos/buscar${consulta(filtros)}`),
    enabled: habilitado,
    retry: false,
  })
}

export function useCalidadInventario(filtros: FiltrosCalidad = {}) {
  return useQuery({
    queryKey: claves.calidad(filtros),
    queryFn: () => api.obtener<CalidadInventario>(`/calidad-inventario${consulta(filtros)}`),
    retry: false,
  })
}

export function useEstadosCampo() {
  return useQuery({
    queryKey: claves.estadosCampo,
    queryFn: () => api.obtener<EstadoCampoCatalogo>('/calidad-inventario/estados-campo'),
    staleTime: 10 * 60_000,
    retry: false,
  })
}

export function useEsquemaEquipo(tipo: string | null) {
  return useQuery({
    queryKey: ['esquema-equipo', tipo],
    queryFn: () => api.obtener<EsquemaEquipo>(`/calidad-inventario/esquema/${tipo}`),
    enabled: Boolean(tipo),
    retry: false,
  })
}

export function useConjuntos(filtros: FiltrosConjuntos = {}, habilitado = true) {
  return useQuery({
    queryKey: claves.conjuntos(filtros),
    queryFn: () => api.obtener<ConjuntosRespuesta>(`/conjuntos${consulta(filtros)}`),
    enabled: habilitado,
    retry: false,
  })
}

export function useSiguienteNombreConjunto(oficinaId: string | undefined, habilitado: boolean) {
  const filtros: FiltrosNombreConjunto = { oficina_id: oficinaId ?? '' }
  return useQuery({
    queryKey: ['siguiente-nombre-conjunto', filtros],
    queryFn: () => api.obtener<SugerenciaNombreConjunto>(`/conjuntos/siguiente-nombre${consulta(filtros)}`),
    enabled: habilitado && Boolean(oficinaId),
    retry: false,
  })
}

/* ══ Importación ══ */

export function useEstadoImportacion() {
  return useQuery({
    queryKey: ['importacion', 'lotes'],
    queryFn: () => api.obtener<EstadoLote>('/importacion'),
    retry: false,
  })
}

/* ══ Organización ══ */

export function useZonas(filtros: FiltrosZonas = {}) {
  return useQuery({
    queryKey: [...claves.zonas, filtros],
    queryFn: () => api.obtener<ZonasRespuesta>(`/zonas${consulta(filtros)}`),
    retry: false,
  })
}

export function useOficinas(filtros: FiltrosOficinas = {}) {
  return useQuery({
    queryKey: claves.oficinas(filtros.zona_id),
    queryFn: () => api.obtener<OficinasRespuesta>(`/oficinas${consulta(filtros)}`),
    retry: false,
  })
}

/**
 * `activo` decide si se espera a que haya algo que buscar.
 *
 * El alta de equipo solo necesita responsables **cuando ya se eligió oficina**, y sin
 * ella no hay nadie que ofrecer: pedir el directorio entero era gasto además de estar
 * mal, porque ofrecía cuentas de otras oficinas.
 */
export function useUsuarios(filtros: FiltrosUsuarios = {}, activo = true) {
  return useQuery({
    queryKey: claves.usuarios(filtros),
    queryFn: () => api.obtener<UsuariosRespuesta>(`/usuarios${consulta(filtros)}`),
    retry: false,
    enabled: activo,
  })
}

export function useCompaneros() {
  return useQuery({
    queryKey: claves.companeros,
    queryFn: () => api.obtener<CompanerosRespuesta>('/usuarios/companeros'),
    retry: false,
  })
}

export function useBuscarUsuarios(texto: string, habilitado: boolean) {
  return useQuery({
    queryKey: ['buscar-usuarios', texto],
    queryFn: () => api.obtener<PersonasBuscadas>(`/usuarios/buscar${consulta({ texto })}`),
    enabled: habilitado && texto.trim().length > 1,
    retry: false,
  })
}

/* ══ Equipo TI ══ */

export function usePanelEquipo() {
  return useQuery({
    queryKey: claves.panelEquipo,
    queryFn: () => api.obtener<PanelEquipo>('/equipo-ti/panel'),
    retry: false,
  })
}

export function useTecnicos() {
  return useQuery({
    queryKey: ['equipo-ti', 'tecnicos'],
    queryFn: () => api.obtener<TecnicosRespuesta>('/equipo-ti/tecnicos'),
    retry: false,
  })
}

export function useTecnico(id: string | undefined) {
  return useQuery({
    queryKey: claves.tecnico(id ?? ''),
    queryFn: () => api.obtener<TecnicoDetalle>(`/equipo-ti/${id}`),
    placeholderData: undefined,
    enabled: Boolean(id),
    retry: false,
  })
}

export function useCalendarioEquipo(desde: string, hasta: string, enabled = true) {
  const filtros: FiltrosCalendario = { desde, hasta }
  return useQuery({
    queryKey: claves.calendarioEquipo(desde, hasta),
    enabled,
    placeholderData: undefined,
    queryFn: () => api.obtener<CalendarioEquipo>(`/equipo-ti/calendario${consulta(filtros)}`),
    retry: false,
  })
}

export function useAusencias(filtros: FiltrosAusencias = {}) {
  return useQuery({
    queryKey: claves.ausencias(filtros.tecnico_id),
    queryFn: () => api.obtener<{ items: Ausencia[] }>(`/ausencias${consulta(filtros)}`),
    retry: false,
  })
}

export function useMiHorarioPermiso() {
  return useQuery({
    queryKey: claves.miHorarioPermiso,
    queryFn: () => api.obtener<MiHorarioPermiso>('/equipo-ti/mi-horario/permiso'),
    retry: false,
  })
}

/* ══ Análisis e IA ══ */

export function useResumenAnalitica() {
  return useQuery({
    queryKey: claves.analiticaResumen,
    queryFn: () => api.obtener<ResumenAnalitica>('/analitica/resumen'),
    retry: false,
  })
}

export function usePanelAnalitica(filtros: FiltrosAnalitica = {}) {
  return useQuery({
    queryKey: claves.analiticaPanel(filtros),
    placeholderData: undefined,
    queryFn: () => api.obtener<PanelAnalitica>(`/analitica/panel${consulta(filtros)}`),
    retry: false,
  })
}

export function usePrediccionEquipos() {
  return useQuery({
    queryKey: claves.prediccion,
    queryFn: () => api.obtener<PrediccionEquipos>('/analitica/equipos-prediccion'),
    retry: false,
  })
}

export function usePreguntasAsistente() {
  return useQuery({
    queryKey: claves.preguntasAsistente,
    queryFn: () => api.obtener<PreguntasAsistente>('/ia/asistente/preguntas'),
    retry: false,
  })
}

export function useConversaciones() {
  return useQuery({
    queryKey: claves.conversaciones,
    queryFn: () => api.obtener<Conversaciones>('/ia/asistente/conversaciones'),
    retry: false,
  })
}

/* ══ Campañas ══ */

export function useCampanas() {
  return useQuery({
    queryKey: claves.campanas,
    queryFn: () => api.obtener<CampanasRespuesta>('/campanas'),
    retry: false,
  })
}

export function useItemsCampana(campanaId: string | undefined, filtros: FiltrosItemsCampana) {
  return useQuery({
    queryKey: claves.campanaItems(campanaId ?? '', filtros),
    placeholderData: undefined,
    queryFn: () => api.obtener<ItemsCampanaRespuesta>(`/campanas/${campanaId}/items${consulta(filtros)}`),
    enabled: Boolean(campanaId),
    retry: false,
  })
}

export function useHistoricoCampanas() {
  return useQuery({
    queryKey: ['campanas', 'historico'],
    queryFn: () => api.obtener<HistoricoCampanas>('/campanas/versiones/historico'),
    retry: false,
  })
}

/* ══ Base de conocimiento ══ */

export function useArticulos(filtros: FiltrosArticulos = {}) {
  return useQuery({
    queryKey: claves.kbArticulos(filtros),
    queryFn: () => api.obtener<ArticuloKb>(`/kb/articulos${consulta(filtros)}`),
    retry: false,
  })
}

export function useArticulo(id: string | undefined) {
  const cache = useQueryClient()
  return useQuery({
    queryKey: claves.kbArticulo(id ?? ''),
    placeholderData: undefined,
    queryFn: async () => { const datos = await api.obtener<ArticuloKbDetalle>(`/kb/articulos/${id}`); void cache.invalidateQueries({ queryKey: ['kb', 'articulos'] }); return datos },
    enabled: Boolean(id),
    retry: false,
  })
}

export function useCategoriasKb() {
  return useQuery({
    queryKey: claves.kbCategorias,
    queryFn: () => api.obtener<{ items: string[] }>('/kb/categorias'),
    staleTime: 10 * 60_000,
    retry: false,
  })
}

export function useRespuestasRapidas() {
  return useQuery({
    queryKey: ['kb', 'respuestas-rapidas'],
    queryFn: () => api.obtener<RespuestasRapidasRespuesta>('/kb/respuestas-rapidas'),
    retry: false,
  })
}

/* ══ Administración ══ */

export function useAuditoria(filtros: FiltrosAuditoria = {}) {
  return useQuery({
    queryKey: claves.auditoria(filtros),
    enabled: !(filtros.desde && filtros.hasta && filtros.hasta < filtros.desde),
    placeholderData: undefined,
    queryFn: () => api.obtener<AuditoriaRespuesta>(`/auditoria${consulta(filtros)}`),
    retry: false,
  })
}

export function useMatrizPermisos() {
  return useQuery({
    queryKey: claves.permisosMatriz,
    queryFn: () => api.obtener<MatrizPermisos>('/permisos/matriz'),
    retry: false,
  })
}

export function usePermisosTecnicos() {
  return useQuery({
    queryKey: claves.permisosTecnicos,
    queryFn: () => api.obtener<PermisosTecnicos>('/permisos/tecnicos'),
    retry: false,
  })
}

export function useConfiguracion() {
  return useQuery({
    queryKey: claves.configuracion,
    queryFn: () => api.obtener<PanelConfiguracion>('/configuracion'),
    retry: false,
  })
}

export function useCatalogos() {
  return useQuery({
    queryKey: claves.catalogos,
    queryFn: () => api.obtener<{ catalogos: CatalogosConfiguracion }>('/configuracion/catalogos'),
    staleTime: 10 * 60_000,
    retry: false,
  })
}

export function useEstadoIa() {
  return useQuery({
    queryKey: claves.estadoIa,
    queryFn: () => api.obtener<EstadoIa>('/configuracion/estado-ia'),
    retry: false,
  })
}

export function useFeriados() {
  return useQuery({
    queryKey: claves.feriados,
    queryFn: () => api.obtener<FeriadosRespuesta>('/configuracion/feriados'),
    retry: false,
  })
}

export function useExportaciones() {
  return useQuery({
    queryKey: claves.exportaciones,
    queryFn: () => api.obtener<ExportacionesRespuesta>('/exportaciones'),
    retry: false,
  })
}

/**
 * Notificaciones de la persona conectada.
 *
 * `refetchInterval` porque el aviso en vivo por WebSocket no está conectado: sin
 * esto el contador de la campana se quedaba con el número de la última visita y
 * parecía que las notificaciones no funcionaban. Se consulta cada medio minuto,
 * que es barato (una sola lectura) y suficiente para un panel de trabajo.
 */
export function useNotificaciones(filtros: FiltrosNotificaciones = {}) {
  return useQuery({
    queryKey: [...claves.notificaciones, filtros],
    queryFn: () => api.obtener<NotificacionesRespuesta>(`/notificaciones${consulta(filtros)}`),
    retry: false,
    refetchInterval: 30_000,
  })
}

/* ══ Mutaciones ══ */

/**
 * Guardar algo e invalidar solo los dominios afectados.
 *
 * `dominios` son las claves raíz: al resolver un ticket hay que refrescar la
 * bandeja, el resumen y el detalle, no la aplicación entera.
 */
export function useGuardar<TEntrada, TSalida = unknown>(
  mutacion: (entrada: TEntrada) => Promise<TSalida>,
  dominios: readonly (readonly unknown[])[],
  alTerminar?: (salida: TSalida) => void,
): UseMutationResult<TSalida, Error, TEntrada> {
  const invalidate = useQueryClient()
  return useMutation({
    mutationFn: mutacion,
    onSuccess: (salida) => {
      for (const dominio of dominios) invalidate.invalidateQueries({ queryKey: dominio })
      alTerminar?.(salida)
    },
  })
}

/* ══ Formas que la API no declara y se declaran aquí ══ */

export type PreferenciaIaShape = {
  recomendaciones_ia: boolean
  ia_global_activa: boolean
  recomendaciones_globales: boolean
  recomendaciones_personales: boolean
  recomendaciones_visibles: boolean
  aprendizaje_activo: boolean
  proveedor_disponible: boolean
  modelo: string | null
}

type ConversacionTicket = { items: MensajeShape[]; total?: number }

type MensajeShape = {
  id: string
  ticket_id: string
  autor_id: string
  autor_nombre: string
  autor_rol: string
  cuerpo: string
  adjunto?: unknown
  adjuntos?: unknown[]
  es_ia?: boolean
  leido_por_tecnico?: boolean
  creado_en: string
}


type ItemsCampanaRespuesta = {
  items: ItemCampana[]
  total: number
  pagina: number
  por_pagina: number
  total_paginas: number
}

type ItemCampana = {
  id: string
  activo_id: string | null
  activo_nombre: string
  activo_codigo: string | null
  activo_tipo: string
  zona_nombre: string
  oficina_nombre: string
  estado_item: string
  observaciones: string | null
}

export type PersonasBuscadas = {
  items: {
    id: string
    nombre: string
    rol?: string
    zona_nombre?: string | null
    oficina_nombre?: string | null
  }[]
}
