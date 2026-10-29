/**
 * Conversación del ticket.
 *
 * Mensajes del usuario y del equipo TI en el mismo hilo, con el autor y la hora.
 * El chat solo se monta si la API dice que el ticket lo tiene: si no, la
 * pantalla lo explica en su lugar (la regla vive en el backend).
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import type { RespuestasRapidasRespuesta } from '../../api/tipos'

import { useMensajesTicket } from '../../api/hooks'
import { useSesion } from '../../estado/useSesion'
import { cn } from '../../lib/cn'
import { fechaHora } from '../../dominio/formato'
import { Panel } from '../base/Estructura'
import { AdjuntosMensaje, CompositorMensaje } from './MultimediaChat'

export function ChatThread({
  ticketId,
  valor,
  alCambiar,
  cargando,
  onEnviar,
}: {
  ticketId: string
  valor: string
  alCambiar: (valor: string) => void
  cargando: boolean
  onEnviar: (adjuntos?: string[]) => Promise<boolean | void>
}) {
  const sesion = useSesion()
  const mensajes = useMensajesTicket(ticketId, true)
  const miId = sesion.usuario?.id
  const plantillas = useQuery({ queryKey: ['kb', 'respuestas-rapidas'], queryFn: () => api.obtener<RespuestasRapidasRespuesta>('/kb/respuestas-rapidas'), enabled: sesion.esTecnico })

  return (
    <Panel
      titulo="Conversación"
      descripcion="El usuario ve este mismo hilo."
      sinRelleno
    >
      <ul className="sin-barra flex max-h-96 flex-col gap-2 overflow-y-auto p-4">
        {(mensajes.data?.items ?? []).map((item) => {
          const propio = item.autor_id === miId
          return (
            <li key={item.id} className={cn('flex', propio ? 'justify-end' : 'justify-start')}>
              <div
                className={cn(
                  'min-w-0 max-w-[85%] break-words rounded-[var(--radius-panel)] border p-3',
                  propio ? 'border-primary/25 bg-primary-soft' : 'border-border bg-surface',
                )}
              >
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  {sesion.esTecnico && sesion.puede('usuarios.ver') && item.autor_id && !item.es_ia ? (
                    <Link to={`/panel/usuarios/${item.autor_id}`} className="font-semibold text-primary-strong hover:underline">
                      {item.autor_nombre}
                    </Link>
                  ) : <span className="font-semibold">{item.autor_nombre}</span>}
                  <span className="rounded bg-muted px-1.5 py-0.5 text-2xs uppercase">{item.autor_rol}</span>
                  <span className="text-muted-foreground">{fechaHora(item.creado_en)}</span>
                  {item.es_ia ? (
                    <span className="rounded bg-ai-soft px-1.5 py-0.5 text-2xs font-semibold text-ai-strong">IA</span>
                  ) : null}
                </p>
                <p className="mt-1 whitespace-pre-line">{item.cuerpo}</p>
                <AdjuntosMensaje adjuntos={item.adjuntos} />
              </div>
            </li>
          )
        })}
        {(mensajes.data?.items.length ?? 0) === 0 && !mensajes.isLoading ? (
          <li className="py-6 text-center text-sm text-muted-foreground">
            Todavía no hay mensajes. Escribe el primero para presentar la solución.
          </li>
        ) : null}
      </ul>

      <div className="border-t border-border p-3">
        {sesion.esTecnico ? <label className="mb-3 flex flex-col gap-1 text-sm font-semibold">Insertar respuesta rápida<select className="rounded border border-input bg-surface p-2 font-normal" value="" disabled={cargando || !plantillas.data?.items.length} onChange={(e) => { const plantilla = plantillas.data?.items.find((p) => p.id === e.target.value); if (plantilla) alCambiar(valor.trim() ? `${valor}\n\n${plantilla.cuerpo}` : plantilla.cuerpo) }}><option value="">{plantillas.isError ? 'No se pudieron cargar las plantillas' : 'Elegir plantilla para revisar antes de enviar'}</option>{plantillas.data?.items.map((p) => <option key={p.id} value={p.id}>{p.titulo}</option>)}</select></label> : null}
        <CompositorMensaje key={ticketId} valor={valor} alCambiar={alCambiar} cargando={cargando} onEnviar={onEnviar} />
      </div>
    </Panel>
  )
}
