/**
 * Botones.
 *
 * Un solo botón para toda la aplicación: mismo aspecto, mismo foco, mismo
 * comportamiento de carga. Nunca se escribe un `<button>` suelto.
 */

import { Slot } from '@radix-ui/react-slot'
import { Loader2 } from 'lucide-react'
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

type Variante = 'primario' | 'destacado' | 'secundario' | 'fantasma' | 'destructivo' | 'exito'
type Tamano = 'sm' | 'md' | 'lg' | 'tactil'

export type PropsBoton = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante
  tamano?: Tamano
  cargando?: boolean
  anchoCompleto?: boolean
  /** Botón de icono: cuadrado, con etiqueta solo para lectores de pantalla. */
  soloIcono?: boolean
  icono?: ReactNode
  /** Cambia a otro elemento (por ejemplo, un enlace de navegación). */
  asChild?: boolean
}

  const VARIANTES: Record<Variante, string> = {
    destacado: 'boton-destacado active:translate-y-px',
    primario: 'bg-accion text-primary-foreground border border-accion shadow-sm hover:bg-accion-strong active:translate-y-px',
    secundario: 'bg-surface text-foreground border border-border hover:border-accion/50 hover:bg-muted hover:text-accion-strong active:bg-muted',
    fantasma: 'bg-transparent text-primary-strong hover:bg-primary-soft active:bg-primary-soft',
    destructivo: 'bg-destructive-soft text-destructive-strong border border-destructive-borde hover:bg-destructive hover:text-primary-foreground active:translate-y-px',
    exito: 'bg-success-soft text-success-strong border border-success-borde hover:bg-success hover:text-primary-foreground active:translate-y-px',
  }

  const TAMANOS: Record<Tamano, string> = {
    sm: 'h-8 px-3 text-xs gap-1.5',
    md: 'h-[var(--spacing-control)] px-4 text-sm gap-2',
    lg: 'h-11 px-6 text-base gap-2',
    tactil: 'h-[var(--spacing-control-touch)] px-6 text-base gap-2.5',
  }

  export const Button = forwardRef<HTMLButtonElement, PropsBoton>(function Button(
    {
      variante = 'secundario',
      tamano = 'md',
      cargando = false,
      anchoCompleto = false,
      soloIcono = false,
      icono,
      asChild = false,
      className,
      children,
      disabled,
      type = 'button',
      ...resto
    },
    referencia,
  ) {
    const Componente = asChild ? Slot : 'button'
    const alto = soloIcono ? { sm: 'size-8', md: 'size-[var(--spacing-control)]', lg: 'size-11', tactil: 'size-[var(--spacing-control-touch)]' }[tamano] : ''

    const clases = cn(
      'inline-flex max-w-full items-center justify-center rounded-[var(--radius-control)] font-semibold',
      'transition-all duration-[var(--transition-ui)]',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
      'disabled:pointer-events-none disabled:opacity-50 disabled:grayscale',
      VARIANTES[variante],
      soloIcono ? alto : TAMANOS[tamano],
      anchoCompleto && 'w-full',
      className,
    )

    if (asChild) {
      return (
        <Componente ref={referencia} className={clases} {...resto}>
          {children}
        </Componente>
      )
    }

    return (
      <Componente
        ref={referencia}
        type={type}
        disabled={disabled || cargando}
        aria-busy={cargando || undefined}
        aria-live={cargando ? 'polite' : undefined}
        className={clases}
        {...resto}
      >
        {cargando ? (
          <Loader2 size={16} className="animate-spin shrink-0" aria-hidden="true" />
        ) : icono ? (
          <span className="shrink-0 transition-transform group-hover:scale-110" aria-hidden="true">
            {icono}
          </span>
        ) : null}
        {children ? <span className="min-w-0 truncate">{children}</span> : null}
      </Componente>
    )
  })

  export function ButtonGroup({
    children,
    className,
    etiqueta,
  }: {
    children: ReactNode
    className?: string
    etiqueta: string
  }) {
    return (
      <div
        role="group"
        aria-label={etiqueta}
        className={cn('inline-flex rounded-[var(--radius-control)] border border-border bg-surface p-1 shadow-inner', className)}
      >
        {children}
      </div>
    )
  }