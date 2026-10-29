/**
 * Campana de notificaciones.
 *
 * Vive en los dos cascarones (panel y portal) porque las notificaciones no son
 * solo del equipo TI: quien reporta un problema es quien recibe el aviso de que
 * se resolvió, y antes el portal no tenía ninguna forma de verlo.
 *
 * El enlace lo decide este componente y no el backend. La API guarda `ticket_id`
 * y además un `enlace` con la forma `/tickets/{id}`, que no corresponde a
 * ninguna ruta: el panel usa `/panel/tickets/{id}` y el portal
 * `/mis-tickets/{id}`. Con `ticket_id` se construye la ruta según el rol.
 */

import { Bell, Check, CheckCheck, ChevronLeft, ChevronRight, MessageSquare, RefreshCw, Trash2, UserCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useNotificaciones } from '../../api/hooks'
import { desdeHace, fechaHora } from '../../dominio/formato'
import { cn } from '../../lib/cn'
import { useSesion } from '../../estado/useSesion'
import { useAvisos } from '../../estado/useAvisos'
import { ErrorState, SkeletonPanel } from '../base/Estructura'
import { Button } from '../base/Button'
import { ConfirmDialog, PopoverSimple } from '../base/Sobreposiciones'

/** La forma antigua que guardó la API, que no lleva a ninguna parte. */
const ENLACE_TICKET_VIEJO = /^\/tickets\/([^/]+)$/

export function CampanaNotificaciones({ className }: { className?: string }) {
  const sesion = useSesion()
  const consultas = useQueryClient()
  const navegar = useNavigate()
  const avisos = useAvisos()
  const [soloPendientes, setSoloPendientes] = useState(false)
  const [pagina, setPagina] = useState(1)
  const notificaciones = useNotificaciones({ limite: 100, solo_no_leidas: soloPendientes })
  const [abierta, setAbierta] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [confirmarVaciado, setConfirmarVaciado] = useState(false)
  const eliminar = async (id?: string) => {
    if (guardando) return
    setGuardando(true)
    try { await api.borrar(id ? `/notificaciones/${encodeURIComponent(id)}` : '/notificaciones'); setConfirmarVaciado(false); await refrescar() }
    catch (fallo) { avisos.desdeError(fallo, 'No pudimos eliminar las notificaciones') }
    finally { setGuardando(false) }
  }

  const noLeidas = notificaciones.data?.no_leidas ?? 0
  const hay = Boolean(notificaciones.data?.items.length)
  const totalPaginas = Math.max(1, Math.ceil((notificaciones.data?.items.length ?? 0) / 5))
  const paginaActual = Math.min(pagina, totalPaginas)
  const refrescar = () => consultas.invalidateQueries({ queryKey: ['notificaciones'] })

  const marcarTodas = async () => {
    if (guardando) return
    setGuardando(true)
    try { await api.crear('/notificaciones/leer', {}); await refrescar() }
    catch (fallo) { avisos.desdeError(fallo) }
    finally { setGuardando(false) }
  }

  /** Ruta según el rol: el panel y el portal organizan distinto. */
  const rutaDe = (ticketId: string | null | undefined, enlace: string | null | undefined): string | null => {
    const id = ticketId ?? enlace?.match(ENLACE_TICKET_VIEJO)?.[1]
    if (id) return sesion.esTecnico ? `/panel/tickets/${id}` : `/mis-tickets/${id}`
    if (!enlace) return null
    // Enlaces que no son de ticket: se respetan tal cual.
    if (enlace.startsWith('/panel/') && !sesion.esTecnico) return null
    return enlace.startsWith('/') && !enlace.startsWith('//') ? enlace : null
  }

  /** Abrir el aviso lo marca como leído: si no, nunca se marcan y la lista no baja. */
  const abrir = async (id: string, destino: string | null, leida: boolean) => {
    if (destino) {
      setAbierta(false); navegar(destino)
      const ticketId = destino.match(/\/(?:mis-tickets|panel\/tickets)\/([^/]+)$/)?.[1]
      if (ticketId) void consultas.invalidateQueries({ queryKey: ['ticket', ticketId] })
    }
    if (leida) return
    try { await api.crear(`/notificaciones/leer?ids=${encodeURIComponent(id)}`, {}); await refrescar() }
    catch (fallo) { avisos.desdeError(fallo) }
  }

  return (
    <><ConfirmDialog abierto={confirmarVaciado} alCerrar={() => setConfirmarVaciado(false)} titulo="¿Eliminar todas tus notificaciones?" mensaje="Se vaciará tu bandeja de avisos. Tus tickets y conversaciones se conservan." textoConfirmar="Eliminar todas" alConfirmar={() => void eliminar()} peligro cargando={guardando} /><PopoverSimple
      alineado="end"
      ancho="w-[min(26rem,calc(100vw-2rem))]"
      abierto={abierta}
      alCambiar={(valor) => { setAbierta(valor); if (valor) { setPagina(1); void notificaciones.refetch() } }}
      disparador={
        <Button
          variante="fantasma"
          soloIcono
          tamano={sesion.esTecnico ? 'sm' : 'md'}
          className={cn('relative text-nav-foreground hover:bg-nav-foreground/10', className)}
          aria-label={`Notificaciones${noLeidas ? `: ${noLeidas} sin leer` : ''}`}
        >
          <Bell size={sesion.esTecnico ? 18 : 20} aria-hidden="true" />
          {noLeidas > 0 ? (
            <span className="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-2xs font-bold text-primary-foreground">
              {noLeidas > 9 ? '9+' : noLeidas}
            </span>
          ) : null}
        </Button>
      }
      contenido={
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2 border-b border-border pb-3">
            <div><p className="flex items-center gap-2 font-bold"><Bell size={18} className="text-info-strong" />Notificaciones</p><p className="mt-0.5 text-xs text-muted-foreground">{noLeidas} sin leer</p></div>
            {noLeidas > 0 ? (
              <Button variante="fantasma" tamano="sm" cargando={guardando} onClick={() => void marcarTodas()}>
                Marcar todas
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-1 rounded-lg bg-surface-2 p-1">
            {[{ texto: 'Todas', valor: false }, { texto: 'Sin leer', valor: true }].map(opcion => <button key={opcion.texto} type="button" aria-pressed={soloPendientes === opcion.valor} onClick={() => { setSoloPendientes(opcion.valor); setPagina(1) }} className={cn('flex-1 rounded-md px-3 py-1.5 text-xs font-semibold', soloPendientes === opcion.valor ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground')}>{opcion.texto}</button>)}
            <Button variante="fantasma" tamano="sm" aria-label="Actualizar notificaciones" disabled={notificaciones.isFetching} onClick={() => void notificaciones.refetch()}><RefreshCw size={14} /></Button>
            {hay ? <Button variante="fantasma" tamano="sm" soloIcono aria-label="Eliminar todas las notificaciones" title="Eliminar todas" disabled={guardando} onClick={() => setConfirmarVaciado(true)}><Trash2 size={15} /></Button> : null}
          </div>

          {notificaciones.isPending ? <SkeletonPanel filas={2} /> : notificaciones.isError ? <ErrorState compacto mensaje="No se pudieron cargar los avisos." alReintentar={() => void notificaciones.refetch()} /> : hay ? (
            <ul className="sin-barra flex max-h-[55vh] flex-col gap-2 overflow-y-auto">
              {notificaciones.data!.items.slice((paginaActual - 1) * 5, paginaActual * 5).map((notificacion) => {
                const destino = rutaDe(notificacion.ticket_id, notificacion.enlace)
                const cerrado = notificacion.tipo === 'mensaje_cerrado'
                const Icono = notificacion.tipo?.startsWith('mensaje') ? MessageSquare : notificacion.tipo?.includes('asign') ? UserCheck : Bell
                return (
                  <li key={notificacion.id} className={cn('flex items-start gap-1 rounded-xl border p-1', cerrado ? 'border-warning-borde bg-warning-soft' : notificacion.leida ? 'border-border' : 'border-info-borde bg-info-soft/40')}>
                    <button
                      type="button"
                      onClick={() => {
                        void abrir(notificacion.id, destino, notificacion.leida)
                      }}
                      className={cn(
                        'min-w-0 flex-1 rounded-lg p-2 text-left transition-colors hover:bg-muted',
                        !destino && 'cursor-default hover:bg-transparent',
                      )}
                    >
                      <span className="flex items-center gap-1.5">
                        <Icono size={15} className={cn('shrink-0', cerrado ? 'text-warning-strong' : 'text-info-strong')} aria-hidden="true" />
                        <span className="min-w-0 flex-1 truncate text-sm font-semibold">{notificacion.titulo}</span>
                        {!notificacion.leida ? (
                          <span className="size-2 shrink-0 rounded-full bg-primary" aria-label="sin leer" />
                        ) : null}
                      </span>
                      {cerrado ? <span className="mt-1 block text-xs font-semibold text-warning-strong">Mensaje en ticket finalizado</span> : null}
                      <span className="mt-1 block line-clamp-3 break-words text-sm text-muted-foreground">{notificacion.mensaje}</span>
                      <span className="mt-1 block text-2xs text-muted-foreground" title={fechaHora(notificacion.creado_en)}>{desdeHace(notificacion.creado_en)}</span>
                    </button>
                    {!notificacion.leida ? <Button variante="fantasma" tamano="sm" aria-label={`Marcar como leída: ${notificacion.titulo}`} title="Marcar como leída" onClick={() => void abrir(notificacion.id, null, false)}><Check size={15} /></Button> : null}
                    <Button variante="fantasma" tamano="sm" soloIcono aria-label={`Eliminar notificación: ${notificacion.titulo}`} title="Eliminar notificación" disabled={guardando} onClick={() => void eliminar(notificacion.id)}><Trash2 size={14} /></Button>
                  </li>
                )
              })}
            </ul>
          ) : (
            // Sin lista no se explica por qué: la gente cree que la campana falló.
            <div className="flex flex-col items-center gap-1.5 py-4 text-center">
              <CheckCheck size={22} aria-hidden="true" className="text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{soloPendientes ? 'No tienes notificaciones sin leer.' : 'No tienes notificaciones.'}</p>
              <p className="text-2xs text-muted-foreground">
                {sesion.esTecnico
                  ? 'Aquí aparece el aviso cuando te asignan un caso o alguien responde lo que pediste.'
                  : 'Aquí aparece el aviso cuando alguien toma tu caso, lo resuelve o necesita algo de ti.'}
              </p>
            </div>
          )}
          {hay ? <div className="flex items-center justify-between border-t border-border pt-2 text-xs text-muted-foreground"><span>Página {paginaActual} de {totalPaginas}</span><div className="flex gap-1"><Button tamano="sm" variante="fantasma" aria-label="Notificaciones anteriores" disabled={paginaActual === 1} onClick={() => setPagina(paginaActual - 1)}><ChevronLeft size={16} /></Button><Button tamano="sm" variante="fantasma" aria-label="Notificaciones siguientes" disabled={paginaActual === totalPaginas} onClick={() => setPagina(paginaActual + 1)}><ChevronRight size={16} /></Button></div></div> : null}
        </div>
      }
    /></>
  )
}
