/**
 * El perfil de una persona, tal como se ve en el diálogo de Usuarios y en la página
 * de perfil completo. Un solo componente para los dos: antes eran dos montajes
 * distintos del mismo dato y se veían distinto.
 *
 * Lo que cambia respecto a una lista de datos:
 *
 * - **Cabecera con el color de la zona.** La banda de arriba y el anillo del avatar
 *   llevan el color de la zona a la que pertenece la persona. Es el mismo código de
 *   color que usan `ZonaBadge` y `EnlaceOficina`, no uno nuevo: identifica la zona de
 *   un vistazo sin tener que leer el nombre.
 * - **Cada dato con su icono.** Zona, oficina, cargo y teléfono no son cuatro líneas
 *   de texto suelto: son cuatro tarjetas con un dibujo al lado que dice de qué va.
 * - **Los números, todos igual.** Antes «0» (tickets), «1 equipo» y «Activada» salían
 *   en el mismo cuerpo de texto pero con tamaños distintos segúncupiera: 0 en grande,
 *   1 en pequeño y una palabra. Ahora las tres métricas comparten cuerpo, cifra de
 *   tabular y alineación, y 0 se lee como lo que es.
 * - **Relleno.** Las tarjetas llevan fondo de superficie, no el mismo blanco del
 *   diálogo: en claro separa los bloques y en oscuro evita que todo sea un solo gris.
 */

import { Bot, Briefcase, Building2, Mail, MapPin, Phone, Ticket } from 'lucide-react'

import { useFotoUsuario } from '../../api/fotos'
import type { UsuarioDetalle } from '../../api/tipos'
import { useZonas } from '../../api/hooks'
import { cn } from '../../lib/cn'
import { plural } from '../../dominio/formato'
import { Avatar, InsigniaRol } from '../base/Estructura'
import { EtiquetaEstadoActivo } from './EtiquetaActivo'
import { ZonaBadge } from './ZonaBadge'
import { IconoTipoEquipo } from './IconoTipoEquipo'

/** Una tarjeta de dato: icono, rótulo arriba y valor debajo. */
function TarjetaDato({
  icono: Icono,
  rotulo,
  valor,
  color,
  sinDato,
}: {
  icono: typeof MapPin
  rotulo: string
  valor?: string | null
  /** Tinte de fondo y del icono. Sin él, el color apagado del tema. */
  color?: string
  sinDato?: boolean
}) {
  return (
    <div className="flex min-w-0 items-start gap-2.5 rounded-[var(--radius-panel)] border border-border bg-surface-2/70 p-2.5">
      <span
        aria-hidden="true"
        className="flex size-8 shrink-0 items-center justify-center rounded-lg"
        style={
          color
            ? { backgroundColor: `color-mix(in srgb, ${color} 18%, transparent)`, color }
            : undefined
        }
      >
        <Icono size={16} />
      </span>
      <span className="min-w-0">
        {/* El rótulo es corto y en versalitas: identifica sin competir con el dato. */}
        <span className="block text-2xs font-semibold uppercase tracking-wide text-muted-foreground">
          {rotulo}
        </span>
        <span
          className={cn(
            'mt-0.5 block text-sm leading-snug break-words',
            sinDato ? 'text-muted-foreground italic' : 'font-medium',
          )}
        >
          {valor?.trim() ? valor : 'Sin indicar'}
        </span>
      </span>
    </div>
  )
}

/**
 * Una métrica: cifra grande y rótulo debajo, siempre con la misma caja.
 *
 * `tabular-nums` para que las cifras ocupen el mismo ancho —sin eso el 1 se ve más
 * estrecho que el 8 y la fila parece torcida— y el mismo cuerpo para las tres.
 */
function Metrica({
  valor,
  rotulo,
  icono: Icono,
  color,
  detalle,
}: {
  valor: string
  rotulo: string
  icono: typeof Ticket
  color?: string
  detalle?: string
}) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-0.5 rounded-[var(--radius-panel)] border border-border bg-surface-2/70 px-3 py-2.5 text-center">
      <Icono size={15} aria-hidden="true" className="shrink-0" style={color ? { color } : undefined} />
      <span className="text-xl leading-tight font-bold tabular-nums" style={color ? { color } : undefined}>
        {valor}
      </span>
      <span className="text-2xs font-semibold uppercase tracking-wide text-muted-foreground">{rotulo}</span>
      {detalle ? <span className="text-2xs text-muted-foreground">{detalle}</span> : null}
    </div>
  )
}

export function CuerpoPerfilUsuario({
  usuario,
  acciones,
}: {
  usuario: UsuarioDetalle
  /** Acciones de la cuenta: desactivar, contraseña, abrir perfil completo. */
  acciones?: React.ReactNode
}) {
  const zonas = useZonas({ solo_activas: false })
  const foto = useFotoUsuario(usuario.id, usuario.tiene_foto)
  const colorZona = (() => {
    const zona = zonas.data?.items.find((z) => z.id === usuario.zona_id)
    const indice = zona?.color_indice
    return indice !== undefined && indice >= 1 && indice <= 8 ? `var(--zona-${indice})` : null
  })()

  const equipos = usuario.equipos_responsable ?? []
  const tickets = usuario.tickets_activos ?? 0

  return (
    <div className="flex flex-col gap-5">
      {/* ── Cabecera ──────────────────────────────────────────────────────
          La banda lleva el color de la zona. Sin zona no lleva color: se queda
          con el fondo del diálogo, que es lo que ya se veía, en lugar de
          inventar un color que no significa nada. */}
      <header
        className="-mx-1 -mt-1 rounded-b-[var(--radius-panel)] px-4 pt-4 pb-4"
        style={
          colorZona
            ? {
                background: `linear-gradient(180deg, color-mix(in srgb, ${colorZona} 22%, transparent) 0%, transparent 100%)`,
              }
            : undefined
        }
      >
        <div className="flex items-start gap-3.5">
          <span
            className="shrink-0 rounded-full"
            style={colorZona ? { boxShadow: `0 0 0 3px color-mix(in srgb, ${colorZona} 45%, transparent)` } : undefined}
          >
            <Avatar nombre={usuario.nombre} tamano="lg" foto={foto} className="size-14 text-lg" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-lg leading-tight font-bold">{usuario.nombre}</h3>
            <p className="mt-0.5 flex min-w-0 items-center gap-1.5 text-sm text-muted-foreground">
              <Mail size={13} aria-hidden className="shrink-0" />
              <span className="truncate">{usuario.email || 'Sin correo registrado'}</span>
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <InsigniaRol rol={usuario.rol} superadministrador={usuario.superadministrador} />
              <EtiquetaEstadoActivo activo={usuario.activo} />
              {usuario.zona_nombre || usuario.oficina_nombre ? (
                <ZonaBadge id={usuario.zona_id} nombre={usuario.zona_nombre} />
              ) : null}
            </div>
          </div>
        </div>
      </header>

      {/* ── Dónde está y qué cargo tiene ─────────────────────────────────── */}
      <section aria-label="Datos de la persona" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <TarjetaDato icono={MapPin} rotulo="Zona" valor={usuario.zona_nombre} color={colorZona ?? undefined} />
        <TarjetaDato icono={Building2} rotulo="Oficina" valor={usuario.oficina_nombre} color={colorZona ?? undefined} />
        <TarjetaDato icono={Briefcase} rotulo="Cargo" valor={usuario.cargo} />
        <TarjetaDato
          icono={Phone}
          rotulo={usuario.anexo ? 'Teléfono y anexo' : 'Teléfono'}
          valor={[usuario.telefono, usuario.anexo && `anexo ${usuario.anexo}`].filter(Boolean).join(' · ')}
        />
      </section>

      {/* ── Actividad: las tres cifras, del mismo tamaño ─────────────────── */}
      <section aria-label="Actividad">
        <p className="mb-1.5 text-2xs font-semibold uppercase tracking-wide text-muted-foreground">Actividad</p>
        <div className="grid grid-cols-3 gap-2">
          <Metrica
            icono={Ticket}
            rotulo={tickets === 1 ? 'Ticket abierto' : 'Tickets abiertos'}
            valor={String(tickets)}
            detalle={tickets === 0 ? 'Ninguno pendiente' : undefined}
          />
          <Metrica
            icono={Building2}
            rotulo={equipos.length === 1 ? 'Equipo' : 'Equipos'}
            valor={String(equipos.length)}
            detalle={equipos.length === 0 ? 'Sin asignar' : 'a su cargo'}
          />
          <Metrica
            icono={Bot}
            rotulo="Ayuda IA"
            valor={usuario.recomendaciones_ia ? 'Sí' : 'No'}
            detalle={usuario.recomendaciones_ia ? 'Sugiere soluciones' : 'Desactivada'}
          />
        </div>
      </section>

      {/* ── Equipos a su cargo ──────────────────────────────────────────── */}
      <section aria-label="Equipos a su cargo">
        <p className="mb-1.5 text-2xs font-semibold uppercase tracking-wide text-muted-foreground">
          Equipos a su cargo
          <span className="ml-1.5 font-normal normal-case">{plural(equipos.length, 'equipo')}</span>
        </p>
        {equipos.length ? (
          <ul className="divide-y divide-border overflow-hidden rounded-[var(--radius-panel)] border border-border">
            {equipos.slice(0, 5).map((equipo) => (
              <li key={equipo.id} className="flex items-center gap-2.5 bg-surface-2/50 px-3 py-2">
                <span
                  aria-hidden="true"
                  className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-background/60"
                >
                  <IconoTipoEquipo tipo={equipo.tipo} tamano={17} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{equipo.nombre}</span>
                  {equipo.tipo ? <span className="block text-2xs text-muted-foreground">{equipo.tipo}</span> : null}
                </span>
                {/* El código va en su propia columna y en cifra de tabular: son
                    dígitos de lectura, no un texto más de la línea. */}
                <span className="shrink-0 text-right text-2xs tabular-nums text-muted-foreground">
                  {equipo.codigo_patrimonial || 'Sin código'}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-[var(--radius-panel)] border border-border bg-surface-2/50 px-3 py-2.5 text-sm text-muted-foreground">
            No tiene equipos asignados.
          </p>
        )}
        {equipos.length > 5 ? <p className="mt-2 text-sm text-muted-foreground">Mostrando 5 de {equipos.length} equipos. Abre el perfil completo para consultar todos.</p> : null}
      </section>

      {acciones}
    </div>
  )
}
