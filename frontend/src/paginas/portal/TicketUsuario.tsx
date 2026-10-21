/**
 * Detalle de un ticket visto por quien lo reportó.
 *
 * La regla del chat la pone la API: `tiene_chat`. Si el equipo TI registró el
 * caso, no hay conversación y la pantalla lo explica en vez de mostrar una caja
 * de mensajes que nadie puede usar.
 */

import { ArrowLeft, CheckCircle2, MessageSquare, Star } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useParams } from 'react-router-dom'

import { api, ErrorPeticion } from '../../api/cliente'
import { useMensajesTicket, useTicket, useSugerenciaReporte, usePreferenciaIa } from '../../api/hooks'
import type { CuerpoMensaje } from '../../api/tipos'
import { EstadoReporte } from '../../componentes/dominio/EstadoReporte'
import { Button } from '../../componentes/base/Button'
import { ConfirmDialog } from '../../componentes/base/Sobreposiciones'
import { ErrorState, Nota, PageHeader, Panel, SkeletonPanel } from '../../componentes/base/Estructura'
import { fechaHora, desdeHace } from '../../dominio/formato'
import { useSesion } from '../../estado/Sesion'
import { cn } from '../../lib/cn'
import { useTiempoReal } from '../../api/tiempoReal'
import { useAvisos } from '../../estado/Avisos'
import { AdjuntosMensaje, CompositorMensaje } from '../../componentes/dominio/MultimediaChat'
import { PerfilTecnicoTicket } from '../../componentes/dominio/PerfilTecnicoTicket'

export function TicketUsuario() {
  const { id } = useParams<{ id: string }>()
  const ubicacion = useLocation()
  const sesion = useSesion()
  const listaMensajes = useRef<HTMLUListElement>(null)
  const seguirMensajes = useRef(true)
  const avisos = useAvisos()
  const ticket = useTicket(id)
  const cache = useQueryClient()
  const preferencias = usePreferenciaIa()
  const recomendacionesActivas = Boolean(preferencias.data?.recomendaciones_visibles)

  // El chat solo se pide si la API dice que este ticket lo tiene
  const ticketActual = ticket.data
  const ayuda = useSugerenciaReporte({ tipo_problema: ticketActual?.tipo_problema ?? undefined, descripcion: ticketActual?.descripcion ?? undefined }, Boolean(ticketActual && recomendacionesActivas))
  const tieneChat = Boolean(ticketActual?.tiene_chat)
  useTiempoReal('ticket', id, tieneChat)
  const mensajes = useMensajesTicket(id, tieneChat)
  const cantidadMensajes = mensajes.data?.items.length ?? 0
  useEffect(() => {
    if (listaMensajes.current && seguirMensajes.current) listaMensajes.current.scrollTop = listaMensajes.current.scrollHeight
  }, [cantidadMensajes])
  useEffect(() => {
    const temporizador = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      void ticket.refetch()
      if (tieneChat) void mensajes.refetch()
    }, 5_000)
    return () => window.clearInterval(temporizador)
  }, [id, tieneChat, ticket.refetch, mensajes.refetch])

  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [valoracion, setValoracion] = useState<{ id: string; valor: number } | null>(null)
  const [valorando, setValorando] = useState(false)
  const bloqueoValoracion = useRef(false)
  const calificacion = typeof ticketActual?.satisfaccion === 'number' ? ticketActual.satisfaccion : valoracion && valoracion.id === id ? valoracion.valor : null
  const [confirmarReapertura, setConfirmarReapertura] = useState(false)
  const [reabriendo, setReabriendo] = useState(false)

  useEffect(() => {
    setMensaje('')
    setValoracion(null)
    setConfirmarReapertura(false)
    seguirMensajes.current = true
  }, [id])

  useEffect(() => {
    if (ticketActual) document.title = `${ticketActual.codigo} · Mesa de Ayuda`
  }, [ticketActual])

  const enviar = async (adjuntos: string[] = []) => {
    if (!id || (!mensaje.trim() && !adjuntos.length) || enviando) return false
    setEnviando(true)
    try {
      const cuerpo: CuerpoMensaje = { cuerpo: mensaje.trim(), adjuntos }
      await api.crear(`/tickets/${id}/mensajes`, cuerpo)
      setMensaje('')
      await mensajes.refetch()
      await ticket.refetch()
      return true
    } catch (fallo) {
      avisos.desdeError(fallo instanceof ErrorPeticion ? fallo : new Error('No pudimos enviar el mensaje.'))
      return false
    } finally {
      setEnviando(false)
    }
  }

  const valorar = async (estrellas: number) => {
    if (!id || calificacion || bloqueoValoracion.current) return
    bloqueoValoracion.current = true
    setValorando(true)
    try {
      const respuesta = await api.crear<{ satisfaccion: number }>(`/tickets/${id}/valorar`, { puntuacion: estrellas })
      setValoracion({ id, valor: respuesta.satisfaccion })
      cache.setQueryData(['ticket', id], (anterior: typeof ticketActual) => anterior ? { ...anterior, satisfaccion: respuesta.satisfaccion } : anterior)
      void cache.invalidateQueries({ queryKey: ['mis-tickets'] })
      avisos.exito('Gracias por tu valoración')
    } catch (fallo) {
      void ticket.refetch()
      avisos.desdeError(fallo)
    } finally { bloqueoValoracion.current = false; setValorando(false) }
  }

  const reabrir = async () => {
    if (!id) return
    setReabriendo(true)
    try {
      await api.crear(`/tickets/${id}/estado`, { estado: 'en_progreso' })
      setConfirmarReapertura(false)
      await ticket.refetch()
      avisos.exito('Aviso reabierto', 'El equipo TI volverá a revisarlo.')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setReabriendo(false)
    }
  }

  if (ticket.isLoading) return <SkeletonPanel filas={5} />

  if (ticket.isError) {
    const fallo = ticket.error
    return (
      <ErrorState
        mensaje={fallo instanceof ErrorPeticion && fallo.estado === 404 ? 'Ese ticket no existe o no es tuyo.' : 'No pudimos cargar el ticket.'}
        detalle={fallo instanceof Error ? fallo.message : undefined}
        alReintentar={() => void ticket.refetch()}
      />
    )
  }

  const datos = ticket.data
  if (!datos) return null

  return (
    <>
      <PageHeader
        titulo={datos.asunto}
        descripcion={`${datos.codigo} · reportado ${desdeHace(datos.creado_en)}`}
        migas={[
          { texto: 'Inicio', enlace: '/' },
          { texto: 'Mis reportes', enlace: '/mis-tickets' },
          { texto: datos.codigo },
        ]}
      />

      {ubicacion.state?.reporteRecibido && datos.estado === 'nuevo' ? <div role="status" className="flex items-start gap-3 rounded-2xl border border-success-borde bg-success-soft p-4 text-success-strong"><CheckCircle2 size={24} className="shrink-0" /><div><p className="font-bold">Tu reporte fue enviado</p><p className="mt-1 text-sm">Código {datos.codigo}. Puedes agregar fotos, audio o más detalles en la conversación.</p></div></div> : null}
      <EstadoReporte estado={datos.estado} seguimiento />

      <details className="rounded-2xl border border-border bg-surface p-4">
        <summary className="cursor-pointer font-semibold">Ver los datos de tu reporte</summary>
        <div className="mt-3">
        <p className="text-base whitespace-pre-line">{datos.descripcion}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Dato etiqueta="Oficina" valor={datos.oficina_nombre ?? 'Sin oficina'} />
          <Dato etiqueta="Equipo" valor={datos.activo_nombre ?? 'No indicado'} />
        </dl>
        </div>
      </details>

      {recomendacionesActivas && ayuda.data?.disponible && ayuda.data.articulos?.length ? <aside className="rounded-xl border border-border bg-surface px-4 py-3" aria-label="Guías recomendadas"><p className="text-sm font-semibold">Guías que pueden ayudarte</p><ul className="mt-2 flex flex-col gap-2">{ayuda.data.articulos.slice(0, 3).map(articulo => <li key={articulo.id}><Link className="block truncate text-sm text-info-strong hover:underline" title={articulo.titulo} to={`/ayuda/${articulo.id}`}>{articulo.titulo}</Link></li>)}</ul></aside> : null}
      {datos.tecnico_nombre ? (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm"><span className="size-2 rounded-full bg-success" aria-hidden="true" /><span>Te atiende</span>{datos.tecnico_id ? <PerfilTecnicoTicket ticketId={id!} tecnicoId={datos.tecnico_id} nombre={datos.tecnico_nombre} /> : <strong>{datos.tecnico_nombre}</strong>}<span className="text-muted-foreground">· Soporte TI</span></div>
      ) : null}

      {datos.nota_resolucion ? (
        <Panel titulo={<span className="flex items-center gap-2 text-success-strong"><CheckCircle2 size={23} />Resultado de la atención</span>} className="portal-resultado border-success-borde shadow-md">
          <p className="break-words text-base leading-relaxed whitespace-pre-line">{datos.nota_resolucion}</p>
        </Panel>
      ) : null}

      {/* El chat depende de una regla del backend, no de una condición de la vista */}
      {tieneChat ? (
        <Panel
          titulo="Habla con soporte"
          descripcion="Escribe, envía una foto o graba un audio. Las respuestas aparecerán aquí."
          className="overflow-hidden rounded-2xl"
        >
          {mensajes.isError ? <ErrorState compacto mensaje="No pudimos cargar la conversación." alReintentar={() => void mensajes.refetch()} /> : null}
          {mensajes.isPending ? <p role="status" className="py-4 text-sm text-muted-foreground">Cargando mensajes…</p> : null}
          <ul ref={listaMensajes} aria-label="Mensajes con soporte" onScroll={() => { const lista = listaMensajes.current; if (lista) seguirMensajes.current = lista.scrollHeight - lista.scrollTop - lista.clientHeight < 100 }} className="sin-barra flex max-h-[50vh] flex-col gap-3 overflow-y-auto overscroll-contain py-2">
            {(mensajes.data?.items ?? []).map((item) => (
              <li key={item.id} className={cn('max-w-[94%] break-words rounded-2xl border p-4 sm:max-w-[85%]', item.autor_id === sesion.usuario?.id ? 'self-end rounded-br-sm border-primary/20 bg-primary-soft' : 'self-start rounded-bl-sm border-border bg-surface-2')}>
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold">{item.autor_id === sesion.usuario?.id ? 'Tú' : item.autor_nombre}</span>
                  <span className="text-xs text-muted-foreground">{fechaHora(item.creado_en)}</span>
                </p>
                <p className="mt-1 break-words text-base whitespace-pre-line">{item.cuerpo}</p>
                <AdjuntosMensaje adjuntos={item.adjuntos} />
              </li>
            ))}
            {!mensajes.isPending && !mensajes.isError && cantidadMensajes === 0 ? (
              <li className="py-6 text-center text-sm text-muted-foreground">
                Tu reporte ya llegó. Si quieres agregar algo, escríbelo aquí; no hace falta reportarlo de nuevo.
              </li>
            ) : null}
          </ul>

          <div className="mt-3 flex flex-col gap-2">
            <CompositorMensaje key={id} valor={mensaje} alCambiar={setMensaje} cargando={enviando} onEnviar={enviar} textoEnviar="Enviar a soporte" />
          </div>
        </Panel>
      ) : (
        <Nota tono="info" titulo="Este ticket no tiene conversación" icono={<MessageSquare size={16} aria-hidden="true" />}>
          Lo registró el equipo TI directamente, así que no hay un canal de chat. El seguimiento está en su estado y
          solución.
        </Nota>
      )}

      {datos.estado === 'cerrado' ? (
        <Panel titulo="Valorar la atención" descripcion="Tu respuesta ayuda a mejorar el servicio">
          <Button variante="secundario" onClick={() => setConfirmarReapertura(true)}>
            El problema continúa
          </Button>
          <div className="flex flex-wrap items-center gap-2" aria-busy={valorando}>
            {[1, 2, 3, 4, 5].map((estrella) => (
              <button
                key={estrella}
                type="button"
                onClick={() => void valorar(estrella)}
                aria-label={`Valorar con ${estrella} ${estrella === 1 ? 'estrella' : 'estrellas'}`}
                aria-pressed={calificacion === estrella}
                disabled={valorando || Boolean(calificacion)}
                className="flex size-11 items-center justify-center rounded-lg hover:bg-muted disabled:cursor-default"
              >
                <Star
                  size={22}
                  aria-hidden="true"
                  className={calificacion && estrella <= calificacion ? 'text-warning-strong' : 'text-muted-foreground'}
                  fill={calificacion && estrella <= calificacion ? 'currentColor' : 'none'}
                />
              </button>
            ))}
            {valorando ? <span role="status" className="text-sm text-muted-foreground">Guardando calificación…</span> : null}
            {calificacion ? (
              <span className="flex items-center gap-1.5 text-sm font-semibold text-success-strong">
                <CheckCircle2 size={16} aria-hidden="true" />
                Calificación guardada: {calificacion}/5
              </span>
            ) : null}
          </div>
        </Panel>
      ) : null}

      <div>
        <Button asChild variante="secundario">
          <Link to="/mis-tickets" className="flex items-center gap-2">
            <ArrowLeft size={16} aria-hidden="true" />
            Volver a mis avisos
          </Link>
        </Button>
      </div>
      <ConfirmDialog
        abierto={confirmarReapertura}
        alCerrar={() => setConfirmarReapertura(false)}
        alConfirmar={() => void reabrir()}
        titulo="Reabrir aviso"
        mensaje={<>Vas a reabrir el ticket <strong>{datos.codigo}</strong>. Volverá a <strong>En progreso</strong>.</>}
        textoConfirmar="Reabrir aviso"
        cargando={reabriendo}
      />
    </>
  )
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="truncate font-medium">{valor}</dd>
    </div>
  )
}
