import type { TicketDetalle } from '../../api/tipos'
import { SelectorDestinoIncidencia, categoriaDePc } from './DestinoIncidencia'

export type VinculoTicket = { alcance_incidencia: NonNullable<TicketDetalle['alcance_incidencia']>; sistema_afectado: string; activo_id: string; conjunto_id: string; destino: 'ninguna' | 'equipo' | 'conjunto' }
export function EditorVinculoTicket({ valor, alCambiar, ticket, categoria }: { valor: VinculoTicket; alCambiar: (valor: VinculoTicket) => void; ticket: TicketDetalle; categoria: string }) {
  return <SelectorDestinoIncidencia ruta={`/tickets/${ticket.id}/vinculos`} categoria={categoria} valor={valor} actual={ticket} alCambiar={datos => alCambiar({ ...valor, ...datos, destino: datos.activo_id ? 'equipo' : datos.conjunto_id ? 'conjunto' : 'ninguna', alcance_incidencia: categoriaDePc(categoria) ? 'programa' : datos.activo_id ? 'equipo' : datos.conjunto_id ? 'conjunto' : 'pendiente' })} />
}
