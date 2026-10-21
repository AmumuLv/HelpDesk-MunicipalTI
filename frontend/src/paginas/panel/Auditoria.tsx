import { LimpiarRegistros } from '../../componentes/dominio/LimpiarRegistros'
/**
 * Auditoría: qué hizo cada persona y cuándo.
 *
 * Registro de solo lectura, con el antes y el después de cada cambio. No hay
 * forma de editar ni de borrar: es el historial del sistema, y por eso mismo no
 * se toca desde la interfaz.
 */

import { ScrollText, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuditoria } from '../../api/hooks'
import type { FiltrosAuditoria } from '../../api/tipos'
import { DataTable, Paginacion, type ColumnaTabla } from '../../componentes/dominio/DataTable'
import { Button } from '../../componentes/base/Button'
import { Select } from '../../componentes/base/Campo'
import { DialogModal } from '../../componentes/base/Sobreposiciones'
import { EmptyState, ErrorState, Nota, PageHeader, Panel } from '../../componentes/base/Estructura'
import { fechaHora, hoy, numero, sumarDias } from '../../dominio/formato'
import { cambiosAuditoria, ENTIDADES_AUDITORIA } from '../../dominio/auditoria'

type Registro = {
  id: string
  accion: string
  entidad: string
  entidad_id?: string | null
  usuario_nombre: string
  rol?: string
  accion_texto?: string
  resumen?: string
  fecha: string
  antes?: Record<string, unknown> | null
  despues?: Record<string, unknown> | null
  resultado?: string
}

export function Auditoria() {
  const [detalle, setDetalle] = useState<Registro | null>(null)
  // La API filtra auditoría por fechas y acepta `accion` como texto suelto
  const [filtros, setFiltros] = useState<FiltrosAuditoria>({
    desde: sumarDias(hoy(), -15),
    hasta: hoy(),
    pagina: 1,
    por_pagina: 20,
  })
  const auditoria = useAuditoria(filtros)
  const rangoInvalido = Boolean(filtros.desde && filtros.hasta && filtros.hasta < filtros.desde)

  useEffect(() => {
    document.title = 'Auditoría · Mesa de Ayuda TI'
  }, [])

  const acciones = (auditoria.data?.acciones ?? []) as { clave?: string; texto?: string }[]
  const cambios = cambiosAuditoria(detalle?.antes, detalle?.despues)

  const columnas: ColumnaTabla<Registro>[] = [
    {
      accessorKey: 'fecha',
      header: 'Fecha',
      cell: ({ row }) => <span className="text-sm whitespace-nowrap">{fechaHora(row.original.fecha)}</span>,
    },
    {
      accessorKey: 'usuario_nombre',
      header: 'Quién',
      cell: ({ row }) => (
        <span className="block min-w-0">
          <span className="block truncate font-medium">{row.original.usuario_nombre}</span>
          <span className="block truncate text-2xs text-muted-foreground capitalize">{row.original.rol}</span>
        </span>
      ),
    },
    {
      accessorKey: 'accion',
      header: 'Movimiento',
      cell: ({ row }) => <div className="min-w-0"><span className="block text-sm font-medium">{row.original.accion_texto || row.original.accion}</span><span className="mt-1 inline-block rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">{ENTIDADES_AUDITORIA[row.original.entidad] ?? row.original.entidad.replaceAll('_', ' ')}</span>{['error', 'fallido', 'denegado', 'bloqueado'].includes(row.original.resultado ?? '') ? <span className="ml-2 text-xs font-semibold text-destructive">Alerta de seguridad</span> : null}</div>,
    },
    {
      accessorKey: 'resumen',
      header: 'Detalle',
      cell: ({ row }) => <div className="min-w-0 max-w-md"><p className="line-clamp-2 break-words text-sm text-muted-foreground">{row.original.resumen || 'Sin descripción adicional'}</p><button className="mt-1 text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400" onClick={() => setDetalle(row.original)}>Ver detalle</button></div>,
    },
  ]

  return (
    <>
      <PageHeader
        titulo="Auditoría"
        descripcion="Movimientos importantes de administradores y técnicos. Se conservan durante 15 días y se eliminan automáticamente."
        acciones={<>
          <LimpiarRegistros ruta="/auditoria" titulo="Vaciar auditoría" descripcion="Se eliminarán permanentemente los movimientos de auditoría. Los tickets, equipos y cuentas se conservan." alLimpiar={() => auditoria.refetch()} />
          <Button variante="secundario" asChild>
            <Link to={`/panel/reportes?tipo=auditoria&desde=${filtros.desde || ''}&hasta=${filtros.hasta || ''}${filtros.accion ? `&accion=${encodeURIComponent(filtros.accion)}` : ''}`} className="flex min-w-0 items-center gap-2">
              <ShieldCheck size={16} className="shrink-0" aria-hidden="true" />
              <span className="min-w-0 truncate">Reporte de auditoría</span>
            </Link>
          </Button>
        </>}
      />

      <Panel>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-semibold">Desde</span>
            <input
              type="date"
              value={filtros.desde ?? ''}
              onChange={(evento) =>
                setFiltros((actual) => ({ ...actual, desde: evento.target.value, pagina: 1 }))
              }
              className="h-[var(--spacing-control)] rounded-[var(--radius-control)] border border-input bg-surface px-3"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-semibold">Hasta</span>
            <input
              type="date"
              value={filtros.hasta ?? ''}
              onChange={(evento) =>
                setFiltros((actual) => ({ ...actual, hasta: evento.target.value, pagina: 1 }))
              }
              className="h-[var(--spacing-control)] rounded-[var(--radius-control)] border border-input bg-surface px-3"
            />
          </label>
          <Select
            etiqueta="Acción"
            value={filtros.accion || ''}
            onChange={(evento) => {
              setFiltros((actual) => ({ ...actual, accion: evento.target.value || undefined, pagina: 1 }))
            }}
            placeholder="Todas"
            opciones={acciones.map((item) => ({
              valor: item.clave ?? '',
              etiqueta: item.texto ?? item.clave ?? '',
            }))}
          />
        </div>
      </Panel>

      {rangoInvalido ? <Nota tono="aviso">La fecha final debe ser igual o posterior a la inicial.</Nota> : auditoria.isError ? (
        <ErrorState
          mensaje="No pudimos cargar el registro de auditoría."
          detalle={auditoria.error instanceof Error ? auditoria.error.message : undefined}
          alReintentar={() => void auditoria.refetch()}
        />
      ) : (auditoria.data?.items.length ?? 0) === 0 && !auditoria.isLoading ? (
        <EmptyState
          icono={<ScrollText size={20} aria-hidden="true" />}
          titulo="No hay movimientos en este periodo"
          descripcion="Amplía el rango de fechas o quita el filtro de acción."
        />
      ) : (
        <>
          <DataTable
            columnas={columnas}
            datos={(auditoria.data?.items ?? []) as Registro[]}
            claveFila={(fila) => fila.id}
            cargando={auditoria.isLoading}
            columnasConfigurables
            etiquetaVacia="No hay movimientos en este periodo."
            tarjeta={(registro) => (
              <>
                <p className="font-semibold">{registro.resumen ?? registro.accion}</p>
                <p className="text-sm text-muted-foreground">
                  {registro.usuario_nombre} · {ENTIDADES_AUDITORIA[registro.entidad] ?? registro.entidad} · {fechaHora(registro.fecha)}
                </p>
                <button className="mt-2 text-sm text-blue-600 hover:underline dark:text-blue-400" onClick={() => setDetalle(registro)}>Ver detalle</button>
              </>
            )}
          />
          <Paginacion
            pagina={auditoria.data?.pagina ?? 1}
            totalPaginas={Math.max(1, Math.ceil((auditoria.data?.total ?? 0) / 20))}
            total={auditoria.data?.total ?? 0}
            porPagina={20}
            alCambiar={(pagina) => setFiltros((actual) => ({ ...actual, pagina }))}
          />
          <p className="text-sm text-muted-foreground">
            {numero(auditoria.data?.total ?? 0)} movimientos registrados en el periodo.
          </p>
        </>
      )}

      <Nota tono="info">
        <p>
          Se muestran cambios importantes y alertas. Los chats, notas, consultas de IA, exportaciones e inicios de sesión exitosos quedan fuera de esta vista. El historial de atención se consulta en cada ticket.
        </p>
      </Nota>
      <DialogModal abierto={Boolean(detalle)} alCerrar={() => setDetalle(null)} titulo="Detalle del movimiento" descripcion={detalle ? `${detalle.usuario_nombre} · ${fechaHora(detalle.fecha)}` : undefined}>
        {detalle ? <div className="space-y-4">
          <div className="rounded-lg border border-border bg-surface-2 p-4"><p className="font-semibold">{detalle.accion_texto || detalle.accion}</p><p className="mt-1 break-words text-sm">{detalle.resumen || 'Sin descripción adicional.'}</p><p className="mt-2 text-xs text-muted-foreground">{ENTIDADES_AUDITORIA[detalle.entidad] ?? detalle.entidad.replaceAll('_', ' ')}</p></div>
          {cambios.length ? <section><h3 className="mb-3 text-sm font-semibold">Qué cambió</h3><ul className="space-y-3">{cambios.map((cambio) => <li key={cambio.campo} className="rounded-lg border border-border p-3"><h4 className="mb-2 break-words text-sm font-semibold capitalize">{cambio.campo}</h4><div className="grid grid-cols-2 gap-3 text-sm"><div className="min-w-0"><p className="mb-1 text-xs text-muted-foreground">Antes</p><p className="whitespace-pre-wrap break-words">{cambio.antes}</p></div><div className="min-w-0 border-l border-border pl-3"><p className="mb-1 text-xs text-muted-foreground">Después</p><p className="whitespace-pre-wrap break-words">{cambio.despues}</p></div></div></li>)}</ul></section> : <p className="text-sm text-muted-foreground">Este movimiento conserva su descripción; no incluye cambios de campos registrados.</p>}
        </div> : null}
      </DialogModal>
    </>
  )
}
