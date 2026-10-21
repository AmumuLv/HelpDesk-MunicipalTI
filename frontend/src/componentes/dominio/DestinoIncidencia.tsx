import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { Input, Select } from '../base/Campo'
import { ErrorState } from '../base/Estructura'

export type DestinoIncidencia = { activo_id: string; conjunto_id: string; sistema_afectado: string }
export type OpcionesDestino = { equipos: { id: string; nombre: string; tipo?: string; codigo?: string; grupo: string; conjunto_id?: string | null }[]; conjuntos: { id: string; nombre: string; grupo: string }[]; grupo_bloqueado?: string | null }
export function categoriaDePc(categoria: string) { const c = categoria.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); return !c.includes('formate') && /programa|sistema|software|correo|cuenta/.test(c) }
const esComputadora = (tipo?: string) => /^(cpu|laptop|port[aá]til|computadora|pc)$/i.test(tipo || '')

export function SelectorDestinoIncidencia({ ruta, categoria, valor, alCambiar, actual, requerido = true }: { ruta?: string; categoria: string; valor: DestinoIncidencia; alCambiar: (valor: DestinoIncidencia) => void; actual?: { activo_nombre?: string | null; conjunto_nombre?: string | null; activo_id?: string | null; conjunto_id?: string | null }; requerido?: boolean }) {
  const opciones = useQuery({ queryKey: ['destinos-ticket', ruta], queryFn: () => api.obtener<OpcionesDestino>(ruta!), enabled: Boolean(ruta), placeholderData: undefined })
  const [eleccionGrupo, setGrupo] = useState<{ ruta?: string; grupo: string }>({ grupo: 'propios' })
  const programa = categoriaDePc(categoria)
  const todos = opciones.data
  const seleccionado = todos?.equipos.find(e => e.id === valor.activo_id) || todos?.conjuntos.find(c => c.id === valor.conjunto_id)
  const original = todos?.equipos.find(e => e.id === actual?.activo_id) || todos?.conjuntos.find(c => c.id === actual?.conjunto_id)
  const grupoBloqueado = todos?.grupo_bloqueado || original?.grupo
  const grupo = grupoBloqueado || (programa ? 'propios' : eleccionGrupo.ruta === ruta ? eleccionGrupo.grupo : seleccionado?.grupo || 'propios')
  const computadoras = (todos?.conjuntos ?? []).filter(c => c.grupo === grupo)
  const equipos = (todos?.equipos ?? []).filter(e => e.grupo === grupo && (!categoria.toLowerCase().includes('formate') || /^(cpu|laptop|computadora|pc)$/i.test(e.tipo || '')))
  useEffect(() => {
    if (!todos) return
    if (categoria.toLowerCase().includes('formate') && (valor.conjunto_id || (valor.activo_id && !equipos.some(e => e.id === valor.activo_id)))) {
      alCambiar({ ...valor, activo_id: '', conjunto_id: '' }); return
    }
    if (programa) {
      const equipo = todos.equipos.find(e => e.id === valor.activo_id)
      if (equipo && !equipo.conjunto_id && esComputadora(equipo.tipo)) return
      const individuales = equipos.filter(e => !e.conjunto_id && esComputadora(e.tipo))
      const id = equipo?.conjunto_id || valor.conjunto_id || (requerido && computadoras.length + individuales.length === 1 ? computadoras[0]?.id : '') || ''
      if (valor.activo_id || id !== valor.conjunto_id) { alCambiar({ ...valor, activo_id: '', conjunto_id: id }); return }
      if (requerido && !id && !valor.activo_id && computadoras.length === 0 && individuales.length === 1) alCambiar({ ...valor, activo_id: individuales[0].id, conjunto_id: '' })
    }
  }, [todos, programa, valor, computadoras, alCambiar])
  if (!ruta) return <p className="text-sm text-muted-foreground">Selecciona primero a la persona afectada.</p>
  if (opciones.isPending) return <p role="status" className="text-sm text-muted-foreground">Cargando sus equipos…</p>
  if (opciones.isError) return <ErrorState compacto mensaje="No pudimos cargar sus equipos." alReintentar={() => void opciones.refetch()} />
  const listado = [...(!categoria.toLowerCase().includes('formate') ? computadoras.map(c => ({ valor: `pc:${c.id}`, etiqueta: requerido ? `${c.nombre} · PC de escritorio` : `Computadora de escritorio · ${c.nombre}` })) : []), ...equipos.filter(e => !programa || (!e.conjunto_id && esComputadora(e.tipo))).map(e => ({ valor: `equipo:${e.id}`, etiqueta: `${!requerido ? `${e.tipo || 'Equipo'} · ` : ''}${e.nombre}${requerido && e.codigo ? ` · ${e.codigo}` : ''}` }))]
  const elegido = valor.activo_id ? `equipo:${valor.activo_id}` : valor.conjunto_id ? `pc:${valor.conjunto_id}` : ''
  if (elegido && !listado.some(e => e.valor === elegido)) listado.unshift({ valor: elegido, etiqueta: actual?.activo_nombre || actual?.conjunto_nombre || seleccionado?.nombre || 'Selección registrada' })
  return <div className="flex flex-col gap-3">
    {!programa && !grupoBloqueado ? <div className="flex gap-1" role="group" aria-label="Origen del equipo">{[{ id: 'propios', nombre: 'Sus equipos' }, { id: 'oficina', nombre: 'De la oficina' }].map(g => <button type="button" key={g.id} aria-pressed={grupo === g.id} className={`rounded-full px-3 py-1.5 text-sm font-medium ${grupo === g.id ? 'bg-primary-soft text-primary-strong ring-1 ring-primary' : 'text-muted-foreground hover:bg-muted'}`} onClick={() => { setGrupo({ ruta, grupo: g.id }); alCambiar({ ...valor, activo_id: '', conjunto_id: '' }) }}>{g.nombre}</button>)}</div> : null}
    <Select etiqueta={!requerido ? '¿En qué equipo te pasa?' : programa ? 'Computadora afectada' : 'Equipo o computadora afectada'} value={elegido} requerido={requerido} placeholder={!requerido ? 'No lo sé' : listado.length ? 'Seleccionar de la lista' : 'Sin equipos registrados'} opciones={listado} onChange={e => { const [tipo, id] = e.target.value.split(':'); alCambiar({ ...valor, activo_id: tipo === 'equipo' ? id : '', conjunto_id: tipo === 'pc' ? id : '' }) }} />
    {!listado.length && requerido ? <p className="text-sm text-warning-strong">Primero registra o asigna la computadora o el equipo en Inventario.</p> : null}
    {programa && requerido ? <Input etiqueta="Programa, sistema o correo" maxLength={120} value={valor.sistema_afectado} placeholder="Office, SIGA, correo institucional…" onChange={e => alCambiar({ ...valor, sistema_afectado: e.target.value })} /> : null}
  </div>
}
