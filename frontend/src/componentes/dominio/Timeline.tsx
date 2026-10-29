/**
 * Línea de tiempo del ticket.
 *
 * Los eventos llegan ya dentro de `GET /tickets/{id}`, filtrados por la API según
 * quién mira: el portal solo ve los marcados como visibles. Antes este
 * componente pedía `/tickets/{id}/eventos`, una ruta que el backend nunca tuvo,
 * así que la respuesta era un 404, la caja se ocultaba y el historial no se veía
 * nunca. Los eventos marcados por la IA llevan su etiqueta y su color teal, no el
 * azul de los datos reales.
 */

import { CheckCircle2, CircleDot, RefreshCw, UserCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useTicket } from '../../api/hooks'
import { fechaHora } from '../../dominio/formato'
import { cn } from '../../lib/cn'
import { hitosDelTicket, type EventoTicket } from '../../dominio/historial-ticket'
import { useSesion } from '../../estado/useSesion'
import { Panel, Skeleton } from '../base/Estructura'

export function Timeline({ ticketId }: { ticketId: string }) {
  const sesion = useSesion()
  // El detalle ya trae los eventos: se reutiliza su caché en vez de pedir una
  // segunda vez lo mismo (y a una ruta que no existe).
  const consulta = useTicket(ticketId)

  if (consulta.isLoading) {
    return (
      <Panel titulo="Historial" descripcion="Cambios importantes del reporte">
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }, (_, indice) => (
            <Skeleton key={indice} className="h-10 w-full" />
          ))}
        </div>
      </Panel>
    )
  }

  if (!consulta.data) return null
  const eventos = hitosDelTicket((consulta.data.eventos ?? []) as EventoTicket[])

  return (
    <Panel titulo="Historial" descripcion="Cambios importantes del reporte">
      {eventos.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">Sin cambios importantes registrados todavía.</p>
      ) : (
        <ol aria-label="Cambios importantes del ticket" className="relative flex flex-col gap-5 pl-8">
          {/* Línea vertical: purely decorative, la lista ya da el orden */}
          <span aria-hidden="true" className="absolute top-1 bottom-1 left-3 w-px bg-border" />
          {eventos.map((evento) => (
            <li key={evento.id} className="relative">
              <span
                aria-hidden="true"
                className={cn(
                  'absolute top-0 -left-8 flex size-6 items-center justify-center rounded-full ring-4 ring-surface',
                  evento.tono === 'exito' ? 'bg-success-soft text-success-strong' : evento.tono === 'aviso' ? 'bg-warning-soft text-warning-strong' : 'bg-info-soft text-info-strong',
                )}
              >
                {evento.tono === 'exito' ? <CheckCircle2 size={14} /> : evento.tipo === 'asignado' ? <UserCheck size={14} /> : evento.tono === 'aviso' ? <RefreshCw size={14} /> : <CircleDot size={14} />}
              </span>
              <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
                <span className="min-w-0 font-semibold [overflow-wrap:anywhere]">{evento.titulo}</span>
                {evento.origen_ia ? (
                  <span className="rounded bg-ai-soft px-1.5 py-0.5 text-2xs font-semibold text-ai-strong">IA</span>
                ) : null}
                <time dateTime={evento.fecha} className="text-xs tabular-nums text-muted-foreground">{fechaHora(evento.fecha)}</time>
              </p>
              {evento.actor?.nombre ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {sesion.esTecnico && sesion.puede('usuarios.ver') && evento.actor.id && !evento.origen_ia ? (
                    <Link to={`/panel/usuarios/${evento.actor.id}`} className="text-foreground hover:text-info-strong hover:underline">
                      {evento.actor.nombre}
                    </Link>
                  ) : evento.actor.nombre}

                </p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}

