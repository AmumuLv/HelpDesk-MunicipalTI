import { TicketsAtencion } from '../../componentes/dominio/TicketsAtencion'
/**
 * Resumen del panel: lo primero que ve el equipo TI al entrar.
 *
 * Seis cifras que se pueden actuar, no un tablero decorativo: cada tarjeta lleva
 * a la lista filtrada que corresponde. Debajo, la carga por técnico con su estado
 * real (el que calcula la API según horario, días libres y ausencias) y los
 * tickets que necesitan atención ya.
 */

import {
  ArrowRight,
  CircleAlert,
  Clock,
  Flame,
  Inbox,
  LifeBuoy,
  ShieldCheck,
  TicketCheck,
} from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'

import { usePanelEquipo, useResumenTickets, useTickets } from '../../api/hooks'
import { DisponibilidadBadge } from '../../componentes/dominio/Badge'
import { KpiCard } from '../../componentes/dominio/KpiCard'
import { Panel, ErrorState, PageHeader, SkeletonKpis, SkeletonPanel } from '../../componentes/base/Estructura'
import { Avatar, Nota } from '../../componentes/base/Estructura'
import { numero } from '../../dominio/formato'
import { cn } from '../../lib/cn'

/** Color de la barra de carga, según lo cerca que esté de rebosar. */
const TONO_BARRA = {
  exito: 'bg-success',
  aviso: 'bg-warning',
  peligro: 'bg-destructive',
} as const

export function Resumen() {
  useEffect(() => {
    document.title = 'Resumen · Mesa de Ayuda TI'
  }, [])

  const resumen = useResumenTickets()
  const panel = usePanelEquipo()
  const criticos = useTickets({ vista: 'criticos', por_pagina: 6 })

  const datosResumen = resumen.data

  return (
    <>
      <PageHeader
        titulo="Resumen"
        descripcion="Estado de la mesa de ayuda ahora mismo."
      />

      {/* El esqueleto solo mientras llegan los datos: si no, se ve duplicado */}
      {resumen.isLoading || panel.isLoading ? (
        <SkeletonKpis cantidad={6} />
      ) : resumen.isError ? (
        <ErrorState
          mensaje="No pudimos cargar el resumen."
          detalle={resumen.error instanceof Error ? resumen.error.message : undefined}
          alReintentar={() => void resumen.refetch()}
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
          <KpiTarjeta
            etiqueta="Abiertos"
            valor={datosResumen?.abiertos}
            icono={<TicketCheck size={16} aria-hidden="true" />}
            enlace="/panel/tickets?vista=abiertos"
          />
          <KpiTarjeta
            etiqueta="Sin asignar"
            valor={datosResumen?.sin_asignar}
            icono={<Inbox size={16} aria-hidden="true" />}
            tono={datosResumen?.sin_asignar ? 'aviso' : 'neutro'}
            enlace="/panel/tickets?vista=sin_asignar"
          />
          <KpiTarjeta
            etiqueta="SLA en riesgo"
            valor={datosResumen?.sla_riesgo}
            icono={<Clock size={16} aria-hidden="true" />}
            tono={datosResumen?.sla_riesgo ? 'peligro' : 'neutro'}
            enlace="/panel/tickets?vista=sla_riesgo"
          />
          <KpiTarjeta
            etiqueta="Críticos"
            valor={datosResumen?.criticos}
            icono={<Flame size={16} aria-hidden="true" />}
            tono={datosResumen?.criticos ? 'peligro' : 'neutro'}
            enlace="/panel/tickets?vista=criticos"
          />
          <KpiTarjeta
            etiqueta="Mis asignaciones"
            valor={datosResumen?.mios}
            icono={<LifeBuoy size={16} aria-hidden="true" />}
            tono="primario"
            enlace="/panel/mis-asignaciones"
          />
          <KpiTarjeta
            etiqueta="Cerrados"
            valor={datosResumen?.cerrados}
            icono={<ShieldCheck size={16} aria-hidden="true" />}
            tono="exito"
            enlace="/panel/cerrados?tab=cerrados"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel
          titulo="Necesitan atención ya"
          descripcion="Críticos y casos cuyo tiempo acordado ya venció."
          acciones={
            <Link
              to="/panel/tickets?vista=criticos"
              className="flex items-center gap-1 text-sm font-semibold text-primary-strong hover:underline"
            >
              Ver todos <ArrowRight size={14} aria-hidden="true" />
            </Link>
          }
        >
          {criticos.isLoading ? (
            <SkeletonPanel filas={3} />
          ) : criticos.isError ? (
            <ErrorState
              compacto
              mensaje="No pudimos cargar los casos críticos."
              alReintentar={() => void criticos.refetch()}
            />
          ) : (criticos.data?.items.length ?? 0) === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No hay casos críticos ni vencidos. Buen momento para ordenar la cola.
            </p>
          ) : (
            <TicketsAtencion tickets={criticos.data?.items ?? []} />
          )}
        </Panel>

        <Panel titulo="Carga del equipo" descripcion="Según horario, días libres, ausencias y tickets asignados">
          {panel.isLoading ? (
            <SkeletonPanel filas={4} />
          ) : panel.isError ? (
            <ErrorState
              compacto
              mensaje="No pudimos cargar el equipo."
              alReintentar={() => void panel.refetch()}
            />
          ) : (
            <ul className="flex flex-col gap-4">
              {(panel.data?.items ?? []).map((tecnico) => {
                const sobrecargado = tecnico.porcentaje_carga >= 90
                const ajustado = tecnico.porcentaje_carga >= 60 && !sobrecargado
                const tono = sobrecargado ? 'peligro' : ajustado ? 'aviso' : 'exito'
                return (
                <li
                  key={tecnico.tecnico_id}
                  className={cn(
                    'rounded-[var(--radius-panel)] border bg-surface p-4',
                    // La tarjeta entera toma el tono de la carga: el problema se ve
                    // antes de leer ningún número, que es lo que se busca en un
                    // panel que se mira de reojo.
                    sobrecargado ? 'border-destructive/40' : ajustado ? 'border-warning/40' : 'border-border',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Avatar nombre={tecnico.tecnico_nombre} tamano="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold">{tecnico.tecnico_nombre}</p>
                      <p className="truncate text-2xs text-muted-foreground">
                        Puede resolver {numero(tecnico.capacidad_diaria)} al día
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <DisponibilidadBadge estado={tecnico.estado} etiqueta={tecnico.etiqueta} tamano="sm" />
                      <span className={cn('text-2xs font-semibold', sobrecargado ? 'text-destructive-strong' : 'text-muted-foreground')}>
                        {numero(tecnico.carga_asignados)} de {numero(tecnico.capacidad_diaria)} del día
                      </span>
                    </div>
                  </div>

                  {/*
                    Una sola fila con la barra, su porcentaje a la derecha y el
                    texto debajo. Antes había tres cifras en cajas, la barra suelta
                    y un párrafo entero: cuatro bloques para decir una sola cosa.
                  */}
                  <div className="mt-3 flex items-center gap-3">
                    <div
                      role="meter"
                      aria-valuenow={Math.round(tecnico.porcentaje_carga)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`Carga de ${tecnico.tecnico_nombre}`}
                      title={`${tecnico.carga_asignados} tickets asignados para una capacidad de ${tecnico.capacidad_diaria} al día`}
                      className="h-2 flex-1 overflow-hidden rounded-full bg-muted"
                    >
                      <div
                        className={cn('h-full rounded-full transition-[width] duration-[var(--transition-ui)]', TONO_BARRA[tono])}
                        style={{ width: `${Math.min(100, tecnico.porcentaje_carga)}%` }}
                      />
                    </div>
                    <span className={cn('w-12 shrink-0 text-right text-sm font-bold tabular-nums', sobrecargado ? 'text-destructive-strong' : 'text-foreground')}>
                      {Math.round(tecnico.porcentaje_carga)} %
                    </span>
                  </div>

                  <p className={cn('mt-1.5 text-2xs', sobrecargado ? 'font-medium text-destructive-strong' : 'text-muted-foreground')}>
                    {sobrecargado && tecnico.carga_asignados > tecnico.capacidad_diaria
                      ? `${tecnico.carga_asignados - tecnico.capacidad_diaria} tickets por encima de lo que puede resolver en un día. Reparta o póngalo en espera.`
                      : tecnico.carga_espera > 0
                        ? `${numero(tecnico.carga_espera)} en espera.`
                        : 'Sin trabajo en espera.'}
                  </p>

                  {tecnico.ticket_actual_codigo ? (
                    <p className="mt-2 truncate border-t border-border/70 pt-2 text-2xs text-muted-foreground">
                      Atendiendo{' '}
                      {/*
                        El código va como enlace: ver «qué está haciendo» y abrir
                        ese caso es el mismo gesto, y quien mira la carga del
                        equipo casi siempre lo que quiere es ir a ese ticket.
                      */}
                      <Link
                        to={`/panel/tickets/${tecnico.ticket_actual_id}`}
                        className="font-semibold text-primary-strong underline underline-offset-2 hover:text-primary"
                      >
                        {tecnico.ticket_actual_codigo}
                      </Link>
                      {tecnico.ticket_oficina ? ` · ${tecnico.ticket_oficina}` : ''}
                    </p>
                  ) : null}
                  {tecnico.sla_mas_critico_min !== null && tecnico.sla_mas_critico_min !== undefined ? (
                    <p className="mt-1 truncate text-2xs text-warning-strong">
                      Caso más apremiante: {duracionCorta(tecnico.sla_mas_critico_min)}
                    </p>
                  ) : null}
                  {tecnico.ausencias.length ? (
                    <p className="mt-1 truncate text-2xs text-muted-foreground">
                      Ausente:{' '}
                      {tecnico.ausencias
                        .map(
                          (ausencia: unknown) =>
                            `${(ausencia as { inicio?: string }).inicio} a ${(ausencia as { fin?: string }).fin}`,
                        )
                        .join(', ')}
                    </p>
                  ) : null}
                </li>
                )
              })}
            </ul>
          )}
        </Panel>
      </div>

      {datosResumen && datosResumen.sla_riesgo > 0 ? (
        <Nota tono="peligro" titulo="Hay casos fuera de tiempo" icono={<CircleAlert size={16} aria-hidden="true" />}>
          <p>
            {datosResumen.sla_riesgo} caso(s) ya pasaron el tiempo acordado. Revisa la{' '}
            <Link to="/panel/tickets?vista=sla_riesgo" className="font-semibold underline">
              lista de SLA en riesgo
            </Link>
            .
          </p>
        </Nota>
      ) : null}
    </>
  )
}

function KpiTarjeta({
  etiqueta,
  valor,
  icono,
  tono,
  enlace,
}: {
  etiqueta: string
  valor: number | undefined
  icono: React.ReactNode
  tono?: 'neutro' | 'primario' | 'exito' | 'aviso' | 'peligro'
  enlace: string
}) {
  return (
    <Link
      to={enlace}
      className="group block rounded-[var(--radius-panel)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      <KpiCard etiqueta={etiqueta} valor={valor ?? 0} icono={icono} tono={tono ?? 'neutro'} />
    </Link>
  )
}

/** Minutos como texto corto: "2 h 15 min" o "Vencido hace 40 min". */
function duracionCorta(minutos: number): string {
  if (minutos < 0) {
    const absoluto = Math.abs(Math.round(minutos))
    return absoluto < 60 ? `vencido hace ${absoluto} min` : `vencido hace ${Math.floor(absoluto / 60)} h`
  }
  if (minutos < 60) return `${Math.round(minutos)} min restantes`
  const horas = Math.floor(minutos / 60)
  const resto = Math.round(minutos) % 60
  return resto ? `${horas} h ${resto} min restantes` : `${horas} h restantes`
}
