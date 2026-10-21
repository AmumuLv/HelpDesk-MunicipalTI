import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { IconoTipoEquipo } from './IconoTipoEquipo'
import { Button } from '../base/Button'

type Conjunto = { id: string; nombre: string; numero: number; total_activos: number; siguiente_numero_equipo: number; componentes?: { id: string; tipo: string; nombre?: string; numero_equipo?: number }[] }
export function DisponibilidadConjuntos({ oficinaId, conjuntoId, equipoActualId, registrando = false }: { oficinaId?: string; conjuntoId?: string; equipoActualId?: string; registrando?: boolean }) {
  const consulta = useQuery({ queryKey: ['conjuntos-disponibilidad', oficinaId, equipoActualId], queryFn: () => api.obtener<{ items: Conjunto[] }>(`/conjuntos?oficina_id=${oficinaId}`), enabled: Boolean(oficinaId), refetchOnMount: 'always' })
  if (!oficinaId) return null
  const lista = consulta.data?.items ?? []
  const actual = lista.find(c => c.id === conjuntoId)
  const equipo = actual?.componentes?.find(c => c.id === equipoActualId)
  return <div className="rounded-lg border border-border bg-surface-2 p-3 text-sm" aria-label="Numeración de conjuntos">
    {consulta.isPending ? <p>Cargando numeración…</p> : consulta.isError ? <><p>No se pudo consultar la numeración.</p><Button tamano="sm" onClick={() => void consulta.refetch()}>Reintentar</Button></> : <>
      <p className="font-semibold">{actual ? `Pertenece a: ${actual.nombre}` : 'Numeración de esta oficina'}</p>
      {registrando ? <div className="my-2 rounded border border-info-borde bg-info-soft p-2 text-info-strong"><p className="font-bold">Número previsto del nuevo equipo: N°{actual?.siguiente_numero_equipo ?? 1}</p><p className="text-xs">{actual?.total_activos ?? 0} equipos registrados · {((actual?.total_activos ?? 0) + 1)} equipos al guardar. El número se confirma al registrar.</p></div> : equipo ? <p className="my-2 font-bold text-info-strong">Este dispositivo: N°{equipo.numero_equipo}</p> : null}
      <p className="mt-1 text-xs text-muted-foreground">{lista.length ? `Conjuntos de esta oficina: ${lista.map(c => `N°${c.numero}`).join(', ')}.` : 'No hay conjuntos numerados en esta oficina.'}</p>
      {actual?.componentes?.length ? <><p className="mt-2 text-xs text-muted-foreground">{equipoActualId ? 'Otros dispositivos del mismo conjunto' : 'Componentes registrados'}</p><ul className="mt-1 flex flex-wrap gap-2">{actual.componentes.filter(c => c.id !== equipoActualId).map(c => <li key={c.id} className="flex items-center gap-1.5 rounded border border-border bg-surface px-2 py-1"><IconoTipoEquipo tipo={c.tipo} tamano={16} /><span><strong>N°{c.numero_equipo}</strong> · {c.nombre || c.tipo}</span></li>)}</ul></> : null}
    </>}
  </div>
}
