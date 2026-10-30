/**
 * Shell del panel TI.
 *
 * Barra lateral y superior en azul marino institucional; el contenido vive sobre
 * un fondo gris azulado. Tres estados de escritorio: expandida (iconos y texto),
 * contraída (solo iconos con tooltip y submenús flotantes) y oculta (un botón
 * fijo devuelve el menú). En móvil/tableta es un cajón con fondo atenuado.
 *
 * El menú sale de los permisos: lo que el backend no autoriza, no se ve.
 */

import {
  BarChart3,
  BookOpen,
  CalendarClock,
  ChevronDown,
  ClipboardList,
  FileSpreadsheet,
  Gauge,
  LifeBuoy,
  LogOut,
  Menu,
  Monitor,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  User,
  Users,
  X,
} from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'
import * as Popover from '@radix-ui/react-popover'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { useTiempoReal } from '../../api/tiempoReal'
import { useSesion } from '../../estado/useSesion'
import { Button } from '../base/Button'
import { InsigniaRol } from '../base/Estructura'
import { AvatarCuenta } from '../dominio/AvatarCuenta'
import { PopoverSimple } from '../base/Sobreposiciones'
import { BotonTema } from '../base/BotonTema'
import { LogoMesa } from '../base/LogoMesa'
import { CampanaNotificaciones } from '../dominio/CampanaNotificaciones'
import { ChatbotTI } from '../dominio/ChatbotTI'
import './NavegacionTI.css'

type Entrada = {
  clave: string
  texto: string
  ruta: string
  icono: typeof Gauge
  permiso?: string
  contador?: number
  separadorAntes?: boolean
  hijos?: Entrada[]
}

type ModoBarra = 'expandida' | 'contraida' | 'oculta'

const CLAVE_BARRA = 'ma.barra'
const COLOR_ICONOS: Record<string, string> = { resumen: '#7dd3fc', tickets: '#facc15', equipos: '#67e8f9', organizacion: '#c4b5fd', usuarios: '#86efac', 'equipo-ti': '#fdba74', analisis: '#f0abfc', reportes: '#5eead4', mas: '#fda4af' }

/** El menú, en el orden en que se recorre trabajando. */
function menuDelPanel(permisos: string[], esAdmin: boolean, contadores: Record<string, number> = {}): Entrada[] {
  const puede = (permiso?: string) => !permiso || esAdmin || permisos.includes(permiso)
  const tickets = [
    { clave: 'todos', texto: 'Abiertos', ruta: '/panel/tickets', icono: ClipboardList, permiso: 'tickets.operar' },
    { clave: 'mios', texto: 'Mis asignaciones', ruta: '/panel/mis-asignaciones', icono: LifeBuoy, permiso: 'tickets.operar' },
    { clave: 'cerrados', texto: 'Cerrados', ruta: '/panel/cerrados?tab=cerrados', icono: BookOpen, permiso: 'tickets.operar' },
  ].filter((entrada) => puede(entrada.permiso))
  const equipos = [
    { clave: 'inventario', texto: 'Inventario', ruta: '/panel/equipos', icono: Monitor, permiso: 'equipos.ver' },
    { clave: 'calidad', texto: 'Calidad', ruta: '/panel/equipos/calidad', icono: FileSpreadsheet, permiso: 'equipos.ver' },
    { clave: 'importar', texto: 'Importar', ruta: '/panel/equipos/importar', icono: FileSpreadsheet, permiso: 'equipos.importar' },
    { clave: 'anual', texto: 'Inventario anual', ruta: '/panel/inventario-anual', icono: CalendarClock, permiso: 'equipos.campanas' },
  ].filter((entrada) => puede(entrada.permiso))
  const otros = [
    { clave: 'conocimiento', texto: 'Base de conocimiento', ruta: '/panel/conocimiento', icono: BookOpen, permiso: 'kb.ver' },
    { clave: 'auditoria', texto: 'Auditoría', ruta: '/panel/auditoria', icono: ShieldCheck, permiso: 'auditoria.ver' },
    { clave: 'configuracion', texto: 'Configuración', ruta: '/panel/configuracion', icono: Settings, permiso: 'configuracion.ver' },
  ].filter((entrada) => puede(entrada.permiso))
  const entradas: Entrada[] = [
    { clave: 'resumen', texto: 'Resumen', ruta: '/panel', icono: Gauge },
    ...(tickets.length ? [{ clave: 'tickets', texto: 'Tickets', ruta: '/panel/tickets', icono: ClipboardList, hijos: tickets }] : []),
    ...(equipos.length ? [{ clave: 'equipos', texto: 'Equipos', ruta: '/panel/equipos', icono: Monitor, hijos: equipos }] : []),
    { clave: 'organizacion', texto: 'Zonas y oficinas', ruta: '/panel/organizacion', icono: Network, permiso: 'org.ver' },
    { clave: 'usuarios', texto: 'Usuarios', ruta: '/panel/usuarios', icono: Users, permiso: 'usuarios.ver' },
    { clave: 'equipo-ti', texto: 'Equipo TI', ruta: '/panel/equipo-ti', icono: Users, permiso: 'horarios.ver' },
    { clave: 'analisis', texto: 'Análisis IA', ruta: '/panel/analisis', icono: BarChart3, permiso: 'analitica.ver' },
    { clave: 'reportes', texto: 'Reportes', ruta: '/panel/reportes', icono: FileSpreadsheet, permiso: 'reportes.ver' },
    ...(otros.length ? [{ clave: 'mas', texto: 'Más', ruta: otros[0].ruta, icono: BookOpen, hijos: otros }] : []),
  ]

  return entradas
    .filter((entrada) => puede(entrada.permiso))
    .map((entrada) => ({ ...entrada, contador: contadores[entrada.clave] }))
}

function leerModoGuardado(): ModoBarra {
  try {
    const guardado = localStorage.getItem(CLAVE_BARRA)
    return guardado === 'contraida' || guardado === 'oculta' ? guardado : 'expandida'
  } catch {
    return 'expandida'
  }
}

export function ShellPanel({ children }: { children: ReactNode }) {
  const sesion = useSesion()
  useTiempoReal('notificaciones')
  const navegar = useNavigate()
  const ubicacion = useLocation()

  const [modo, setModo] = useState<ModoBarra>(() => leerModoGuardado())
  const [cajonAbierto, setCajonAbierto] = useState(false)
  const [cuentaAbierta, setCuentaAbierta] = useState(false)
  const navRef = useRef<HTMLElement>(null)

  const guardarModo = (siguiente: ModoBarra) => {
    setModo(siguiente)
    try {
      localStorage.setItem(CLAVE_BARRA, siguiente)
    } catch {
      // Sin almacenamiento local el estado solo dura la sesión
    }
  }

  // Al cambiar de ruta en móvil el cajón se cierra: si no, tapa la pantalla nueva
  useEffect(() => setCajonAbierto(false), [ubicacion.pathname])

  // Escape cierra el cajón; Ctrl+B alterna entre expandida y contraída
  useEffect(() => {
    const alTeclado = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') setCajonAbierto(false)
      if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === 'b') {
        evento.preventDefault()
        setModo((actual) => (actual === 'expandida' ? 'contraida' : 'expandida'))
      }
    }
    window.addEventListener('keydown', alTeclado)
    return () => window.removeEventListener('keydown', alTeclado)
  }, [])

  // Foco atrapado dentro del cajón en móvil mientras está abierto
  useEffect(() => {
    if (!cajonAbierto) return
    const nav = navRef.current
    if (!nav) return
    const enfocables = () =>
      Array.from(nav.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')).filter((el) => el.offsetParent !== null)
    const alTabulador = (evento: KeyboardEvent) => {
      const lista = enfocables()
      if (lista.length === 0) return
      const primero = lista[0]
      const ultimo = lista[lista.length - 1]
      if (evento.shiftKey && document.activeElement === primero) {
        evento.preventDefault()
        ultimo.focus()
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault()
        primero.focus()
      }
    }
    nav.addEventListener('keydown', alTabulador)
    return () => nav.removeEventListener('keydown', alTabulador)
  }, [cajonAbierto])

  const menu = menuDelPanel(sesion.permisos, sesion.esAdmin)

  /** Cierra el menú de la cuenta y va a la ruta: si no, el menú sigue abierto encima. */
  const irA = (ruta: string) => {
    setCuentaAbierta(false)
    navegar(ruta)
  }

  const salir = async () => {
    await sesion.salir()
    navegar('/acceder')
  }

  const contraida = modo === 'contraida'
  const oculta = modo === 'oculta'

  return (
    <div className="min-h-dvh bg-background">
      {/* ══ Cajón de navegación (móvil/tableta) ═════════════════ */}
      {cajonAbierto ? (
        <div
          className="fixed inset-0 z-30 lg:hidden"
          style={{ backgroundColor: 'var(--sombra-atenuacion)' }}
          onClick={() => setCajonAbierto(false)}
          aria-hidden="true"
        />
      ) : null}

      {/* La barra se oculta por completo en escritorio cuando el modo es "oculta";
          en móvil el cajón sigue disponible con el botón de menú. */}
      <nav
        ref={navRef}
        aria-label="Navegación del panel"
        className={cn(
          'ti-navegacion fixed inset-y-0 left-0 z-40 flex flex-col border-r border-nav-foreground/20 bg-nav shadow-nav transition-[width] duration-[var(--transition-ui-slow)]',
          'w-64 lg:w-64',
          contraida ? 'lg:w-[72px]' : 'lg:w-64',
          oculta && 'lg:hidden',
          cajonAbierto ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        )}
      >
          <div className="flex h-14 shrink-0 items-center gap-2 border-b border-nav-foreground/20 bg-nav-deep/35 px-3">
            <LogoMesa />
            {!contraida ? (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-nav-foreground">Mesa de Ayuda</p>
                <p className="truncate text-2xs text-nav-muted">{sesion.nombreInstitucion}</p>
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => setCajonAbierto(false)}
              className="rounded p-1 text-nav-muted hover:bg-nav-foreground/10 lg:hidden"
              aria-label="Cerrar el menú"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          <ul className="sin-barra flex-1 overflow-y-auto p-2">
            {menu.map((entrada) => (
              <EntradaMenu key={entrada.clave} entrada={entrada} contraida={contraida} />
            ))}
          </ul>

          {/* Colapsar: en móvil no aplica, la barra ya es un cajón */}
          <div className="shrink-0 border-t border-nav-foreground/20 bg-nav-deep/35 p-2">
            <button
              type="button"
              onClick={() => guardarModo(contraida ? 'expandida' : 'contraida')}
              className={cn(
                'hidden h-10 w-full items-center gap-2 rounded-[var(--radius-control)] text-sm text-nav-muted hover:bg-nav-foreground/10 lg:flex',
                contraida && 'justify-center',
              )}
              aria-label={contraida ? 'Ampliar el menú' : 'Reducir el menú a iconos'}
              aria-pressed={contraida}
              aria-expanded={!contraida}
            >
              <PanelLeftClose size={16} aria-hidden="true" className={cn('transition-transform', contraida && 'rotate-180')} />
              {!contraida ? 'Contraer' : null}
            </button>
          </div>
      </nav>

      {/* ══ Columna principal ═════════════════════════════════════ */}
      <div
        className={cn(
          'flex min-h-dvh flex-col transition-[padding] duration-[var(--transition-ui-slow)]',
          oculta ? 'lg:pl-0' : contraida ? 'lg:pl-[72px]' : 'lg:pl-64',
        )}
      >
        <header
          className="ti-barra-superior sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-nav px-4 text-nav-foreground sm:px-6"
          style={{ boxShadow: 'var(--shadow-nav)' }}
        >
          <Button
            variante="fantasma"
            soloIcono
            tamano="sm"
            className="lg:hidden"
            onClick={() => setCajonAbierto(true)}
            aria-label="Abrir el menú"
          >
            <Menu size={20} aria-hidden="true" />
          </Button>
          {oculta ? (
            <Button
              variante="fantasma"
              soloIcono
              tamano="sm"
              className="hidden lg:inline-flex text-nav-foreground hover:bg-nav-foreground/10"
              onClick={() => guardarModo('expandida')}
              aria-label="Mostrar el menú"
              aria-expanded={false}
            >
              <PanelLeftOpen size={20} aria-hidden="true" />
            </Button>
          ) : null}

          <h1 className="min-w-0 flex-1 truncate text-base font-semibold">{sesion.nombreInstitucion}</h1>

          <CampanaNotificaciones />

          <BotonTema compacto />

          <PopoverSimple
            alineado="end"
            ancho="w-64"
            disparador={
              <button
                type="button"
                className="flex items-center gap-2 rounded-[var(--radius-control)] px-1.5 py-1 hover:bg-nav-foreground/10"
                aria-label="Abrir el menú de la cuenta"
              >
                <AvatarCuenta tamano="sm" />
                <span className="hidden min-w-0 text-left sm:block">
                  <span className="block truncate text-sm font-semibold">{sesion.usuario?.nombre}</span>
                  <span className="block truncate text-2xs text-nav-muted">{sesion.esSuperadmin ? 'Superadministrador' : textoRol(sesion.rol)}</span>
                </span>
              </button>
            }
contenido={
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-3 border-b border-border pb-3">
                  <AvatarCuenta tamano="lg" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-base font-semibold text-foreground">{sesion.usuario?.nombre}</p>
                    <p className="truncate text-xs text-muted-foreground">{sesion.usuario?.email}</p>
                    <div className="mt-1.5">
                      <InsigniaRol rol={sesion.rol} superadministrador={sesion.esSuperadmin} />
                    </div>
                  </div>
                </div>

                {/* Opciones de la cuenta. Antes el menú solo tenía «Cerrar
                    sesión», así que abrirlo no llevaba a ninguna parte. */}
                <ul className="mt-1 flex flex-col gap-0.5">
                  <OpcionMenu icono={<User size={16} aria-hidden="true" />} texto="Mi perfil" onClick={() => irA('/panel/perfil')} />
                  <OpcionMenu
                    icono={<ClipboardList size={16} aria-hidden="true" />}
                    texto="Mis tickets"
                    onClick={() => irA('/panel/mis-asignaciones')}
                  />
                  {sesion.puede('configuracion.ver') ? (
                    <OpcionMenu
                      icono={<Settings size={16} aria-hidden="true" />}
                      texto="Configuración"
                      onClick={() => irA('/panel/configuracion')}
                    />
                  ) : null}
                  {sesion.puede('usuarios.ver') ? (
                    <OpcionMenu icono={<Users size={16} aria-hidden="true" />} texto="Usuarios" onClick={() => irA('/panel/usuarios')} />
                  ) : null}
                </ul>

                <Button
                  variante="fantasma"
                  anchoCompleto
                  className="mt-1 justify-start text-destructive-strong hover:bg-destructive-soft"
                  icono={<LogOut size={16} aria-hidden="true" />}
                  onClick={() => void salir()}
                >
                  Cerrar sesión
                </Button>
              </div>
            }
            abierto={cuentaAbierta}
            alCambiar={setCuentaAbierta}
          />
        </header>

        <main className="min-w-0 flex-1 p-3 sm:p-4 lg:p-6">
          <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4">{children}</div>
        </main>
        <ChatbotTI />
      </div>
    </div>
  )
}

/** Una entrada del menú: enlace (o grupo con submenú flotante al contraer). */
function EntradaMenu({ entrada, contraida }: { entrada: Entrada; contraida: boolean }) {
  const activo = useActivo(entrada)
  const { pathname } = useLocation()
  const grupoId = useId()
  const [extendido, setExtendido] = useState(true)
  const [submenuAbierto, setSubmenuAbierto] = useState(false)
  const esGrupo = Boolean(entrada.hijos?.length)
  const plegable = (entrada.hijos?.length ?? 0) >= 3
  useEffect(() => { if (activo) setExtendido(true) }, [pathname, activo])
  const controlGrupo = plegable ? <button type="button" className="ti-nav-toggle" aria-label={`${extendido ? 'Contraer' : 'Extender'} ${entrada.texto}`} aria-expanded={extendido} aria-controls={grupoId} onClick={() => setExtendido(valor => !valor)}><ChevronDown size={15} className={extendido ? '' : '-rotate-90'} aria-hidden="true" /></button> : null

  // Grupo contraído en escritorio: icono + submenú flotante al pasar el mouse.
  // En móvil la barra siempre es un cajón expandido, así que esta variante se
  // oculta y se muestra la lista completa más abajo.
  if (contraida && esGrupo) {
    return (
      <>
        <li className="relative hidden lg:block">
          <Tooltip.Provider delayDuration={150}>
          <Tooltip.Root>
          <Popover.Root open={submenuAbierto} onOpenChange={setSubmenuAbierto}>
            <Tooltip.Trigger asChild>
            <Popover.Trigger asChild>
              <button
                type="button"
                aria-label={entrada.texto}
                data-activo={activo || undefined}
                className={cn(
                  'mb-0.5 flex min-h-10 w-full items-center justify-center gap-2.5 rounded-[var(--radius-control)] px-0 text-nav-foreground',
                  'transition-colors duration-[var(--transition-ui)] hover:bg-nav-foreground/10',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                  activo && 'bg-nav-foreground/15 text-nav-foreground',
                )}
              >
                <entrada.icono size={18} style={{ color: COLOR_ICONOS[entrada.clave] || '#a5b4fc' }} className="ti-nav-icono shrink-0" aria-hidden="true" />
                {entrada.contador ? <span className="absolute top-0.5 right-1.5 flex size-4 items-center justify-center rounded-full bg-destructive text-2xs font-bold text-primary-foreground">{entrada.contador}</span> : null}
              </button>
            </Popover.Trigger>
            </Tooltip.Trigger>
            <Popover.Portal>
              <Popover.Content
                side="right"
                sideOffset={8}
                aria-label={`Opciones de ${entrada.texto}`}
                className="ti-nav-flotante z-50 min-w-56 rounded-[var(--radius-panel)] border border-border-fuerte bg-surface-elevated p-2 text-foreground shadow-dialogo"
              >
                <p className="mb-1 border-b border-border px-2.5 pt-1.5 pb-2 text-xs font-bold text-foreground">{entrada.texto}</p>
                {entrada.hijos!.map((hijo) => (
                  <NavLink
                    key={hijo.clave}
                    to={hijo.ruta}
                    onClick={() => setSubmenuAbierto(false)}
                    end
                    className={({ isActive }) =>
                      cn(
                        'block rounded-[var(--radius-control)] px-2.5 py-1.5 text-sm',
                        isActive ? 'border-l-2 border-info bg-info-soft font-semibold text-info-strong' : 'text-foreground hover:bg-muted',
                      )
                    }
                  >
                    {hijo.texto}
                  </NavLink>
                ))}
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>
          <Tooltip.Portal><Tooltip.Content side="right" sideOffset={10} className="z-50 rounded-[var(--radius-control)] border border-nav-foreground/25 bg-nav px-3 py-2 text-sm font-semibold text-nav-foreground shadow-dialogo">{entrada.texto}</Tooltip.Content></Tooltip.Portal>
          </Tooltip.Root>
          </Tooltip.Provider>
        </li>
        <li className="relative lg:hidden"><NavLink to={entrada.ruta} aria-label={entrada.texto} data-activo={activo || undefined} className="flex min-h-10 items-center gap-2.5 rounded-lg px-2.5 pr-10 text-sm"><entrada.icono size={18} style={{ color: COLOR_ICONOS[entrada.clave] || '#a5b4fc' }} className="ti-nav-icono" />{entrada.texto}</NavLink>{controlGrupo}{extendido || !plegable ? <GrupoExpandido entrada={entrada} id={grupoId} /> : null}</li>
      </>
    )
  }

  const enlace = (
    <NavLink
      to={entrada.ruta}
      aria-label={entrada.texto}
      data-activo={activo || undefined}
      end={entrada.ruta === '/panel'}
      className={cn(
          'mb-0.5 flex min-h-10 items-center gap-2.5 rounded-[var(--radius-control)] px-2.5 text-sm font-medium text-nav-foreground',
          'transition-colors duration-[var(--transition-ui)]',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
          activo ? 'bg-nav-foreground/15 font-semibold text-nav-foreground' : 'hover:bg-nav-foreground/10 hover:text-nav-foreground',
          contraida && 'lg:justify-center lg:px-0',
          plegable && 'pr-10',
        )}
    >
      <entrada.icono size={18} style={{ color: COLOR_ICONOS[entrada.clave] || '#a5b4fc' }} className="ti-nav-icono shrink-0" aria-hidden="true" />
      <span className={cn('min-w-0 flex-1 truncate', contraida && 'lg:hidden')}>{entrada.texto}</span>
      {entrada.contador ? (
        <span className="shrink-0 rounded-full bg-destructive px-1.5 py-0.5 text-2xs font-bold text-primary-foreground lg:hidden">
          {entrada.contador}
        </span>
      ) : null}
      {contraida && entrada.contador ? (
        <span className="absolute top-0.5 right-1.5 hidden size-4 items-center justify-center rounded-full bg-destructive text-2xs font-bold text-primary-foreground lg:flex">
          {entrada.contador}
        </span>
      ) : null}
    </NavLink>
  )

  return (
    <li className={cn('relative', entrada.separadorAntes && 'mt-3 border-t border-nav-deep/40 pt-3')}>
      {contraida && !esGrupo ? (
        <Tooltip.Provider delayDuration={200}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>{enlace}</Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={8} className="z-50 rounded-[var(--radius-control)] border border-nav-foreground/25 bg-nav px-3 py-2 text-sm font-semibold text-nav-foreground shadow-dialogo">
                {entrada.texto}
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </Tooltip.Provider>
      ) : (
        enlace
      )}
      {!contraida ? controlGrupo : null}
      {!contraida && esGrupo && (extendido || !plegable) ? <GrupoExpandido entrada={entrada} id={grupoId} /> : null}
    </li>
  )
}

/** La lista de hijos de un grupo, en su forma expandida. */
function GrupoExpandido({ entrada, soloMovil, id }: { entrada: Entrada; soloMovil?: boolean; id?: string }) {
  return (
    <ul id={id} className={cn('mb-2 ml-7 border-l border-nav-foreground/25 pl-2', soloMovil && 'lg:hidden')}>
      {entrada.hijos!.map((hijo) => (
        <li key={hijo.clave}>
          <NavLink
            to={hijo.ruta}
            end
            className={({ isActive }) =>
              cn(
                'block rounded px-2 py-1.5 text-sm',
                isActive ? 'font-semibold text-nav-foreground' : 'text-nav-muted hover:bg-nav-foreground/10 hover:text-nav-foreground',
              )
            }
          >
            {hijo.texto}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

/**
 * `true` si la entrada o alguno de sus hijos es la ruta activa.
 *
 * Es un hook (llama a `useLocation`), así que el nombre lleva el prefijo `use`
 * que exige la regla `react-hooks/rules-of-hooks`; el resto va en español.
 */
function useActivo(entrada: Entrada): boolean {
  const { pathname } = useLocation()
  if (entrada.ruta === '/panel') return pathname === '/panel'
  if (entrada.hijos?.length) return entrada.hijos.some((hijo) => pathname.startsWith(hijo.ruta.split('?')[0]))
  return pathname === entrada.ruta.split('?')[0] || pathname.startsWith(`${entrada.ruta.split('?')[0]}/`)
}

function textoRol(rol: string | null): string {
  if (rol === 'administrador') return 'Administrador'
  if (rol === 'tecnico') return 'Equipo TI'
  if (rol === 'usuario') return 'Usuario'
  return ''
}

/** Una opción del menú de la cuenta: icono, texto y acción al pulsarla. */
function OpcionMenu({
  icono,
  texto,
  onClick,
}: {
  icono: ReactNode
  texto: string
  onClick: () => void
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 text-left text-sm font-medium text-foreground transition-colors hover:bg-muted"
      >
        <span aria-hidden="true" className="shrink-0 text-muted-foreground">
          {icono}
        </span>
        {texto}
      </button>
    </li>
  )
}
