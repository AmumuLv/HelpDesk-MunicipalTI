import { BriefcaseBusiness, CalendarOff, Mail, Plus, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api, erroresDeValidacion } from '../../api/cliente'
import { useAusencias, usePanelEquipo, useTecnicos } from '../../api/hooks'
import type { Ausencia } from '../../api/tipos'
import { DisponibilidadBadge } from '../../componentes/dominio/Badge'
import { KpiCard } from '../../componentes/dominio/KpiCard'
import { ContenidoTab, ErrorState, ListaTabs, Nota, PageHeader, Panel, SkeletonPanel, Tab, TabsPanel } from '../../componentes/base/Estructura'
import { Button } from '../../componentes/base/Button'
import { Input, Select } from '../../componentes/base/Campo'
import { ConfirmDialog, DialogModal } from '../../componentes/base/Sobreposiciones'
import { fechaCorta, hoy, numero } from '../../dominio/formato'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'
import { AvatarTecnico } from '../../componentes/dominio/AvatarTecnico'
import { HorarioTecnico } from '../../componentes/dominio/HorarioTecnico'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { CalendarioEquipoTi } from '../../componentes/dominio/CalendarioEquipoTi'

export function EquipoTi() {
  const sesion = useSesion()
  const avisos = useAvisos()
  const invalidar = useQueryClient()
  const [parametros, setParametros] = useSearchParams()
  const panel = usePanelEquipo()
  const tecnicos = useTecnicos()
  const puedeEditarTodos = sesion.puede('horarios.editar_todos')
  const puedeEditarPropio = sesion.puede('horarios.editar_propio')
  const puedeVerTodos = sesion.puede('horarios.ver_todos')
  const tabSolicitado = parametros.get('tab') || 'disponibilidad'
  const pestana = ['disponibilidad', 'horarios', 'ausencias', 'calendario'].includes(tabSolicitado) ? tabSolicitado : 'disponibilidad'
  const seleccionado = parametros.get('tecnico_id') || sesion.usuario?.id || tecnicos.data?.items[0]?.id || ''
  const tecnico = tecnicos.data?.items.find((t) => t.id === seleccionado)
  const [filtroAusencias, setFiltroAusencias] = useState(parametros.get('tecnico_id') || '')
  const [paginaEquipo, setPaginaEquipo] = useState(1)
  const [paginaAusencias, setPaginaAusencias] = useState(1)
  const [periodo, setPeriodo] = useState('vigentes')
  const ausencias = useAusencias({ tecnico_id: puedeVerTodos ? filtroAusencias || undefined : sesion.usuario?.id })
  const [creando, setCreando] = useState(false)
  const [tecnicoId, setTecnicoId] = useState('')
  const [tipo, setTipo] = useState('Vacaciones')
  const [inicio, setInicio] = useState(hoy())
  const [fin, setFin] = useState(hoy())
  const [motivo, setMotivo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)
  const [borrando, setBorrando] = useState<Ausencia | null>(null)
  const [eliminando, setEliminando] = useState(false)
  useEffect(() => { document.title = 'Equipo TI y horarios - Mesa de Ayuda TI' }, [])
  const refrescar = () => Promise.all([
    invalidar.invalidateQueries({ queryKey: ['equipo-ti'] }),
    invalidar.invalidateQueries({ queryKey: ['ausencias'] }),
    invalidar.invalidateQueries({ queryKey: ['usuario'] }),
    invalidar.invalidateQueries({ queryKey: ['instalacion'] }),
  ])
  const registrar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (guardando || !tecnicoId || !inicio || !fin || fin < inicio) return
    setGuardando(true)
    setErrores({})
    setErrorGeneral(null)
    try {
      await api.crear('/ausencias', { tecnico_id: tecnicoId, tipo, inicio, fin, motivo: motivo.trim() || undefined })
      await refrescar()
      setCreando(false)
      setMotivo('')
      setParametros({ tab: 'ausencias' })
      setFiltroAusencias(puedeVerTodos ? tecnicoId : '')
      avisos.exito('Ausencia registrada')
    } catch (fallo) {
      setErrores(erroresDeValidacion(fallo))
      setErrorGeneral(fallo instanceof Error ? fallo.message : 'No se pudo registrar la ausencia.')
    } finally { setGuardando(false) }
  }
  const eliminar = async () => {
    if (!borrando || eliminando) return
    setEliminando(true)
    try {
      await api.borrar(`/ausencias/${borrando.id}`)
      await refrescar()
      setBorrando(null)
      avisos.exito('Ausencia eliminada')
    } catch (fallo) { avisos.desdeError(fallo) }
    finally { setEliminando(false) }
  }
  const personas = panel.data?.items ?? []
  const filtroEquipo = parametros.get('filtro') || 'todos'
  const personasFiltradas = personas.filter((t) => filtroEquipo === 'disponibles' ? t.estado === 'disponible' : filtroEquipo === 'ausentes' ? t.ausencias.length > 0 : filtroEquipo === 'pendientes' ? t.carga_asignados > 0 : true)
  const filtrarEquipo = (filtro: string) => { setPaginaEquipo(1); setParametros({ tab: 'disponibilidad', filtro }) }
  const visibles = (ausencias.data?.items ?? []).filter((a) => periodo === 'todas' || a.fin >= hoy())
  const paginaEquipoActual = Math.min(paginaEquipo, Math.max(1, Math.ceil(personasFiltradas.length / 10)))
  const paginaAusenciasActual = Math.min(paginaAusencias, Math.max(1, Math.ceil(visibles.length / 10)))
  return <>
    <PageHeader titulo="Equipo TI y horarios" descripcion="Disponibilidad, jornada y ausencias. Los datos personales se comparten con Usuarios."
      acciones={<>
        {sesion.esAdmin ? <Button asChild variante="secundario"><Link to="/panel/usuarios?crear=tecnico">Registrar técnico</Link></Button> : null}
        {puedeEditarTodos || puedeEditarPropio ? <Button variante="destacado" icono={<Plus size={16} />} onClick={() => {
          setTecnicoId(seleccionado); setInicio(hoy()); setFin(hoy()); setMotivo(''); setErrores({}); setErrorGeneral(null); setCreando(true)
        }}>Registrar ausencia</Button> : null}
      </>} />
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {([
        { filtro: 'todos', etiqueta: 'Personas en el equipo', valor: personas.length, icono: <Users size={16} /> },
        { filtro: 'disponibles', etiqueta: 'Disponibles ahora', valor: personas.filter((t) => t.estado === 'disponible').length, tono: 'exito' as const },
        { filtro: 'ausentes', etiqueta: 'Ausentes hoy', valor: personas.filter((t) => t.ausencias.length > 0).length, tono: 'aviso' as const, icono: <CalendarOff size={16} /> },
        { filtro: 'pendientes', etiqueta: 'Tickets abiertos', valor: personas.reduce((n, t) => n + t.carga_asignados, 0) },
      ]).map((indicador) => <button key={indicador.filtro} type="button" aria-label={`${indicador.etiqueta}: ver integrantes`} aria-pressed={pestana === 'disponibilidad' && filtroEquipo === indicador.filtro}
        className="cursor-pointer rounded-[var(--radius-panel)] text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary aria-pressed:ring-2 aria-pressed:ring-primary/40"
        onClick={() => filtrarEquipo(indicador.filtro)}>
        <KpiCard {...indicador} cargando={panel.isLoading} detalle="Ver integrantes →" />
      </button>)}
    </div>
    <TabsPanel valor={pestana} alCambiar={(tab) => setParametros({ tab })} className="flex flex-col gap-4">
      <ListaTabs><Tab valor="disponibilidad">Disponibilidad</Tab><Tab valor="horarios">Horarios</Tab><Tab valor="ausencias">Ausencias</Tab><Tab valor="calendario">Calendario semanal</Tab></ListaTabs>
      <ContenidoTab valor="disponibilidad">
        <Panel titulo="Estado del equipo" descripcion="Fuera de horario y no laborable son distintos de una ausencia registrada.">
          <Select etiqueta="Mostrar integrantes" className="mb-3 max-w-xs" value={filtroEquipo} opciones={[{ valor: 'todos', etiqueta: 'Todo el equipo' }, { valor: 'disponibles', etiqueta: 'Disponibles ahora' }, { valor: 'ausentes', etiqueta: 'Ausentes hoy' }, { valor: 'pendientes', etiqueta: 'Con tickets abiertos' }]} onChange={(evento) => filtrarEquipo(evento.target.value)} />
          {panel.isLoading ? <SkeletonPanel filas={4} /> : panel.isError ? <ErrorState mensaje="No pudimos cargar el equipo." alReintentar={() => void panel.refetch()} /> : !personasFiltradas.length ? <Nota>No hay integrantes para este filtro.</Nota> : (
            <ul className="divide-y divide-border">{personasFiltradas.slice((paginaEquipoActual - 1) * 10, paginaEquipoActual * 10).map((t) => <li key={t.tecnico_id} className="flex flex-wrap items-center gap-3 py-3">
              <AvatarTecnico id={t.tecnico_id} nombre={t.tecnico_nombre} tieneFoto={t.tiene_foto} />
              <div className="min-w-0 flex-1">
                <Link to={`/panel/equipo-ti/${t.tecnico_id}`} className="font-semibold text-foreground hover:underline">{t.tecnico_nombre}</Link>
                <div className="mt-1 flex min-w-0 flex-col gap-1 text-xs text-muted-foreground">
                  {t.cargo && !t.cargo.includes('@') ? <span className="inline-flex min-w-0 items-center gap-1.5"><BriefcaseBusiness size={12} className="shrink-0" /><span className="truncate" title={t.cargo}>{t.cargo}</span></span> : null}
                  {t.email ? <span className="inline-flex min-w-0 items-center gap-1.5"><Mail size={12} className="shrink-0" /><span className="truncate" title={t.email}>{t.email}</span></span> : null}
                </div>
                <p className="mt-1 text-2xs text-muted-foreground">{numero(t.carga_asignados)} pendientes · {numero(t.carga_espera)} en espera</p>
              </div>
              <DisponibilidadBadge estado={t.estado} etiqueta={t.etiqueta} />
            </li>)}</ul>
          )}
          {personasFiltradas.length > 10 && <Paginacion pagina={paginaEquipoActual} totalPaginas={Math.ceil(personasFiltradas.length / 10)} total={personasFiltradas.length} porPagina={10} alCambiar={setPaginaEquipo} />}
        </Panel>
      </ContenidoTab>
      <ContenidoTab valor="horarios">
        <Panel titulo="Horario semanal" descripcion="La jornada tiene dos turnos y una hora de descanso.">
          {tecnicos.isError ? <ErrorState mensaje="No pudimos cargar el equipo." alReintentar={() => void tecnicos.refetch()} /> : tecnicos.isPending ? <SkeletonPanel /> : <>
            <Select etiqueta="Persona del horario" className="mb-4 max-w-sm" value={seleccionado}
              opciones={(tecnicos.data?.items ?? []).map((t) => ({ valor: t.id, etiqueta: t.nombre }))}
              onChange={(evento) => setParametros({ tab: 'horarios', tecnico_id: evento.target.value })} />
            {tecnico ? <HorarioTecnico key={tecnico.id} id={tecnico.id} nombre={tecnico.nombre} puedeEditar={tecnico.id === sesion.usuario?.id ? puedeEditarPropio : puedeEditarTodos} /> : <Nota>Selecciona un integrante del equipo.</Nota>}
          </>}
        </Panel>
      </ContenidoTab>
      <ContenidoTab valor="ausencias">
        <Panel titulo="Ausencias" descripcion="Fechas inclusivas: desde el primer hasta el último día. Las ausencias afectan a la disponibilidad y a las horas disponibles del calendario.">
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            {puedeVerTodos ? <Select etiqueta="Filtrar ausencias por técnico" value={filtroAusencias} placeholder="Todo el equipo" opciones={(tecnicos.data?.items ?? []).map((t) => ({ valor: t.id, etiqueta: t.nombre }))} onChange={(evento) => { setFiltroAusencias(evento.target.value); setPaginaAusencias(1) }} /> : null}
            <Select etiqueta="Periodo de ausencias" value={periodo} opciones={[{ valor: 'vigentes', etiqueta: 'En curso y futuras' }, { valor: 'todas', etiqueta: 'Todas, incluido el historial' }]} onChange={(evento) => { setPeriodo(evento.target.value); setPaginaAusencias(1) }} />
          </div>
          {ausencias.isPending ? <SkeletonPanel filas={3} /> : ausencias.isError ? <ErrorState mensaje="No pudimos cargar las ausencias." alReintentar={() => void ausencias.refetch()} /> : !visibles.length ? <Nota>No hay ausencias para este filtro.</Nota> : (
            <ul className="divide-y divide-border">{visibles.slice((paginaAusenciasActual - 1) * 10, paginaAusenciasActual * 10).map((a) => <li key={a.id} className="flex items-center gap-3 py-3">
              <CalendarOff size={18} className="shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1"><p className="font-medium">{a.tecnico_nombre || tecnicos.data?.items.find((t) => t.id === a.tecnico_id)?.nombre || 'Integrante TI'} · {a.tipo.replace('Capacitacion', 'Capacitación')}</p>
                <p className="text-sm text-muted-foreground">{fechaCorta(a.inicio)} - {fechaCorta(a.fin)}{a.motivo ? ` · ${a.motivo}` : ''}</p>
                <p className="text-2xs text-muted-foreground">{a.fin < hoy() ? 'Finalizada' : a.inicio > hoy() ? 'Próxima' : 'En curso'}</p>
              </div>
              {(a.tecnico_id === sesion.usuario?.id ? puedeEditarPropio : puedeEditarTodos) ? <Button tamano="sm" onClick={() => setBorrando(a)}>Eliminar</Button> : null}
            </li>)}</ul>
          )}
          {visibles.length > 10 && <Paginacion pagina={paginaAusenciasActual} totalPaginas={Math.ceil(visibles.length / 10)} total={visibles.length} porPagina={10} alCambiar={setPaginaAusencias} />}
        </Panel>
      </ContenidoTab>
      <ContenidoTab valor="calendario"><Panel titulo="Calendario del equipo"><CalendarioEquipoTi /></Panel></ContenidoTab>
    </TabsPanel>
    <DialogModal abierto={creando} alCerrar={() => { if (!guardando) setCreando(false) }} titulo="Registrar ausencia" descripcion="La persona aparecerá como ausente en las fechas indicadas. Sus tickets existentes se conservan."
      pie={<><Button disabled={guardando} onClick={() => setCreando(false)}>Cancelar</Button><Button type="submit" form="ausencia-ti" variante="primario" cargando={guardando} disabled={!tecnicoId || !inicio || !fin || fin < inicio}>Registrar</Button></>}>
      <form id="ausencia-ti" onSubmit={registrar} className="flex flex-col gap-4">
        {errorGeneral ? <Nota tono="peligro" titulo="No se pudo registrar">{errorGeneral}</Nota> : null}
        <Select etiqueta="Técnico" value={tecnicoId} requerido disabled={guardando || !puedeEditarTodos} opciones={(tecnicos.data?.items ?? []).filter((t) => puedeEditarTodos || t.id === sesion.usuario?.id).map((t) => ({ valor: t.id, etiqueta: t.nombre }))} onChange={(evento) => setTecnicoId(evento.target.value)} error={errores.tecnico_id} />
        <Select etiqueta="Tipo" value={tipo} disabled={guardando} opciones={['Vacaciones', 'Permiso', 'Capacitacion', 'Enfermedad', 'Licencia', 'Otros'].map((t) => ({ valor: t, etiqueta: t.replace('Capacitacion', 'Capacitación') }))} onChange={(evento) => setTipo(evento.target.value)} error={errores.tipo} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Input etiqueta="Desde" type="date" requerido disabled={guardando} value={inicio} onChange={(evento) => setInicio(evento.target.value)} error={errores.inicio} />
          <Input etiqueta="Hasta" type="date" requerido disabled={guardando} min={inicio} value={fin} onChange={(evento) => setFin(evento.target.value)} error={fin < inicio ? 'La fecha final debe ser igual o posterior al inicio.' : errores.fin} />
        </div>
        <Input etiqueta="Motivo" maxLength={500} disabled={guardando} value={motivo} onChange={(evento) => setMotivo(evento.target.value)} ayuda="Opcional. Describe brevemente el motivo." error={errores.motivo} />
      </form>
    </DialogModal>
    <ConfirmDialog abierto={Boolean(borrando)} alCerrar={() => { if (!eliminando) setBorrando(null) }} alConfirmar={() => void eliminar()} titulo="Eliminar ausencia" mensaje="Se quitará esta ausencia y se actualizará la disponibilidad del equipo." textoConfirmar="Eliminar ausencia" cargando={eliminando} peligro />
  </>
}
