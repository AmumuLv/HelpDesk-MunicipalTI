/**
 * Análisis IA: dos pestañas y ninguna más.
 *
 * «Paneles» muestra indicadores y el historial real de incidencias.
 * El historial por familia no se presenta como una predicción futura.
 *
 * «Asistente» es una conversación con fuentes. Si la ayuda avanzada no está
 * disponible, lo explica y conserva las funciones básicas.
 */

import { Activity, RefreshCw, ScanLine, ShieldCheck, Sparkles, Star, TicketCheck, Timer } from 'lucide-react'
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
import { BloqueLectura, GuiaIndicador, ResumenLectura } from '../../componentes/dominio/LecturaAnalisis'
import './Analisis.css'

const PERIODOS = [
  { valor: '7d', etiqueta: 'Últimos 7 días' },
  { valor: '30d', etiqueta: 'Últimos 30 días' },
  { valor: '90d', etiqueta: 'Últimos 90 días' },
  { valor: '365d', etiqueta: 'Último año' },
  { valor: 'mes', etiqueta: 'Este mes' },
  { valor: 'mes_anterior', etiqueta: 'Mes anterior' },
  { valor: 'anio', etiqueta: 'Este año' },
]

export function Analisis() {
  const [parametros, setParametros] = useSearchParams()
  const pestana = parametros.get('tab') === 'asistente' ? 'asistente' : 'paneles'
  const periodo = PERIODOS.some((p) => p.valor === parametros.get('periodo')) ? parametros.get('periodo')! : '30d'
  const cambiar = (clave: string, valor: string) => { const siguientes = new URLSearchParams(parametros); siguientes.set(clave, valor); setParametros(siguientes) }
  const consultar = (pregunta: string) => { const siguientes = new URLSearchParams(parametros); siguientes.set('tab', 'asistente'); siguientes.set('pregunta', pregunta); siguientes.delete('conversacion'); setParametros(siguientes) }
  const panel = usePanelAnalitica({ periodo })
  const prediccion = usePrediccionEquipos()
  const estadoIa = useEstadoIa()
  const [paginaConjuntos, setPaginaConjuntos] = useState(1)
  const conjuntos = panel.data?.ranking_conjuntos?.items ?? []

  useEffect(() => {
    document.title = 'Análisis IA · Mesa de Ayuda TI'
  }, [])

  const kpis = panel.data?.kpis


  const panelFamilias = (<BloqueLectura significado="Una familia es un tipo de dispositivo: laptop, monitor, impresora, etc." calculo="Equipos de ese tipo con al menos una incidencia ÷ equipos de ese tipo × 100. Varios tickets de un equipo cuentan una sola vez." limite="Usa los últimos doce meses, no el periodo del selector. No predice qué equipo fallará después."><Panel titulo="Incidencias por familia de equipos" descripcion="Qué tipos de dispositivos tuvieron problemas en los últimos 12 meses.">
            {prediccion.isPending ? <SkeletonPanel filas={3} /> : prediccion.isError ? <ErrorState compacto mensaje="No pudimos cargar el historial de equipos." alReintentar={() => void prediccion.refetch()} /> : !prediccion.data?.familias.length ? <SinDatos titulo="Sin equipos para analizar" descripcion="Registra equipos y vincula sus incidencias para consultar este historial." /> : <>
              <BarrasCampos unidad="%" sufijo="%" maximo={100} anchoEtiqueta="w-2/5" datos={prediccion.data.familias.map((f) => ({ etiqueta: f.tipo || 'Sin tipo', valor: Math.round(f.tasa_falla * 1000) / 10, detalle: `${f.tickets_12m} tickets / ${f.activos} equipos` }))} pie="Porcentaje de equipos con al menos una incidencia. Varios tickets del mismo equipo cuentan una sola vez en este porcentaje." />
              <p className="mt-3 text-xs text-muted-foreground">Consulta los equipos con incidencias antes de planificar su mantenimiento.</p>
            </>}
          </Panel></BloqueLectura>)

  return (
    <div className="analisis-centro">
      <PageHeader
        titulo="Análisis IA"
        descripcion="Entiende la atención, detecta qué revisar y consulta tus datos con explicaciones claras."
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
          {panel.data ? <ResumenLectura datos={panel.data} alPreguntar={consultar} /> : null}
          <p className="text-xs text-muted-foreground">Periodo: {fechaNumerica(kpis?.periodo.desde)} — {fechaNumerica(kpis?.periodo.hasta)}. Tickets creados en estas fechas; se excluyen los eliminados.</p>
          {kpis?.suficiente_datos === false ? (
            <Nota tono="aviso" titulo="Datos insuficientes para este periodo">
              <p>
                Hay pocos tickets en {periodo === '30d' ? 'los últimos 30 días' : 'el periodo elegido'} para concluir
                algo con confianza. Los recuentos siguen disponibles; las estimaciones requieren más historial.
              </p>
            </Nota>
          ) : null}

          <div className="analisis-section-title"><h2>Tu servicio en seis cifras</h2><p>Abre «Cómo interpretar» cuando necesites una explicación.</p></div>
          <div className="analisis-indicators">
            <div className="analisis-indicator"><KpiCard etiqueta="Tickets del periodo" valor={kpis?.tickets_analizados} icono={<Activity size={19} />} detalle="Reportes creados en las fechas elegidas." />
              <GuiaIndicador significado="Cuántos reportes nuevos se registraron." calculo="Cuenta los tickets cuya fecha de creación está dentro del intervalo; excluye eliminados." limite="Una subida de reportes no demuestra que la atención haya empeorado." pregunta="¿Hay más tickets que en el periodo anterior?" alPreguntar={consultar} /></div>
            <div className="analisis-indicator"><KpiCard etiqueta="Cerrados" valor={kpis?.cerrados} tono="exito" icono={<TicketCheck size={19} />} detalle="De los creados en el periodo, ya están cerrados." />
              <GuiaIndicador significado="Cuántos de los tickets analizados terminaron su atención." calculo="Cuenta los tickets creados en el periodo que actualmente tienen estado cerrado; incluye el estado legado equivalente." limite="No cuenta todos los cierres hechos durante esas fechas si el ticket se creó antes." pregunta="¿Cuántos tickets están abiertos y cerrados?" alPreguntar={consultar} /></div>
            <div className="analisis-indicator"><KpiCard etiqueta="Tiempo medio de resolución" valor={kpis?.tiempo_medio_resolucion_min == null ? 'Sin datos' : duracionLegible(kpis.tiempo_medio_resolucion_min)} icono={<Timer size={19} />} detalle={kpis?.muestras_tiempo != null ? `Basado en ${numero(kpis.muestras_tiempo)} tiempos registrados.` : 'Solo usa tickets con tiempo informado.'} />
              <GuiaIndicador significado="Cuánto tardó en promedio la resolución registrada." calculo="Suma los minutos informados y divide entre los tickets que tienen ese dato." limite="Es un promedio histórico, no una promesa de cuánto tardará el próximo caso." pregunta="¿Cuál es el tiempo promedio de resolución?" alPreguntar={consultar} /></div>
            <div className="analisis-indicator">{kpis?.cumplimiento_sla == null ? <KpiCard etiqueta="Cumplimiento de SLA" valor="Sin datos" icono={<ShieldCheck size={19} />} detalle="No hay tickets cerrados para calcularlo." /> : <KpiPorcentaje etiqueta="Cumplimiento de SLA" porcentaje={kpis.cumplimiento_sla} detalle={`${numero(kpis.cerrados_a_tiempo ?? kpis.casos_atendidos_anticipadamente)} de ${numero(kpis.cerrados)} cerrados sin incumplimiento registrado.`} tono="exito" />}
              <GuiaIndicador significado="Qué parte de los tickets cerrados figura sin incumplimiento del plazo de atención." calculo="Cerrados sin marca de incumplimiento ÷ total de cerrados analizados × 100." limite="Depende de que los plazos y las marcas estén registrados correctamente. Sin cierres no hay porcentaje." pregunta="¿Cuál es el cumplimiento de SLA?" alPreguntar={consultar} /></div>
            <div className="analisis-indicator"><KpiCard etiqueta="Satisfacción" valor={kpis?.satisfaccion_promedio == null ? 'Sin datos' : kpis.satisfaccion_promedio} sufijo={kpis?.satisfaccion_promedio == null ? undefined : '/5'} icono={<Star size={19} />} detalle={kpis?.muestras_satisfaccion != null ? `${numero(kpis.muestras_satisfaccion)} valoraciones recibidas.` : 'Promedio de las valoraciones recibidas.'} />
              <GuiaIndicador significado="Cómo calificaron la atención quienes enviaron una valoración." calculo="Suma las valoraciones y divide entre la cantidad recibida, en una escala de 1 a 5." limite="Quien no calificó no cuenta como una nota de cero. Una muestra pequeña puede ser poco representativa." pregunta="¿Cuál es la satisfacción del servicio?" alPreguntar={consultar} /></div>
            <div className="analisis-indicator">{kpis?.precision_clasificacion == null ? <KpiCard etiqueta="Precisión de la clasificación" valor="Sin datos" icono={<ScanLine size={19} />} detalle="Sin evaluaciones de clasificación." /> : <KpiPorcentaje etiqueta="Precisión de la clasificación" porcentaje={kpis.precision_clasificacion} detalle={kpis.retroalimentaciones_clasificacion != null ? `${numero(kpis.retroalimentaciones_clasificacion)} evaluaciones registradas.` : 'Según evaluaciones registradas de la clasificación.'} tono="ia" />}
              <GuiaIndicador significado="Cuántas clasificaciones evaluadas se confirmaron como correctas." calculo="Evaluaciones correctas ÷ evaluaciones registradas × 100." limite="Tener una categoría escrita no demuestra que sea correcta. Sin evaluaciones no se muestra un cero ficticio." pregunta="¿Qué significa la precisión de clasificación?" alPreguntar={consultar} /></div>
          </div>
          <div className="analisis-section-title"><h2>Explora dónde y por qué ocurre</h2><p>Cada gráfico incluye sus datos y una guía para leerlo.</p></div>

          <MosaicoGraficos>
            <BloqueLectura significado="Muestra las PC de escritorio con más reportes vinculados." calculo="Agrupa cada ticket una vez en su conjunto, incluidos los componentes y programas vinculados." limite="Las laptops y los equipos independientes no se convierten en conjuntos. Solo incluye vínculos registrados."><Panel titulo="Computadoras con más incidencias" descripcion="PC de escritorio: componentes y programas vinculados. Cada ticket cuenta una vez.">
              <DataTable datos={conjuntos.slice((paginaConjuntos - 1) * 10, paginaConjuntos * 10)} claveFila={c => c.id} permitirOrdenar={false} columnas={[
                { accessorKey: 'nombre', header: 'Computadora', cell: ({ row }) => <div><p className="font-semibold">{row.original.nombre}</p><p className="text-xs text-muted-foreground">{row.original.oficina}</p><p className="text-xs">{row.original.responsable_id ? <Link to={`/panel/usuarios/${row.original.responsable_id}`} className="text-primary-strong hover:underline">{row.original.responsable}</Link> : row.original.responsable}</p></div> },
                { accessorKey: 'total', header: 'Tickets' }, { accessorKey: 'programas', header: 'Programas' }, { accessorKey: 'abiertos', header: 'Abiertos' },
              ]} />
              <Paginacion pagina={paginaConjuntos} totalPaginas={Math.ceil(conjuntos.length / 10)} total={conjuntos.length} porPagina={10} alCambiar={setPaginaConjuntos} />
            </Panel></BloqueLectura>
            <BloqueLectura significado="Permite ver qué días recibieron más reportes." calculo="Cuenta los tickets creados cada día con el horario de la institución." limite="Un pico muestra más reportes, pero no demuestra su causa ni anticipa el siguiente día."><GraficoLinea
              titulo="Tickets por día"
              descripcion="Casos registrados en el periodo"
              unidad="tickets"
              datos={lineaDelPanel(panel.data)}
            /></BloqueLectura>
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
            <BloqueLectura significado="Muestra dónde hay casos abiertos cuyo plazo ya pasó." calculo="Compara la fecha límite de los tickets abiertos con la hora actual. Solo toma los creados en el periodo." limite="Los tickets sin fecha límite no se consideran a tiempo ni vencidos. Puedes consultarlos en el asistente."><Panel titulo="SLA vencidos por oficina" descripcion="Casos abiertos creados en el periodo que ya superaron su plazo.">
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
            </Panel></BloqueLectura>
            <BloqueLectura significado="Agrupa los problemas que se registran con mayor frecuencia." calculo="Cuenta los tickets que comparten categoría y problema informado." limite="La categoría de un reporte no equivale necesariamente a una causa técnica confirmada."><Panel titulo="Causas más frecuentes" descripcion="Categoría y problema registrados en los tickets.">
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
            </Panel></BloqueLectura>
            {panelFamilias}
          </MosaicoGraficos>

          </>}
          {(panel.isPending || panel.isError) && panelFamilias}
        </ContenidoTab>

        <ContenidoTab valor="asistente">
          <AsistenteAnalisis periodo={periodo} />
        </ContenidoTab>
      </TabsPanel>
    </div>
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
  return <BloqueLectura significado={`Compara cuántos tickets se registraron en cada ${destino === 'oficinas' ? 'oficina' : 'zona'}.`} calculo="Agrupa por ubicación los tickets creados dentro del intervalo. Las barras muestran hasta ocho resultados; la tabla conserva el listado completo." limite="El tamaño de cada ubicación puede ser distinto. Más tickets no demuestra por sí solo peor desempeño."><ChartCard titulo={titulo} descripcion="Abre una barra para revisar su detalle. La tabla contiene el listado completo." tabla={datos} sufijo="tickets">
    <BarrasCampos datos={datos.slice(0, 8)} unidad="tickets" anchoEtiqueta="w-2/5" descripcionSeleccion="Abrir detalle." alSeleccionar={(fila) => navegar(`/panel/${destino}/${fila.id}`)} pie={`${numero(datos.reduce((suma, fila) => suma + fila.valor, 0))} tickets en total en este periodo.`} />
  </ChartCard></BloqueLectura>
}
