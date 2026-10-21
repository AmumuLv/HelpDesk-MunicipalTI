import { Link, useNavigate } from 'react-router-dom'
import type { TicketResumen } from '../../api/tipos'
import { DataTable, type ColumnaTabla } from './DataTable'
import { EstadoBadge, PrioridadBadge } from './Badge'
import { Ubicacion } from './Ubicacion'
import { EquipoTicket } from './EquipoTicket'
import { tonoUrgenciaTicket } from '../../dominio/estados'

const columnasTicket = (alAbrirTicket?: () => void): ColumnaTabla<TicketResumen>[] => [
  { accessorKey: 'codigo', header: 'Ticket', meta: { ancho: '29%' }, cell: ({ row }) => <Link to={`/panel/tickets/${row.original.id}`} onClick={() => alAbrirTicket?.()} className="block min-w-0"><span className="block font-mono text-2xs font-bold">{row.original.codigo}</span><span className="line-clamp-2 font-medium" title={row.original.asunto}>{row.original.asunto}</span></Link> },
  { accessorKey: 'afectado_nombre', header: 'Afectado', meta: { celdaLibre: true, ancho: '25%' }, cell: ({ row }) => <span className="block min-w-0 overflow-hidden"><span className="block truncate" title={row.original.afectado_nombre}>{row.original.afectado_nombre}</span><Ubicacion oficinaId={row.original.oficina_id} oficinaNombre={row.original.oficina_nombre} zonaId={row.original.zona_id} zonaNombre={row.original.zona_nombre} /></span> },
  { accessorKey: 'estado', header: 'Estado y prioridad', meta: { celdaLibre: true, ancho: '23%' }, cell: ({ row }) => <span className="flex flex-col items-start gap-1.5"><EstadoBadge estado={row.original.estado} tamano="sm" /><PrioridadBadge prioridad={row.original.prioridad} tamano="sm" /></span> },
  { id: 'equipo', header: 'Equipo', meta: { celdaLibre: true, ancho: '23%' }, cell: ({ row }) => <EquipoTicket ticket={row.original} /> },
]
export function TicketsAtencion({ tickets, alAbrirTicket }: { tickets: TicketResumen[]; alAbrirTicket?: () => void }) {
  const navegar = useNavigate()
  return <DataTable className="[&_table]:min-w-0" columnas={columnasTicket(alAbrirTicket)} datos={tickets} claveFila={t => t.id} permitirOrdenar={false} alPulsarFila={t => { alAbrirTicket?.(); navegar(`/panel/tickets/${t.id}`) }} tonoFila={t => tonoUrgenciaTicket(t)} />
}
