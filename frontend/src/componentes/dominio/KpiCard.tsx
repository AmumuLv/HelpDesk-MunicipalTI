/**
 * Indicadores: tarjeta de cifra con su contexto.
 *
 * Un KPI sin contexto es un número suelto. Cada tarjeta dice qué mide, en qué
 * periodo y, si la API trae comparación, si sube o baja. Nunca inventa la
 * variación: si no viene, no se muestra flecha.
 */

import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { numero, porcentaje, variacion } from '../../dominio/formato'

type Tono = 'neutro' | 'primario' | 'exito' | 'aviso' | 'peligro' | 'ia'

const TONOS: Record<Tono, string> = {
  neutro: 'text-foreground',
  primario: 'text-primary-strong',
  exito: 'text-success-strong',
  aviso: 'text-warning-strong',
  peligro: 'text-destructive-strong',
  ia: 'text-ai-strong',
}

export function KpiCard({
  etiqueta,
  valor,
  detalle,
  periodo,
  variacion: cambio,
  /** `true` si bajar es una buena noticia (por ejemplo, incidencias). */
  menosEsMejor,
  tono = 'neutro',
  icono,
  accion,
  cargando,
  sufijo,
}: {
  etiqueta: string
  valor: number | string | null | undefined
  detalle?: ReactNode
  periodo?: string
  variacion?: number | null
  menosEsMejor?: boolean
  tono?: Tono
  icono?: ReactNode
  accion?: ReactNode
  cargando?: boolean
  /** Por ejemplo "%" o "días". */
  sufijo?: string
}) {
  if (cargando) {
    return (
      <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-4 shadow-tarjeta">
        <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        <div className="mt-3 h-8 w-16 animate-pulse rounded bg-muted" />
      </div>
    )
  }

  const texto = typeof valor === 'number' ? numero(valor) : (valor ?? '—')
  const tieneCambio = cambio !== undefined && cambio !== null

  /*
    La tarjeta levanta y se marca al pasar el ratón por encima.

    Antes llevaba `group-hover:shadow-panel` **en sí misma**, y eso no hace nada:
    `group-hover` solo funciona si el elemento cuelga de un ancestro marcado como
    `group`, y la tarjeta no colga de ninguno. El resultado era que no había ninguna
    señal de dónde estaba el puntero: seis tarjetas iguales y ninguna decía «aquí».
    Ahora reaction al pasar, con borde de color y un pelín de desplazamiento, más
    la etiqueta y el icono que cambian de tinta.
  */
  return (
    <div
      className={cn(
        'group flex h-full min-h-[104px] flex-col justify-between gap-2.5 rounded-[var(--radius-panel)] border bg-surface p-4 shadow-tarjeta',
        'transition-[transform,box-shadow,border-color] duration-[var(--transition-ui)]',
        'hover:-translate-y-0.5 hover:border-[var(--borde-seleccion)] hover:shadow-panel',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground transition-colors group-hover:text-foreground">{etiqueta}</p>
        {icono ? (
          <span
            aria-hidden="true"
            className={cn('flex size-8 shrink-0 items-center justify-center rounded-lg bg-current/5', tono === 'neutro' ? 'text-info-strong bg-info-soft' : TONOS[tono])}
          >
            {icono}
          </span>
        ) : null}
      </div>

      <div className="flex items-end justify-between gap-2">
        <p className={cn('text-3xl leading-none font-bold tracking-tight', TONOS[tono])}>
          {texto}
          {sufijo && texto !== '—' ? <span className="ml-0.5 text-lg font-semibold">{sufijo}</span> : null}
        </p>
        {tieneCambio ? <Cambio valor={cambio} menosEsMejor={menosEsMejor} /> : null}
      </div>

      {detalle ? <p className="text-sm text-muted-foreground">{detalle}</p> : null}
      {periodo ? <p className="text-2xs text-muted-foreground">{periodo}</p> : null}
      {accion ? <div className="pt-0.5">{accion}</div> : null}
    </div>
  )
}

/** Flecha de variación con su color, su icono y su texto: nunca solo color. */
export function Cambio({ valor, menosEsMejor }: { valor: number; menosEsMejor?: boolean }) {
  if (valor === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-2xs font-semibold text-muted-foreground">
        <Minus size={12} aria-hidden="true" />
        igual
      </span>
    )
  }
  const sube = valor > 0
  const bueno = menosEsMejor ? !sube : sube
  const Icono = sube ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-2xs font-semibold',
        bueno ? 'border-success/25 bg-success-soft text-success-strong' : 'border-warning/25 bg-warning-soft text-warning-strong',
      )}
      title={`${sube ? 'Aumentó' : 'Disminuyó'} ${variacion(Math.abs(valor))} respecto al periodo anterior`}
    >
      <Icono size={12} aria-hidden="true" />
      {variacion(Math.abs(valor))}
    </span>
  )
}

/** Tarjeta de porcentaje con barra: para completitud del inventario y SLA. */
export function KpiPorcentaje({
  etiqueta,
  porcentaje: valor,
  detalle,
  tono = 'primario',
  cargando,
}: {
  etiqueta: string
  porcentaje: number | null | undefined
  detalle?: ReactNode
  tono?: Tono
  cargando?: boolean
}) {
  const ancho = Math.max(0, Math.min(100, valor ?? 0))
  const color = {
    neutro: 'bg-chart-neutral',
    primario: 'bg-chart-real',
    exito: 'bg-chart-ok',
    aviso: 'bg-chart-warn',
    peligro: 'bg-chart-critical',
    ia: 'bg-chart-ai',
  }[tono]

  if (cargando) {
    return (
      <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-4 shadow-tarjeta">
        <div className="h-3 w-24 animate-pulse rounded bg-muted" />
        <div className="mt-3 h-2 w-full animate-pulse rounded bg-muted" />
      </div>
    )
  }

  return (
    <div
      className={cn(
        'group flex h-full min-h-[104px] flex-col gap-2.5 rounded-[var(--radius-panel)] border bg-surface p-4 shadow-tarjeta',
        'transition-[transform,box-shadow,border-color] duration-[var(--transition-ui)]',
        'hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-panel',
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground transition-colors group-hover:text-foreground">{etiqueta}</p>
        <p className={cn('text-2xl font-bold', TONOS[tono])}>{porcentaje(valor, 0)}</p>
      </div>
      {/* La barra lleva el valor como texto para quien no ve el color */}
      <div
        role="meter"
        aria-valuenow={Math.round(ancho)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={etiqueta}
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div className={cn('h-full rounded-full', color)} style={{ width: `${ancho}%` }} />
      </div>
      {detalle ? <p className="text-sm text-muted-foreground">{detalle}</p> : null}
    </div>
  )
}
