import { Link } from 'react-router-dom'
import { useZonas } from '../../api/hooks'
import { useSesion } from '../../estado/useSesion'

export function EnlaceOficina({
  id,
  nombre,
  zonaId,
  colorIndice,
}: {
  id?: string | null
  nombre?: string | null
  zonaId?: string | null
  colorIndice?: number
}) {
  const sesion = useSesion()
  const zonas = useZonas({ solo_activas: false })
  const indice = colorIndice ?? zonas.data?.items.find((zona) => zona.id === zonaId)?.color_indice
  /*
    La raya lleva el color de la zona a la que pertenece la oficina. Sin zona no
    hay color propio, y se usa el del texto: gris. Es lo que se conoce y lo que
    marca el sitio de la oficina en la celda aunque el nombre falte.
  */
  const colorRaya = indice !== undefined && indice >= 1 && indice <= 8 ? `var(--zona-${indice})` : 'var(--color-muted-foreground)'
  return (
    <span className="inline-flex min-w-0 max-w-full border-l-2 pl-1.5" style={{ borderColor: colorRaya }}>
      {id && sesion.puede('org.ver') ? (
        <Link className="truncate font-medium text-primary-strong underline-offset-2 hover:underline" to={`/panel/oficinas/${id}`} onClick={(evento) => evento.stopPropagation()}>
          {nombre || 'Ver oficina'}
        </Link>
      ) : <span className="truncate font-medium">{nombre || 'Sin oficina'}</span>}
    </span>
  )
}
