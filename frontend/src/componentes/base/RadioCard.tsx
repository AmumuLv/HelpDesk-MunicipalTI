/**
 * RadioCard: botones grandes de elección.
 *
 * Se usa cuando las opciones se leen de un vistazo y hay que compararlas:
 * el tipo de problema, para quién es, la urgencia, conjunto o equipo
 * individual. Tocar un toque en móvil.
 */

import { Check } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export type OpcionRadio = {
  valor: string
  titulo: string
  descripcion?: string
  icono?: ReactNode
  /** Contenido extra a la derecha (por ejemplo, un badge). */
  extra?: ReactNode
}

export function RadioCard<T extends string>({
  opciones,
  valor,
  alCambiar,
  etiqueta,
  descripcion,
  columnas = 2,
  className,
}: {
  opciones: OpcionRadio[]
  valor: T | null
  alCambiar: (valor: T) => void
  etiqueta: string
  descripcion?: string
  columnas?: 1 | 2 | 3
  className?: string
}) {
  const clasesColumnas = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  }[columnas]

  return (
    <fieldset className={cn('flex flex-col gap-2', className)}>
      <legend className="text-sm font-semibold">{etiqueta}</legend>
      {descripcion ? <p className="-mt-1 mb-1 text-sm text-muted-foreground">{descripcion}</p> : null}
      <div className={cn('grid gap-3', clasesColumnas)}>
        {opciones.map((opcion) => {
          const activo = valor === opcion.valor
          return (
            <button
              key={opcion.valor}
              type="button"
              onClick={() => alCambiar(opcion.valor as T)}
              aria-pressed={activo}
              className={cn(
                'group relative flex min-h-[var(--spacing-control-touch)] items-start gap-4 p-4 text-left',
                'rounded-[var(--radius-panel)] border bg-surface',
                'transition-colors duration-[var(--transition-ui-slow)]',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                activo
                  ? 'border-accion bg-accion-soft'
                  : 'border-border shadow-panel hover:border-accion/50 hover:bg-muted/40',
              )}
            >
              {opcion.icono ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    'mt-0.5 flex size-12 shrink-0 items-center justify-center rounded-[var(--radius-control)] transition-colors duration-[var(--transition-ui)]',
                    activo
                      ? 'bg-accion text-primary-foreground'
                      : 'bg-muted text-muted-foreground group-hover:text-accion group-hover:bg-accion-soft',
                  )}
                >
                  {opcion.icono}
                </span>
              ) : null}
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className={cn('text-base font-semibold transition-colors', activo ? 'text-accion-strong' : 'text-foreground')}>
                    {opcion.titulo}
                  </span>
                  {activo ? (
                    <span className="flex items-center justify-center rounded-full bg-accion p-0.5 text-primary-foreground">
                      <Check size={14} strokeWidth={3} aria-label="seleccionado" />
                    </span>
                  ) : null}
                </span>
                {opcion.descripcion ? (
                  <span className="mt-1 block text-sm text-muted-foreground leading-snug">{opcion.descripcion}</span>
                ) : null}
              </span>
              {opcion.extra ? <span className="shrink-0">{opcion.extra}</span> : null}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
