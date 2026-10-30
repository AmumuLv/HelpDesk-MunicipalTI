/**
 * Tipos de la interfaz.
 *
 * Tres fuentes, en este orden de confianza:
 *
 * 1. `esquema-api.ts`: generado con openapi-typescript desde el OpenAPI real.
 *    Veraz para lo que la API declara: cuerpos de petición y parámetros.
 * 2. `respuestas-api.ts`: generado desde las formas observadas en la API en
 *    marcha. Existe porque el backend no declara `response_model`, así que el
 *    OpenAPI publica todas las respuestas sin forma.
 * 3. Este archivo: solo alias con nombre de dominio y los tipos propios.
 *
 * Un campo que la API no entrega no se inventa aquí: se documenta en
 * docs/BACKEND_GAPS.md.
 */

import type { components } from './esquema-api'
import type * as Respuestas from './respuestas-api'

type Esquemas = components['schemas']

/* ══ Patrón común: casi todo lista con envoltorio ══════════ */

type Envoltura<T> = {
  items: T[]
  total: number
  pagina: number
  por_pagina: number
  total_paginas: number
}

/* ══ Sesión e instalación ══════════════════════════════════ */

export type UsuarioSesion = Respuestas.RespuestaAuthSesion & { administrador_principal?: boolean }
export type ConfiguracionPublica = Respuestas.RespuestaPublicoConfiguracion
export type EstadoInstalacion = Omit<Respuestas.RespuestaInstalacion, 'pasos'> & {
  acceso_habilitado?: boolean
  equipo_ti_total?: number
  horarios_definidos?: number
  responsables_total?: number
  responsables_pendientes?: number
  pasos: (Respuestas.RespuestaInstalacion['pasos'][number] & { descripcion?: string; accion?: string; ruta?: string })[]
}
export type PreferenciaIa = Respuestas.RespuestaAuthPreferenciaIa
export type MiPerfil = Omit<Respuestas.RespuestaMiPerfil, 'equipos_responsable'> & {
  administrador_principal?: boolean
  tiene_foto?: boolean
  equipos_responsable: { id: string; nombre: string; tipo: string; codigo_patrimonial: string | null }[]
}
export type Salud = Respuestas.RespuestaSalud

export type Rol = 'administrador' | 'tecnico' | 'usuario'

export type RespuestaLogin = UsuarioSesion & {
  access_token: string
  token_type: string
  csrf_token: string | null
}

/* ══ Tickets ══════════════════════════════════════════════ */

/**
 * Filtros de `GET /api/tickets`.
 *
 * Los filtros de lista (`estado`, `prioridad`, `categoria`, `origen`) viajan como
 * parámetros repetidos (`?estado=nuevo&estado=cerrado`), no como un texto con
 * comas. `ConsultaTickets` sale de la forma observada en la API viva y no los
 * recoge, así que se declaran aquí; el archivo generado no se edita a mano.
 */
export type FiltrosTicket = Respuestas.ConsultaTickets & {
  conjunto_id?: string
  direccion?: 'asc' | 'desc'
  estado?: string | string[]
  prioridad?: string | string[]
  categoria?: string | string[]
  origen?: string | string[]
}
export type FiltrosMisTickets = Respuestas.ConsultaTickets
export type AjustesTicket = Omit<Respuestas.RespuestaTicketsAjustesCrear, 'tipos_problema'> & { tipos_problema: (Respuestas.RespuestaTicketsAjustesCrear['tipos_problema'][number] & { categoria?: string | null })[]; categorias_especiales?: { formateo?: string | null; correo?: string | null } }
export type ResumenTickets = Respuestas.RespuestaTicketsResumen & {
  en_atencion: number
  resueltos: number
}
export type ListaTickets = Omit<Respuestas.RespuestaTickets, 'items'> & { items: TicketResumen[] }
export type TicketResumen = Respuestas.RespuestaTickets['items'][number] & { reporte_para?: 'propio' | 'companero' | 'oficina' | null }
export type TicketCreado = {
  ticket: Pick<TicketResumen, 'id' | 'codigo' | 'estado' | 'prioridad' | 'tiene_chat'>
  mensaje?: string
  enlace_seguimiento?: string
}
export type MensajeTicket = Respuestas.RespuestaTicketsPorticket_idMensajes
export type NotaTicket = Respuestas.RespuestaTicketsPorticket_idNotas
/**
 * Lo que ya se decidió sobre cada sugerencia de IA.
 *
 * `clave` es el punto («categoria», «prioridad», «tecnico_sugerido_id») y
 * `anterior` el valor que tenía el ticket, para poder decir qué cambió sin
 * adivinar. No viene en el tipo generado porque se añadió al servicio después.
 */
export type DecisionIA = {
  accion: 'aplicar' | 'editar' | 'descartar'
  elegido?: string | null
  anterior?: string | null
  por?: string | null
  en?: string | null
}

/**
 * Detalle del ticket con lo que esta persona puede hacer sobre él.
 *
 * `puede_cerrar` y `puede_reabrir` replican la misma regla que aplica el
 * servidor al cambiar el estado: el permiso `tickets.cerrar_reabrir` es
 * delegable y arranca apagado, así que un técnico que no es el asignado no puede
 * cerrar el ticket de otro. Sin estos campos la interfaz le ofrecía el botón y
 * el servidor le respondía con un 403.
 */
export type TicketDetalle = Respuestas.RespuestaTicketsPorticket_id & {
  reporte_para?: 'propio' | 'companero' | 'oficina' | null
  alcance_incidencia?: 'equipo' | 'conjunto' | 'programa' | 'servicio' | 'pendiente'
  sistema_afectado?: string | null
  tipo_problema?: string | null
  puede_operar?: boolean
  puede_cerrar?: boolean
  puede_reabrir?: boolean
  puede_eliminar?: boolean
}

export type SugerenciasTicket = Respuestas.RespuestaTicketsPorticket_idIa & {
  decisiones?: Record<string, DecisionIA | undefined>
}
export type SugerenciaReporte = Respuestas.RespuestaIaSugerenciasReporte
export type FiltrosSugerenciaReporte = Respuestas.ConsultaIaSugerenciasReporte
export type VistasGuardadas = Respuestas.RespuestaVistasGuardadas
export type VistaGuardada = NonNullable<VistasGuardadas['items']>[number]

/* ══ Inventario ════════════════════════════════════════════ */

export type FiltrosActivos = Omit<Respuestas.ConsultaActivos, 'orden'> & {
  responsables_pendientes?: boolean
  orden?: 'ubicacion' | 'nombre_equipo' | 'tipo' | 'marca' | 'estado' | 'actualizado_en' | 'creado_en'
}
export type ActivoDetalle = Respuestas.RespuestaActivosPoractivo_id & {
  numero_equipo?: number | null
  detalle_avanzado?: Record<string, unknown> | null
}
export type ItemActivo = ActivoDetalle
export type ListaActivos = Envoltura<ItemActivo>
export type EquiposDePersona = Respuestas.RespuestaUsuarioEquiposMis
export type CatalogoEquipos = Respuestas.RespuestaEquiposCatalogos
export type SugerenciaCampo = Respuestas.RespuestaEquiposSugerencias
export type FiltrosSugerenciasCampo = Respuestas.ConsultaEquiposSugerencias
export type FiltrosBusquedaEquipo = Respuestas.ConsultaEquiposBuscar
export type FiltrosPorCodigo = Respuestas.ConsultaEquiposPorCodigo
export type ListaEquiposBuscados = Respuestas.RespuestaEquiposBuscar
export type ItemEquipoBuscado = NonNullable<ListaEquiposBuscados['items']>[number]
export type FiltrosCalidad = Respuestas.ConsultaCalidadInventario
type FilaCalidadOficina = Respuestas.RespuestaCalidadInventario['por_oficina'][number] & {
  campos_faltantes: { campo: string; faltantes: number }[]
}
export type CalidadInventario = Omit<Respuestas.RespuestaCalidadInventario, 'por_oficina'> & {
  por_oficina: FilaCalidadOficina[]
}
export type EstadoCampoCatalogo = Respuestas.RespuestaCalidadInventarioEstadosCampo
export type EsquemaEquipo = Respuestas.RespuestaCalidadInventarioEsquemaMonitor
export type ConjuntosRespuesta = Respuestas.RespuestaConjuntos
export type Conjunto = NonNullable<ConjuntosRespuesta['items']>[number]
export type FiltrosConjuntos = Respuestas.ConsultaConjuntos
export type SugerenciaNombreConjunto = Respuestas.RespuestaConjuntosSiguienteNombre
export type FiltrosNombreConjunto = Respuestas.ConsultaConjuntosSiguienteNombre
export type EstadoLote = Respuestas.RespuestaImportacion
export type LoteImportacion = Respuestas.RespuestaImportacion['items'][number]
export type FiltrosImportacion = Respuestas.ConsultaImportacion

/* ══ Campañas ══════════════════════════════════════════════ */

export type CampanasRespuesta = Respuestas.RespuestaCampanas
export type Campana = NonNullable<CampanasRespuesta['items']>[number]
export type CampanaActiva = NonNullable<CampanasRespuesta['campana_activa']>
export type FiltrosItemsCampana = Respuestas.ConsultaCampanasPorcampana_idItems
export type HistoricoCampanas = Respuestas.RespuestaCampanasVersionesHistorico
export type VersionInventario = NonNullable<HistoricoCampanas['items']>[number]

/* ══ Organización ══════════════════════════════════════════ */

export type FiltrosZonas = Respuestas.ConsultaZonas
export type Zona = NonNullable<Respuestas.RespuestaZonas['items']>[number] & { color_indice: number }
export type ZonasRespuesta = Omit<Respuestas.RespuestaZonas, 'items'> & { items: Zona[] }
export type ZonaDetalle = Respuestas.RespuestaZonasPorzona_id & { color_indice: number }
export type FiltrosOficinas = Respuestas.ConsultaOficinas
export type OficinasRespuesta = Respuestas.RespuestaOficinas
export type ItemOficina = OficinasRespuesta['items'][number]
export type Oficina = NonNullable<OficinasRespuesta['items']>[number]
export type OficinaDetalle = Respuestas.RespuestaOficinasPoroficina_id
export type FiltrosUsuarios = Respuestas.ConsultaUsuarios
export type UsuariosRespuesta = Omit<Respuestas.RespuestaUsuarios, 'items'> & { items: UsuarioResumen[] }
export type UsuarioResumen = NonNullable<Respuestas.RespuestaUsuarios['items']>[number] & { tiene_foto?: boolean; administrador_principal?: boolean }
/*
  `tiene_foto` no está en el archivo generado porque se añadió al backend después de
  la última generación. Se declara aquí, como ya se hizo con `MiPerfil`, en vez de
  editar a mano el generado: en cuanto se regenere, el `&` sobra y no rompe nada.
*/
export type UsuarioDetalle = Omit<Respuestas.RespuestaUsuariosPorusuario_id, 'equipos_responsable'> & {
  administrador_principal?: boolean
  /**
   * El archivo generado lo deja como `unknown[]`; aquí se declara lo que el backend
   * devuelve de verdad, como ya se hacía con `MiPerfil`.
   */
  equipos_responsable: {
    id: string
    nombre: string
    tipo: string
    codigo_patrimonial: string | null
    estado?: string
    oficina_nombre?: string | null
    conjunto_nombre?: string | null
    completitud?: number
  }[]
  tiene_foto?: boolean
}
export type FiltrosCompaneros = Respuestas.ConsultaUsuariosCompaneros
/**
 * Compañeros de la oficina.
 *
 * Con sesión de administrador la lista viene vacía (no hay oficina asignada),
 * así que el tipo se toma de la respuesta con sesión de usuario, que sí trae la
 * forma observada.
 */
export type CompanerosRespuesta = Respuestas.RespuestaUsuarioUsuariosCompaneros
export type Companero = NonNullable<CompanerosRespuesta['items']>[number]
export type FiltrosBuscarUsuario = Respuestas.ConsultaUsuariosBuscar
export type BuscarUsuarioRespuesta = Respuestas.RespuestaUsuariosBuscar
export type PersonaBuscada = NonNullable<BuscarUsuarioRespuesta['items']>[number]

/* ══ Equipo TI ═════════════════════════════════════════════ */

type IdentidadTI = Pick<UsuarioResumen, 'email' | 'telefono' | 'anexo' | 'cargo' | 'oficina_nombre' | 'oficina_id' | 'zona_id' | 'zona_nombre' | 'rol' | 'tiene_foto'>
export type PanelEquipo = Omit<Respuestas.RespuestaEquipoTiPanel, 'items'> & {
  items: (Respuestas.RespuestaEquipoTiPanel['items'][number] & IdentidadTI)[]
}
export type ItemPanelEquipo = NonNullable<PanelEquipo['items']>[number]
export type TecnicosRespuesta = { items: (Respuestas.RespuestaEquipoTiTecnicos['items'][number] & IdentidadTI)[] }
export type TecnicoResumen = NonNullable<TecnicosRespuesta['items']>[number]
export type TecnicoDetalle = Respuestas.RespuestaEquipoTiPortecnico_id & { tiene_foto?: boolean }
export type FiltrosCalendario = Respuestas.ConsultaEquipoTiCalendario
export type CalendarioEquipo = Omit<Respuestas.RespuestaEquipoTiCalendario, 'items'> & {
  items: (Omit<Respuestas.RespuestaEquipoTiCalendario['items'][number], 'ausencia'> & {
    ausencia: string | null; horas_disponibles: number; carga_pendiente: number; vencimientos: number
  })[]
}
export type AusenciasRespuesta = Respuestas.RespuestaAusencias
export type Ausencia = NonNullable<AusenciasRespuesta['items']>[number] & { tecnico_nombre?: string }
export type FiltrosAusencias = Respuestas.ConsultaAusencias
export type MiHorarioPermiso = Respuestas.RespuestaEquipoTiMiHorarioPermiso

/* ══ Análisis e IA ═════════════════════════════════════════ */

export type ResumenAnalitica = Respuestas.RespuestaAnaliticaResumen
export type FiltrosAnalitica = Respuestas.ConsultaAnaliticaPanel
export type PanelAnalitica = Respuestas.RespuestaAnaliticaPanel & {
  ranking_conjuntos?: { items: { id: string; nombre: string; oficina: string; oficina_id: string | null; responsable: string; responsable_id: string | null; total: number; programas: number; abiertos: number }[] }
}
export type PrediccionEquipos = Respuestas.RespuestaAnaliticaEquiposPrediccion
export type PreguntasAsistente = Respuestas.RespuestaIaAsistentePreguntas
export type Conversaciones = { items: { id: string; titulo: string; actualizado_en?: string }[] }
export type Conversacion = NonNullable<Conversaciones['items']>[number]

/* ══ Base de conocimiento ══════════════════════════════════ */

export type FiltrosArticulos = Respuestas.ConsultaKbArticulos & { visibilidad?: 'todos' | 'equipo_ti' | '' }
export type ArticulosRespuesta = Omit<Respuestas.RespuestaKbArticulos, 'items'> & { items: (NonNullable<Respuestas.RespuestaKbArticulos['items']>[number] & { visibilidad?: 'todos' | 'equipo_ti'; me_gusta?: number })[] }
export type ArticuloKb = Envoltura<ArticuloResumen>
export type ArticuloResumen = NonNullable<ArticulosRespuesta['items']>[number]
export type ArticuloKbDetalle = Respuestas.RespuestaKbArticulosPorarticulo_id & { visibilidad?: 'todos' | 'equipo_ti'; me_gusta?: number; mi_valoracion?: boolean | null }
export type CategoriasRespuesta = Respuestas.RespuestaKbCategorias
export type RespuestasRapidasRespuesta = Respuestas.RespuestaKbRespuestasRapidas
export type RespuestaRapida = NonNullable<RespuestasRapidasRespuesta['items']>[number]

/* ══ Administración ════════════════════════════════════════ */

export type FiltrosAuditoria = Respuestas.ConsultaAuditoria
export type AuditoriaRespuesta = Respuestas.RespuestaAuditoria
export type RegistroAuditoria = NonNullable<AuditoriaRespuesta['items']>[number]
export type MatrizPermisos = Respuestas.RespuestaPermisosMatriz
export type PermisosTecnicos = Respuestas.RespuestaPermisosTecnicos
export type PanelConfiguracion = Respuestas.RespuestaConfiguracion
export type CatalogosRespuesta = Respuestas.RespuestaConfiguracionCatalogos
export type CatalogosConfiguracion = CatalogosRespuesta['catalogos']
export type ItemCatalogo = { valor: string; etiqueta: string; activo: boolean; orden: number }
export type EstadoIa = Respuestas.RespuestaConfiguracionEstadoIa
export type FeriadosRespuesta = Respuestas.RespuestaConfiguracionFeriados
export type Feriado = NonNullable<FeriadosRespuesta['items']>[number]
export type ExportacionesRespuesta = { items: (Respuestas.RespuestaExportaciones['items'][number] & { alcance?: string })[] }
export type Exportacion = NonNullable<ExportacionesRespuesta['items']>[number]
export type FiltrosNotificaciones = Respuestas.ConsultaNotificaciones
export type NotificacionesRespuesta = Respuestas.RespuestaNotificaciones
export type Notificacion = NonNullable<NotificacionesRespuesta['items']>[number]
export type Notificaciones = NotificacionesRespuesta

/* ══ Cuerpos de petición (sí declarados por la API) ═══════ */

export type CuerpoLogin = Esquemas['Body_login_api_auth_login_post']
export type CuerpoCambiarPassword = Esquemas['CambioPassword']
export type CuerpoAdministradorInicial = Esquemas['AdministradorInicial']
/**
 * Cuerpo del reporte del usuario.
 *
 * Se declara a mano y no desde el esquema porque la API exige dos campos de
 * confirmación (`aceptar_categoria_ia`, `aceptar_prioridad_ia`) que el portal
 * no envía: la persona no acepta sugerencias, simplemente no las hay.
 */
export type CuerpoTicket = Omit<Esquemas['TicketUsuarioCrear'], 'aceptar_categoria_ia' | 'aceptar_prioridad_ia'> & { reporte_para?: 'propio' | 'companero' | 'oficina' }
export type CuerpoTicketManual = Esquemas['TicketManualCrear'] & { sistema_afectado?: string }
export type CuerpoTicketActualizar = Esquemas['TicketActualizar']
export type CuerpoVistaGuardada = Esquemas['VistasGuardadas']
export type CuerpoActivoCrear = Esquemas['ActivoCrear']
export type CuerpoActivoActualizar = Esquemas['ActivoActualizar']
export type CambioMasivo = Esquemas['CambioMasivo']
export type CambioCamposMasivo = Esquemas['CambioCamposMasivo']
export type CambioEstadoCampo = Esquemas['CambioEstadoCampo']
export type CambioResponsable = Esquemas['CambioResponsable']
export type CuerpoConjuntoCrear = Esquemas['ConjuntoCrear']
export type CuerpoConjuntoActualizar = Esquemas['ConjuntoActualizar']
export type CuerpoAsignarTicket = Esquemas['AsignarTicket']
export type CuerpoCambiarEstado = Esquemas['CambiarEstado']
export type CuerpoMensaje = Esquemas['MensajeCrear']
export type CuerpoAusenciaCrear = Esquemas['AusenciaCrear']
export type CuerpoCampanaCrear = Esquemas['CampanaCrear']
export type CuerpoCampanaActualizar = Esquemas['CampanaActualizar']
export type CuerpoImportarCampana = Esquemas['ImportarCampana']
export type CuerpoArticuloCrear = Esquemas['ArticuloCrear']
export type CuerpoArticuloActualizar = Esquemas['ArticuloActualizar']
export type CuerpoFeriado = Esquemas['Feriado']
export type CuerpoExportacion = Esquemas['ExportarSolicitud']
export type CuerpoAplicarPermisos = Esquemas['AplicarPermisosTecnico']
export type HorarioSemanal = Esquemas['HorarioSemanal']
export type CuerpoConfiguracion = Partial<{
  negocio: Esquemas['ConfigRespuesta']
  sla: Esquemas['ConfigSLA']
  ia: Esquemas['ConfigIA']
  notificaciones: Esquemas['ConfigNotificaciones']
}>
export type CuerpoConfigIA = Esquemas['ConfigIA']
export type CuerpoPerfilTecnico = Esquemas['TecnicoPerfilActualizar']
export type CuerpoPreguntaIA = Esquemas['PreguntaIA']
export type CuerpoValorar = Esquemas['ValorarArticulo']

/* ══ Tipos propios del dominio ═════════════════════════════ */

/** Envoltura de guardado: se usa al inventar el mismo patrón en toda la app. */
export type ConItems<T> = { items: T[] }

/** Campo del inventario con el estado que la persona le dio. */
export type EstadoCampo = 'completo' | 'pendiente' | 'no_aplica' | 'no_disponible'
