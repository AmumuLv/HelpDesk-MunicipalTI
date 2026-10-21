import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { useTecnico } from '../../api/hooks'
import type { HorarioSemanal } from '../../api/tipos'
import { DIAS_TI, horarioBaseTI } from '../../dominio/horario-base'
import { useAvisos } from '../../estado/Avisos'
import { Button } from '../base/Button'
import { Input } from '../base/Campo'
import { ErrorState, Nota, SkeletonPanel } from '../base/Estructura'

type Dias = NonNullable<HorarioSemanal['dias']>

export function HorarioTecnico({ id, nombre, puedeEditar }: { id: string; nombre: string; puedeEditar: boolean }) {
  const consulta = useTecnico(id)
  const invalidar = useQueryClient()
  const avisos = useAvisos()
  const [editados, setEditados] = useState<Dias | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dias: Dias = editados ?? consulta.data?.horario?.dias ?? {}
  const cambiar = (dia: number, cambio: Partial<Dias[number]>) => {
    setEditados({ ...dias, [dia]: { ...(dias[dia] ?? { libre: true, tramos: [] }), ...cambio } })
    setError(null)
  }
  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (!editados || guardando) return
    setGuardando(true)
    setError(null)
    try {
      await api.reemplazar(`/equipo-ti/${id}/horario`, { dias: editados })
      await Promise.all([
        invalidar.invalidateQueries({ queryKey: ['equipo-ti'] }),
        invalidar.invalidateQueries({ queryKey: ['usuario', id] }),
        invalidar.invalidateQueries({ queryKey: ['instalacion'] }),
      ])
      setEditados(null)
      avisos.exito('Horario guardado', nombre)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar el horario.')
    } finally { setGuardando(false) }
  }
  if (consulta.isPending) return <SkeletonPanel filas={3} />
  if (consulta.isError) return <ErrorState mensaje="No pudimos cargar el horario." alReintentar={() => void consulta.refetch()} />
  return (
    <form onSubmit={guardar} aria-label={`Horario de ${nombre}`} className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">Horario base: lunes a viernes, 08:00–13:00 y 14:00–17:00. Descanso: 13:00–14:00. Sábado y domingo no laborables.</p>
      {error ? <Nota tono="peligro" titulo="No se pudo guardar">{error}</Nota> : null}
      {puedeEditar ? <div className="flex flex-wrap gap-2">
        {editados ? <>
          <Button type="submit" variante="primario" cargando={guardando}>Guardar horario</Button>
          <Button disabled={guardando} onClick={() => { setEditados(null); setError(null) }}>Cancelar cambios</Button>
        </> : <Button variante="secundario" onClick={() => setEditados(structuredClone(dias))}>Editar horario</Button>}
        <Button disabled={guardando} onClick={() => { setEditados(horarioBaseTI()); setError(null) }}>Aplicar horario base</Button>
      </div> : null}
      <fieldset disabled={guardando} className="min-w-0 divide-y divide-border rounded-xl border border-border px-3">
        <legend className="sr-only">Jornada semanal</legend>
        {DIAS_TI.map((dia, indice) => {
          const config = dias[indice] ?? { libre: true, tramos: [] }
          const tramos = config.tramos ?? []
          return <div key={dia} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
            <div className="w-28 shrink-0 text-sm font-semibold">{editados ? <label className="flex items-center gap-2">
              <input type="checkbox" checked={!config.libre} onChange={(evento) => cambiar(indice, {
                libre: !evento.target.checked, tramos: evento.target.checked ? horarioBaseTI()[0].tramos : [],
              })} />{dia}
            </label> : dia}</div>
            {config.libre || !tramos.length ? <span className="text-sm text-muted-foreground">No laborable</span> : editados ? (
              <div className="flex min-w-0 flex-1 flex-wrap items-end gap-2">
                {tramos.map((tramo, n) => <div key={n} className="flex min-w-0 items-end gap-2">
                  <Input etiqueta={`Entrada ${dia} ${n + 1}`} type="time" requerido value={tramo.entrada}
                    onChange={(evento) => cambiar(indice, { tramos: tramos.map((t, i) => i === n ? { ...t, entrada: evento.target.value } : t) })} />
                  <Input etiqueta={`Salida ${dia} ${n + 1}`} type="time" requerido value={tramo.salida}
                    onChange={(evento) => cambiar(indice, { tramos: tramos.map((t, i) => i === n ? { ...t, salida: evento.target.value } : t) })} />
                </div>)}
              </div>
            ) : <span className="text-sm tabular-nums">{tramos.map((t) => `${t.entrada}–${t.salida}`).join(' · ')}</span>}
          </div>
        })}
      </fieldset>
    </form>
  )
}
