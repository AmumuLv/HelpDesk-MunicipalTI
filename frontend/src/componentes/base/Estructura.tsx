/**
 * Piezas de estructura: panel, encabezado, migas, pestañas, estados y avatar.
 *
 * Reúne todo lo que estructura una pantalla, para que cada vista se lea como
 * documento y no como colección de cajas.
 */

import * as Tabs from '@radix-ui/react-tabs'
import { ChevronRight, Crown, Info, Lock, RotateCw, User, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { Button } from './Button'
import { iniciales } from '../../dominio/formato'

/* ══ Panel ══════════════════════════════════════════════════ */

export function Panel({
  titulo,
  descripcion,
  acciones,
  children,
  sinRelleno,
  className,
  cuerpoClassName,
  ...resto
}: {
  titulo?: ReactNode
  descripcion?: ReactNode
  acciones?: ReactNode
  children: ReactNode
  sinRelleno?: boolean
  className?: string
  cuerpoClassName?: string
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn('panel rounded-[var(--radius-panel)] border border-border bg-surface', className)} {...resto}>
      {/*
        El encabezado del panel lleva un fondo apenas más oscuro que el cuerpo.
        Sin él, el título y el contenido están sobre el mismo blanco y separados
        solo por una línea: la lectura parece un bloque largo sin principio.
        Es el mismo fondo suave que usa la cabecera de las tablas, para que las
        dos cosas se lean como una sola convención.
      */}
      {titulo ? (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 bg-surface-2/60 px-4 py-3.5">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">{titulo}</h2>
            {descripcion ? <p className="mt-0.5 text-sm text-muted-foreground">{descripcion}</p> : null}
          </div>
          {acciones ? <div className="flex flex-wrap items-center gap-2">{acciones}</div> : null}
        </header>
      ) : null}
      <div className={cn(sinRelleno ? '' : 'p-4', cuerpoClassName)}>{children}</div>
    </section>
  )
}

/* ══ Encabezado de página ═══════════════════════════════════ */

/**
 * Contenedor de las pantallas de formulario.
 *
 * Una columna centrada y de ancho de lectura: el formulario no se estira de lado
 * a lado en una pantalla ancha y, en las estrechas, nada se sale por la derecha
 * (`min-w-0` en todos los niveles). Todas las pantallas de captura usan el mismo
 * ancho y el mismo espaciado, así que moverse entre ellas no da saltos.
 *
 * `data-pantalla` deja que las pruebas comprueben el ancho real del contenedor.
 */
export const ANCHO_FORMULARIO = 'max-w-[1100px]'

export function PantallaFormulario({
  children,
  className,
  ...resto
}: {
  children: ReactNode
  className?: string
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-pantalla="formulario"
      className={cn('mx-auto flex w-full min-w-0 flex-col gap-4', ANCHO_FORMULARIO, className)}
      {...resto}
    >
      {children}
    </div>
  )
}

export function PageHeader({
  titulo,
  descripcion,
  migas,
  acciones,
}: {
  titulo: string
  descripcion?: ReactNode
  migas?: { texto: string; enlace?: string }[]
  acciones?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-3" data-encabezado="pagina">
      {migas?.length ? <Migas items={migas} /> : null}
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0 flex-1">
          <h1 className="titulo-pagina break-words">{titulo}</h1>
          {descripcion ? <p className="mt-1 text-sm text-muted-foreground">{descripcion}</p> : null}
        </div>
        {/* Las acciones envuelven: en pantallas estrechas bajan de línea en vez
            de salirse por la derecha. */}
        {acciones ? (
          <div data-acciones="pagina" className="no-imprimir flex min-w-0 flex-wrap items-center gap-2">
            {acciones}
          </div>
        ) : null}
      </div>
    </header>
  )
}

/* ══ Migas ══════════════════════════════════════════════════ */

export function Migas({ items }: { items: { texto: string; enlace?: string }[] }) {
  if (items.length === 0) return null
  return (
    <nav aria-label="Ruta de navegación">
      <ol className="flex flex-wrap items-center gap-1 text-sm">
        {items.map((item, indice) => {
          const ultimo = indice === items.length - 1
          return (
            <li key={`${item.texto}-${indice}`} className="flex min-w-0 items-center gap-1">
              {indice > 0 ? (
                <ChevronRight size={14} className="shrink-0 text-muted-foreground" aria-hidden="true" />
              ) : null}
              {item.enlace && !ultimo ? (
                <Link to={item.enlace} className="min-w-0 rounded font-medium text-primary-strong hover:underline">
                  <span className="block truncate">{item.texto}</span>
                </Link>
              ) : (
                <span
                  aria-current={ultimo ? 'page' : undefined}
                  className={cn('block min-w-0 truncate', ultimo && 'font-semibold')}
                >
                  {item.texto}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/* ══ Pestañas ═══════════════════════════════════════════════ */

export function TabsPanel({
  valor,
  alCambiar,
  children,
  className,
}: {
  valor: string
  alCambiar: (valor: string) => void
  children: ReactNode
  className?: string
}) {
  return (
    <Tabs.Root value={valor} onValueChange={alCambiar} className={className}>
      {children}
    </Tabs.Root>
  )
}

export function ListaTabs({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Tabs.List className={cn('no-imprimir flex gap-1 overflow-x-auto border-b border-border', className)}>
      {children}
    </Tabs.List>
  )
}

export function Tab({ valor, children }: { valor: string; children: ReactNode }) {
  return (
    <Tabs.Trigger
      value={valor}
      className={cn(
        '-mb-px shrink-0 border-b-2 border-transparent px-3 py-2 text-sm font-semibold whitespace-nowrap',
        'transition-colors duration-[var(--transition-ui)]',
        'hover:text-primary-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        'data-[state=active]:border-primary data-[state=active]:text-primary-strong',
      )}
    >
      {children}
    </Tabs.Trigger>
  )
}

export function ContenidoTab({ valor, children, className }: { valor: string; children: ReactNode; className?: string }) {
  return (
    <Tabs.Content value={valor} className={cn('focus-visible:outline-none', className)}>
      {children}
    </Tabs.Content>
  )
}

/* ══ Avatar ═════════════════════════════════════════════════ */

const TONOS_AVATAR = [
  'bg-primary-soft text-primary-strong',
  'bg-success-soft text-success-strong',
  'bg-warning-soft text-warning-strong',
  'bg-ai-soft text-ai-strong',
  'bg-destructive-soft text-destructive-strong',
  'bg-muted text-muted-foreground',
]

export function Avatar({
  nombre,
  tamano = 'md',
  rol,
  foto,
  className,
}: {
  nombre: string | null | undefined
  tamano?: 'sm' | 'md' | 'lg'
  rol?: string | null
  /** URL de la foto de perfil. Si no hay, se dibujan las iniciales. */
  foto?: string | null
  className?: string
}) {
  const letras = iniciales(nombre)
  const indice = [...(nombre ?? '?')].reduce((total, letra) => total + letra.charCodeAt(0), 0) % TONOS_AVATAR.length
  const medidas = { sm: 'size-7 text-2xs', md: 'size-9 text-sm', lg: 'size-11 text-base' }[tamano]

  // Con rol, el anillo lleva el color de identidad del rol.
  const clasesTono = rol
    ? 'bg-primary-soft text-primary-strong ring-2 ring-primary-borde'
    : TONOS_AVATAR[indice]

  /*
    Foto o iniciales, no las dos. Antes no había foto; ahora, si la hay, se pinta
    la imagen y las iniciales quedan debajo por si la imagen no carga —una URL rota
    no puede dejar un círculo vacío—.
  */
  return (
    <span
      aria-hidden="true"
      title={nombre ?? undefined}
      data-rol={rol ? rol : undefined}
      className={cn('relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-bold', medidas, clasesTono, className)}
    >
      {letras}
      {foto ? (
        <img
          key={foto}
          src={foto}
          alt=""
          className="absolute inset-0 size-full object-cover"
          // Una foto que no carga no debe romper el avatar ni tapar las iniciales.
          onError={(evento) => {
            evento.currentTarget.style.display = 'none'
          }}
        />
      ) : null}
    </span>
  )
}

/** Insignia de rol: identidad por color + icono + texto, nunca un permiso. */
export function InsigniaRol({ rol, className }: { rol: string | null | undefined; className?: string }) {
  const icono = rol === 'administrador' ? Crown : rol === 'tecnico' ? Wrench : User
  const Icono = icono
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-bold uppercase tracking-wide',
        'border-primary-borde bg-primary-soft text-primary-strong',
        className,
      )}
    >
      <Icono size={12} aria-hidden="true" className="shrink-0" />
      {textoRol(rol)}
    </span>
  )
}

function textoRol(rol: string | null | undefined): string {
  if (rol === 'administrador') return 'Administrador'
  if (rol === 'tecnico') return 'Equipo TI'
  if (rol === 'usuario') return 'Usuario'
  return 'Sin rol'
}

/** Avatar + nombre, para listas de personas. */
export function PersonaFila({
  nombre,
  detalle,
  rol,
  tamano = 'md',
  foto,
  className,
}: {
  nombre: string
  detalle?: string | null
  rol?: string | null
  tamano?: 'sm' | 'md' | 'lg'
  /** URL de la foto de perfil, si la persona tiene. */
  foto?: string | null
  className?: string
}) {
  return (
    <div className={cn('flex min-w-0 items-center gap-3', className)}>
      <Avatar nombre={nombre} tamano={tamano} rol={rol} foto={foto} />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-foreground">{nombre}</p>
        {detalle ? <p className="truncate text-xs text-muted-foreground">{detalle}</p> : null}
      </div>
    </div>
  )
}

/* ══ Estados de pantalla ════════════════════════════════════ */

/** Esqueleto con la silueta del contenido que va a aparecer. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded bg-muted', className)} aria-hidden="true" />
}

export function SkeletonPanel({ filas = 4 }: { filas?: number }) {
  return (
    <div className="flex flex-col gap-3" role="status" aria-live="polite">
      <span className="solo-lectores">Cargando…</span>
      <Skeleton className="h-6 w-48" />
      {Array.from({ length: filas }, (_, indice) => (
        <Skeleton key={indice} className="h-11 w-full" />
      ))}
    </div>
  )
}

export function SkeletonKpis({ cantidad = 6 }: { cantidad?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6" role="status" aria-live="polite">
      <span className="solo-lectores">Cargando indicadores…</span>
      {Array.from({ length: cantidad }, (_, indice) => (
        <div key={indice} className="rounded-[var(--radius-panel)] border border-border bg-surface p-3">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="mt-2 h-7 w-14" />
        </div>
      ))}
    </div>
  )
}

/** Pantalla vacía con la acción siguiente, nunca un hueco muerto. */
export function EmptyState({
  icono,
  titulo,
  descripcion,
  accion,
  compacto,
}: {
  icono?: ReactNode
  titulo: string
  descripcion?: ReactNode
  accion?: ReactNode
  compacto?: boolean
}) {
  return (
    <div
      className={cn(
        'flex w-full flex-col items-center justify-center text-center',
        compacto ? 'gap-2 p-6' : 'min-h-[280px] gap-4 p-10',
      )}
    >
      {icono ? (
        <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          {icono}
        </span>
      ) : null}
      <div className="max-w-[420px]">
        <p className="font-semibold">{titulo}</p>
        {descripcion ? <p className="mt-1.5 text-sm text-muted-foreground">{descripcion}</p> : null}
      </div>
      {accion}
    </div>
  )
}

/** Error recuperable: siempre con su botón de reintentar. */
export function ErrorState({
  mensaje = 'No pudimos cargar estos datos.',
  detalle,
  alReintentar,
  compacto,
}: {
  mensaje?: string
  detalle?: string
  alReintentar?: () => void
  compacto?: boolean
}) {
  return (
    <div
      className={cn(
        'flex w-full flex-col items-center justify-center gap-3 text-center',
        compacto ? 'p-6' : 'min-h-[280px] p-10',
      )}
      role="alert"
    >
      <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-destructive-soft text-destructive-strong">
        <Info size={20} />
      </span>
      <div className="max-w-[420px]">
        <p className="font-semibold text-destructive-strong">{mensaje}</p>
        {detalle ? <p className="mt-1.5 text-sm text-muted-foreground">{detalle}</p> : null}
      </div>
      {alReintentar ? (
        <Button onClick={alReintentar} icono={<RotateCw size={16} aria-hidden="true" />}>
          Reintentar
        </Button>
      ) : null}
    </div>
  )
}

/** Sin permisos: explica qué hacer, no muestra un 403 seco. */
export function NoPermission({
  queIntentas,
  permiso,
  children,
}: {
  queIntentas: string
  permiso?: string
  children?: ReactNode
}) {
  return (
    <div className="flex w-full min-h-[280px] flex-col items-center justify-center gap-3 p-10 text-center">
      <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Lock size={20} />
      </span>
      <div className="max-w-[420px]">
        <p className="font-semibold">No tienes acceso a {queIntentas}</p>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {permiso
            ? `El administrador de la institución puede activarte el permiso «${permiso}» en Configuración.`
            : 'Pídele al administrador de la institución que te habilite este acceso.'}
        </p>
      </div>
      {children}
    </div>
  )
}

/* ══ Aviso en línea ══════════════════════════════════════════ */

export function Nota({
  tono = 'info',
  titulo,
  children,
  accion,
  className,
  icono,
}: {
  tono?: 'info' | 'exito' | 'aviso' | 'peligro' | 'ia'
  titulo?: ReactNode
  children?: ReactNode
  accion?: ReactNode
  className?: string
  icono?: ReactNode
}) {
  const estilos = {
    info: 'border-primary/25 bg-primary-soft',
    exito: 'border-success/25 bg-success-soft',
    aviso: 'border-warning/25 bg-warning-soft',
    peligro: 'border-destructive/25 bg-destructive-soft',
    ia: 'border-ai/25 bg-ai-soft',
  }[tono]

  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-3 rounded-[var(--radius-panel)] border p-3', estilos, className)}>
      <div className="flex min-w-0 flex-1 gap-2.5">
        {icono ? <span aria-hidden="true" className="mt-0.5 shrink-0">{icono}</span> : null}
        <div className="min-w-0 text-sm">
          {titulo ? <p className="font-semibold">{titulo}</p> : null}
          {children ? <div className={cn(titulo ? 'mt-0.5' : '')}>{children}</div> : null}
        </div>
      </div>
      {accion ? <div className="no-imprimir shrink-0">{accion}</div> : null}
    </div>
  )
}

/** Nota informativa con el icono por defecto. */
export function NotaInfo({ titulo, children }: { titulo?: ReactNode; children?: ReactNode }) {
  return (
    <Nota tono="info" titulo={titulo} icono={<Info size={16} aria-hidden="true" />}>
      {children}
    </Nota>
  )
}
