import { ArrowLeft, ArrowRight, Check, MessageCircle, Send, ShieldCheck } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ErrorPeticion } from '../../api/cliente'
import { useAjustesTicket, useCompaneros } from '../../api/hooks'
import type { CuerpoTicket, TicketCreado } from '../../api/tipos'
import { Button } from '../../componentes/base/Button'
import { Select, Textarea } from '../../componentes/base/Campo'
import { ErrorState, SkeletonPanel } from '../../componentes/base/Estructura'
import { useSesion } from '../../estado/Sesion'
import { elementoIcono } from '../../dominio/iconos'
import { URGENCIAS, type ClaveUrgencia } from '../../dominio/estados'
import { cn } from '../../lib/cn'
import { IconoTipoEquipo } from '../../componentes/dominio/IconoTipoEquipo'

export function Reportar() {
  const sesion = useSesion()
  const navegar = useNavigate()
  const [parametros] = useSearchParams()
  const cache = useQueryClient()
  const ajustes = useAjustesTicket()
  const companeros = useCompaneros()
  const [paso, setPaso] = useState(1)
  const [tipo, setTipo] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [urgencia, setUrgencia] = useState<ClaveUrgencia | null>(null)
  const [reportePara, setReportePara] = useState<'propio' | 'companero' | 'oficina'>('propio')
  const [tipoOficina, setTipoOficina] = useState('')
  const [afectadoId, setAfectadoId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const bloqueo = useRef(false)
  const encabezado = useRef<HTMLHeadingElement>(null)
  const tipos = useMemo(() => ajustes.data?.tipos_problema ?? [], [ajustes.data])
  const tipoElegido = tipos.find(item => item.clave === tipo)
  const equiposOficina = useQuery({ queryKey: ['portal-tipos-oficina', sesion.usuario?.id], queryFn: () => api.obtener<{ tipos: string[] }>('/portal/equipos-oficina-tipos'), enabled: reportePara === 'oficina' })
  const valido = Boolean(tipoElegido && urgencia && descripcion.trim().length >= 10 && descripcion.trim().length <= 3800 && (reportePara !== 'companero' || afectadoId))

  useEffect(() => { document.title = 'Pedir ayuda · Mesa de Ayuda' }, [])
  const tipoEnlace = parametros.get('tipo') === 'Correo/cuenta' ? 'Otro' : parametros.get('tipo')
  const solicitudPassword = parametros.get('solicitud') === 'password'
  useEffect(() => { if (solicitudPassword) setDescripcion('Necesito que el administrador restablezca mi contraseña. Solicito la revisión del equipo TI.') }, [solicitudPassword])
  useEffect(() => { if (tipoEnlace && tipos.some(item => item.clave === tipoEnlace)) { setTipo(tipoEnlace); setPaso(2) } }, [tipoEnlace, tipos])
  useEffect(() => { encabezado.current?.focus(); window.scrollTo({ top: 0, behavior: 'instant' }) }, [paso])

  const enviar = async () => {
    if (!valido || bloqueo.current) return
    bloqueo.current = true
    setEnviando(true); setError('')
    let creado: TicketCreado
    try {
      const cuerpo: CuerpoTicket = {
        tipo_problema: tipo,
        descripcion: descripcion.trim(),
        urgencia: urgencia!,
        reporte_para: reportePara,
        persona: reportePara === 'companero' ? { es_para_mi: false, afectado_id: afectadoId } : { es_para_mi: true, afectado_id: sesion.usuario?.id ?? null },
        ...(reportePara === 'oficina' && tipoOficina ? { activo_no_identificado: tipoOficina } : {}),
        adjuntos: [],
      }
      creado = await api.crear<TicketCreado>('/tickets', cuerpo)
    } catch (fallo) {
      setError(fallo instanceof ErrorPeticion ? fallo.message : 'No pudimos enviar tu reporte. Tus datos siguen aquí; puedes volver a intentarlo.')
      bloqueo.current = false; setEnviando(false)
      return
    }
    // Una recarga de listas fallida nunca debe repetir un ticket ya creado.
    void cache.invalidateQueries({ queryKey: ['tickets'] })
    void cache.invalidateQueries({ queryKey: ['mis-tickets'] })
    navegar(`/mis-tickets/${creado.ticket.id}`, { replace: true, state: { reporteRecibido: true } })
  }

  if (ajustes.isPending) return <SkeletonPanel filas={4} />
  if (ajustes.isError) return <ErrorState mensaje="No pudimos cargar las opciones de ayuda." alReintentar={() => void ajustes.refetch()} />

  return <div className="mx-auto w-full max-w-3xl">
    <Link to="/" className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft size={17} />Volver al inicio</Link>
    <ol aria-label="Pasos para pedir ayuda" className="mb-6 flex items-center gap-3 text-sm">
      {['Qué falla', 'Enviar a soporte'].map((texto, indice) => <li key={texto} aria-current={paso === indice + 1 ? 'step' : undefined} className="flex items-center gap-2"><span className={cn('flex size-8 items-center justify-center rounded-full font-bold', paso >= indice + 1 ? 'bg-accion text-primary-foreground' : 'bg-muted text-muted-foreground')}>{paso > indice + 1 ? <Check size={16} /> : indice + 1}</span><span className={paso === indice + 1 ? 'font-bold' : 'text-muted-foreground'}>{texto}</span>{indice === 0 ? <span className="mx-1 h-px w-6 bg-border sm:w-14" /> : null}</li>)}
    </ol>
    <h1 ref={encabezado} tabIndex={-1} className="text-2xl font-bold outline-none sm:text-3xl">{paso === 1 ? '¿Con qué necesitas ayuda?' : 'Cuéntanos qué ocurre'}</h1>
    <p className="mt-2 text-base text-muted-foreground">{paso === 1 ? 'Elige la opción que más se parezca. Si no sabes, elige «Otro problema».' : 'Descríbelo con tus palabras. Soporte se encarga de la parte técnica.'}</p>

    {paso === 1 ? <>
      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2" role="group" aria-label="Tipo de problema">
        {tipos.map((item, indice) => <Button key={item.clave} variante="secundario" data-color={indice % 4} className="portal-opcion-ayuda h-auto min-h-28 justify-start gap-4 rounded-2xl p-5 text-left text-base font-normal shadow-sm hover:border-warning" onClick={() => { setTipo(item.clave); setError(''); setPaso(2) }}>
          <span className="flex items-center gap-4 whitespace-normal"><span className={cn('flex size-12 shrink-0 items-center justify-center rounded-2xl', ['bg-warning-soft text-warning-strong', 'bg-primary-soft text-primary-strong', 'bg-ai-soft text-ai-strong', 'bg-success-soft text-success-strong'][indice % 4])}>{elementoIcono(item.icono)}</span><span className="min-w-0 flex-1"><span className="block font-bold">{item.clave === 'Otro' ? 'Otro problema' : item.titulo}</span><span className="mt-1 block text-sm text-muted-foreground">{item.descripcion}</span></span><ArrowRight size={17} className="shrink-0 text-muted-foreground" /></span>
        </Button>)}
      </div>
      {!tipos.length ? <ErrorState mensaje="No hay opciones de ayuda disponibles." alReintentar={() => void ajustes.refetch()} /> : null}
    </> : <form className="mt-6 flex flex-col gap-5" onSubmit={evento => { evento.preventDefault(); void enviar() }}>
      <fieldset disabled={enviando} className="contents">
        <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-4 py-3"><span className="flex min-w-0 items-center gap-3 font-semibold"><span className="shrink-0 text-info-strong">{elementoIcono(tipoElegido?.icono || 'message-circle')}</span>{tipoElegido?.titulo}</span><Button tamano="sm" variante="fantasma" onClick={() => setPaso(1)}>Cambiar</Button></div>
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">
          <Textarea etiqueta="¿Qué está pasando?" requerido filas={4} maxLength={3800} value={descripcion} onChange={evento => setDescripcion(evento.target.value)} placeholder="Por ejemplo: mi computadora se apaga cuando abro un documento. Empezó esta mañana." ayuda="Con una frase clara es suficiente. Mínimo 10 caracteres." />
          <fieldset className="mt-6"><legend className="mb-3 text-base font-bold">¿Puedes seguir trabajando?</legend><div className="grid gap-2 sm:grid-cols-3">{URGENCIAS.map((opcion, indice) => <label key={opcion.clave} className={cn('flex min-h-24 cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm transition-colors hover:border-warning', urgencia === opcion.clave ? 'border-accion bg-primary-soft ring-1 ring-accion' : 'border-border bg-surface')}><input className="mt-1 size-4 shrink-0 accent-accion" type="radio" name="urgencia" value={opcion.clave} checked={urgencia === opcion.clave} onChange={() => setUrgencia(opcion.clave)} required /><span><span className="block font-bold">{['Sí, puedo continuar', 'Con dificultad', 'No puedo trabajar'][indice]}</span><span className="mt-1 block text-xs text-muted-foreground">{opcion.descripcion}</span></span></label>)}</div></fieldset>
        </section>
        <section className="rounded-2xl border border-border bg-surface p-5">
          <h2 className="mb-4 font-semibold">¿Para quién necesitas ayuda?</h2>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3" role="group" aria-label="A quién afecta el problema">{[{ valor: 'propio', titulo: 'Para mí' }, { valor: 'companero', titulo: 'Para un compañero' }, { valor: 'oficina', titulo: 'Para la oficina' }].map(opcion => <button key={opcion.valor} type="button" aria-pressed={reportePara === opcion.valor} className={cn('min-h-12 rounded-xl border px-3 py-2 text-sm font-semibold transition-colors', reportePara === opcion.valor ? 'border-accion bg-primary-soft text-primary-strong ring-1 ring-accion' : 'border-border hover:bg-muted')} onClick={() => { setReportePara(opcion.valor as typeof reportePara); setAfectadoId(''); setTipoOficina('') }}>{opcion.titulo}</button>)}</div>
            {reportePara === 'companero' ? <Select etiqueta="Persona que necesita ayuda" value={afectadoId} placeholder="Elige a la persona" requerido onChange={evento => setAfectadoId(evento.target.value)} opciones={(companeros.data?.items ?? []).map(persona => ({ valor: persona.id, etiqueta: persona.nombre }))} /> : null}
            {reportePara === 'oficina' ? <div>
              <p className="mb-3 text-sm text-muted-foreground">¿Qué equipo de la oficina tiene el problema? Si no sabes, continúa con «No lo sé».</p>
              {equiposOficina.isError ? <ErrorState compacto mensaje="No pudimos cargar los tipos de equipos. Puedes enviar el reporte sin elegir uno." alReintentar={() => void equiposOficina.refetch()} /> : null}
              {equiposOficina.isPending ? <p role="status" className="mb-2 text-sm text-muted-foreground">Cargando opciones…</p> : null}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="group" aria-label="Tipo de equipo de la oficina">{['', ...(equiposOficina.data?.tipos ?? [])].map(nombre => <button type="button" key={nombre} aria-pressed={tipoOficina === nombre} className={cn('flex min-h-24 min-w-0 flex-col items-center justify-center gap-2 rounded-xl border p-3 text-center text-sm font-semibold transition-colors', tipoOficina === nombre ? 'border-accion bg-primary-soft text-primary-strong ring-1 ring-accion' : 'border-border hover:bg-muted')} onClick={() => setTipoOficina(nombre)}><span aria-hidden="true"><IconoTipoEquipo tipo={nombre || undefined} tamano={30} /></span><span className="break-words">{nombre || 'No lo sé'}</span></button>)}</div>
            </div> : null}
          </div>
        </section>
        <p className="flex items-start gap-2 text-sm text-muted-foreground"><MessageCircle size={19} className="mt-0.5 shrink-0 text-info-strong" />Después de enviar podrás escribir, mandar fotos o grabar un audio para soporte.</p>
      </fieldset>
      {error ? <div role="alert" className="rounded-xl border border-destructive-borde bg-destructive-soft p-4 text-sm text-destructive-strong">{error}<Link to="/mis-tickets" className="mt-2 block font-semibold underline">Ver mis reportes antes de volver a enviar</Link></div> : null}
      <div className="rounded-2xl border border-border bg-surface p-3 shadow-panel">
        <Button type="submit" variante="primario" tamano="tactil" anchoCompleto icono={<Send size={20} />} className="min-h-14 rounded-xl text-base" cargando={enviando} disabled={!valido}>Enviar a soporte</Button>
        {!valido && !enviando ? <p role="status" className="mt-2 text-center text-xs text-muted-foreground">{descripcion.trim().length < 10 ? 'Escribe al menos 10 caracteres para contar el problema.' : !urgencia ? 'Indica si puedes seguir trabajando.' : 'Elige a la persona que necesita ayuda.'}</p> : <p className="mt-2 flex items-center justify-center gap-1 text-xs text-muted-foreground"><ShieldCheck size={13} />Tu reporte llegará al equipo de soporte TI.</p>}
      </div>
    </form>}
  </div>
}
