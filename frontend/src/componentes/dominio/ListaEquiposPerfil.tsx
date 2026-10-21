import { Link } from 'react-router-dom'
import { IconoTipoEquipo } from './IconoTipoEquipo'
import { DisponibilidadBadge } from './Badge'

export type EquipoPerfil = { id: string; nombre?: string | null; tipo?: string | null; estado?: string | null; codigo_patrimonial?: string | null; oficina_nombre?: string | null }
export function ListaEquiposPerfil({ equipos, etiqueta = 'Equipos', enlazar = true }: { equipos: EquipoPerfil[]; etiqueta?: string; enlazar?: boolean }) {
  if (!equipos.length) return <p className="text-sm text-muted-foreground">Sin equipos asignados.</p>
  return <ul aria-label={etiqueta} className="divide-y divide-border">{equipos.map(equipo => <li key={equipo.id} className="grid min-w-0 grid-cols-[22px_minmax(0,1fr)_auto] items-center gap-3 py-2.5">
    <IconoTipoEquipo tipo={equipo.tipo} tamano={22} />
    <div className="min-w-0">{enlazar ? <Link to={`/panel/equipos/${equipo.id}`} className="block truncate text-sm font-semibold hover:underline" title={equipo.nombre || equipo.tipo || 'Equipo'}>{equipo.nombre || equipo.tipo || 'Equipo'}</Link> : <p className="truncate text-sm font-semibold">{equipo.nombre || equipo.tipo}</p>}<p className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-muted-foreground"><span>{equipo.tipo || 'Sin tipo'}</span>{equipo.codigo_patrimonial ? <span>Patrimonio: {equipo.codigo_patrimonial}</span> : null}{equipo.oficina_nombre ? <span>{equipo.oficina_nombre}</span> : null}</p></div>
    {equipo.estado ? <DisponibilidadBadge estado={equipo.estado} tamano="sm" /> : <span />}
  </li>)}</ul>
}
