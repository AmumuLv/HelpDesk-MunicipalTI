import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export function DatoPerfil({ etiqueta, icono: Icono, children, color = 'var(--perfil-acento, var(--color-muted-foreground))' }: {
  etiqueta: string; icono: LucideIcon; children: ReactNode; color?: string
}) {
  return (
    <div className="flex min-w-0 items-start gap-3 rounded-xl border border-border bg-surface-2/50 p-3">
      <span aria-hidden="true" className="flex size-9 shrink-0 items-center justify-center rounded-lg"
        style={{ color, backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)` }}>
        <Icono size={18} />
      </span>
      <div className="min-w-0 flex-1">
        <dt className="text-2xs font-semibold uppercase tracking-wide text-muted-foreground">{etiqueta}</dt>
        <dd className="mt-1 break-words text-sm font-medium">{children}</dd>
      </div>
    </div>
  )
}
