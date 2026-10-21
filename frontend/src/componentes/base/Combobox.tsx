/**
 * Combobox: búsqueda con sugerencias y escritura libre.
 *
 * El usuario elige de una lista ordenada por frecuencia real del inventario o
 * escribe un valor nuevo. Lo usan los campos del equipo (marca → modelo) y los
 * buscadores de personas.
 *
 * Construido sobre Radix Popover para tener foco atrapado, roles correctos y
 * navegación por teclado sin reescribirla.
 */

import * as Popover from '@radix-ui/react-popover'
import { Check, ChevronsUpDown, X } from 'lucide-react'
import { useMemo, useRef, useState, type ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { numero } from '../../dominio/formato'

export type SugerenciaCombobox = {
  valor: string
  /** Texto secundario: por ejemplo "HP · 12 veces escrito". */
  detalle?: string | null
  /** Frecuencia real, usada para ordenar. */
  frecuencia?: number
}

export function Combobox({
  etiqueta,
  sugerencias,
  valor,
  alCambiar,
  placeholder = 'Escribe o elige…',
  ayuda,
  error,
  requerido,
  vacio = 'Sin sugerencias todavía',
  disabled,
  className,
  /** Texto de la etiqueta del botón cuando no hay valor. */
  sinSeleccion = 'Ninguno',
  onBuscar,
  ancho = 'w-full',
}: {
  etiqueta: string
  sugerencias: SugerenciaCombobox[]
  valor: string | null
  alCambiar: (valor: string | null) => void
  placeholder?: string
  ayuda?: ReactNode
  error?: string
  requerido?: boolean
  vacio?: string
  disabled?: boolean
  className?: string
  sinSeleccion?: string
  /** Si se envía, la lista se pide al servidor mientras se escribe. */
  onBuscar?: (texto: string) => void
  ancho?: string
}) {
  const [abierto, setAbierto] = useState(false)
  const [texto, setTexto] = useState('')
  const boton = useRef<HTMLButtonElement>(null)

  const filtradas = useMemo(() => {
    const limpio = texto.trim().toLowerCase()
    const base = limpio ? sugerencias.filter((s) => s.valor.toLowerCase().includes(limpio)) : sugerencias
    // Orden por frecuencia real: lo que más se usa, primero
    return [...base].sort((a, b) => (b.frecuencia ?? 0) - (a.frecuencia ?? 0)).slice(0, 50)
  }, [sugerencias, texto])

  const escribir = (nuevo: string) => {
    setTexto(nuevo)
    alCambiar(nuevo.trim() || null)
    onBuscar?.(nuevo)
  }

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <span className="text-sm font-semibold">
        {etiqueta}
        {requerido ? (
          <span className="ml-0.5 text-destructive-strong" aria-hidden="true">
            *
          </span>
        ) : null}
      </span>

      <Popover.Root
        open={abierto}
        onOpenChange={(estado) => {
          setAbierto(estado)
          if (!estado) setTexto('')
        }}
      >
        <Popover.Trigger asChild>
          <button
            ref={boton}
            type="button"
            disabled={disabled}
            role="combobox"
            aria-expanded={abierto}
            aria-haspopup="listbox"
            // Sin valor el botón solo muestra «Ninguno»: el lector necesita el nombre
            aria-label={`${etiqueta}${valor ? `: ${valor}` : `, ${sinSeleccion}`}`}
            className={cn(
              'flex h-[var(--spacing-control)] w-full items-center justify-between gap-2 rounded-[var(--radius-control)] border bg-surface px-3 text-left',
              'transition-colors duration-[var(--transition-ui)]',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              'disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground',
              error ? 'border-destructive' : 'border-input hover:border-primary/40',
              ancho,
            )}
          >
            <span className={cn('min-w-0 truncate', !valor && 'text-muted-foreground')}>
              {valor || sinSeleccion}
            </span>
            {valor ? (
              <span
                role="button"
                tabIndex={0}
                aria-label={`Quitar ${etiqueta}`}
                onClick={(evento) => {
                  evento.stopPropagation()
                  alCambiar(null)
                  setTexto('')
                }}
                onKeyDown={(evento) => {
                  if (evento.key === 'Enter' || evento.key === ' ') {
                    evento.stopPropagation()
                    evento.preventDefault()
                    alCambiar(null)
                  }
                }}
                className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X size={14} aria-hidden="true" />
              </span>
            ) : (
              <ChevronsUpDown size={16} className="shrink-0 text-muted-foreground" aria-hidden="true" />
            )}
          </button>
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Content
            align="start"
            sideOffset={4}
            className="z-50 w-[var(--radix-popover-trigger-width)] min-w-56 rounded-[var(--radius-panel)] border border-border bg-surface p-1 shadow-popover"
          >
            <div className="border-b border-border p-1.5">
              <input
                autoFocus
                type="text"
                value={texto}
                onChange={(evento) => setTexto(evento.target.value)}
                placeholder={placeholder}
                aria-label={`Buscar en ${etiqueta}`}
                className="h-8 w-full rounded-[var(--radius-control)] border border-input bg-surface px-2 text-sm placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
              />
            </div>

            <ul role="listbox" aria-label={etiqueta} className="sin-barra max-h-64 overflow-y-auto py-1">
              {filtradas.length === 0 ? (
                <li className="px-3 py-4 text-center text-sm text-muted-foreground">
                  {texto.trim() ? (
                    <>
                      <span className="block">«{texto.trim()}» no está en la lista.</span>
                      <span className="mt-1 block">Se guardará como texto libre.</span>
                    </>
                  ) : (
                    vacio
                  )}
                </li>
              ) : (
                filtradas.map((sugerencia) => (
                  <li key={sugerencia.valor}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={valor === sugerencia.valor}
                      onClick={() => {
                        alCambiar(sugerencia.valor)
                        setAbierto(false)
                        setTexto('')
                      }}
                      onKeyDown={(evento) => {
                        if (evento.key === 'Enter') {
                          alCambiar(sugerencia.valor)
                          setAbierto(false)
                        }
                      }}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-[var(--radius-control)] px-2.5 py-2 text-left text-sm',
                        'hover:bg-muted focus-visible:bg-muted focus-visible:outline-none',
                        valor === sugerencia.valor && 'bg-primary-soft',
                      )}
                    >
                      <Check
                        size={14}
                        aria-hidden="true"
                        className={cn('shrink-0', valor === sugerencia.valor ? 'text-primary-strong' : 'invisible')}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{sugerencia.valor}</span>
                        {sugerencia.detalle ? (
                          <span className="block truncate text-2xs text-muted-foreground">{sugerencia.detalle}</span>
                        ) : null}
                      </span>
                      {sugerencia.frecuencia ? (
                        <span className="shrink-0 text-2xs text-muted-foreground">{numero(sugerencia.frecuencia)}×</span>
                      ) : null}
                    </button>
                  </li>
                ))
              )}
            </ul>

            <div className="border-t border-border p-1.5">
              <button
                type="button"
                onClick={() => {
                  escribir(texto)
                  setAbierto(false)
                }}
                disabled={!texto.trim()}
                className="w-full rounded-[var(--radius-control)] px-2 py-1.5 text-left text-sm font-medium text-primary-strong hover:bg-primary-soft disabled:opacity-50"
              >
                Usar «{texto.trim() || '…'}»
              </button>
            </div>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>

      <div className="flex items-start justify-between gap-2 text-sm">
        <div className="min-w-0 flex-1">
          {error ? (
            <p role="alert" className="font-semibold text-destructive-strong">
              {error}
            </p>
          ) : ayuda ? (
            <p className="text-muted-foreground">{ayuda}</p>
          ) : null}
        </div>
        <p className="shrink-0 text-2xs text-muted-foreground">{sugerencias.length} sugerencias</p>
      </div>
    </div>
  )
}