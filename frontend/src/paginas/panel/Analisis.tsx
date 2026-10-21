/**
 * Análisis IA: dos pestañas y ninguna más.
 *
 * «Paneles» muestra indicadores y el historial real de incidencias.
 * El historial por familia no se presenta como una predicción futura.
 *
 * «Asistente» es una conversación con fuentes. Si la ayuda avanzada no está
 * disponible, lo explica y conserva las funciones básicas.
 */

import { RefreshCw, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { DataTable, Paginacion } from '../../componentes/dominio/DataTable'

import { useEstadoIa, usePanelAnalitica, usePrediccionEquipos } from '../../api/hooks'
import { AsistenteAnalisis } from '../../componentes/dominio/AsistenteAnalisis'
import { KpiCard, KpiPorcentaje } from '../../componentes/dominio/KpiCard'
import { BarrasCampos, ChartCard, GraficoLinea, SinDatos } from '../../componentes/graficos/Graficos'
import { ContenidoTab, ErrorState, ListaTabs, Nota, PageHeader, Panel, SkeletonPanel, Tab, TabsPanel } from '../../componentes/base/Estructura'
import { Button } from '../../componentes/base/Button'
import { Select } from '../../componentes/base/Campo'
import { duracionLegible, fechaNumerica, numero } from '../../dominio/formato'
import { TEXTOS_IA } from '../../dominio/textos-ia'
import { MosaicoGraficos } from '../../componentes/graficos/MosaicoGraficos'

const PERIODOS = [
  { valor: '30d', etiqueta: 'Últimos 30 días' },
  { valor: '90d', etiqueta: 'Últimos 90 días' },
  { valor: '365d', etiqueta: 'Último año' },
]

export function Analisis() {
  const [parametros, setParametros] = useSearchParams()
  const pestana = parametros.get('tab') === 'asistente' ? 'asistente' : 'paneles'
  const periodo = PERIODOS.some((p) => p.valor === parametros.get('periodo')) ? parametros.get('periodo')! : '30d'
  const cambiar = (clave: string, valor: string) => { const siguientes = new URLSearchParams(parametros); siguientes.set(clave, valor); setParametros(siguientes) }
  const panel = usePanelAnalitica({ periodo })
  const prediccion = usePrediccionEquipos()
  const estadoIa = useEstadoIa()
  const [paginaConjuntos, setPaginaConjuntos] = useState(1)
  const conjuntos = panel.data?.ranking_conjuntos?.items ?? []

  useEffect(() => {
    document.title = 'Análisis IA · Mesa de Ayuda TI'
  }, [])

  const kpis = panel.data?.kpis

  const panelFamilias = (<Panel titulo="Incidencias por familia de equipos" descripcion="Historial de los últimos 12 meses, independiente del periodo seleccionado. No es una predicción de fallas futuras.">
            {prediccion.isPending ? <SkeletonPanel filas={3} /> : prediccion.isError ? <ErrorState compacto mensaje="No pudimos cargar el historial de equipos." alReintentar={() => void prediccion.refetch()} /> : !prediccion.data?.familias.length ? <SinDatos titulo="Sin equipos para analizar" descripcion="Registra equipos y vincula sus incidencias para consultar este historial." /> : <>
              <BarrasCampos unidad="%" sufijo="%" maximo={100} anchoEtiqueta="w-2/5" datos={prediccion.data.familias.map((f) => ({ etiqueta: f.tipo || 'Sin tipo', valor: Math.round(f.tasa_falla * 1000) / 10, detalle: `${f.tickets_12m} tickets / ${f.activos} equipos` }))} pie="Porcentaje de equipos con al menos una incidencia. Varios tickets del mismo equipo cuentan una sola vez en este porcentaje." />
              <p className="mt-3 text-xs text-muted-foreground">Consulta los equipos con incidencias antes de planificar su mantenimiento.</p>
            </>}
          </Panel>)

  return (
    <>
      <PageHeader
        titulo="Análisis IA"
        descripcion="Indicadores del servicio, historial de incidencias y consultas con fuentes."
        acciones={
          <div className="flex flex-wrap items-end gap-2">
          <Button icono={<RefreshCw size={15} />} disabled={panel.isFetching || prediccion.isFetching} onClick={() => { void panel.refetch(); void prediccion.refetch(); void estadoIa.refetch() }}>Actualizar datos</Button>
          <Select
            etiqueta="Periodo"
            value={periodo}
            onChange={(evento) => cambiar('periodo', evento.target.value)}
            opciones={PERIODOS}
          /></div>
        }
      />

      <TabsPanel valor={pestana} alCambiar={(tab) => cambiar('tab', tab)} className="flex flex-col gap-4">
        <ListaTabs>
          <Tab valor="paneles">Paneles</Tab>
          <Tab valor="asistente">Consultas de datos</Tab>
        </ListaTabs>

        <ContenidoTab valor="paneles" className="flex flex-col gap-4">
          {estadoIa.data && !estadoIa.data.disponible ? (
            <Nota tono="info" titulo="Ayuda automática limitada" icono={<Sparkles size={16} aria-hidden="true" />}>
              <p>{TEXTOS_IA.basica}</p>
            </Nota>
          ) : null}

          {panel.isPending ? <SkeletonPanel filas={6} /> : panel.isError ? <ErrorState mensaje="No pudimos cargar el análisis." detalle={panel.error.message} alReintentar={() => void panel.refetch()} /> : <>
          <p className="text-xs text-muted-foreground">Periodo: {fechaNumerica(kpis?.periodo.desde)} — {fechaNumerica(kpis?.periodo.hasta)}. Tickets creados en estas fechas; se excluyen los eliminados.</p>
          {kpis?.suficiente_datos === false ? (
            <Nota tono="aviso" titulo="Datos insuficientes para este periodo">
              <p>
                Hay pocos tickets en {periodo === '30d' ? 'los últimos 30 días' : 'el periodo elegido'} para concluir
                algo con confianza. Los recuentos siguen disponibles; las estimaciones requieren más historial.
              </p>
            </Nota>
          ) : null}

          <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
            <KpiCard
              etiqueta="Tickets del periodo"
              valor={kpis?.tickets_analizados}
              variacion={kpis?.variacion}
              cargando={panel.isLoading}
            />
            <KpiCard etiqueta="Cerrados" valor={kpis?.cerrados} tono="exito" cargando={panel.isLoading} />
            <KpiCard
              etiqueta="Tiempo medio de resolución"
              valor={duracionLegible(kpis?.tiempo_medio_resolucion_min)}
              cargando={panel.isLoading}
            />
            <KpiPorcentaje
              etiqueta="Cumplimiento de SLA"
              porcentaje={kpis?.cumplimiento_sla}
              tono="primario"
              cargando={panel.isLoading}
            />
            <KpiCard
              etiqueta="Satisfacción"
              valor={kpis?.satisfaccion_promedio}
              sufijo="/5"
              cargando={panel.isLoading}
            />
            <KpiPorcentaje
              etiqueta="Precisión de la clasificación"
              porcentaje={kpis?.precision_clasificacion}
              detalle={kpis?.precision_clasificacion == null ? 'Sin evaluaciones de clasificación' : 'Según evaluaciones registradas de la clasificación'}
              tono="ia"
              cargando={panel.isLoading}
            />
          </div>

          <MosaicoGraficos>
            <Panel titulo="Computadoras con más incidencias" descripcion="Incluye componentes y programas vinculados a la PC. Cada ticket se cuenta una vez en este ranking.">
              <DataTable datos={conjuntos.slice((paginaConjuntos - 1) * 10, paginaConjuntos * 10)} claveFila={c => c.id} permitirOrdenar={false} columnas={[
                { accessorKey: 'nombre', header: 'Computadora', cell: ({ row }) => <div><p className="font-semibold">{row.original.nombre}</p><p className="text-xs text-muted-foreground">{row.original.oficina}</p><p className="text-xs">{row.original.responsable_id ? <Link to={`/panel/usuarios/${row.original.responsable_id}`} className="text-primary-strong hover:underline">{row.original.responsable}</Link> : row.original.responsable}</p></div> },
                { accessorKey: 'total', header: 'Tickets' }, { accessorKey: 'programas', header: 'Programas' }, { accessorKey: 'abiertos', header: 'Abiertos' },
              ]} />
              <Paginacion pagina={paginaConjuntos} totalPaginas={Math.ceil(conjuntos.length / 10)} total={conjuntos.length} porPagina={10} alCambiar={setPaginaConjuntos} />
            </Panel>
            <GraficoLinea
              titulo="Tickets por día"
              descripcion="Casos registrados en el periodo"
              unidad="tickets"
              datos={lineaDelPanel(panel.data)}
            />
            <RankingAnalisis
              titulo="Oficinas con más tickets"
              destino="oficinas"
              datos={(panel.data?.ranking_oficinas?.items ?? []).map((fila) => ({
                id: fila.id || undefined,
                etiqueta: fila.oficina ?? 'Sin oficina',
                valor: fila.total,
                detalle: `${numero(fila.criticas ?? 0)} críticos`,
              }))}
            />
            <RankingAnalisis
              titulo="Zonas con más tickets"
              destino="zonas"
              datos={(panel.data?.ranking_zonas?.items ?? []).map((fila) => ({
                id: fila.id || undefined,
                etiqueta: fila.zona,
                valor: fila.total,
              }))}
            />
            <Panel titulo="SLA vencidos por oficina" descripcion="Tickets abiertos del periodo que superaron su plazo; excluye casos sin fecha límite">
              {(panel.data?.riesgo_sla_oficina?.items?.length ?? 0) === 0 ? (
                <SinDatos titulo="Sin datos de riesgo en este periodo" />
              ) : (
                <GraficoBarrasInterno
                  datos={(panel.data?.riesgo_sla_oficina?.items ?? []).map((fila) => ({
                    etiqueta: fila.nombre,
                    valor: fila.vencidos,
                  }))}
                />
              )}
            </Panel>
            <Panel titulo="Causas más frecuentes" descripcion="Categoría y problema o equipo registrados en los tickets">
              {(panel.data?.causas?.items?.length ?? 0) === 0 ? (
                <SinDatos titulo="Sin causas identificadas" />
              ) : (
                <GraficoBarrasInterno
                  datos={(panel.data?.causas?.items ?? []).map((fila) => ({
                    etiqueta: etiquetaCausa(fila.categoria, fila.problema),
                    valor: fila.total,
                  }))}
                />
              )}
            </Panel>
            {panelFamilias}
          </MosaicoGraficos>

          </>}
          {(panel.isPending || panel.isError) && panelFamilias}
        </ContenidoTab>

        <ContenidoTab valor="asistente">
          <AsistenteAnalisis periodo={periodo} />
        </ContenidoTab>
      </TabsPanel>
    </>
  )
}


/** Serie diaria, manteniendo la fecha completa en los datos accesibles. */
function lineaDelPanel(panel: { tendencia?: { serie?: { fecha?: string; valor?: number }[] } } | undefined) {
  return (panel?.tendencia?.serie ?? []).map((punto) => ({ etiqueta: punto.fecha ?? '', valor: Number(punto.valor ?? 0) }))
}
function GraficoBarrasInterno({ datos }: { datos: { etiqueta: string; valor: number }[] }) {
  return <BarrasCampos datos={datos} unidad="casos" anchoEtiqueta="w-2/5" />
}

function etiquetaCausa(categoria: string, problema: string | null) {
  const clave = (texto: string) => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]/gi, '').toLowerCase()
  return !problema || clave(categoria) === clave(problema) ? categoria : `${categoria} · ${problema}`
}

function RankingAnalisis({ titulo, destino, datos }: { titulo: string; destino: 'oficinas' | 'zonas'; datos: { id?: string; etiqueta: string; valor: number; detalle?: string }[] }) {
  const navegar = useNavigate()
  return <ChartCard titulo={titulo} descripcion="Hasta ocho resultados; abre una fila para consultar su detalle. La tabla contiene el listado completo." tabla={datos} sufijo="tickets">
    <BarrasCampos datos={datos.slice(0, 8)} unidad="tickets" anchoEtiqueta="w-2/5" descripcionSeleccion="Abrir detalle." alSeleccionar={(fila) => navegar(`/panel/${destino}/${fila.id}`)} pie={`${numero(datos.reduce((suma, fila) => suma + fila.valor, 0))} tickets en total en este periodo.`} />
  </ChartCard>
}
