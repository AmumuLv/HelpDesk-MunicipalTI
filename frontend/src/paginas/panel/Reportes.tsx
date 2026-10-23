import { LimpiarRegistros } from '../../componentes/dominio/LimpiarRegistros'
import { CheckCircle2, Download, FileSpreadsheet, FileText, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../../api/cliente'
import { descargarDeLaApi, nombreDeArchivo } from '../../api/descarga'
import { useExportaciones, useOficinas, useZonas } from '../../api/hooks'
import { Button } from '../../componentes/base/Button'
import { Input, Select } from '../../componentes/base/Campo'
import { EmptyState, ErrorState, NoPermission, Nota, PageHeader, Panel, SkeletonPanel } from '../../componentes/base/Estructura'
import { fechaHora, fechaNumerica, hoy, sumarDias, tamano } from '../../dominio/formato'
import { useAvisos } from '../../estado/Avisos'
import { useSesion } from '../../estado/Sesion'

const REPORTES = [
  { valor: 'tickets', etiqueta: 'Tickets del periodo', detalle: 'Para revisar qué se reportó y cómo se encuentra cada caso creado en las fechas elegidas.', incluye: ['Casos abiertos y finalizados', 'Persona, equipo y ubicación', 'Técnico, fechas y tiempos'] },
  { valor: 'inventario', etiqueta: 'Inventario por zona', detalle: 'Para conocer los equipos registrados actualmente y quién los tiene a cargo. No depende de un periodo.', incluye: ['Equipos y responsables', 'Ubicación y patrimonio', 'Excel por zonas · PDF por zonas'] },
  { valor: 'carga_equipo', etiqueta: 'Carga del equipo TI', detalle: 'Casos creados en el periodo, agrupados por el técnico asignado actualmente. Los finalizados son parte de esos casos; no son todos los cierres realizados en esas fechas.', incluye: ['Casos del periodo por técnico', 'Pendientes de todo su historial', 'Disponibilidad actual'] },
  { valor: 'analitica', etiqueta: 'Resumen de atención de tickets', detalle: 'Para presentar resultados de atención: volumen, tiempos, cumplimiento de plazos y satisfacción, con comparación del periodo anterior.', incluye: ['Cuatro indicadores principales', 'Oficinas, zonas y problemas frecuentes', 'Atención TI y estado de los plazos'] },
  { valor: 'auditoria', etiqueta: 'Movimientos importantes', detalle: 'Para revisar quién cambió qué y cuándo: cuentas, permisos, inventario, tickets y alertas de seguridad.', incluye: ['Fecha y responsable', 'Acción y registro afectado', 'Descripción del cambio'] },
]

const NOMBRES_ADICIONALES: Record<string, string> = { ticket_individual: 'Ficha de ticket', equipo: 'Ficha de equipo', pendientes_calidad: 'Datos pendientes de inventario', campana: 'Verificación de inventario' }

export function Reportes() {
  const avisos = useAvisos()
  const sesion = useSesion()
  const [parametros, setParametros] = useSearchParams()
  const exportaciones = useExportaciones(sesion.puede('exportar'))
  const [tipo, setTipo] = useState(REPORTES.some((r) => r.valor === parametros.get('tipo')) ? parametros.get('tipo')! : 'tickets')
  const [formato, setFormato] = useState('excel')
  const [desde, setDesde] = useState(parametros.get('desde') || sumarDias(hoy(), -29))
  const [hasta, setHasta] = useState(parametros.get('hasta') || hoy())
  const [zonaId, setZonaId] = useState('')
  const [oficinaId, setOficinaId] = useState('')
  const zonas = useZonas()
  const oficinas = useOficinas(zonaId ? { zona_id: zonaId } : {})
  const [conNotas, setConNotas] = useState(false)
  const [pidiendo, setPidiendo] = useState(false)
  const [descargando, setDescargando] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const esInventario = tipo === 'inventario'
  const esAuditoria = tipo === 'auditoria'
  const elegido = REPORTES.find((r) => r.valor === tipo)!
  const fechasInvalidas = !esInventario && (!desde || !hasta || hasta < desde)
  const opciones = REPORTES.filter((r) => r.valor !== 'analitica' || sesion.puede('analitica.ver')).filter((r) => r.valor !== 'auditoria' || sesion.puede('reportes.ver'))
  useEffect(() => { document.title = 'Reportes · Mesa de Ayuda TI' }, [])
  const pedir = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (pidiendo || fechasInvalidas) return
    setPidiendo(true); setError(null)
    try {
      await api.crear('/exportaciones', { tipo, formato,
        filtros: { ...(!esInventario ? { fecha_desde: desde, fecha_hasta: hasta } : {}),
          ...(!esAuditoria && zonaId ? { zona_id: zonaId } : {}), ...(!esAuditoria && oficinaId ? { oficina_id: oficinaId } : {}),
          ...(esAuditoria && parametros.get('accion') ? { accion: parametros.get('accion') } : {}),
        }, incluir_notas_internas: tipo === 'tickets' && conNotas,
      })
      await exportaciones.refetch()
      avisos.exito('Archivo listo', 'Ya puedes descargarlo desde la lista de archivos.')
    } catch (fallo) { setError(fallo instanceof Error ? fallo.message : 'No pudimos generar el archivo. Revisa los filtros e inténtalo de nuevo.') }
    finally { setPidiendo(false) }
  }
  const bajar = async (item: { id: string; nombre_archivo: string }) => {
    if (descargando) return
    setDescargando(item.id)
    try { await descargarDeLaApi(`/exportaciones/${item.id}/descargar`, nombreDeArchivo(item.nombre_archivo, 'reporte')) }
    catch (fallo) { avisos.desdeError(fallo) }
    finally { setDescargando(null) }
  }
  if (!sesion.puede('exportar')) return <NoPermission queIntentas="la generación y descarga de reportes" permiso="exportar" />
  return <>
    <PageHeader titulo="Reportes" descripcion="Cinco informes esenciales para revisar casos, inventario y atención TI." />
    <div className="mb-4 grid gap-3 sm:grid-cols-3">
      {[['1', 'Elige el informe', 'Cada reporte responde una pregunta distinta.'], ['2', 'Define el alcance', 'Revisa las fechas y la ubicación antes de generar.'], ['3', 'Descarga y comparte', 'PDF para presentar; Excel o CSV para trabajar los datos.']].map(([paso, titulo, detalle]) => <div key={paso} className="flex gap-3 rounded-xl border border-border bg-surface-2/60 p-3"><span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft font-bold text-primary-strong">{paso}</span><div><p className="text-sm font-semibold">{titulo}</p><p className="mt-1 text-xs text-muted-foreground">{detalle}</p></div></div>)}
    </div>
    <div className="grid min-w-0 gap-4 xl:grid-cols-2">
      <Panel titulo="Preparar reporte" descripcion="Elige el contenido y su alcance antes de generar el archivo.">
        <form onSubmit={pedir} className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Select etiqueta="Reporte" value={tipo} disabled={pidiendo} opciones={opciones} onChange={(e) => { setTipo(e.target.value); setConNotas(false); setError(null) }} />
            <Select etiqueta="Formato" value={formato} disabled={pidiendo} opciones={[{ valor: 'excel', etiqueta: 'Excel (.xlsx)' }, { valor: 'pdf', etiqueta: 'Informe PDF · horizontal' }, { valor: 'csv', etiqueta: 'CSV · tabla continua' }]} onChange={(e) => setFormato(e.target.value)} />
            {!esInventario ? <>
              <Input etiqueta="Desde" type="date" requerido value={desde} disabled={pidiendo} onChange={(e) => setDesde(e.target.value)} />
              <Input etiqueta="Hasta" type="date" requerido min={desde} value={hasta} disabled={pidiendo} error={hasta < desde ? 'La fecha final debe ser igual o posterior al inicio.' : undefined} onChange={(e) => setHasta(e.target.value)} />
            </> : null}
            {!esAuditoria ? <>
              <Select etiqueta="Zona" value={zonaId} placeholder="Todas las zonas" disabled={pidiendo || zonas.isPending} opciones={(zonas.data?.items ?? []).map((z) => ({ valor: z.id, etiqueta: z.nombre }))} onChange={(e) => { setZonaId(e.target.value); setOficinaId('') }} />
              <Select etiqueta="Oficina" value={oficinaId} placeholder="Todas las oficinas" disabled={pidiendo || oficinas.isFetching} opciones={(oficinas.data?.items ?? []).map((o) => ({ valor: o.id, etiqueta: o.nombre }))} onChange={(e) => setOficinaId(e.target.value)} />
            </> : null}
          </div>
          {!esInventario ? <div className="flex flex-wrap items-center gap-2"><span className="text-xs text-muted-foreground">Periodo rápido:</span>{[{ etiqueta: 'Hoy', dias: 0 }, { etiqueta: 'Últimos 7 días', dias: 6 }, { etiqueta: 'Últimos 30 días', dias: 29 }].map((periodo) => <Button key={periodo.dias} tamano="sm" variante="fantasma" disabled={pidiendo} onClick={() => { setDesde(sumarDias(hoy(), -periodo.dias)); setHasta(hoy()) }}>{periodo.etiqueta}</Button>)}</div> : null}
          <div className="rounded-xl border border-primary/30 bg-primary-soft/30 p-4 text-sm" aria-live="polite">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary-strong">Contenido del archivo</p>
            <h2 className="font-semibold">{elegido.etiqueta}</h2>
            <p className="mt-2 text-muted-foreground">{elegido.detalle}</p>
            <ul className="my-3 grid gap-2">{elegido.incluye.map((contenido) => <li key={contenido} className="flex items-start gap-2"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-primary-strong" /><span>{contenido}</span></li>)}</ul>
            {!esInventario ? <p className="mt-1 text-xs text-muted-foreground">Del {fechaNumerica(desde)} al {fechaNumerica(hasta)}, ambos días incluidos.</p> : null}
            {tipo === 'carga_equipo' ? <p className="mt-2 text-xs text-muted-foreground">La carga pendiente actual abarca todas las ubicaciones del técnico, aunque filtres los casos del periodo por oficina.</p> : null}
            {tipo === 'analitica' && formato !== 'pdf' ? <p className="mt-2 text-xs text-muted-foreground">El archivo de datos también incluye métricas del asistente y familias de equipos. Estas últimas cubren los últimos doce meses.</p> : null}
            {esAuditoria && parametros.get('accion') ? <div className="mt-2 flex flex-wrap items-center gap-2 text-xs"><span>Acción: {parametros.get('accion')}</span><Button tamano="sm" variante="fantasma" onClick={() => { const siguientes = new URLSearchParams(parametros); siguientes.delete('accion'); setParametros(siguientes) }}>Quitar filtro</Button></div> : null}
            <p className="mt-2 text-xs text-muted-foreground">{formato === 'pdf' ? 'PDF A4 horizontal, encabezados repetidos y páginas numeradas.' : formato === 'excel' ? 'Filas continuas, filtros por columna y encabezado fijo. Fechas y números conservan su formato.' : 'Una sola tabla separada por punto y coma, compatible con Excel.'}</p>
          </div>
          {tipo === 'tickets' ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={conNotas} disabled={pidiendo} onChange={(e) => setConNotas(e.target.checked)} className="mt-0.5 size-4 accent-primary" /><span>Incluir notas internas<span className="block text-xs text-muted-foreground">Solo para documentos de trabajo del equipo TI.</span></span></label> : null}
          {error ? <Nota tono="peligro" titulo="No se pudo generar el reporte">{error}</Nota> : null}
          <div className="flex justify-end"><Button type="submit" variante="primario" cargando={pidiendo} disabled={Boolean(fechasInvalidas) || (!esAuditoria && (zonas.isError || oficinas.isError))} icono={formato === 'pdf' ? <FileText size={16} /> : <FileSpreadsheet size={16} />}>{pidiendo ? 'Generando archivo…' : 'Generar archivo'}</Button></div>
          {!esAuditoria && (zonas.isError || oficinas.isError) ? <ErrorState compacto mensaje="No pudimos cargar las ubicaciones." alReintentar={() => { void zonas.refetch(); void oficinas.refetch() }} /> : null}
        </form>
      </Panel>
      <Panel titulo="Archivos generados" descripcion="Últimos 25 archivos disponibles. Los archivos se conservan durante siete días."
        acciones={<div className="flex flex-wrap gap-2"><LimpiarRegistros ruta="/exportaciones" titulo="Limpiar reportes" descripcion="Se eliminarán los archivos generados y su historial. No se eliminan tickets ni equipos. Las tareas en curso se conservarán." alLimpiar={() => exportaciones.refetch()} /><Button tamano="sm" disabled={exportaciones.isFetching} icono={<RefreshCw size={14} />} onClick={() => void exportaciones.refetch()}>Actualizar lista</Button></div>}>
        {exportaciones.isPending ? <SkeletonPanel filas={3} /> : exportaciones.isError ? <ErrorState compacto mensaje="No pudimos cargar los archivos." alReintentar={() => void exportaciones.refetch()} /> : !exportaciones.data?.items.length ? <EmptyState compacto icono={<FileSpreadsheet size={20} />} titulo="Todavía no has generado archivos" descripcion="Prepara el reporte y aparecerá aquí para descargarlo." /> : <ul className="max-h-[640px] divide-y divide-border overflow-y-auto">
          {exportaciones.data.items.map((item) => <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-strong">{item.formato === 'pdf' ? <FileText size={19} /> : <FileSpreadsheet size={19} />}</span>
            <div className="min-w-0 flex-1"><p className="text-sm font-semibold">{REPORTES.find((r) => r.valor === item.tipo)?.etiqueta || NOMBRES_ADICIONALES[item.tipo] || 'Reporte'} <span className="text-xs font-normal text-muted-foreground">· {item.formato === 'excel' ? 'XLSX' : item.formato.toUpperCase()}</span></p>
              <p className="mt-0.5 text-xs text-muted-foreground">{fechaHora(item.creado_en)} · {tamano(item.tamanio)} · {item.usuario_nombre}</p>
              <p className="mt-1 text-xs text-muted-foreground" title={item.nombre_archivo}>{item.alcance || item.nombre_archivo}</p>
              {item.error ? <p className="mt-1 break-words text-xs text-destructive-strong">No se completó: {item.error}</p> : null}
            </div>
            {item.estado === 'listo' ? <Button tamano="sm" icono={<Download size={14} />} disabled={Boolean(descargando)} onClick={() => void bajar(item)}>{descargando === item.id ? 'Descargando…' : 'Descargar'}</Button> : <span className="text-xs font-medium text-muted-foreground">{item.estado === 'en_proceso' ? 'Generando…' : 'No disponible'}</span>}
          </li>)}
        </ul>}
      </Panel>
    </div>
  </>
}
