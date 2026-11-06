/**
 * Estado de una cuenta: activa, desactivada o archivada.
 *
 * Se comunica con texto e icono, no solo con color: «Activo» / «Desactivado»
 * con su propio icono, para que se lea sin depender del tono.
 */

import { Archive, CircleCheck, CircleSlash } from 'lucide-react'

import { cn } from '../../lib/cn'

export function EtiquetaEstadoActivo({ activo, archivado = false, cuenta = false }: {
  activo: boolean | null | undefined
  archivado?: boolean
  cuenta?: boolean
}) {
  const estaActiva = Boolean(activo) && !archivado
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-semibold',
        estaActiva
          ? 'border-success/25 bg-success-soft text-success-strong'
          : 'border-border bg-muted text-muted-foreground',
      )}
      title={archivado ? 'La cuenta está archivada y conserva su historial' : estaActiva ? 'La cuenta puede entrar al sistema' : 'La cuenta existe pero no puede entrar'}
    >
      {archivado ? <Archive size={12} aria-hidden="true" /> : estaActiva ? <CircleCheck size={12} aria-hidden="true" /> : <CircleSlash size={12} aria-hidden="true" />}
      {archivado ? cuenta ? 'Archivada' : 'Archivado' : estaActiva ? cuenta ? 'Activa' : 'Activo' : cuenta ? 'Desactivada' : 'Desactivado'}
    </span>
  )
}
