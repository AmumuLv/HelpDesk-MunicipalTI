import { Link } from 'react-router-dom'
import type { TicketResumen } from '../../api/tipos'
import { IconoTipoEquipo } from './IconoTipoEquipo'

export function EquipoTicket({ ticket }: { ticket: TicketResumen }) {
  const nombre = ticket.activo_nombre || ticket.conjunto_nombre || ticket.activo_tipo || 'Sin equipo vinculado'
  return <div className="flex min-w-0 items-start gap-2"><IconoTipoEquipo tipo={ticket.activo_tipo} tamano={17} /><div className="min-w-0"><span className="block break-words font-medium">{ticket.activo_id ? <Link to={`/panel/equipos/${ticket.activo_id}`} className="hover:text-primary-strong hover:underline">{nombre}</Link> : nombre}</span>{ticket.activo_nombre && ticket.conjunto_nombre && ticket.activo_nombre !== ticket.conjunto_nombre ? <span className="block truncate text-xs text-muted-foreground" title={ticket.conjunto_nombre}>{ticket.conjunto_nombre}</span> : null}</div></div>
}
