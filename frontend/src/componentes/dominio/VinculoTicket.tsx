import { categoriaDePc } from '../../dominio/categoriaDePc'
import type { TicketDetalle } from '../../api/tipos'
import { SelectorDestinoIncidencia } from './DestinoIncidencia'

export type VinculoTicket = { corregir_origen?: boolean; alcance_incidencia: NonNullable<TicketDetalle['alcance_incidencia']>; sistema_afectado: string; activo_id: string; conjunto_id: string; destino: 'ninguna' | 'equipo' | 'conjunto' }
export function EditorVinculoTicket({ valor, alCambiar, ticket, categoria }: { valor: VinculoTicket; alCambiar: (valor: VinculoTicket) => void; ticket: TicketDetalle; categoria: string }) {
  return <SelectorDestinoIncidencia mostrarTarjetasOrigen ruta={`/tickets/${ticket.id}/vinculos?corregir_origen=true`} categoria={categoria} valor={valor} actual={ticket} alCambiar={datos => alCambiar({ ...valor, ...datos, corregir_origen: true, destino: datos.activo_id ? 'equipo' : datos.conjunto_id ? 'conjunto' : 'ninguna', alcance_incidencia: categoriaDePc(categoria) ? 'programa' : datos.activo_id ? 'equipo' : datos.conjunto_id ? 'conjunto' : 'pendiente' })} />
}
