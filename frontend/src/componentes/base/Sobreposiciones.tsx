/**
 * Diálogos, paneles laterales y tooltips.
 *
 * Todo lo que se abre por encima del contenido y no es un aviso:
 * `DialogModal`, `ConfirmDialog`, `Sheet`, `InfoTooltip` y `PopoverSimple`.
 * Los avisos viven en `estado/Avisos.tsx`; antes había dos implementaciones del
 * mismo contexto y la que no correspondía fallaba en ejecución.
 *
 * Todos usan primitivas de Radix, así que el foco queda atrapado, Escape
 * cierra y el foco vuelve al elemento que lo abrió.
 */

import * as Dialog from '@radix-ui/react-dialog'
import * as Popover from '@radix-ui/react-popover'
import * as Tooltip from '@radix-ui/react-tooltip'
import { AlertTriangle, X } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { Button } from './Button'

/* ══ Diálogo ════════════════════════════════════════════════ */

export function DialogModal({
  abierto,
  alCerrar,
  titulo,
  descripcion,
  children,
  pie,
  tamano = 'md',
  className,
}: {
  abierto: boolean
  alCerrar: () => void
  titulo: string
  descripcion?: ReactNode
  children: ReactNode
  pie?: ReactNode
  tamano?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}) {
  const ancho = { sm: 'max-w-md', md: 'max-w-2xl', lg: 'max-w-4xl', xl: 'max-w-6xl' }[tamano]
  return (
    <Dialog.Root open={abierto} onOpenChange={(estado) => !estado && alCerrar()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 data-[state=open]:animate-in data-[state=open]:fade-in" style={{ backgroundColor: 'var(--sombra-atenuacion)' }} />
        <Dialog.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col',
            'rounded-[var(--radius-panel)] border border-border bg-surface shadow-dialogo',
            ancho,
            className,
          )}
        >
          <header className="flex items-start justify-between gap-4 border-b border-border p-4 sm:p-5 bg-surface-2">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold text-foreground">{titulo}</Dialog.Title>
              {descripcion ? (
                <Dialog.Description asChild>
                  <div className="mt-0.5 text-sm text-muted-foreground">{descripcion}</div>
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close asChild>
              <Button variante="fantasma" soloIcono tamano="sm" aria-label="Cerrar">
                <X size={18} aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </header>

          <div className="sin-barra max-h-[65vh] min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">{children}</div>

          {pie ? <footer className="flex flex-wrap items-center justify-end gap-3 border-t border-border p-4 sm:p-5 bg-surface-2">{pie}</footer> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/* ══ Confirmación de acción con consecuencia ═══════════════ */

export function ConfirmDialog({
  abierto,
  alCerrar,
  alConfirmar,
  titulo,
  mensaje,
  textoConfirmar = 'Confirmar',
  textoCancelar = 'Cancelar',
  peligro,
  cargando,
}: {
  abierto: boolean
  alCerrar: () => void
  alConfirmar: () => void
  titulo: string
  mensaje: ReactNode
  textoConfirmar?: string
  textoCancelar?: string
  peligro?: boolean
  cargando?: boolean
}) {
  return (
    <DialogModal
      abierto={abierto}
      alCerrar={alCerrar}
      titulo={titulo}
      tamano="sm"
      pie={
        <>
          <Dialog.Close asChild>
            <Button disabled={cargando}>{textoCancelar}</Button>
          </Dialog.Close>
          <Button variante={peligro ? 'destructivo' : 'primario'} onClick={alConfirmar} cargando={cargando}>
            {textoConfirmar}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        {peligro ? (
          <span
            aria-hidden="true"
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-destructive-soft text-destructive-strong border border-destructive-borde"
          >
            <AlertTriangle size={20} />
          </span>
        ) : null}
        <div className="min-w-0 flex-1 text-sm text-foreground leading-relaxed">{mensaje}</div>
      </div>
    </DialogModal>
  )
}

/* ══ Panel lateral (detalles rápidos y flujos de 2 pasos) ════ */

export function Sheet({
  abierto,
  alCerrar,
  titulo,
  descripcion,
  children,
  pie,
  ancho = 'md',
  lado = 'derecha',
  cerrarFuera = true,
}: {
  abierto: boolean
  alCerrar: () => void
  titulo: string
  descripcion?: ReactNode
  children: ReactNode
  pie?: ReactNode
  ancho?: 'sm' | 'md' | 'lg'
  lado?: 'derecha' | 'izquierda'
  /**
   * Cerrar al pulsar fuera del panel.
   *
   * Se puede apagar en formularios largos: en el alta de equipo se perdía todo lo
   * escrito —tipo, marca, código, tres pasos— por un clic perdido fuera del panel,
   * sin aviso y sin haber pulsado la X. Con esto apagado solo se cierra con la X
   * o con Escape, que son gestos deliberados.
   */
  cerrarFuera?: boolean
}) {
  const medidas = { sm: 'sm:max-w-md', md: 'sm:max-w-xl', lg: 'sm:max-w-3xl' }[ancho]
  return (
    <Dialog.Root open={abierto} onOpenChange={(estado) => !estado && alCerrar()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40" style={{ backgroundColor: 'var(--sombra-atenuacion)' }} />
        <Dialog.Content
          onPointerDownOutside={(evento) => {
            if (!cerrarFuera) evento.preventDefault()
          }}
          className={cn(
            'fixed inset-y-0 z-50 flex w-full flex-col border-border bg-surface shadow-dialogo',
            'sm:data-[state=open]:animate-in sm:data-[state=open]:slide-in-from-right',
            lado === 'derecha' ? 'border-l' : 'border-r',
            medidas,
          )}
        >
          <header className="flex items-start justify-between gap-4 border-b border-border p-4 bg-surface-2">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold text-foreground">{titulo}</Dialog.Title>
              {descripcion ? (
                <Dialog.Description asChild>
                  <div className="mt-0.5 text-sm text-muted-foreground">{descripcion}</div>
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close asChild>
              <Button variante="fantasma" soloIcono tamano="sm" aria-label="Cerrar">
                <X size={18} aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </header>

          <div className="sin-barra min-h-0 flex-1 overflow-y-auto p-4">{children}</div>

          {pie ? <footer className="border-t border-border p-4 bg-surface-2">{pie}</footer> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/* ══ Tooltip ════════════════════════════════════════════════ */

export function InfoTooltip({ contenido, children }: { contenido: ReactNode; children: ReactNode }) {
  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            sideOffset={6}
            className="z-50 max-w-xs rounded-[var(--radius-control)] bg-surface-elevated border border-border px-3 py-2 text-xs font-medium text-foreground shadow-popover"
          >
            {contenido}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}

/* ══ Popover genérico ══════════════════════════════════════ */

export function PopoverSimple({
  disparador,
  contenido,
  alineado = 'end',
  ancho = 'w-64',
  abierto,
  alCambiar,
}: {
  disparador: ReactNode
  contenido: ReactNode
  alineado?: 'start' | 'center' | 'end'
  ancho?: string
  /** Control opcional: permite cerrarlo al navegar, por ejemplo. */
  abierto?: boolean
  alCambiar?: (abierto: boolean) => void
}) {
  return (
    <Popover.Root open={abierto} onOpenChange={alCambiar}>
      <Popover.Trigger asChild>{disparador}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align={alineado}
          sideOffset={8}
          className={cn('z-50 max-w-[calc(100vw-2rem)] rounded-[var(--radius-panel)] border border-border bg-surface p-3 text-foreground shadow-popover', ancho)}
        >
          {contenido}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
