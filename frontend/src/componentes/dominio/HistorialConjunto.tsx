import { History } from 'lucide-react'
import { useState } from 'react'
import { useTickets } from '../../api/hooks'
import { Button } from '../base/Button'
import { DialogModal } from '../base/Sobreposiciones'
import { ErrorState } from '../base/Estructura'
import { Paginacion } from './DataTable'
import { TicketsAtencion } from './TicketsAtencion'

export function HistorialConjunto({ id, nombre, equipoId, etiqueta, estado }: { id?: string | null; nombre?: string | null; equipoId?: string; etiqueta?: string; estado?: 'cerrado' }) {
  const [abierto, setAbierto] = useState(false)
  const [pagina, setPagina] = useState(1)
  const tickets = useTickets({ ...(equipoId ? { activo_id: equipoId } : { conjunto_id: id ?? undefined }), estado, pagina, por_pagina: 15 }, Boolean(abierto && (id || equipoId)))
  if (!id && !equipoId) return null
  return <><Button variante="fantasma" tamano="sm" icono={<History size={15} />} onClick={() => { setPagina(1); setAbierto(true) }}>{etiqueta || (equipoId ? 'Historial del equipo' : 'Historial del conjunto')}</Button><DialogModal tamano="xl" abierto={abierto} alCerrar={() => setAbierto(false)} titulo={nombre || 'Historial del conjunto'} descripcion={equipoId ? "Incidencias de este equipo, incluidos sus antecedentes." : "Incidencias de la computadora, sus programas y sus componentes."}>
    {tickets.isPending ? <p role="status">Cargando historial…</p> : tickets.isError ? <ErrorState compacto mensaje="No pudimos cargar el historial." alReintentar={() => void tickets.refetch()} /> : <><TicketsAtencion tickets={tickets.data?.items ?? []} alAbrirTicket={() => setAbierto(false)} />{!tickets.data?.items.length ? <p className="py-4 text-sm text-muted-foreground">Este conjunto todavía no tiene incidencias vinculadas.</p> : null}<Paginacion pagina={pagina} totalPaginas={tickets.data?.total_paginas ?? 1} total={tickets.data?.total ?? 0} porPagina={15} alCambiar={setPagina} /></>}
  </DialogModal></>
}
