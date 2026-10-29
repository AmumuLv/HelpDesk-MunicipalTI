import { Clock3, Plus, Save, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { useConfiguracion } from '../../api/hooks'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'
import { Button } from '../base/Button'
import { Checkbox, Input } from '../base/Campo'
import { Nota, Panel } from '../base/Estructura'
import { PrioridadBadge } from './Badge'

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
export function ConfiguracionSla() {
  const config = useConfiguracion()
  const cache = useQueryClient()
  const sesion = useSesion()
  const avisos = useAvisos()
  const [reglas, setReglas] = useState<{ prioridad: string; responder: string; resolver: string }[]>([])
  const [dias, setDias] = useState<number[]>([])
  const [tramos, setTramos] = useState<{ entrada: string; salida: string }[]>([])
  const [pausa, setPausa] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const ultimoFormulario = useRef<string | null>(null)
  const formularioActual = useRef('')
  formularioActual.current = JSON.stringify([reglas, dias, tramos, pausa])
  useEffect(() => {
    const sla = config.data?.sla
    if (!sla) return
    const nuevasReglas = ['critica', 'alta', 'media', 'baja'].map((prioridad, indice) => {
      const regla = sla.reglas.find(r => r.prioridad === prioridad)
      return { prioridad, responder: String(regla?.horas_responder ?? 2 ** indice), resolver: String(regla?.horas_resolver ?? 2 ** (indice + 1)) }
    })
    const actual = formularioActual.current
    const nuevo = JSON.stringify([nuevasReglas, sla.calendario.dias_laborables, sla.calendario.tramos, sla.pausa_fuera_de_horario])
    const editando = ultimoFormulario.current !== null && actual !== ultimoFormulario.current
    ultimoFormulario.current = nuevo
    if (editando) return
    setReglas(nuevasReglas)
    setDias(sla.calendario.dias_laborables)
    setTramos(sla.calendario.tramos.map(t => ({ ...t })))
    setPausa(sla.pausa_fuera_de_horario)
  }, [config.data])
  const guardar = async () => {
    if (guardando) return
    setError('')
    if (reglas.some(r => !r.responder || !r.resolver || !Number.isFinite(Number(r.responder)) || !Number.isFinite(Number(r.resolver)) || Number(r.responder) <= 0 || Number(r.resolver) < Number(r.responder) || Number(r.responder) > 2000 || Number(r.resolver) > 8000)) {
      setError('Usa plazos positivos. La resolución debe ser igual o posterior a la respuesta.'); return
    }
    const ordenados = [...tramos].sort((a, b) => a.entrada.localeCompare(b.entrada))
    if (!dias.length || !ordenados.length || ordenados.some((t, i) => !t.entrada || !t.salida || t.entrada >= t.salida || (i > 0 && ordenados[i - 1].salida > t.entrada))) {
      setError('Elige al menos un día y revisa que los tramos tengan una duración válida y no se solapen.'); return
    }
    setGuardando(true)
    try {
      await api.editar('/configuracion', { sla: { pausa_fuera_de_horario: pausa, reglas: reglas.map(r => ({ prioridad: r.prioridad, horas_responder: Number(r.responder), horas_resolver: Number(r.resolver) })), calendario: { dias_laborables: dias, tramos: ordenados } } })
      await cache.invalidateQueries({ queryKey: ['configuracion'] })
      await config.refetch()
      avisos.exito('SLA y horarios guardados')
    } catch (fallo) { setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar el SLA.') }
    finally { setGuardando(false) }
  }
  return <div className="space-y-5">
    <Panel titulo={<span className="flex items-center gap-2"><Clock3 size={20} className="text-info-strong" />Plazos por prioridad</span>} descripcion="Horas laborables para responder y resolver. Se aplican al crear nuevos tickets.">
      <fieldset disabled={!sesion.esAdmin || guardando} className="grid gap-3 sm:grid-cols-2">
        {reglas.map((r, i) => <div key={r.prioridad} className="rounded-xl border border-border bg-surface-2/50 p-3">
          <PrioridadBadge prioridad={r.prioridad} />
          <div className="mt-3 grid grid-cols-2 gap-3">{(['responder', 'resolver'] as const).map(campo => <Input key={campo} etiqueta={`${campo === 'responder' ? 'Respuesta' : 'Resolución'} ${r.prioridad} (horas)`} type="number" min="0.25" step="0.25" max={campo === 'responder' ? 2000 : 8000} value={r[campo]} onChange={e => setReglas(actuales => actuales.map((regla, indice) => indice === i ? { ...regla, [campo]: e.target.value } : regla))} />)}</div>
        </div>)}
      </fieldset>
    </Panel>
    <Panel titulo="Calendario de atención" descripcion="Los horarios particulares y ausencias se administran en Equipo TI.">
      <fieldset disabled={!sesion.esAdmin || guardando} className="space-y-4">
        <div className="flex flex-wrap gap-3">{DIAS.map((dia, indice) => <Checkbox key={dia} etiqueta={dia} valor={dias.includes(indice)} alCambiar={activo => setDias(actuales => activo ? [...actuales, indice].sort() : actuales.filter(d => d !== indice))} />)}</div>
        {tramos.map((tramo, indice) => <div key={indice} className="grid grid-cols-[1fr_1fr_auto] items-end gap-3 rounded-lg border border-border p-3">
          <Input etiqueta={`Entrada tramo ${indice + 1}`} type="time" value={tramo.entrada} onChange={e => setTramos(actuales => actuales.map((t, i) => i === indice ? { ...t, entrada: e.target.value } : t))} />
          <Input etiqueta={`Salida tramo ${indice + 1}`} type="time" value={tramo.salida} onChange={e => setTramos(actuales => actuales.map((t, i) => i === indice ? { ...t, salida: e.target.value } : t))} />
          <Button aria-label={`Quitar tramo ${indice + 1}`} disabled={tramos.length === 1} onClick={() => setTramos(actuales => actuales.filter((_, i) => i !== indice))}><Trash2 size={16} /></Button>
        </div>)}
        <Button icono={<Plus size={16} />} disabled={tramos.length >= 4} onClick={() => setTramos(actuales => [...actuales, { entrada: '', salida: '' }])}>Añadir tramo</Button>
        <Checkbox etiqueta="Pausar el SLA fuera del horario laboral" valor={pausa} alCambiar={setPausa} />
      </fieldset>
    </Panel>
    {error ? <Nota tono="peligro" titulo="Revisa el SLA y los horarios">{error}</Nota> : null}
    {sesion.esAdmin ? <div className="flex justify-end"><Button variante="primario" icono={<Save size={16} />} cargando={guardando} onClick={() => void guardar()}>Guardar SLA y horarios</Button></div> : null}
  </div>
}
