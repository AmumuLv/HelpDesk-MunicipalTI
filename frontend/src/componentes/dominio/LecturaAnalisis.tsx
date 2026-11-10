import { ArrowRight, CircleAlert, Compass, Lightbulb, ShieldCheck, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import type { PanelAnalitica } from '../../api/tipos'
import { fechaNumerica, numero } from '../../dominio/formato'
import { Button } from '../base/Button'

export function GuiaIndicador({ titulo = 'Cómo interpretar este dato', significado, calculo, limite, pregunta, alPreguntar }: {
  titulo?: string; significado: string; calculo: string; limite: string; pregunta?: string; alPreguntar?: (pregunta: string) => void
}) {
  return <details className="analisis-explicacion"><summary><Lightbulb size={15} aria-hidden="true" />{titulo}</summary><dl>
    <div><dt>En palabras sencillas</dt><dd>{significado}</dd></div>
    <div><dt>Cómo se obtiene</dt><dd>{calculo}</dd></div>
    <div><dt>Ten en cuenta</dt><dd>{limite}</dd></div>
  </dl>{pregunta && alPreguntar ? <Button tamano="sm" icono={<ArrowRight size={14} />} onClick={() => alPreguntar(pregunta)}>Preguntar por este dato</Button> : null}</details>
}

export function BloqueLectura({ children, significado, calculo, limite }: { children: ReactNode; significado: string; calculo: string; limite: string }) {
  return <div className="analisis-chart-group">{children}<GuiaIndicador titulo="Ayúdame a entender este gráfico" significado={significado} calculo={calculo} limite={limite} /></div>
}

export function ResumenLectura({ datos, alPreguntar }: { datos: PanelAnalitica; alPreguntar: (pregunta: string) => void }) {
  const kpis = datos.kpis
  const filas = datos.riesgo_sla_oficina?.items
  const vencidos = filas?.reduce((suma, f) => suma + (f.vencidos ?? 0), 0)
  const sinPlazo = filas?.reduce((suma, f) => suma + (f.sin_plazo ?? 0), 0)
  const primera = datos.ranking_oficinas?.items?.[0]
  const empates = primera ? datos.ranking_oficinas.items.filter(f => f.total === primera.total).length : 0
  const total = kpis.tickets_analizados
  const anterior = kpis.tickets_periodo_anterior
  const cambio = anterior == null ? 'No hay una comparación anterior disponible.' : total === anterior
    ? 'La cantidad se mantiene respecto al intervalo anterior.'
    : `${numero(Math.abs(total - anterior))} tickets ${total > anterior ? 'más' : 'menos'} que en el intervalo anterior (${numero(anterior)}).`
  return <section className="analisis-overview" aria-label="Lectura sencilla del servicio">
    <div className="analisis-intro"><span className="analisis-emblema" aria-hidden="true"><Sparkles size={27} /></span><div><p className="analisis-kicker">CENTRO DE ANÁLISIS</p><h2>Primero entiende. Después decide.</h2><p>Una lectura de tus registros, con cifras que puedes comprobar.</p></div><Button icono={<ArrowRight size={16} />} onClick={() => alPreguntar('¿Puedes darme un resumen del servicio?')}>Consultar mis datos</Button></div>
    <div className="analisis-reading-grid">
      <article className="analisis-brief"><span className="analisis-step"><Compass size={19} aria-hidden="true" />Lo que está pasando</span>
        <p className="analisis-lead"><strong>{numero(total)}</strong> tickets creados</p>
        <p>Del {fechaNumerica(kpis.periodo.desde)} al {fechaNumerica(kpis.periodo.hasta)}.</p>
        <p className="analisis-insight">{cambio}</p><small>Compara intervalos consecutivos de la misma duración. Más reportes no significa por sí solo peor atención.</small>
        <Button variante="fantasma" tamano="sm" onClick={() => alPreguntar('¿Hay más tickets que en el periodo anterior?')}>Entender la comparación <ArrowRight size={14} aria-hidden="true" /></Button>
      </article>
      <article className={`analisis-brief ${vencidos ? 'analisis-brief-alert' : ''}`}><span className="analisis-step"><CircleAlert size={19} aria-hidden="true" />Qué revisar primero</span>
        <p className="analisis-lead">{vencidos == null ? 'Sin información de plazos' : <><strong>{numero(vencidos)}</strong> {vencidos === 1 ? 'ticket vencido' : 'tickets vencidos'}</>}</p>
        <p>Casos abiertos creados en las fechas elegidas.</p>
        {sinPlazo ? <p className="analisis-insight">Hay {numero(sinPlazo)} abiertos sin fecha límite registrada. Revísalos por separado.</p> : null}
        {primera ? <p className="analisis-insight">{empates > 1 ? `${numero(empates)} oficinas empatan con ${numero(primera.total)} tickets cada una.` : <>Mayor volumen: <strong>{primera.oficina}</strong>, con {numero(primera.total)} tickets.</>}</p> : <p className="analisis-insight">No hay oficinas con tickets para comparar.</p>}
        <Button variante="fantasma" tamano="sm" onClick={() => alPreguntar('¿Qué tickets tienen el plazo vencido?')}>Revisar los plazos <ArrowRight size={14} aria-hidden="true" /></Button>
      </article>
    </div>
    <div className="analisis-scope"><ShieldCheck size={16} aria-hidden="true" /><span>Datos del sistema · Tickets creados en el periodo · Equipos: historial de 12 meses donde se indica</span>{datos.actualizado_en ? <span>Actualizado: {new Date(datos.actualizado_en).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' })}</span> : null}</div>
  </section>
}
