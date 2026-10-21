/**
 * Stepper: los pasos de un flujo.
 *
 * Se usa en el reporte de problema (dos pasos) y en la importación de Excel.
 * Muestra en qué paso se está, cuántos faltan y permite volver a un paso ya
 * hecho, pero no saltar a uno que necesita lo anterior.
 */

import { Check } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export type Paso = {
  clave: string
  titulo: string
  descripcion?: string
  /** Marca el paso como alcanzado; el que se puede abrir. */
  hecho?: boolean
}

export function Stepper({
  pasos,
  actual,
  alIr,
  /** Último paso alcanzado, por su clave. Permite volver a él desde uno posterior. */
  alcanzado,
}: {
  pasos: Paso[]
  actual: string
  /** Si no se pasa, los pasos hechos no son pulsables. */
  alIr?: (clave: string) => void
  /**
   * Clave del último paso que se completó de verdad.
   *
   * Sin esto, al retroceder a un paso anterior los de delante quedaban
   * deshabilitados —«no se puede saltar a un paso que necesita el anterior»— y
   * volver atrás era una trampa sin salida. La importación tiene tres pasos y
   * al llegar al resultado se puede volver al archivo: desde ahí el paso
   * «Resultado» seguía apagado y no había forma de regresar.
   */
  alcanzado?: string
}) {
  const indiceActual = Math.max(
    0,
    pasos.findIndex((paso) => paso.clave === actual),
  )
  const indiceAlcanzado = alcanzado
    ? pasos.findIndex((paso) => paso.clave === alcanzado)
    : indiceActual

  return (
    <nav aria-label="Pasos del proceso">
      {/* Siempre en una línea: apilados en móvil ocupaban más alto que el
          propio formulario y el número del paso se leía dos veces. */}
      <ol className="flex items-center gap-1 sm:gap-2">
        {pasos.map((paso, indice) => {
          const activo = indice === indiceActual
          // Un paso está hecho si se quedó atrás **o** si se sabe que se llegó a
          // él. Lo segundo es lo que permite volver: sin él, al retroceder, los
          // pasos de delante se apagan y no hay manera de regresar.
          const completado = indice < indiceActual || indice <= indiceAlcanzado

          return (
            <li key={paso.clave} className="flex min-w-0 flex-1 items-center gap-1 sm:gap-2">
              {/* Los pasos ya hechos se pueden volver a abrir; los futuros no */}
              <button
                type="button"
                disabled={!alIr || (!completado && !activo)}
                onClick={() => alIr?.(paso.clave)}
                aria-current={activo ? 'step' : undefined}
                className="flex min-w-0 flex-1 items-center gap-2 rounded text-left disabled:cursor-default"
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'flex size-7 shrink-0 items-center justify-center rounded-full border-2 text-2xs font-bold',
                    completado && 'border-success bg-success text-primary-foreground',
                    activo && 'border-primary bg-primary-boton text-primary-foreground',
                    !activo && !completado && 'border-border bg-surface text-muted-foreground',
                  )}
                >
                  {completado ? <Check size={14} /> : indice + 1}
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      'block truncate text-sm font-semibold',
                      !activo && !completado && 'text-muted-foreground',
                    )}
                  >
                    {paso.titulo}
                  </span>
                  {/* La descripción no cabe en móvil: la lleva el pie del flujo */}
                  {paso.descripcion ? (
                    <span className="hidden truncate text-2xs text-muted-foreground sm:block">
                      {paso.descripcion}
                    </span>
                  ) : null}
                </span>
              </button>

              {indice < pasos.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn('mx-1 hidden h-0.5 flex-1 sm:block', indice < Math.max(indiceActual, indiceAlcanzado) ? 'bg-success' : 'bg-border')}
                />
              ) : null}
            </li>
          )
        })}
      </ol>
      <p className="solo-lectores">
        Paso {indiceActual + 1} de {pasos.length}: {pasos[indiceActual]?.titulo}
      </p>
    </nav>
  )
}

/** Pie de los flujos por pasos: atrás, adelante y enviar. */
export function PiePasos({
  paso,
  total,
  alAtras,
  alAdelante,
  alEnviar,
  textoEnviar = 'Enviar',
  enviando,
  puedeAdelantar = true,
  puedeEnviar = true,
  ayuda,
}: {
  paso: number
  total: number
  alAtras?: () => void
  alAdelante?: () => void
  alEnviar?: () => void
  textoEnviar?: string
  enviando?: boolean
  puedeAdelantar?: boolean
  puedeEnviar?: boolean
  ayuda?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-2 border-t border-border bg-surface p-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-muted-foreground">
        Paso {paso} de {total}
        {ayuda ? <span className="ml-2">{ayuda}</span> : null}
      </p>
      <div className="flex flex-wrap gap-2">
        {alAtras ? (
          <button
            type="button"
            onClick={alAtras}
            className="h-[var(--spacing-control)] rounded-[var(--radius-control)] border border-border bg-surface px-3.5 text-sm font-semibold hover:bg-muted"
          >
            Atrás
          </button>
        ) : null}
        {alAdelante && !alEnviar ? (
          <button
            type="button"
            onClick={alAdelante}
            disabled={!puedeAdelantar}
            className="h-[var(--spacing-control)] rounded-[var(--radius-control)] bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary-deep disabled:opacity-50"
          >
            Continuar
          </button>
        ) : null}
        {alEnviar ? (
          <button
            type="button"
            onClick={alEnviar}
            disabled={!puedeEnviar}
            className="h-[var(--spacing-control)] rounded-[var(--radius-control)] bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary-deep disabled:opacity-50"
          >
            {enviando ? 'Enviando…' : textoEnviar}
          </button>
        ) : null}
      </div>
    </div>
  )
}