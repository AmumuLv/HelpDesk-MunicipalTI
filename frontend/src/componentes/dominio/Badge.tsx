/**
 * Badge con color + texto + icono.
 *
 * Es el único lugar donde se pinta un estado. Nunca solo color: siempre color,
 * texto e icono, para que se lea con daltonismo, en impresión y con lector de
 * pantalla.
 */

import { cn } from '../../lib/cn'
import { estadoCampoDe, estadoDe, disponibilidadDe, prioridadDe, slaDe, type DefinicionEstado, type EstadoCampo } from '../../dominio/estados'

const TONOS = {
  primary: 'bg-primary-soft text-primary-strong border-primary-borde',
  success: 'bg-success-soft text-success-strong border-success-borde',
  warning: 'bg-warning-soft text-warning-strong border-warning-borde',
  destructive: 'bg-destructive-soft text-destructive-strong border-destructive-borde',
  ai: 'bg-ai-soft text-ai-strong border-ai-borde',
  info: 'bg-info-soft text-info-strong border-info-borde',
  'info-deep': 'bg-info-deep-soft text-info-deep-strong border-info-borde',
  muted: 'bg-muted text-muted-foreground border-border',
} as const

/**
 * Tonos **rellenos**: el color fuerte va de fondo.
 *
 * En una tabla con quince filas, dos pastillas claras del mismo tamaño se leen
 * como la misma: «Operativo» y «Dado de baja» solo se distinguían por un matiz
 * del fondo. Rellenando, cada estado es una mancha distinta.
 *
 * El relleno usa el token `-fuerte`, que es oscuro en el tema claro y claro en el
 * oscuro, y el texto es `primary-foreground`: el mismo token que se usa sobre un
 * botón relleno, que ya se probó legible en los dos temas. Así esta tabla no
 * necesita seis pares de tokens nuevos.
 */
const TONOS_FUERTES = {
  primary: 'bg-primary-strong text-primary-foreground border-primary-strong',
  success: 'bg-success-strong text-primary-foreground border-success-strong',
  warning: 'bg-warning-strong text-primary-foreground border-warning-strong',
  destructive: 'bg-destructive-strong text-primary-foreground border-destructive-strong',
  ai: 'bg-ai-strong text-primary-foreground border-ai-strong',
  info: 'bg-info-strong text-primary-foreground border-info-strong',
  'info-deep': 'bg-info-deep-strong text-primary-foreground border-info-deep-strong',
  muted: 'bg-muted-foreground text-primary-foreground border-muted-foreground',
} as const

type Tamano = 'sm' | 'md'

/**
 * Estados que no deberían pasar desapercibidos.
 *
 * Un estado de «puesto vacío» y uno de «no hay nada» son lo mismo en cualquier
 * sitio, pero no en el inventario: un equipo dado de baja es un hecho que hay que
 * ver, no un dato más de una columna. Por eso llevan **otra forma**, no solo otro
 * color: son rectángulos con el texto en versalitas en vez de la pastilla redonda
 * de los estados corrientes. Un escaneo rápido de la columna los separa por la
 * silueta, antes de leer una sola palabra.
 */
function esEstadoCritico(tono: DefinicionEstado['tono']): boolean {
  return tono === 'destructive'
}

export function Badge({
  definicion,
  tamano = 'md',
  conIcono = true,
  destacado = false,
  alerta = false,
  className,
}: {
  definicion: DefinicionEstado
  tamano?: Tamano
  conIcono?: boolean
  /** Rellena el fondo con el color en vez de tintarlo: se ve de un vistazo. */
  destacado?: boolean
  /** Otra forma y texto en versalitas, para los estados que no deben pasar desapercibidos. */
  alerta?: boolean
  className?: string
}) {
  const Icono = definicion.icono
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 border font-semibold whitespace-nowrap',
        // La forma es lo primero que distingue un estado crítico de uno normal,
        // y es lo único que se sigue viendo en una tabla a media columna.
        alerta ? 'rounded-[var(--radius-control)] px-2 py-1 uppercase tracking-wide' : 'rounded-full',
        !alerta && (tamano === 'sm' ? 'px-2 py-0.5 text-2xs' : 'px-2.5 py-1 text-sm'),
        alerta && (tamano === 'sm' ? 'text-2xs' : 'text-xs'),
        destacado ? TONOS_FUERTES[definicion.tono] : TONOS[definicion.tono],
        alerta && destacado && 'border-2 border-primary-foreground/30',
        className,
      )}
      title={definicion.descripcion}
    >
      {conIcono ? <Icono size={tamano === 'sm' || alerta ? 13 : 14} aria-hidden="true" className="shrink-0" /> : null}
      {definicion.texto}
    </span>
  )
}

/** Estado de ticket */
export function EstadoBadge({
  estado,
  tamano,
  className,
}: {
  estado: string | null | undefined
  tamano?: Tamano
  className?: string
}) {
  return <Badge definicion={estadoDe(estado)} tamano={tamano} className={className} />
}

/** Prioridad del ticket */
export function PrioridadBadge({
  prioridad,
  tamano,
  className,
}: {
  prioridad: string | null | undefined
  tamano?: Tamano
  className?: string
}) {
  return <Badge definicion={prioridadDe(prioridad)} tamano={tamano} className={className} />
}

/**
 * Estado del equipo TI (la etiqueta la calcula la API).
 *
 * Se pinta relleno a propósito: estos estados conviven en la misma columna de la
 * tabla y hay que distinguir «Operativo» de «Dado de baja» sin leerlos. Los que
 * son una baja o una pérdida llevan además forma de alerta, para que se separen
 * por la silueta y no solo por el color.
 */
export function DisponibilidadBadge({
  estado,
  etiqueta,
  tamano,
  destacado = true,
  className,
}: {
  estado: string | null | undefined
  etiqueta?: string | null
  tamano?: Tamano
  destacado?: boolean
  className?: string
}) {
  const definicion = disponibilidadDe(estado, etiqueta)
  return (
    <Badge
      definicion={definicion}
      tamano={tamano}
      destacado={destacado}
      alerta={esEstadoCritico(definicion.tono)}
      className={className}
    />
  )
}

/** Estado de un campo del inventario: No aplica ≠ vacío */
export function EstadoCampoBadge({
  estado,
  tamano,
  className,
}: {
  estado: EstadoCampo | string | null | undefined
  tamano?: Tamano
  className?: string
}) {
  return <Badge definicion={estadoCampoDe(estado)} tamano={tamano} className={className} />
}

/** SLA con su barra de tiempo restante */
export function SlaBadge({
  estado,
  minutos,
  minutosTranscurridos,
  activo,
  modo,
  tamano,
  className,
}: {
  estado: string | null | undefined
  /** Acepta `unknown` porque el backend lo envía sin tipo declarado. */
  minutos?: number | null | unknown
  /** Minutos de trabajo que tardó el caso. Solo para casos ya cerrados. */
  minutosTranscurridos?: number | null | unknown
  /** `false` cuando el caso está cerrado: entonces lo que se enseña es cuánto tardó. */
  activo?: boolean
  /**
   * Qué plazo es el que se está mostrando: `responder` mientras nadie ha
   * tomado el caso, `resolver` en cuanto lo toma.
   *
   * No se deduce de la insignia: los dos plazos existen a la vez y cambia cuál
   * corre según el estado. Sin decir cuál es, «Quedan 4 h» no dice si es para
   * cogerlo o para arreglarlo, que es justo la diferencia entre las dos líneas.
   */
  modo?: string | null
  tamano?: Tamano
  className?: string
}) {
  const definicion = slaDe(estado)
  const cerrado = activo === false
  const valor = typeof minutos === 'number' ? minutos : null
  const gastado = typeof minutosTranscurridos === 'number' ? minutosTranscurridos : null
  const pie =
    cerrado && gastado !== null
      ? textoDuracion(gastado)
      : valor !== null
        ? `${modo === 'responder' ? 'Para cogerlo: ' : ''}${textoTiempo(valor)}`
        : null
  return (
    <span className={cn('inline-flex flex-col items-start gap-0.5', className)}>
      <Badge definicion={definicion} tamano={tamano} />
      {pie ? <span className="text-2xs text-muted-foreground">{pie}</span> : null}
    </span>
  )
}

/**
 * El tiempo que queda, en la unidad más grande que quepa.
 *
 * Antes salía siempre en horas y minutos: «116 h 5 min restantes». Con cuatro
 * cifras y la palabra «restantes» la columna se cortaba y no se leía nada útil.
 * Ahora se cuenta en días en cuanto hay un día entero, porque es como se habla
 * de un plazo: «quedan 2 días», no «quedan 48 h».
 *
 * Los minutos son **de trabajo**, no de reloj: el plazo son 16 horas de labor y
 * se cuentan en horas de labor, aunque el caso siga abierto el fin de semana. Por
 * eso un caso creado un viernes puede decir «Quedan 8 h» un lunes, y no hay
 * ningún error: el fin de semana no cuenta ni en un lado ni en el otro.
 */
function textoTiempo(minutos: number): string {
  const absoluto = Math.abs(minutos)
  // `<= 0` y no `< 0`: el backend marca «vencido» cuando el resto llega a cero, así
  // que cero ya es vencido. Y un caso que venció el viernes y se mira el sábado
  // tiene cero minutos de retraso —el fin de semana no se cuenta—: decir «0 min»
  // sería literal y no diría nada.
  if (minutos <= 0) {
    if (absoluto < 60) return 'Plazo agotado'
    const dias = Math.floor(absoluto / (60 * 24))
    return dias > 0
      ? `Se pasó hace ${plural(dias, 'día')}`
      : `Se pasó hace ${plural(Math.floor(absoluto / 60), 'hora')}`
  }
  if (absoluto < 60) return `${minutos} min`
  const dias = Math.floor(absoluto / (60 * 24))
  const horas = Math.floor(absoluto / 60) % 24
  if (dias > 0) return `Quedan ${dias} ${dias === 1 ? 'día' : 'días'}${horas ? ` y ${horas} h` : ''}`
  const resto = absoluto % 60
  return resto
    ? `Quedan ${Math.floor(absoluto / 60)} h ${resto} min`
    : `Quedan ${plural(Math.floor(absoluto / 60), 'hora')}`
}

/** Tiempo empleado por un caso ya cerrado, en la misma línea de siempre. */
function textoDuracion(minutos: number): string {
  if (minutos < 60) return `Se cerró en ${minutos} min`
  const horas = Math.floor(minutos / 60)
  const dias = Math.floor(horas / 24)
  if (dias > 0) return `Se cerró en ${plural(dias, 'día')}`
  const resto = minutos % 60
  return resto ? `Se cerró en ${horas} h ${resto} min` : `Se cerró en ${plural(horas, 'hora')}`
}

/** «1 día» / «3 días»: el plural no se escribe a mano en cinco sitios. */
function plural(cantidad: number, palabra: string): string {
  return `${cantidad} ${palabra}${cantidad === 1 ? '' : 's'}`
}

/** Confianza de la IA: siempre con el color teal y el rótulo "IA" */
export function ConfianzaIABadge({
  confianza,
  suficiente,
  className,
}: {
  confianza: number | null | undefined
  /** Si la API dice que no hay confianza suficiente, no se muestra el número. */
  suficiente?: boolean
  className?: string
}) {
  if (confianza === null || confianza === undefined) return null
  if (suficiente === false) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-2xs font-semibold text-muted-foreground',
          className,
        )}
        title="La IA no tiene confianza suficiente en esta predicción"
      >
        IA · confianza baja
      </span>
    )
  }
  const porcentaje = Math.round(confianza * 100)
  const tono = porcentaje >= 70 ? 'success' : porcentaje >= 40 ? 'warning' : 'destructive'
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-semibold',
        TONOS[tono],
        className,
      )}
      title={`La IA está ${porcentaje}% segura de esta clasificación`}
    >
      <span className="text-ai-strong" aria-hidden="true">
        IA
      </span>
      {porcentaje}%
    </span>
  )
}

/**
 * Completitud del inventario: una barra y la cifra.
 *
 * Antes era una pastilla con un número. El problema no era el color: es que
 * «50%» no dice nada sobre la forma de la columna. Con la barra, de un vistazo
 * se ve cuántos equipos están completos, cuántos van por la mitad y cuántos están
 * vacíos, sin leer ni un número.
 *
 * La escala tiene cuatro pasos y no dos: un inventario al 90 % no es lo mismo que
 * uno al 50 %, y con dos tonos parecían iguales.
 */
export function CompletitudBadge({
  porcentaje,
  faltantes,
  className,
}: {
  porcentaje: number
  faltantes?: number
  className?: string
}) {
  const valor = Math.max(0, Math.min(100, Math.round(porcentaje)))
  const tono = valor >= 100 ? 'success' : valor >= 70 ? 'info' : valor >= 30 ? 'warning' : 'destructive'
  return (
    <span
      className={cn('inline-flex items-center gap-2', className)}
      title={
        valor >= 100
          ? 'Todos los datos esperados de este equipo están escritos'
          : `Faltan ${faltantes ?? 0} datos de los que este tipo de equipo espera`
      }
    >
      <span aria-hidden="true" className="block h-1.5 w-10 shrink-0 overflow-hidden rounded-full bg-muted">
        <span
          className={cn('block h-full rounded-full', TONOS_FUERTES[tono].split(' ')[0])}
          style={{ width: `${Math.max(valor, 4)}%` }}
        />
      </span>
      <span className={cn('text-2xs font-semibold whitespace-nowrap', TONOS[tono].split(' ')[1])}>
        {valor >= 100 ? 'Completo' : `${valor}%`}
      </span>
    </span>
  )
}

/** Etiqueta de IA genérica, para marcar contenido generado por IA */
export function EtiquetaIA({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border border-ai/25 bg-ai-soft px-2 py-0.5 text-2xs font-semibold text-ai-strong',
        className,
      )}
    >
      IA
    </span>
  )
}
