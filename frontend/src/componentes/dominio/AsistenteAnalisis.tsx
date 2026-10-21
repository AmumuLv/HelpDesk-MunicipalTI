import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Activity, ArrowUpRight, BarChart3, Database, Layers3, MessageSquarePlus, ScanLine, Send, ShieldCheck } from 'lucide-react'
import { api } from '../../api/cliente'
import { useConversaciones, usePreguntasAsistente } from '../../api/hooks'
import { Button } from '../base/Button'
import { Select, Textarea } from '../base/Campo'
import { ErrorState, Nota, Panel, SkeletonPanel } from '../base/Estructura'
import './AsistenteAnalisis.css'

type Tabla = { columnas: { clave: string; titulo: string }[]; filas: Record<string, unknown>[] }
type Mensaje = { rol: string; texto: string; fuentes?: string[]; tabla?: Tabla | null; enlaces?: { texto: string; href: string }[] | null; explicacion?: string | null; periodo?: string | null }
type Conversacion = { id: string; titulo: string; mensajes: Mensaje[] }
type Respuesta = Omit<Mensaje, 'rol'> & { conversacion_id: string }
const FUENTES: Record<string, string> = {
  ranking_oficinas: 'Tickets por oficina', ranking_zonas: 'Tickets por zona', causas_recurrentes: 'Causas registradas',
  disponibilidad_equipo: 'Disponibilidad del equipo TI', tecnicos_rendimiento: 'Métricas del equipo TI',
  equipos_de_usuario: 'Inventario y responsables', equipos_con_fallas: 'Historial de equipos', tickets_de_usuario: 'Historial de tickets',
  ranking_conjuntos: 'Historial de computadoras',
  guia_analisis: 'Guía del asistente interno',
}
const PERIODOS: Record<string, string> = { '7d': 'Últimos 7 días', '30d': 'Últimos 30 días', '90d': 'Últimos 90 días', '365d': 'Último año', mes: 'Este mes', mes_anterior: 'Mes anterior', anio: 'Este año' }
function textoVisible(texto: string) {
  return texto.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, '$3/$2/$1')
}
function alcance(mensaje: Mensaje) {
  if (mensaje.fuentes?.includes('guia_analisis')) return 'Ayuda del sistema'
  if (mensaje.fuentes?.includes('equipos_con_fallas')) return 'Últimos 12 meses'
  if (mensaje.fuentes?.includes('disponibilidad_equipo')) return 'Estado actual'
  if (mensaje.fuentes?.includes('equipos_de_usuario')) return 'Inventario actual'
  if (mensaje.fuentes?.includes('tickets_de_usuario')) return 'Historial completo'
  return PERIODOS[mensaje.periodo || ''] || mensaje.periodo
}

function TextoProgresivo({ texto, animar, registro }: { texto: string; animar: boolean; registro: { current: HTMLDivElement | null } }) {
  const [longitud, setLongitud] = useState(animar ? 0 : texto.length)
  useEffect(() => {
    if (!animar || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setLongitud(texto.length); return }
    let posicion = 0
    setLongitud(0)
    const paso = Math.max(6, Math.ceil(texto.length / 80))
    const reloj = window.setInterval(() => {
      posicion = Math.min(texto.length, posicion + paso)
      setLongitud(posicion)
      if (posicion === texto.length) window.clearInterval(reloj)
    }, 30)
    return () => window.clearInterval(reloj)
  }, [texto, animar])
  useEffect(() => {
    const area = registro.current
    if (animar && area && area.scrollHeight - area.scrollTop - area.clientHeight < 100) area.scrollTop = area.scrollHeight
  }, [longitud, animar, registro])
  const escribiendo = animar && longitud < texto.length
  return <div className="datos-answer" aria-busy={escribiendo}>{(animar ? texto.slice(0, longitud) : texto).split(/\n\s*\n/).map((p, i) => <p key={i}>{p}</p>)}{escribiendo ? <span className="datos-writing-cursor" aria-hidden="true">▍</span> : null}</div>
}

function VistaDatos({ tabla }: { tabla: Tabla }) {
  const medida = ['total', 'tickets_12m', 'resueltos', 'carga_asignados'].find(c => tabla.columnas.some(col => col.clave === c))
  const etiqueta = ['oficina', 'zona', 'tipo', 'tecnico', 'nombre', 'categoria'].find(c => tabla.columnas.some(col => col.clave === c))
  if (!medida || !etiqueta) return null
  const filas = tabla.filas.slice(0, 5)
  const maximo = Math.max(1, ...filas.map(f => Number(f[medida]) || 0))
  return <figure className="datos-ranking" aria-label="Comparación de resultados"><figcaption><BarChart3 size={14} />Comparación · {tabla.columnas.find(c => c.clave === medida)?.titulo}</figcaption>{filas.map((fila, i) => <div className="datos-ranking-row" key={i}><span className="datos-ranking-name">{String(fila[etiqueta] ?? 'Sin identificar')}</span><strong>{Number(fila[medida]).toLocaleString('es-PE')}</strong><span className="datos-ranking-track"><span style={{ width: `${Math.max(0, Number(fila[medida]) || 0) / maximo * 100}%` }} /></span></div>)}<p>Hasta cinco resultados de la consulta. Longitud relativa al valor mayor.</p></figure>
}

export function AsistenteAnalisis({ periodo }: { periodo: string }) {
  const [parametros, setParametros] = useSearchParams()
  const id = parametros.get('conversacion') || ''
  const consultas = useQueryClient()
  const preguntas = usePreguntasAsistente()
  const historial = useConversaciones()
  const conversacion = useQuery({ queryKey: ['asistente-conversacion', id], enabled: Boolean(id), placeholderData: undefined,
    queryFn: () => api.obtener<Conversacion>(`/ia/asistente/conversaciones/${id}`), retry: false })
  const [pregunta, setPregunta] = useState('')
  const [enviada, setEnviada] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [animada, setAnimada] = useState<{ id: string; indice: number } | null>(null)
  const ocupado = useRef(false)
  const presente = useRef(true)
  const registro = useRef<HTMLDivElement>(null)
  const mensajes = conversacion.data?.mensajes ?? []
  useEffect(() => { presente.current = true; return () => { presente.current = false } }, [])
  useEffect(() => { if (registro.current) registro.current.scrollTop = registro.current.scrollHeight }, [mensajes.length, enviada])
  const seleccionar = (valor: string) => {
    if (ocupado.current) return
    setAnimada(null)
    const siguientes = new URLSearchParams(parametros)
    if (valor) siguientes.set('conversacion', valor)
    else siguientes.delete('conversacion')
    setParametros(siguientes)
    setError(null)
    setPregunta('')
  }
  const preguntar = async (texto: string) => {
    const limpia = texto.trim()
    if (ocupado.current || limpia.length < 2 || limpia.length > 1000 || (id && !conversacion.data)) return
    ocupado.current = true
    setEnviada(limpia)
    setError(null)
    try {
      const respuesta = await api.crear<Respuesta>('/ia/asistente', { pregunta: limpia, filtros: { periodo }, conversacion_id: id || undefined })
      if (!respuesta.texto?.trim()) throw new Error('El asistente no devolvió una respuesta. Puedes reintentar tu pregunta.')
      consultas.setQueryData<Conversacion>(['asistente-conversacion', respuesta.conversacion_id], {
        id: respuesta.conversacion_id, titulo: conversacion.data?.titulo || limpia.slice(0, 60),
        mensajes: [...mensajes, { rol: 'user', texto: limpia }, { ...respuesta, rol: 'assistant' }],
      })
      void consultas.invalidateQueries({ queryKey: ['ia', 'conversaciones'] })
      if (!presente.current) return
      setAnimada({ id: respuesta.conversacion_id, indice: mensajes.length + 1 })
      setParametros((actuales) => { const siguientes = new URLSearchParams(actuales); siguientes.set('conversacion', respuesta.conversacion_id); return siguientes }, { replace: true })
      setPregunta('')
    } catch (fallo) { if (presente.current) setError(fallo instanceof Error ? fallo.message : 'No se pudo completar la consulta. Inténtalo de nuevo.') }
    finally { ocupado.current = false; if (presente.current) setEnviada('') }
  }
  const bloqueado = Boolean(enviada) || (Boolean(id) && !conversacion.data)
  return <div className="datos-lab"><header className="datos-lab-hero"><div className="datos-lab-symbol" aria-hidden="true"><ScanLine size={30} /></div><div><p className="datos-eyebrow">ANÁLISIS DEL SERVICIO</p><h2>Inteligencia operativa</h2><p>De tus registros a una respuesta clara.</p></div><div className="datos-lab-status"><span><Database size={13} /> Consultas internas</span><span><ShieldCheck size={13} /> Solo lectura</span><span><Activity size={13} />{PERIODOS[periodo] || periodo}</span></div></header><div className="datos-lab-grid">
    <section className="datos-workspace" aria-label="Chat de análisis interno"><header className="datos-chat-header"><span className="datos-chat-avatar" aria-hidden="true"><Layers3 size={24} /></span><div><p className="datos-eyebrow">ASISTENTE INTERNO</p><h3>Consultas de datos</h3><p>Explora tus registros. Encuentra respuestas.</p></div><Button tamano="sm" icono={<MessageSquarePlus size={15} />} disabled={Boolean(enviada)} onClick={() => seleccionar('')}>Nueva conversación</Button></header>
      <div ref={registro} role="log" aria-label="Conversación con el asistente" aria-live="polite" aria-busy={Boolean(enviada)} className="datos-log">
        {id && conversacion.isPending ? <SkeletonPanel filas={3} /> : conversacion.isError ? <ErrorState compacto mensaje="No pudimos abrir la conversación." alReintentar={() => void conversacion.refetch()} /> : null}
        {!id && !enviada ? <div className="datos-empty"><span className="datos-empty-orbit" aria-hidden="true"><Layers3 size={35} /></span><p className="datos-eyebrow">EXPLORA. COMPARA. DECIDE.</p><h3>¿Qué necesitas conocer del servicio?</h3><p>Identifica dónde se concentran las incidencias, revisa tu inventario o consulta la disponibilidad de TI.</p><div className="datos-empty-tags"><span>Tickets</span><span>Inventario</span><span>Equipo TI</span></div><small>Elige una consulta sugerida o escribe tu pregunta. No se modifican registros.</small></div> : null}
        {mensajes.map((mensaje, indice) => <article key={indice} className={mensaje.rol === 'user' ? 'datos-question' : 'datos-result'}>
          {mensaje.rol !== 'user' ? <div className="datos-result-header"><span><Layers3 size={15} />{mensaje.fuentes?.includes('guia_analisis') ? 'Asistente interno' : 'Resultado de la consulta'}</span>{alcance(mensaje) ? <span className="datos-periodo">{alcance(mensaje)}</span> : null}</div> : <p className="datos-question-label">TÚ · CONSULTA {String(Math.floor(indice / 2) + 1).padStart(2, '0')}</p>}
          <TextoProgresivo texto={textoVisible(mensaje.texto)} animar={mensaje.rol === 'assistant' && animada?.id === id && animada.indice === indice} registro={registro} />
          {mensaje.rol !== 'user' && mensaje.tabla?.filas.length ? <VistaDatos tabla={mensaje.tabla} /> : null}
          {mensaje.fuentes?.length ? <div className="datos-sources">{mensaje.fuentes.map(f => <span key={f}><Database size={11} />{FUENTES[f] || f}</span>)}</div> : null}
          {mensaje.tabla?.filas.length ? <details className="mt-3 text-xs"><summary className="cursor-pointer font-semibold text-ai-strong">Ver datos de la respuesta</summary>
            <div className="mt-2 max-h-64 overflow-auto"><table className="w-full text-left"><thead><tr>{mensaje.tabla.columnas.map((c) => <th key={c.clave} className="border-b border-border p-2">{c.titulo}</th>)}</tr></thead>
              <tbody>{mensaje.tabla.filas.map((fila, i) => <tr key={i}>{mensaje.tabla!.columnas.map((c) => <td key={c.clave} className="border-b border-border/50 p-2">{fila[c.clave] == null ? '—' : typeof fila[c.clave] === 'object' ? 'Ver detalle' : String(fila[c.clave])}</td>)}</tr>)}</tbody></table></div>
          </details> : null}
          {mensaje.enlaces?.length ? <div className="mt-2 flex flex-wrap gap-2">{mensaje.enlaces.filter((e) => /^\/panel\/(oficinas|zonas)\/[a-f\d]{24}$/i.test(e.href)).map((e) => <Link key={e.href} to={e.href} className="text-xs font-medium text-primary-strong hover:underline">{e.texto} ↗</Link>)}</div> : null}
          {mensaje.explicacion ? <details className="mt-2 text-xs text-muted-foreground"><summary className="cursor-pointer">Cómo se obtuvo</summary><p className="mt-1">{mensaje.explicacion}</p></details> : null}
        </article>)}
        {enviada ? <><div className="datos-question"><p className="datos-question-label">TU CONSULTA</p><p>{enviada}</p></div><p role="status" className="datos-thinking"><Activity size={15} />Consultando los datos del servicio…</p></> : null}
      </div>
      {error ? <div className="mt-3"><Nota tono="peligro" titulo="La consulta no se completó">{error} Tu pregunta se conserva para reintentar.</Nota></div> : null}
      <form className="datos-composer" onSubmit={(e) => { e.preventDefault(); void preguntar(pregunta) }}>
        <Textarea etiqueta="Tu pregunta" filas={2} maxLength={1000} disabled={bloqueado} value={pregunta} onChange={(e) => setPregunta(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void preguntar(pregunta) } }} />
        <div className="flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">{pregunta.length}/1000 · Ctrl + Enter para enviar</span><Button type="submit" variante="primario" cargando={Boolean(enviada)} disabled={bloqueado || pregunta.trim().length < 2} icono={<Send size={15} />}>Preguntar</Button></div>
      </form>
    </section>
    <div className="flex min-w-0 flex-col gap-4">
      <Panel titulo="Consultas sugeridas" descripcion="Accesos directos a tus datos" className="datos-suggestions">
        {preguntas.isPending ? <SkeletonPanel filas={3} /> : preguntas.isError ? <ErrorState compacto mensaje="No pudimos cargar las sugerencias." alReintentar={() => void preguntas.refetch()} /> : <div className="flex flex-col gap-2">{preguntas.data?.preguntas.map((texto, i) => <button key={texto} type="button" disabled={bloqueado} onClick={() => { setPregunta(texto); void preguntar(texto) }} className="datos-suggestion"><span className="datos-suggestion-icon" aria-hidden="true">{i === 2 ? <Activity size={18} /> : i === 4 ? <Layers3 size={18} /> : <BarChart3 size={18} />}</span><span>{texto}</span><ArrowUpRight size={14} aria-hidden="true" /></button>)}</div>}
      </Panel>
      <Panel titulo="Conversaciones recientes" className="datos-history">
        {historial.isError ? <ErrorState compacto mensaje="No pudimos cargar el historial." alReintentar={() => void historial.refetch()} /> : historial.isPending ? <SkeletonPanel filas={2} /> : <Select etiqueta="Abrir conversación" value={id} disabled={Boolean(enviada)} placeholder="Selecciona una consulta" opciones={(historial.data?.items ?? []).map((c) => ({ valor: c.id, etiqueta: c.titulo }))} onChange={(e) => seleccionar(e.target.value)} />}
        <p className="mt-2 text-xs text-muted-foreground">Las conversaciones se guardan en tu cuenta y puedes retomarlas después.</p>
      </Panel>
      <div className="datos-help"><ShieldCheck size={18} /><p><strong>Resultados respaldados</strong>Las consultas reconocidas se calculan en el sistema. El chatbot TI queda para orientación y conversación general.</p></div>
    </div>
  </div></div>
}
