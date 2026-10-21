/**
 * Distintivo de zona con el color de la zona.
 *
 * Antes el color era un punto de 8 px dentro de una pastilla gris para todas: a
 * simple vista «COMPLEJO» y «DEMUNA» se leían igual. Ahora el fondo y el borde se
 * tiñen con el color de la zona, que es lo que hace falta para distinguirlas de
 * un vistazo al recorrer la tabla.
 *
 * El texto se mantiene en el color normal del tema: el color de la zona puede ser
 * claro u oscuro según el índice, y el texto tiene que seguir teniendo buen
 * contraste en los dos casos.
 */

import { Link } from 'react-router-dom'

import { useZonas } from '../../api/hooks'
import { useSesion } from '../../estado/Sesion'

export function ZonaBadge({ id, nombre, colorIndice }: { id?: string | null; nombre?: string | null; colorIndice?: number }) {
  const sesion = useSesion()
  const zonas = useZonas({ solo_activas: false })
  const indice = colorIndice ?? zonas.data?.items.find((zona) => zona.id === id)?.color_indice
  const conColor = Boolean(nombre) && indice !== undefined && indice >= 1 && indice <= 8
  const color = conColor ? `var(--zona-${indice})` : 'var(--color-muted-foreground)'
  const texto = nombre || 'Sin zona'

  const pastilla = (
    <span
      data-zona={nombre?.trim().toUpperCase()}
      className="inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-semibold"
      style={
        conColor
          ? {
              backgroundColor: `color-mix(in srgb, ${color} 26%, transparent)`,
              borderColor: `color-mix(in srgb, ${color} 62%, transparent)`,
              // El texto lleva el color de la zona mezclado con el del tema: en
              // claro se oscurece y en oscuro se aclara, así siempre contrasta.
              color: `color-mix(in srgb, ${color} 70%, var(--color-foreground))`,
            }
          : {
              backgroundColor: 'var(--color-muted)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-foreground)',
            }
      }
    >
      <span aria-hidden="true" className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <span className="truncate">{texto}</span>
    </span>
  )

  return id && sesion.puede('org.ver') ? (
    <Link className="inline-flex max-w-full" to={`/panel/zonas/${id}`} onClick={(evento) => evento.stopPropagation()}>
      {pastilla}
    </Link>
  ) : (
    pastilla
  )
}