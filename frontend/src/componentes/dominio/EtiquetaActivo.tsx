/**
 * Estado de una cuenta: activo o desactivado.
 *
 * Se comunica con texto e icono, no solo con color: «Activo» / «Desactivado»
 * con su propio icono, para que se lea sin depender del tono.
 */

import { CircleCheck, CircleSlash } from 'lucide-react'

import { cn } from '../../lib/cn'

export function EtiquetaEstadoActivo({ activo }: { activo: boolean | null | undefined }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-semibold',
        activo
          ? 'border-success/25 bg-success-soft text-success-strong'
          : 'border-border bg-muted text-muted-foreground',
      )}
      title={activo ? 'La cuenta puede entrar al sistema' : 'La cuenta existe pero no puede entrar'}
    >
      {activo ? <CircleCheck size={12} aria-hidden="true" /> : <CircleSlash size={12} aria-hidden="true" />}
      {activo ? 'Activo' : 'Desactivado'}
    </span>
  )
}