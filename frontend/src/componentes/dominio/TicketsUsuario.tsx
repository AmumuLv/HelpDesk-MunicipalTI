import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api, consulta } from '../../api/cliente'
import type { TicketResumen } from '../../api/tipos'
import { Select } from '../base/Campo'
import { ErrorState, Panel, SkeletonPanel } from '../base/Estructura'
import { Paginacion } from './DataTable'
import { TicketsAtencion } from './TicketsAtencion'

export function TicketsUsuario({ usuarioId, esPersonalTI }: { usuarioId: string; esPersonalTI: boolean }) {
  const [parametros] = useSearchParams()
  const [pagina, setPagina] = useState(1)
  const [relacion, setRelacion] = useState('todos')
  const [estado, setEstado] = useState(parametros.get('estado') === 'cerrado' ? 'cerrado' : '')
  const [conjunto, setConjunto] = useState('')
  const [equipo, setEquipo] = useState(parametros.get('activo_id') || '')
  const inventario = useQuery({ queryKey: ['usuario', usuarioId, 'inventario-historial'], queryFn: () => api.obtener<{ equipos: { id: string; nombre: string; conjunto_id: string | null }[]; conjuntos: { id: string; nombre: string; tickets: number }[] }>(`/usuarios/${usuarioId}/inventario-historial`) })
  const tickets = useQuery({ queryKey: ['usuario', usuarioId, 'tickets', relacion, estado, conjunto, equipo, pagina], queryFn: () => api.obtener<{ items: TicketResumen[]; total: number; pagina: number; total_paginas: number }>(`/usuarios/${usuarioId}/tickets${consulta({ relacion, estado, conjunto_id: conjunto, activo_id: equipo, pagina, por_pagina: 15 })}`), placeholderData: undefined })
  return <Panel titulo="Historial de tickets" descripcion="Casos de la persona y de sus equipos actuales, incluidos sus antecedentes.">
    <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Select etiqueta="Relación" value={relacion} disabled={Boolean(conjunto || equipo)} onChange={e => { setRelacion(e.target.value); setPagina(1) }} opciones={[{ valor: 'todos', etiqueta: 'Todos los relacionados' }, { valor: 'creados', etiqueta: 'Creados por esta persona' }, { valor: 'afectado', etiqueta: 'Como persona afectada' }, ...(esPersonalTI ? [{ valor: 'asignados', etiqueta: 'Asignados para atender' }] : [])]} />
      <Select etiqueta="Estado" value={estado} onChange={e => { setEstado(e.target.value); setPagina(1) }} opciones={[{ valor: '', etiqueta: 'Todos los estados' }, { valor: 'nuevo', etiqueta: 'Nuevo' }, { valor: 'en_progreso', etiqueta: 'En progreso' }, { valor: 'en_espera', etiqueta: 'En espera' }, { valor: 'cerrado', etiqueta: 'Cerrado' }]} />
      <Select etiqueta="Computadora / conjunto" value={conjunto} onChange={e => { setConjunto(e.target.value); setEquipo(''); setPagina(1) }} opciones={[{ valor: '', etiqueta: 'Todas las computadoras' }, ...(inventario.data?.conjuntos ?? []).map(c => ({ valor: c.id, etiqueta: `${c.nombre} · ${c.tickets}` }))]} />
      <Select etiqueta="Equipo específico" value={equipo} onChange={e => { setEquipo(e.target.value); setPagina(1) }} opciones={[{ valor: '', etiqueta: 'Todos los componentes' }, ...(inventario.data?.equipos ?? []).filter(e => !conjunto || e.conjunto_id === conjunto).map(e => ({ valor: e.id, etiqueta: e.nombre }))]} />
    </div>
    {inventario.isError ? <ErrorState compacto mensaje="No pudimos cargar los filtros de equipos." alReintentar={() => void inventario.refetch()} /> : null}
    {tickets.isPending ? <SkeletonPanel filas={3} /> : tickets.isError ? <ErrorState mensaje="No pudimos cargar los tickets." alReintentar={() => void tickets.refetch()} /> : <><TicketsAtencion tickets={tickets.data.items} /><Paginacion pagina={tickets.data.pagina} totalPaginas={tickets.data.total_paginas} total={tickets.data.total} porPagina={15} alCambiar={setPagina} /></>}
  </Panel>
}
