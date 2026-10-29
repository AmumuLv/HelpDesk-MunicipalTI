import { Building2, UserRound } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { Input, Select } from '../base/Campo'
import { ErrorState } from '../base/Estructura'

export type DestinoIncidencia = { activo_id: string; conjunto_id: string; sistema_afectado: string }
export type OpcionesDestino = { equipos: { id: string; nombre: string; tipo?: string; codigo?: string; grupo: string; conjunto_id?: string | null }[]; conjuntos: { id: string; nombre: string; grupo: string }[]; grupo_bloqueado?: string | null }
import { categoriaDePc } from '../../dominio/categoriaDePc'
const esComputadora = (tipo?: string) => /^(cpu|laptop|port[aá]til|computadora|pc)$/i.test(tipo || '')

export function SelectorDestinoIncidencia({ ruta, categoria, valor, alCambiar, actual, requerido = true, mostrarTarjetasOrigen = false }: { ruta?: string; categoria: string; valor: DestinoIncidencia; alCambiar: (valor: DestinoIncidencia) => void; actual?: { reporte_para?: string | null; afectado_nombre?: string | null; oficina_nombre?: string | null; activo_nombre?: string | null; conjunto_nombre?: string | null; activo_id?: string | null; conjunto_id?: string | null }; requerido?: boolean; mostrarTarjetasOrigen?: boolean }) {
  const opciones = useQuery({ queryKey: ['destinos-ticket', ruta], queryFn: () => api.obtener<OpcionesDestino>(ruta!), enabled: Boolean(ruta), placeholderData: undefined })
  const [eleccionGrupo, setGrupo] = useState<{ ruta?: string; grupo: string }>({ grupo: 'propios' })
  const programa = categoriaDePc(categoria)
  const todos = opciones.data
  const seleccionado = todos?.equipos.find(e => e.id === valor.activo_id) || todos?.conjuntos.find(c => c.id === valor.conjunto_id)
  const original = todos?.equipos.find(e => e.id === actual?.activo_id) || todos?.conjuntos.find(c => c.id === actual?.conjunto_id)
  const grupoBloqueado = todos?.grupo_bloqueado || (!mostrarTarjetasOrigen ? original?.grupo : undefined)
  const grupo = grupoBloqueado || (programa && !mostrarTarjetasOrigen ? 'propios' : eleccionGrupo.ruta === ruta ? eleccionGrupo.grupo : seleccionado?.grupo || (actual?.reporte_para === 'oficina' ? 'oficina' : 'propios'))
  const computadoras = useMemo(() => (todos?.conjuntos ?? []).filter(c => c.grupo === grupo), [todos, grupo])
  const equipos = useMemo(() => (todos?.equipos ?? []).filter(e => e.grupo === grupo && (!categoria.toLowerCase().includes('formate') || /^(cpu|laptop|computadora|pc)$/i.test(e.tipo || ''))), [todos, grupo, categoria])
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
  }, [todos, programa, valor, computadoras, equipos, categoria, requerido, alCambiar])
  if (!ruta) return null
  if (opciones.isPending) return <p role="status" className="text-sm text-muted-foreground">Cargando sus equipos…</p>
  if (opciones.isError) return <ErrorState compacto mensaje="No pudimos cargar sus equipos." alReintentar={() => void opciones.refetch()} />
  const listado = [...(!categoria.toLowerCase().includes('formate') ? computadoras.map(c => ({ valor: `pc:${c.id}`, etiqueta: requerido ? `${c.nombre} · PC de escritorio` : `Computadora de escritorio · ${c.nombre}` })) : []), ...equipos.filter(e => !programa || (!e.conjunto_id && esComputadora(e.tipo))).map(e => ({ valor: `equipo:${e.id}`, etiqueta: `${!requerido ? `${e.tipo || 'Equipo'} · ` : ''}${e.nombre}${requerido && e.codigo ? ` · ${e.codigo}` : ''}` }))]
  const elegido = valor.activo_id ? `equipo:${valor.activo_id}` : valor.conjunto_id ? `pc:${valor.conjunto_id}` : ''
  if (elegido && !listado.some(e => e.valor === elegido)) listado.unshift({ valor: elegido, etiqueta: actual?.activo_nombre || actual?.conjunto_nombre || seleccionado?.nombre || 'Selección registrada' })
  return <div className="flex flex-col gap-3">
    {mostrarTarjetasOrigen && !grupoBloqueado ? <fieldset><legend className="mb-2 text-sm font-semibold">Registrar incidencia en</legend><div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="Origen del equipo">{[
      { id: 'propios', nombre: 'Equipo de la persona', detalle: actual?.afectado_nombre || 'Persona afectada', Icono: UserRound },
      { id: 'oficina', nombre: 'Equipo compartido de la oficina', detalle: actual?.oficina_nombre || 'Oficina del reporte', Icono: Building2 },
    ].map(({ Icono, ...opcion }) => <button key={opcion.id} type="button" aria-label={opcion.nombre} aria-pressed={grupo === opcion.id} className={`flex min-h-20 items-center gap-3 rounded-xl border p-3 text-left ${grupo === opcion.id ? 'border-accion bg-primary-soft text-primary-strong ring-1 ring-accion' : 'border-border hover:bg-muted'}`} onClick={() => { setGrupo({ ruta, grupo: opcion.id }); alCambiar({ ...valor, activo_id: '', conjunto_id: '' }) }}><Icono size={24} className="shrink-0" aria-hidden="true" /><span><span className="block text-sm font-semibold">{opcion.nombre}</span><span className="mt-1 block text-xs text-muted-foreground">{opcion.detalle}</span></span></button>)}</div></fieldset> : null}
    {!mostrarTarjetasOrigen && !programa && !grupoBloqueado ? <div className="flex gap-1" role="group" aria-label="Origen del equipo">{[{ id: 'propios', nombre: 'Sus equipos' }, { id: 'oficina', nombre: 'De la oficina' }].map(g => <button type="button" key={g.id} aria-pressed={grupo === g.id} className={`rounded-full px-3 py-1.5 text-sm font-medium ${grupo === g.id ? 'bg-primary-soft text-primary-strong ring-1 ring-primary' : 'text-muted-foreground hover:bg-muted'}`} onClick={() => { setGrupo({ ruta, grupo: g.id }); alCambiar({ ...valor, activo_id: '', conjunto_id: '' }) }}>{g.nombre}</button>)}</div> : null}
    <Select etiqueta={!requerido ? '¿En qué equipo te pasa?' : programa ? 'Computadora afectada' : 'Equipo o computadora afectada'} value={elegido} requerido={requerido} placeholder={!requerido ? 'No lo sé' : listado.length ? 'Seleccionar de la lista' : 'Sin equipos registrados'} opciones={listado} onChange={e => { const [tipo, id] = e.target.value.split(':'); const destino = tipo === 'equipo' ? todos?.equipos.find(item => item.id === id) : todos?.conjuntos.find(item => item.id === id); if (destino) setGrupo({ ruta, grupo: destino.grupo }); alCambiar({ ...valor, activo_id: tipo === 'equipo' ? id : '', conjunto_id: tipo === 'pc' ? id : '' }) }} />
    {!listado.length && requerido ? <p className="text-sm text-warning-strong">Primero registra o asigna la computadora o el equipo en Inventario.</p> : null}
    {programa && requerido ? <Input etiqueta="Programa, sistema o correo" maxLength={120} value={valor.sistema_afectado} placeholder="Office, SIGA, correo institucional…" onChange={e => alCambiar({ ...valor, sistema_afectado: e.target.value })} /> : null}
  </div>
}
