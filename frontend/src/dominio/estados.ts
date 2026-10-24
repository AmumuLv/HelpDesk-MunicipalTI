/**
 * Estados, prioridades, disponibilidad y SLA: la única fuente de verdad.
 *
 * Nadie escribe el nombre de un estado en una pantalla. Además del color,
 * cada estado trae texto e icono: nunca se comunica solo con color.
 */

import {
  Archive,
  ArrowDown,
  ArrowUp,
  CalendarOff,
  CheckCircle2,
  CircleAlert,
  CircleDot,
  Clock3,
  Equal,
  Flame,
  Inbox,
  Moon,
  OctagonAlert,
  Pause,
  Plane,
  PowerOff,
  Timer,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/** Par de color de estado: fondo suave + texto fuerte (contraste AA). */
export type Tono = 'primary' | 'success' | 'warning' | 'destructive' | 'ai' | 'muted' | 'info' | 'info-deep'

export type DefinicionEstado = {
  clave: string
  texto: string
  tono: Tono
  icono: LucideIcon
  /** Texto para lectores de pantalla cuando el icono no basta. */
  descripcion: string
}

/* ── Estados de ticket ─────────────────────────────────────── */

export const ESTADOS: Record<string, DefinicionEstado> = {
  nuevo: {
    clave: 'nuevo',
    texto: 'Nuevo',
    tono: 'info',
    icono: Inbox,
    descripcion: 'Nadie lo ha tomado todavía',
  },
  en_progreso: {
    clave: 'en_progreso',
    texto: 'En progreso',
    tono: 'ai',
    icono: Wrench,
    descripcion: 'Un técnico lo está atendiendo ahora',
  },
  en_espera: {
    clave: 'en_espera',
    texto: 'En espera',
    tono: 'warning',
    icono: Pause,
    descripcion: 'Detenido a la espera de algo',
  },
  /*
    No hay estado «resuelto»: existió hasta la versión 4 y era redundante con
    «cerrado». Los dos significaban «el problema está solucionado», los dos eran
    finales y los dos se podían reabrir, así que eran dos nombres para lo mismo y
    dos pasos donde bastaba uno. En la práctica «resuelto» se quedaba ahi sin que
    nadie lo cerrara.

    Tampoco hay estado «asignado»: existió hasta la versión 5 y separaba «ya
    tiene técnico» de «el técnico lo está tocando». No se notaba en ninguna parte
    —el contador que medía esa diferencia no se mostraba en ninguna pantalla— y
    costaba un clic: asignar dejaba el ticket ahí y pasarlo a «en progreso»
    exigía un segundo paso que nadie daba. Trece tickets se quedaron parados en
    «asignado» y ni uno pasó a «en progreso». Ahora asignar un técnico **es** poner
    el caso en progreso.

    Se quedan **cuatro estados**: tres abiertos —nuevo, en progreso y en espera— y
    uno final, «cerrado». Cerrado no es «no se vuelve a tocar»: se puede reabrir,
    igual que antes, para cuando la solución no sirva.
  */
  cerrado: {
    clave: 'cerrado',
    texto: 'Cerrado',
    tono: 'muted',
    icono: Archive,
    descripcion: 'El problema está solucionado y el caso archivado; se puede reabrir si vuelve a fallar',
  },
}

export const TRANSICIONES_TICKET: Record<string, readonly string[]> = {
  nuevo: ['en_progreso', 'en_espera', 'cerrado'],
  en_progreso: ['en_espera', 'cerrado', 'nuevo'],
  en_espera: ['en_progreso', 'cerrado', 'nuevo'],
  cerrado: ['en_progreso'],
}

export const ESTADO_DESCONOCIDO: DefinicionEstado = {
  clave: 'desconocido',
  texto: 'Sin estado',
  tono: 'muted',
  icono: CircleDot,
  descripcion: 'Estado no reconocido',
}

/**
 * Normaliza para buscar en un catálogo: minúsculas, sin tildes, y espacios o guiones
 * convertidos en guion bajo.
 *
 * Hace falta porque la base guarda los estados **como los escribe el Excel** —
 * «Operativo», «En reparación»— y los catálogos están en minúsculas con guion bajo
 * (`operativo`, `en_reparacion`). Sin esto, `estadoDe('Operativo')` no encontraba nada
 * y caía en «Estado no reconocido»: todas las insignias de estado de la ficha de
 * oficina salían **en gris**, cuando en Inventario el mismo estado salía en verde.
 */
function claveNormalizada(clave: string): string {
  return clave
    .trim()
    .toLocaleLowerCase('es')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[\s-]+/g, '_')
}

export function estadoDe(clave: string | null | undefined): DefinicionEstado {
  if (!clave) return ESTADO_DESCONOCIDO
  return (
    ESTADOS[clave] ??
    ESTADOS[claveNormalizada(clave)] ??
    /*
      Los equipos tienen su propio vocabulario —`operativo`, `dado_de_baja`— y viven en
      `DISPONIBILIDADES`, no en `ESTADOS`. Antes, si una pantalla pintaba el estado de
      un equipo con `estadoDe` (que es lo que hace `EstadoBadge`), caía siempre en «Sin
      estado» y salía **gris**: el mismo equipo aparecía verde en Inventario y gris en
      su propia oficina, sin que nada fallara. Se busca también aquí para que ningún
      valor conocido acabe en gris por hablar de su catálogo equivocado.
    */
    DISPONIBILIDADES[clave] ??
    DISPONIBILIDADES[claveNormalizada(clave)] ?? {
      ...ESTADO_DESCONOCIDO,
      clave,
      // Lo que se ve es lo que vino, no la clave normalizada: si alguien escribió
      // «FUNDIDO», en pantalla tiene que leerse «FUNDIDO».
      texto: clave.replace(/_/g, ' '),
    }
  )
}

/* ── Prioridades ───────────────────────────────────────────── */

export const PRIORIDADES: Record<string, DefinicionEstado> = {
  baja: {
    clave: 'baja',
    texto: 'Baja',
    tono: 'muted',
    icono: ArrowDown,
    descripcion: 'No detiene el trabajo',
  },
  media: {
    clave: 'media',
    texto: 'Media',
    tono: 'primary',
    icono: Equal,
    descripcion: 'Conviene atenderlo pronto',
  },
  alta: {
    clave: 'alta',
    texto: 'Alta',
    tono: 'warning',
    icono: ArrowUp,
    descripcion: 'Está frenando a la persona',
  },
  critica: {
    clave: 'critica',
    texto: 'Crítica',
    tono: 'destructive',
    icono: Flame,
    descripcion: 'La persona no puede trabajar',
  },
}

export function prioridadDe(clave: string | null | undefined): DefinicionEstado {
  if (!clave) return { ...ESTADO_DESCONOCIDO, texto: 'Sin prioridad' }
  return PRIORIDADES[clave] ?? { ...ESTADO_DESCONOCIDO, clave, texto: clave, icono: CircleAlert }
}

/* ── Disponibilidad del equipo TI ───────────────────────────── */

export const DISPONIBILIDADES: Record<string, DefinicionEstado> = {
  disponible: {
    clave: 'disponible',
    texto: 'Disponible',
    tono: 'success',
    icono: CheckCircle2,
    descripcion: 'Puede tomar un ticket ahora',
  },
  ocupado: {
    clave: 'ocupado',
    texto: 'Ocupado',
    tono: 'warning',
    icono: Wrench,
    descripcion: 'Atendiendo un caso',
  },
  en_espera: {
    clave: 'en_espera',
    texto: 'En espera',
    tono: 'primary',
    icono: Pause,
    descripcion: 'Tiene un ticket en cola',
  },
  fuera_de_horario: {
    clave: 'fuera_de_horario',
    texto: 'Fuera de horario',
    tono: 'muted',
    icono: Moon,
    descripcion: 'Su horario ya terminó',
  },
  dia_libre: {
    clave: 'dia_libre',
    texto: 'Día libre',
    tono: 'muted',
    icono: CalendarOff,
    descripcion: 'Hoy no le toca trabajar',
  },
  ausente: {
    clave: 'ausente',
    texto: 'Ausente',
    tono: 'muted',
    icono: Plane,
    descripcion: 'De vacaciones, licencia o permiso',
  },
  operativo: {
    clave: 'operativo',
    texto: 'Operativo',
    tono: 'success',
    icono: CheckCircle2,
    descripcion: 'El equipo está en servicio',
  },
  // El Excel trae su propio vocabulario y no coincide con el catálogo. Sin esto,
  // 38 equipos de la municipalidad salían como «Sin estado», que es lo mismo que
  // un dato corrupto y no dice nada de si el equipo funciona.
  inoperativo: {
    clave: 'inoperativo',
    texto: 'Inoperativo',
    tono: 'destructive',
    icono: PowerOff,
    descripcion: 'El equipo no está en servicio',
  },
  inoperativa: {
    clave: 'inoperativa',
    texto: 'Inoperativo',
    tono: 'destructive',
    icono: PowerOff,
    descripcion: 'El equipo no está en servicio',
  },
  en_reparacion: {
    clave: 'en_reparacion',
    texto: 'En reparación',
    tono: 'warning',
    icono: Wrench,
    descripcion: 'El equipo requiere reparación',
  },
  dado_de_baja: {
    clave: 'dado_de_baja',
    texto: 'Dado de baja',
    tono: 'destructive',
    icono: OctagonAlert,
    descripcion: 'El equipo ya no está en servicio',
  },
  en_almacen: {
    clave: 'en_almacen',
    texto: 'En almacén',
    tono: 'info',
    icono: Archive,
    descripcion: 'El equipo está guardado',
  },
  prestado: {
    clave: 'prestado',
    texto: 'Prestado',
    tono: 'ai',
    icono: ArrowUp,
    descripcion: 'El equipo está asignado temporalmente',
  },
  no_localizado: {
    clave: 'no_localizado',
    texto: 'No localizado',
    tono: 'destructive',
    icono: CircleAlert,
    descripcion: 'No se encontró el equipo',
  },
}

export function disponibilidadDe(clave: string | null | undefined, etiqueta?: string | null): DefinicionEstado {
  if (!clave) return { ...ESTADO_DESCONOCIDO, texto: etiqueta || 'Sin dato' }
  const base = DISPONIBILIDADES[clave] ?? DISPONIBILIDADES[claveNormalizada(clave)]
  if (!base) return { ...ESTADO_DESCONOCIDO, clave, texto: etiqueta || clave }
  return etiqueta ? { ...base, texto: etiqueta } : base
}

/* ── SLA ───────────────────────────────────────────────────── */

/**
 * Estados que emite `sla_service.estado_sla`. La lista es exactamente la del
 * backend (`seguro`, `atencion`, `critico`, `vencido`, `cerrado_en_plazo`,
 * `cerrado_tarde`, `sin_configuracion`): antes la interfaz declaraba `ok`,
 * `por_vencer`, `en_riesgo`, `incumplido` y `en_pausa`, que no coinciden con
 * ninguno, así que toda insignia de SLA caía en «SLA sin dato» y nunca tenía
 * color.
 *
 * `cerrado_en_plazo` y `cerrado_tarde` no existían. El caso cerrado salía como
 * «Cumplido» con una barra casi vacía o como «Vencido» en rojo: en el historial
 * cerrado, un caso ya resuelto con la barra roja y la palabra «vencido» parece
 * una alarma abierta. Cerrado a tiempo y cerrado con retraso son las dos
 * respuestas que serving, y ninguna de las dos es una alarma.
 */
export type EstadoSla =
  | 'seguro'
  | 'atencion'
  | 'critico'
  | 'vencido'
  | 'cerrado_en_plazo'
  | 'cerrado_tarde'
  | 'sin_configuracion'

export const SLA: Record<EstadoSla, DefinicionEstado> = {
  seguro: {
    clave: 'seguro',
    texto: 'En tiempo',
    tono: 'success',
    icono: CheckCircle2,
    descripcion: 'Dentro del tiempo acordado',
  },
  atencion: {
    clave: 'atencion',
    texto: 'Queda poco',
    tono: 'warning',
    icono: CircleAlert,
    descripcion: 'Quedan pocas horas laborables',
  },
  critico: {
    clave: 'critico',
    texto: 'A punto de vencer',
    tono: 'destructive',
    icono: Timer,
    descripcion: 'El tiempo acordado está por agotarse',
  },
  vencido: {
    clave: 'vencido',
    texto: 'Vencido',
    tono: 'destructive',
    icono: OctagonAlert,
    descripcion: 'El tiempo acordado ya pasó',
  },
  cerrado_en_plazo: {
    clave: 'cerrado_en_plazo',
    texto: 'Cerrado a tiempo',
    tono: 'success',
    icono: CheckCircle2,
    descripcion: 'Se cerró dentro del tiempo acordado',
  },
  cerrado_tarde: {
    clave: 'cerrado_tarde',
    texto: 'Cerrado con retraso',
    // Ámbar y no rojo: el caso ya está resuelto, así que esto informa de cuánto
    // tardó, no de que haya algo que resolver. En rojo parecía una alarma abierta
    // dentro del historial cerrado.
    tono: 'warning',
    icono: Clock3,
    descripcion: 'Se cerró después del tiempo acordado',
  },
  sin_configuracion: {
    clave: 'sin_configuracion',
    texto: 'Sin tiempo acordado',
    tono: 'muted',
    icono: Moon,
    descripcion: 'No hay regla de tiempo para este caso',
  },
}

export function slaDe(clave: string | null | undefined): DefinicionEstado {
  if (!clave) return { ...ESTADO_DESCONOCIDO, texto: 'SLA sin dato' }
  return SLA[clave as EstadoSla] ?? { ...ESTADO_DESCONOCIDO, clave, texto: 'SLA sin dato' }
}

/* ── Urgencia de un ticket ──────────────────────────────────── */

export type TonoUrgencia = 'peligro' | 'aviso' | 'exito' | null

/**
 * Tono de la franja lateral de un ticket: rojo, ámbar o verde.
 *
 * Es la única fuente de ese color, como el resto del archivo. El orden importa:
 * un caso ya cerrado se pinta verde aunque llegara crítico, porque lo que hay que
 * ver de un vistazo es qué sigue pidiendo atención.
 */
export function tonoUrgenciaTicket(ticket: {
  estado?: string | null
  prioridad?: string | null
  sla?: { estado?: string | null } | null
  tecnico_id?: string | null
}): TonoUrgencia {
  if (ticket.estado === 'cerrado') return 'exito'
  const sla = ticket.sla?.estado
  if (sla === 'vencido' || sla === 'critico' || ticket.prioridad === 'critica') return 'peligro'
  if (sla === 'atencion' || ticket.prioridad === 'alta' || !ticket.tecnico_id) return 'aviso'
  return null
}

/* ── Campos del inventario ─────────────────────────────────── */

export type EstadoCampo = 'pendiente' | 'no_aplica' | 'no_disponible' | 'completo'

export const ESTADOS_CAMPO: Record<EstadoCampo, DefinicionEstado> = {
  completo: {
    clave: 'completo',
    texto: 'Completo',
    tono: 'success',
    icono: CheckCircle2,
    descripcion: 'El dato está escrito',
  },
  pendiente: {
    clave: 'pendiente',
    texto: 'Pendiente',
    tono: 'warning',
    icono: CircleAlert,
    descripcion: 'Falta escribir este dato',
  },
  no_aplica: {
    clave: 'no_aplica',
    texto: 'No aplica',
    tono: 'muted',
    icono: CircleDot,
    descripcion: 'Este equipo no tiene este dato y no lo tendrá',
  },
  no_disponible: {
    clave: 'no_disponible',
    texto: 'No disponible',
    tono: 'muted',
    icono: CircleDot,
    descripcion: 'Todavía no se sabe el dato',
  },
}

export function estadoCampoDe(clave: string | null | undefined): DefinicionEstado {
  if (!clave) return ESTADOS_CAMPO.pendiente
  return ESTADOS_CAMPO[clave as EstadoCampo] ?? ESTADOS_CAMPO.pendiente
}

/* ── Origen del ticket ─────────────────────────────────────── */

export const ORIGENES: Record<string, { texto: string; explicacion: string }> = {
  usuario: { texto: 'Reportado por la persona', explicacion: 'Lo reportó quien lo suffería' },
  usuario_por_companero: {
    texto: 'Reportado por un compañero',
    explicacion: 'Alguien lo reportó por otra persona',
  },
  tecnico: { texto: 'Registrado por el equipo TI', explicacion: 'Lo detectó el soporte' },
  administrador: { texto: 'Registrado por administración', explicacion: 'Lo registró un administrador' },
  automatico: { texto: 'Creado automáticamente', explicacion: 'Lo generó el sistema' },
}

export function origenDe(clave: string | null | undefined) {
  return ORIGENES[clave ?? ''] ?? { texto: 'Origen sin dato', explicacion: '' }
}

/* ── Urgencia (la que elige el usuario) ────────────────────── */

export const URGENCIAS = [
  {
    clave: 'puede_esperar',
    titulo: 'Puedo esperar',
    descripcion: 'No me detiene el trabajo.',
  },
  { clave: 'me_frena', titulo: 'Me frena', descripcion: 'Me cuesta trabajar, pero puedo continuar.' },
  {
    clave: 'no_puedo_trabajar',
    titulo: 'No puedo trabajar',
    descripcion: 'Me detiene por completo.',
  },
] as const

export type ClaveUrgencia = (typeof URGENCIAS)[number]['clave']
