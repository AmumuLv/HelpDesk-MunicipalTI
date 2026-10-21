/**
 * Shell del portal del usuario.
 *
 * No es el panel en pequeño: quien entra aquí es una persona con un problema
 * ahora. Sin barra lateral densa, sin métricas internas, con controles de 48 px
 * y navegación inferior en móvil.
 */

import { HelpCircle, House, Monitor, Ticket, User } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { NAVEGACION_PORTAL } from '../../dominio/navegacion'
import { cn } from '../../lib/cn'
import { useSesion } from '../../estado/Sesion'
import { AvatarCuenta } from '../dominio/AvatarCuenta'
import { BotonTema } from '../base/BotonTema'
import { LogoMesa } from '../base/LogoMesa'
import { CampanaNotificaciones } from '../dominio/CampanaNotificaciones'
import { useTiempoReal } from '../../api/tiempoReal'

const ICONOS = {
  inicio: House,
  tickets: Ticket,
  equipos: Monitor,
  ayuda: HelpCircle,
  perfil: User,
} as const

export function ShellPortal({ children }: { children: ReactNode }) {
  const sesion = useSesion()
  useTiempoReal('notificaciones')

  return (
    <div className="portal-futurista min-h-dvh bg-background pb-20 md:pb-0">
      <header className="relative z-20 border-b border-border bg-nav text-nav-foreground" style={{ boxShadow: 'var(--shadow-nav)' }}>
        <div className="mx-auto flex h-20 w-full max-w-5xl items-center gap-2 px-3 sm:gap-4 sm:px-6">
          <LogoMesa />
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-bold text-nav-foreground">Mesa de ayuda</p>
            <p className="truncate text-xs text-nav-muted">{sesion.nombreInstitucion}</p>
          </div>

          <BotonTema compacto />

          {/* La campana también en el portal: es quien reporta el problema quien
              recibe el aviso de que se tomó o resolvió su caso. */}
          <CampanaNotificaciones />

          <NavLink
            to="/perfil"
            className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nav-foreground focus-visible:ring-offset-2 focus-visible:ring-offset-nav"
            aria-label="Ver mi perfil"
          >
            <AvatarCuenta tamano="md" />
          </NavLink>

        </div>
      </header>

      <nav aria-label="Navegación principal" className="hidden border-b border-border bg-surface md:block"><ul className="mx-auto flex max-w-5xl gap-2 px-6 py-2">{NAVEGACION_PORTAL.map(entrada => {
        const Icono = ICONOS[entrada.clave]
        return <li key={entrada.clave}><NavLink data-destino={entrada.clave} to={entrada.ruta} end={entrada.ruta === '/'} className={({ isActive }) => cn('flex min-h-11 items-center gap-2 rounded-xl px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', isActive ? 'bg-primary-soft text-primary-strong' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}><Icono size={18} />{entrada.texto}</NavLink></li>
      })}</ul></nav>

      <main className="mx-auto w-full max-w-5xl p-4 sm:p-6 md:p-8">
        <div className="flex flex-col gap-6">{children}</div>
      </main>

      {/* Navegación inferior en móvil: los cinco destinos del portal */}
      <nav
        aria-label="Navegación del portal"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface pb-safe md:hidden"
        style={{ boxShadow: 'var(--shadow-nav)' }}
      >
        <ul className="grid grid-cols-3">
          {NAVEGACION_PORTAL.map((entrada) => {
            const Icono = ICONOS[entrada.clave]
            return (
              <li key={entrada.clave}>
                <NavLink
                  data-destino={entrada.clave}
                  to={entrada.ruta}
                  end={entrada.ruta === '/'}
                  className={({ isActive }) =>
                    cn(
                      'relative flex min-h-16 flex-col items-center justify-center gap-1 px-1 py-2 text-xs font-semibold transition-colors',
                      'focus-visible:outline-none focus-visible:bg-primary-soft',
                      isActive ? 'text-primary-strong' : 'text-muted-foreground hover:text-foreground',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && <div className="absolute top-0 left-1/2 w-8 h-0.5 -translate-x-1/2 rounded-b bg-primary" />}
                      <Icono size={22} aria-hidden="true" className={cn('transition-colors', isActive && 'text-primary')} />
                      <span className="text-center leading-none">{entrada.texto}</span>
                    </>
                  )}
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
