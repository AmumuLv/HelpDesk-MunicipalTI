/**
 * Mis avisos: la lista de lo que la persona ha reportado.
 *
 * Sin métricas internas ni columnas de riesgo: solo su código, qué pasa, en
 * qué estado y cuándo lo escribió. En móvil son tarjetas, no una tabla que
 * alguien tenga que desplazar de lado.
 */

import { ArrowRight, Inbox, MessageCircle, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useMisTickets } from '../../api/hooks'
import type { FiltrosMisTickets } from '../../api/tipos'
import { EstadoReporte } from '../../componentes/dominio/EstadoReporte'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { Button } from '../../componentes/base/Button'
import { SearchInput, Select } from '../../componentes/base/Campo'
import { EmptyState, ErrorState, PageHeader } from '../../componentes/base/Estructura'
import { desdeHace } from '../../dominio/formato'

export function MisTickets() {
  const [texto, setTexto] = useState('')
  const [estado, setEstado] = useState('')
  const [pagina, setPagina] = useState(1)

  useEffect(() => {
    document.title = 'Mis reportes · Mesa de Ayuda'
  }, [])

  const filtros: FiltrosMisTickets = {
    ...(texto.trim() ? { texto: texto.trim() } : {}),
    ...(estado ? { estado } : {}),
    pagina,
    por_pagina: 25,
  }
  const tickets = useMisTickets(filtros)

  const items = tickets.data?.items ?? []

  return (
    <>
      <PageHeader
        titulo="Mis reportes"
        descripcion="Abre un reporte para ver su avance o conversar con soporte."
        acciones={
          <Button asChild variante="primario" tamano="tactil">
            <Link to="/reportar" className="flex items-center gap-2">
              <Plus size={18} aria-hidden="true" />
              Pedir ayuda
            </Link>
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <SearchInput
          etiqueta="Buscar un reporte"
          className="sm:flex-1"
          valor={texto}
          alCambiar={(valor) => {
            setTexto(valor)
            setPagina(1)
          }}
          placeholder="Por código o por texto…"
        />
        <Select
          etiqueta="Estado"
          value={estado}
          onChange={(evento) => {
            setEstado(evento.target.value)
            setPagina(1)
          }}
          placeholder="Todos"
          opciones={[{ valor: 'nuevo', etiqueta: 'Recibidos' }, { valor: 'en_progreso', etiqueta: 'En atención' }, { valor: 'en_espera', etiqueta: 'En espera' }, { valor: 'cerrado', etiqueta: 'Finalizados' }]}
        />
      </div>

      {tickets.isLoading ? (
        <div className="flex flex-col gap-2" role="status" aria-live="polite">
          <span className="solo-lectores">Cargando tus avisos…</span>
          {Array.from({ length: 4 }, (_, indice) => (
            <div key={indice} className="h-20 animate-pulse rounded-[var(--radius-panel)] bg-muted" />
          ))}
        </div>
      ) : tickets.isError ? (
        <ErrorState
          mensaje="No pudimos cargar tus avisos."
          detalle={tickets.error instanceof Error ? tickets.error.message : undefined}
          alReintentar={() => void tickets.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icono={texto || estado ? <Search size={20} aria-hidden="true" /> : <Inbox size={20} aria-hidden="true" />}
          titulo={texto || estado ? 'Ningún aviso coincide con la búsqueda' : 'Todavía no tienes avisos'}
          descripcion={
            texto || estado
              ? 'Prueba con otro texto o quita los filtros.'
              : 'Cuando reportes un problema aparecerá aquí con su estado.'
          }
          accion={
            texto || estado ? (
              <Button
                onClick={() => {
                  setTexto('')
                  setEstado('')
                }}
              >
                Quitar filtros
              </Button>
            ) : (
              <Button asChild variante="primario" tamano="tactil">
                <Link to="/reportar">Reportar un problema</Link>
              </Button>
            )
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {items.map((ticket) => (
              <li key={ticket.id}>
                <Link
                  to={`/mis-tickets/${ticket.id}`}
                  className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5 shadow-sm transition-colors hover:border-warning focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-semibold text-muted-foreground">{ticket.codigo}</span><EstadoReporte estado={ticket.estado} /></div>
                    <p className="mt-2 line-clamp-2 break-words text-lg font-bold [overflow-wrap:anywhere]" title={ticket.asunto}>{ticket.asunto}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                      <span>{desdeHace(ticket.creado_en)}</span>
                      {ticket.tecnico_nombre ? <span>· Te atiende {ticket.tecnico_nombre}</span> : null}
                    </p>
                  </div>
                  <span className="flex items-center gap-2 text-sm font-semibold text-info-strong"><MessageCircle size={17} />Ver seguimiento y mensajes <ArrowRight size={16} /></span>
                </Link>
              </li>
            ))}
          </ul>

          <Paginacion
            pagina={tickets.data?.pagina ?? 1}
            totalPaginas={tickets.data?.total_paginas ?? 1}
            total={tickets.data?.total ?? 0}
            porPagina={25}
            alCambiar={setPagina}
          />
        </>
      )}
    </>
  )
}
