/**
 * AIPanel: lo que la IA propone sobre un ticket.
 *
 * Reglas de la casa, sin excepción:
 * - Si el backend no devuelve sugerencias, no se pinta nada.
 * - Cada sugerencia lleva etiqueta «IA», su confianza y la explicación de por
 *   qué la propone. Sin explicación no se muestra: una predicción sin motivo no
 *   es una ayuda.
 * - Hay tres salidas: Aplicar, Editar y Descartar. Descartar es una decisión
 *   real y queda auditada en el backend.
 * - Una vez que se decide, la sugerencia deja de ofrecerse. Se queda una línea
 *   que dice qué se cambió, y en el caso del descarte es deliberadamente
 *   discreta: descartar es mayoritariamente, no necesita ocupar espacio.
 */

import { AlertTriangle, Check, CheckCheck, Pencil, Sparkles, ThumbsDown } from 'lucide-react'
import { useState } from 'react'

import { api } from '../../api/cliente'
import type { DecisionIA, SugerenciasTicket } from '../../api/tipos'
import { ConfianzaIABadge, EtiquetaIA } from './Badge'
import { useAvisos } from '../../estado/useAvisos'
import { cn } from '../../lib/cn'
import { limitarTextoIA, TEXTOS_IA } from '../../dominio/textos-ia'

type Sugerencia = {
  clave: string
  etiqueta: string
  valor: string
  valorAplicar?: string
  editable?: boolean
  confianza?: number
  explicacion?: string
  /** `false` cuando no hay nada que decidir (el riesgo de SLA es un dato). */
  accionable?: boolean
}

export function AIPanel({
  ticketId,
  consulta,
  alAplicar,
}: {
  ticketId: string
  consulta: { data?: SugerenciasTicket; isLoading: boolean; isError: boolean }
  alAplicar: () => void
}) {
  const avisos = useAvisos()
  const [editando, setEditando] = useState<string | null>(null)
  const [valorEditado, setValorEditado] = useState('')
  const [ocupado, setOcupado] = useState<string | null>(null)

  const datos = consulta.data

  if (consulta.isLoading) {
    return (
      <div className="rounded-[var(--radius-panel)] border border-ai/25 bg-ai-soft p-3" role="status" aria-live="polite">
        <span className="solo-lectores">Consultando las ayudas automáticas…</span>
        <div className="h-4 w-40 animate-pulse rounded bg-muted" />
        <div className="mt-2 h-16 w-full animate-pulse rounded bg-muted" />
      </div>
    )
  }

  // Sin sugerencias no hay panel: ni franja vacía ni «no disponible»
  if (!datos || !datos.disponible) return null
  const decisiones = datos.decisiones ?? {}
  const sugerencias = aSugerencias(datos)
  if (sugerencias.length === 0) return null

  const insuficiente = datos.confianza_suficiente === false
  const pendientes = sugerencias.filter((item) => !decisiones[item.clave])

  const decidir = async (clave: string, accion: 'aplicar' | 'descartar', valor?: string) => {
    setOcupado(clave)
    try {
      const respuesta = await api.crear<{ cambios?: Record<string, unknown> }>(`/tickets/${ticketId}/ia`, {
        clave,
        accion,
        ...(valor ? { valor } : {}),
      })
      if (accion === 'aplicar') {
        avisos.exito('Sugerencia aplicada', descripcionDeCambio(respuesta?.cambios))
      } else {
        avisos.info('Sugerencia descartada', 'No volverás a ver esta recomendación en este ticket.')
      }
      setEditando(null)
      alAplicar()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setOcupado(null)
    }
  }

  return (
    <section
      aria-labelledby="titulo-ia"
      className="rounded-[var(--radius-panel)] border border-ai/30 bg-ai-soft"
    >
      <header className="flex items-start justify-between gap-2 border-b border-ai/25 p-3">
        <h2 id="titulo-ia" className="flex items-center gap-2 text-base font-semibold text-ai-strong">
          <Sparkles size={16} aria-hidden="true" />
          Sugerencias
          <EtiquetaIA />
        </h2>
        {datos.confianza !== undefined && datos.confianza !== null ? (
          <ConfianzaIABadge confianza={datos.confianza} suficiente={datos.confianza_suficiente} />
        ) : null}
      </header>

      {insuficiente ? (
        <p className="flex items-start gap-2 border-b border-ai/25 p-3 text-sm text-ai-strong">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>{TEXTOS_IA.pocosCasos}</span>
        </p>
      ) : null}

      {/* Lo ya decidido. Va arriba y en una línea: es un cierre, no una propuesta. */}
      {pendientes.length < sugerencias.length ? (
        <ul className="divide-y divide-ai/20 border-b border-ai/20">
          {sugerencias
            .filter((item) => decisiones[item.clave])
            .map((item) => (
              <LineaDecidida
                key={item.clave}
                etiqueta={item.etiqueta}
                valor={item.valor}
                decision={decisiones[item.clave] as DecisionIA}
              />
            ))}
        </ul>
      ) : null}

      {pendientes.length > 0 ? (
        <ul className="divide-y divide-ai/20">
          {pendientes.map((sugerencia) => (
            <li key={sugerencia.clave} className="p-3">
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                {sugerencia.etiqueta}
                <ConfianzaIABadge confianza={sugerencia.confianza} />
              </p>

              {editando === sugerencia.clave ? (
                <div className="mt-2 flex flex-col gap-2">
                  <input
                    type="text"
                    value={valorEditado}
                    onChange={(evento) => setValorEditado(evento.target.value)}
                    aria-label={`Editar ${sugerencia.etiqueta}`}
                    className="h-9 w-full rounded-[var(--radius-control)] border border-input bg-surface px-2.5 text-sm"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={!valorEditado.trim() || ocupado === sugerencia.clave}
                      onClick={() => void decidir(sugerencia.clave, 'aplicar', valorEditado.trim())}
                      className="rounded-[var(--radius-control)] bg-ai px-2.5 py-1 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                    >
                      Guardar cambio
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditando(null)}
                      className="rounded-[var(--radius-control)] border border-border bg-surface px-2.5 py-1 text-sm font-semibold hover:bg-muted"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p className={cn('mt-1 text-sm font-medium')}>{sugerencia.valor}</p>
                  {sugerencia.explicacion ? (
                    <p className="mt-1 text-sm text-muted-foreground">
                      <span className="font-semibold">Por qué: </span>
                      {limitarTextoIA(sugerencia.explicacion)}
                    </p>
                  ) : null}
                  {/* El riesgo de SLA es un dato, no una decisión: sin botones. */}
                  {sugerencia.accionable === false ? null : (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Boton
                        icono={<Check size={14} aria-hidden="true" />}
                        // El valor viaja siempre: sin él el backend no sabe qué
                        // aplicar y «Aplicar» solo registraba la decisión.
                        onClick={() => void decidir(sugerencia.clave, 'aplicar', sugerencia.valorAplicar ?? sugerencia.valor)}
                        cargando={ocupado === sugerencia.clave}
                      >
                        Aplicar
                      </Boton>
                      {sugerencia.editable === false ? null : <Boton
                        icono={<Pencil size={14} aria-hidden="true" />}
                        onClick={() => {
                          setEditando(sugerencia.clave)
                          setValorEditado(sugerencia.valor)
                        }}
                      >
                        Editar
                      </Boton>}
                      <Boton
                        icono={<ThumbsDown size={14} aria-hidden="true" />}
                        onClick={() => void decidir(sugerencia.clave, 'descartar')}
                      >
                        Descartar
                      </Boton>
                    </div>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      ) : null}

      {datos.articulos.length ? (
        <div className="border-t border-ai/25 p-3">
          <p className="text-sm font-semibold text-ai-strong">Artículos que podrían resolverlo</p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {datos.articulos.map((articulo) => (
              <li key={articulo.id} className="text-sm text-muted-foreground">
                · {articulo.titulo}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {datos.llm_disponible === false ? (
        <p className="border-t border-ai/25 p-3 text-sm text-muted-foreground">{TEXTOS_IA.basica}</p>
      ) : null}
    </section>
  )
}

/**
 * Una sugerencia ya decidida: una línea con lo que pasó.
 *
 * Aplicada dice qué valor quedó y cuál había antes, porque «Aplicado» a secas no
 * explica nada. Descartada es deliberadamente más discreta: sin color, sin icono
 * destacado y en letra pequeña, porque rechazar una recomendación no es un
 * evento que haya que celebrar ni que ocupe espacio.
 */
function LineaDecidida({
  etiqueta,
  valor,
  decision,
}: {
  etiqueta: string
  valor: string
  decision: DecisionIA
}) {
  if (decision.accion === 'descartar') {
    return (
      <li className="flex items-center gap-1.5 px-3 py-1.5 text-2xs text-muted-foreground">
        <ThumbsDown size={11} aria-hidden="true" className="shrink-0 opacity-70" />
        <span>
          {etiqueta}: sugerencia descartada
          {decision.anterior ? `, se mantuvo «${decision.anterior}»` : ''}
        </span>
      </li>
    )
  }

  const elegido = decision.elegido || valor
  return (
    <li className="flex items-start gap-1.5 px-3 py-1.5 text-sm">
      <CheckCheck size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-ai-strong" />
      <span>
        <span className="font-semibold">{etiqueta} aplicada: </span>
        <span className="font-medium">{elegido}</span>
        {decision.anterior && decision.anterior !== elegido ? (
          <span className="text-muted-foreground"> (antes: {decision.anterior})</span>
        ) : null}
      </span>
    </li>
  )
}

/** Texto del aviso tras aplicar, a partir de lo que la API dice que cambió. */
function descripcionDeCambio(cambios?: Record<string, unknown>): string | undefined {
  if (!cambios || Object.keys(cambios).length === 0) return 'No había nada que cambiar.'
  const etiquetas: Record<string, string> = {
    categoria: 'la categoría',
    prioridad: 'la prioridad',
    tecnico_nombre: 'el técnico',
    estado: 'el estado',
  }
  const partes = Object.keys(cambios)
    .filter((clave) => etiquetas[clave])
    .map((clave) => `Actualizó ${etiquetas[clave]}.`)
  if (partes.length === 0) return 'Quedó registrada como decisión de la IA.'
  return partes.join(' ')
}

function Boton({
  children,
  onClick,
  icono,
  cargando,
}: {
  children: React.ReactNode
  onClick: () => void
  icono: React.ReactNode
  cargando?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={cargando}
      className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] border border-ai/40 bg-surface px-2.5 py-1 text-sm font-semibold text-ai-strong transition-colors hover:bg-ai-soft disabled:opacity-50"
    >
      {icono}
      {children}
    </button>
  )
}

/**
 * Traduce la respuesta de la API a sugerencias con su explicación.
 * Los nombres de campo son los que declara el backend; aquí no se inventa ninguno.
 * `accionable: false` marca las que son un dato y no una decisión.
 */
function aSugerencias(datos: SugerenciasTicket): Sugerencia[] {
  const lista: Sugerencia[] = []

  if (datos.categoria) {
    lista.push({
      clave: 'categoria',
      etiqueta: 'Categoría',
      valor: datos.categoria,
      confianza: datos.confianza,
      explicacion: `Palabras clave del texto. ${datos.explicacion ?? ''}`.trim(),
    })
  }
  if (datos.prioridad) {
    lista.push({
      clave: 'prioridad',
      etiqueta: 'Prioridad',
      valor: datos.prioridad,
      confianza: datos.confianza,
      explicacion: 'Urgencia declarada y casos parecidos.',
    })
  }
  if (datos.tecnico_sugerido_nombre) {
    lista.push({
      clave: 'tecnico_sugerido_id',
      etiqueta: 'Técnico sugerido',
      valor: datos.tecnico_sugerido_nombre,
      valorAplicar: datos.tecnico_sugerido_id ?? undefined,
      editable: false,
      accionable: Boolean(datos.tecnico_sugerido_id) && datos.tecnico_sugerido_aplicable !== false,
      confianza: datos.confianza,
      explicacion: datos.explicacion_asignacion ?? 'Según carga actual y especialidad.',
    })
  }
  if (datos.riesgo_sla) {
    lista.push({
      clave: 'riesgo_sla',
      etiqueta: 'Riesgo de SLA',
      valor: datos.riesgo_sla,
      confianza: datos.confianza,
      explicacion: 'Historial de tickets parecidos.',
      accionable: false,
    })
  }

  return lista
}
