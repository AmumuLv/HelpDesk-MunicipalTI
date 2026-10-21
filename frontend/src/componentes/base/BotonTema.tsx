/**
 * Botón que alterna el tema claro/oscuro (la luna).
 *
 * Vive en los dos cascarones (panel y portal) pero el mecanismo es el mismo:
 * `data-tema` en la raíz + preferencia guardada. El icono cambia según el tema
 * y lleva `aria-pressed` para que el lector de pantalla conozca el estado.
 *
 * Se pinta con los tokens de la barra de navegación (`nav-*`), no con los de la
 * página: antes usaba `bg-surface` y quedaba un cuadrado blanco sobre el azul
 * institucional, o casi invisible en tema oscuro. Ahora comparte el aspecto con
 * el botón de notificaciones que tiene al lado.
 */

import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

import { alternarTema, temaActual } from '../../estado/tema'
import { cn } from '../../lib/cn'

export function BotonTema({ className, compacto }: { className?: string; compacto?: boolean }) {
  const [tema, setTema] = useState<'claro' | 'oscuro'>(() => temaActual())

  // Mantiene el icono al día si el tema cambia por otro medio (atajo, otra pestaña)
  useEffect(() => {
    const observador = new MutationObserver(() => setTema(temaActual()))
    observador.observe(document.documentElement, { attributes: true, attributeFilter: ['data-tema'] })
    return () => observador.disconnect()
  }, [])

  const oscuro = tema === 'oscuro'
  const Icono = oscuro ? Sun : Moon

  return (
    <button
      type="button"
      onClick={() => setTema(alternarTema())}
      aria-pressed={oscuro}
      aria-label={oscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
      title={oscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] border border-nav-foreground/25 bg-transparent text-nav-foreground transition-colors duration-[var(--transition-ui)] hover:bg-nav-foreground/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        compacto ? 'size-9' : 'h-9 px-3 text-sm font-medium',
        className,
      )}
    >
      <Icono size={18} aria-hidden="true" className="transition-transform duration-[var(--transition-ui-slow)]" />
      {!compacto ? (oscuro ? 'Claro' : 'Oscuro') : null}
    </button>
  )
}
