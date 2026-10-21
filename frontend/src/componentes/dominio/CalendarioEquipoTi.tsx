import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCalendarioEquipo } from '../../api/hooks'
import { fechaCorta, hoy, sumarDias } from '../../dominio/formato'
import { Button } from '../base/Button'
import { Select } from '../base/Campo'
import { ErrorState, Nota, SkeletonPanel } from '../base/Estructura'
import { Paginacion } from './DataTable'
import { DIAS_TI } from '../../dominio/horario-base'

function lunes(fecha: string) {
  const dia = new Date(`${fecha}T12:00:00`).getDay()
  return sumarDias(fecha, -((dia + 6) % 7))
}

export function CalendarioEquipoTi({ tecnicoInicial = '' }: { tecnicoInicial?: string }) {
  const [desde, setDesde] = useState(() => lunes(hoy()))
  const [filtro, setFiltro] = useState(tecnicoInicial)
  const [pagina, setPagina] = useState(1)
  const hasta = sumarDias(desde, 6)
  const calendario = useCalendarioEquipo(desde, hasta)
  const items = calendario.data?.items ?? []
  const tecnicos = [...new Map(items.map((fila) => [fila.tecnico_id, { id: fila.tecnico_id, nombre: fila.tecnico_nombre, carga: fila.carga_pendiente }])).values()]
  const personasVisibles = tecnicos.filter((t) => !filtro || t.id === filtro)
  const paginaActual = Math.min(pagina, Math.max(1, Math.ceil(personasVisibles.length / 10)))
  return <div className="flex flex-col gap-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <Select etiqueta="Persona en el calendario" className="w-full sm:max-w-xs" value={filtro} placeholder="Todo el equipo"
        opciones={tecnicos.map((t) => ({ valor: t.id, etiqueta: t.nombre }))} onChange={(evento) => { setFiltro(evento.target.value); setPagina(1) }} />
      <div className="flex flex-wrap items-center gap-2">
        <Button tamano="sm" onClick={() => setDesde(sumarDias(desde, -7))}>Semana anterior</Button>
        <Button tamano="sm" onClick={() => setDesde(lunes(hoy()))}>Esta semana</Button>
        <Button tamano="sm" onClick={() => setDesde(sumarDias(desde, 7))}>Semana siguiente</Button>
      </div>
    </div>
    <p className="text-sm font-semibold">Del {fechaCorta(desde)} al {fechaCorta(hasta)}</p>
    <p className="text-sm text-muted-foreground">Disponibilidad prevista y vencimientos de tickets abiertos. Los pendientes junto al nombre son la carga actual; no representan una predicción por día.</p>
    {calendario.isPending ? <SkeletonPanel filas={3} /> : calendario.isError ? (
      <ErrorState mensaje="No pudimos cargar el calendario." alReintentar={() => void calendario.refetch()} />
    ) : !personasVisibles.length ? <Nota>No hay integrantes activos para este filtro.</Nota> : (
      <div className="overflow-x-auto rounded-xl border border-border">
        <table aria-label="Planificación semanal del equipo TI" className="w-full min-w-[900px] border-collapse text-left text-sm">
          <thead className="bg-surface-2"><tr>
            <th scope="col" className="p-3">Persona / pendientes actuales</th>
            {DIAS_TI.map((dia, indice) => <th scope="col" key={dia} className="p-2 text-center font-semibold">
              {dia.slice(0, 3)}<span className="block text-2xs font-normal text-muted-foreground">{fechaCorta(sumarDias(desde, indice))}</span>
            </th>)}
          </tr></thead>
          <tbody className="divide-y divide-border">
            {personasVisibles.slice((paginaActual - 1) * 10, paginaActual * 10).map((tecnico) => <tr key={tecnico.id}>
              <th scope="row" className="max-w-48 p-3 font-medium"><Link to={`/panel/equipo-ti/${tecnico.id}`} className="text-primary-strong hover:underline">{tecnico.nombre}</Link>
                <span className="mt-1 block text-2xs font-normal text-muted-foreground">{tecnico.carga} pendientes ahora</span>
              </th>
              {DIAS_TI.map((dia, indice) => {
                const fila = items.find((f) => f.tecnico_id === tecnico.id && f.fecha === sumarDias(desde, indice))
                const estado = fila?.ausencia || (fila?.feriado ? 'No laborable' : fila?.libre ? 'No laborable' : `${fila?.horas_disponibles ?? 0} h`)
                return <td key={dia} className="p-2 text-center align-top">
                  <span className={`inline-block rounded-lg px-2 py-1 text-2xs ${fila?.ausencia ? 'bg-warning-soft font-semibold text-warning-strong' : !fila?.horas_disponibles ? 'bg-muted text-muted-foreground' : 'bg-success-soft text-success-strong'}`}>{estado}</span>
                  {fila?.tramos.map((tramo) => <span key={tramo.entrada} className="mt-1 block text-2xs text-muted-foreground">{tramo.entrada}–{tramo.salida}</span>)}
                  {fila && fila.vencimientos > 0 ? <span className="mt-2 block text-2xs font-semibold text-warning-strong">{fila.vencimientos} {fila.fecha < hoy() ? 'vencidos' : 'vencen'}</span> : null}
                </td>
              })}
            </tr>)}
          </tbody>
        </table>
      </div>
    )}
    {!calendario.isPending && !calendario.isError && personasVisibles.length > 10 && <Paginacion pagina={paginaActual} totalPaginas={Math.ceil(personasVisibles.length / 10)} total={personasVisibles.length} porPagina={10} alCambiar={setPagina} />}
  </div>
}
