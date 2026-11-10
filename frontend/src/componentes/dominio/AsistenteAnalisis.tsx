import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Activity, ArrowDown, ArrowRight, BarChart3, Building2, Check, Clock3, Copy, Database, Download, Layers3, ListChecks, MapPin, MessageSquarePlus, Monitor, PanelLeft, Pencil, RotateCcw, Search, Send, ShieldCheck, Sparkles, Square, Trash2, Wrench } from 'lucide-react'
import { api, ErrorPeticion } from '../../api/cliente'
import { useConversaciones, usePreguntasAsistente } from '../../api/hooks'
import { Button } from '../base/Button'
import { Textarea } from '../base/Campo'
import { ErrorState, Nota, SkeletonPanel } from '../base/Estructura'
import { ConfirmDialog, DialogModal } from '../base/Sobreposiciones'
import { TextoChat } from './TextoChat'
import { useScrollChat } from './useScrollChat'
import './AsistenteAnalisis.css'

type Tabla = { columnas: { clave: string; titulo: string }[]; filas: Record<string, unknown>[] }
type Mensaje = { rol: string; texto: string; fuentes?: string[]; tabla?: Tabla | null; enlaces?: { texto: string; href: string }[] | null; explicacion?: string | null; periodo?: string | null; analisis?: { significado: string; revision: string; limite: string } | null; seguimientos?: string[]; alcance_consulta?: string | null }
type Conversacion = { id: string; titulo: string; mensajes: Mensaje[]; version?: number }
type Respuesta = Omit<Mensaje, 'rol'> & { conversacion_id: string; mensajes?: Mensaje[]; version?: number }
type Intento = { texto: string; tipo: 'preguntar' | 'regenerar' | 'editar'; indice?: number; solicitud_id?: string }
const FUENTES: Record<string, string> = {
  ranking_oficinas: 'Tickets por oficina', ranking_zonas: 'Tickets por zona', causas_recurrentes: 'Causas registradas',
  disponibilidad_equipo: 'Disponibilidad del equipo TI', tecnicos_rendimiento: 'Métricas del equipo TI',
  equipos_de_usuario: 'Inventario y responsables', equipos_con_fallas: 'Historial de equipos', tickets_de_usuario: 'Historial de tickets',
  ranking_conjuntos: 'Historial de computadoras',
  guia_analisis: 'Guía del asistente interno',
  metricas_generales: 'Indicadores del servicio', comparacion_periodos: 'Recuento por periodos', estados_tickets: 'Estados actuales de tickets',
  plazos_atencion: 'Fechas límite de tickets abiertos', evolucion_tickets: 'Tickets creados por día', resumen_inventario: 'Inventario activo actual',
  calidad_inventario: 'Calidad del inventario', equipos_datos_pendientes: 'Datos pendientes por equipo', oficinas_datos_pendientes: 'Datos pendientes por oficina',
  responsables_inventario: 'Vínculos y uso compartido', conjuntos_incompletos: 'Componentes de PC de escritorio', inventarios_disponibles: 'Inventarios anuales guardados', comparar_inventarios: 'Comparación entre inventarios anuales',
  tickets_pendientes_detalle: 'Listado de tickets', resumen_equipo_ti: 'Carga, tiempos y valoraciones de TI', horarios_manana: 'Horarios y ausencias registrados',
  guias_consultadas: 'Lecturas de guías', guias_valoradas: 'Valoraciones de guías', brechas_guias: 'Categorías de tickets y guías visibles',
  auditoria_cambios: 'Registro de auditoría', auditoria_responsables: 'Cambios de responsable registrados',
}
const PERIODOS: Record<string, string> = { '7d': 'Últimos 7 días', '30d': 'Últimos 30 días', '90d': 'Últimos 90 días', '365d': 'Último año', mes: 'Este mes', mes_anterior: 'Mes anterior', anio: 'Este año' }
function nuevaSolicitud() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-')
}
function textoVisible(texto: string) {
  return texto.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, '$3/$2/$1')
}
function presentarPregunta(texto: string) {
  if (/inventarios.*(?:guardados|disponibles)|años.*inventario/i.test(texto)) return { titulo: 'Qué años tenemos guardados', subtitulo: texto, Icono: Layers3 }
  if (/compara.*inventario|cambi[oó].*inventario/i.test(texto)) return { titulo: 'Comparar inventarios anuales', subtitulo: texto, Icono: BarChart3 }
  if (/oficina.*(?:datos|completar|faltantes)/i.test(texto)) return { titulo: 'Dónde faltan más datos', subtitulo: texto, Icono: Building2 }
  if (/equipos.*(?:datos incompletos|datos pendientes|sin patrimonio)/i.test(texto)) return { titulo: 'Qué datos completar primero', subtitulo: texto, Icono: Database }
  if (/calidad.*inventario|datos.*inventario.*complet|datos.*faltan.*inventario/i.test(texto)) return { titulo: 'Cómo está nuestro inventario', subtitulo: texto, Icono: Database }
  if (/sin responsable|pendientes de vincular/i.test(texto)) return { titulo: 'Revisar responsables y compartidos', subtitulo: texto, Icono: Monitor }
  if (/(?:computadoras|conjuntos|PC de escritorio).*(?:incomplet|componentes)/i.test(texto)) return { titulo: 'Qué PC necesitan componentes', subtitulo: texto, Icono: Monitor }
  if (/muestra.*vencidos|lista.*vencidos/i.test(texto)) return { titulo: 'Abrir los tickets vencidos', subtitulo: texto, Icono: Clock3 }
  if (/sin asignar/i.test(texto)) return { titulo: 'Qué tickets necesitan un técnico', subtitulo: texto, Icono: Wrench }
  if (/reabiert|reapertura/i.test(texto)) return { titulo: 'Qué casos volvieron a abrirse', subtitulo: texto, Icono: Activity }
  if (/más tiempo|m[aá]s antiguos/i.test(texto)) return { titulo: 'Qué casos esperan más', subtitulo: texto, Icono: Clock3 }
  if (/tickets.*sin equipo/i.test(texto)) return { titulo: 'Qué equipos falta identificar', subtitulo: texto, Icono: Monitor }
  if (/ma[ñn]ana.*(?:horario|t[eé]cnic)|(?:horario|t[eé]cnic).*ma[ñn]ana/i.test(texto)) return { titulo: 'Quién tiene horario mañana', subtitulo: texto, Icono: Clock3 }
  if (/gu[ií]as.*(?:valorad|[uú]tiles)/i.test(texto)) return { titulo: 'Guías mejor valoradas', subtitulo: texto, Icono: Check }
  if (/gu[ií]as.*(?:consultad|le[ií]das)/i.test(texto)) return { titulo: 'Guías más consultadas', subtitulo: texto, Icono: Search }
  if (/sin gu[ií]a|necesitan.*gu[ií]a/i.test(texto)) return { titulo: 'Qué problemas necesitan una guía', subtitulo: texto, Icono: ListChecks }
  if (/qui[eé]n.*(?:responsable|cambi)|auditor[ií]a|qu[eé] cambios/i.test(texto)) return { titulo: 'Revisar cambios registrados', subtitulo: texto, Icono: ListChecks }
  if (/resumen.*servicio/i.test(texto)) return { titulo: 'Cómo está el servicio', subtitulo: 'Un resumen para empezar.', Icono: Sparkles }
  if (/periodo anterior/i.test(texto)) return { titulo: '¿Hay más o menos tickets?', subtitulo: 'Compara con las fechas anteriores.', Icono: BarChart3 }
  if (/plazo vencido/i.test(texto)) return { titulo: 'Qué necesita atención', subtitulo: 'Revisa los tickets fuera de plazo.', Icono: Clock3 }
  if (/abiertos y cerrados/i.test(texto)) return { titulo: 'Cómo están los tickets', subtitulo: 'Mira su estado actual.', Icono: ListChecks }
  if (/evolucionan|por día/i.test(texto)) return { titulo: 'Qué pasa cada día', subtitulo: 'Revisa cuándo llegan más reportes.', Icono: Activity }
  if (/equipos tenemos/i.test(texto)) return { titulo: 'Qué equipos tenemos', subtitulo: 'Consulta el inventario actual.', Icono: Monitor }
  if (/faltantes/i.test(texto)) return { titulo: 'Entender los datos faltantes', subtitulo: 'Qué significa cada porcentaje.', Icono: Database }
  if (/oficina.*m[aá]s|m[aá]s.*oficina/i.test(texto)) return { titulo: 'Oficinas con más problemas', subtitulo: 'Dónde se pide más ayuda.', Icono: Building2 }
  if (/zona.*m[aá]s|m[aá]s.*zona/i.test(texto)) return { titulo: 'Zonas con más reportes', subtitulo: 'En qué zona hay más tickets.', Icono: MapPin }
  if (/disponible/i.test(texto)) return { titulo: 'Quién puede atender ahora', subtitulo: 'Revisa la disponibilidad de TI.', Icono: Wrench }
  if (/causas|frecuentes/i.test(texto)) return { titulo: 'Problemas que se repiten', subtitulo: 'Ve las causas más frecuentes.', Icono: ListChecks }
  if (/(equipos|familias).*falla/i.test(texto)) return { titulo: 'Equipos con más fallas', subtitulo: 'Compara los tipos de equipo.', Icono: Monitor }
  if (/sirve|hacer|ayuda/i.test(texto)) return { titulo: 'Qué puedo preguntarte', subtitulo: 'Conoce lo que puedes consultar.', Icono: Sparkles }
  return { titulo: texto, subtitulo: texto, Icono: BarChart3 }
}
function grupoPregunta(texto: string) {
  if (/para qué|qué significa|explica/i.test(texto)) return 'Entender'
  if (/técnico|equipo TI/i.test(texto)) return 'Equipo TI'
  if (/equipos|inventario|computadoras|familias/i.test(texto)) return 'Equipos'
  return 'Tickets'
}
function enlaceDeDatosSeguro(href: string) {
  return /^\/panel\/(?:oficinas|zonas|equipos|tickets|usuarios|ayuda)\/[a-f\d]{24}$/i.test(href)
    || /^\/panel\/(?:inventario-anual|auditoria|conocimiento|equipos\/calidad|equipo-ti)$/.test(href)
}
function normalizarBusqueda(texto: string) {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/\bpatrimoni(?:o|al(?:es)?)\b/g, 'patrimonio')
}
function alcance(mensaje: Mensaje) {
  if (mensaje.fuentes?.includes('guia_analisis')) return 'Ayuda del sistema'
  if (mensaje.fuentes?.includes('equipos_con_fallas')) return 'Últimos 12 meses'
  if (mensaje.fuentes?.includes('disponibilidad_equipo')) return 'Estado actual'
  if (mensaje.fuentes?.includes('equipos_de_usuario')) return 'Inventario actual'
  if (mensaje.fuentes?.includes('resumen_inventario')) return 'Inventario actual'
  if (mensaje.fuentes?.includes('tickets_de_usuario')) return 'Historial completo'
  return PERIODOS[mensaje.periodo || ''] || mensaje.periodo
}

function TextoProgresivo({ texto, animar, alProgresar, alTerminar }: { texto: string; animar: boolean; alProgresar: () => void; alTerminar: () => void }) {
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
  useEffect(() => { if (animar) alProgresar() }, [longitud, animar, alProgresar])
  useEffect(() => { if (animar && longitud >= texto.length) alTerminar() }, [animar, longitud, texto.length, alTerminar])
  const escribiendo = animar && longitud < texto.length
  return <div className="datos-answer" aria-busy={escribiendo}><TextoChat texto={animar ? texto.slice(0, longitud) : texto} />{escribiendo ? <span className="datos-writing-cursor" aria-hidden="true">▍</span> : null}</div>
}

function VistaDatos({ tabla }: { tabla: Tabla }) {
  if (tabla.columnas.some(c => c.clave === 'fecha') && tabla.columnas.some(c => c.clave === 'valor') && tabla.filas.length) {
    const valores = tabla.filas.map(f => Math.max(0, Number(f.valor) || 0))
    const maximo = Math.max(1, ...valores)
    const puntos = valores.map((v, i) => `${15 + i / Math.max(1, valores.length - 1) * 570},${145 - v / maximo * 125}`).join(' ')
    return <figure className="datos-ranking datos-timeline"><figcaption><Activity size={15} aria-hidden="true" />Tickets creados por día</figcaption><svg viewBox="0 0 600 165" role="img" aria-label={`Actividad de ${valores.length} días. Máximo: ${Math.max(...valores)} tickets por día.`}><line x1="15" x2="585" y1="145" y2="145" /><polyline points={puntos} fill="none" />{valores.length === 1 ? <circle cx="15" cy={145 - valores[0] / maximo * 125} r="4" /> : null}</svg><div className="datos-timeline-dates"><span>{textoVisible(String(tabla.filas[0].fecha))}</span><span>{textoVisible(String(tabla.filas[tabla.filas.length - 1].fecha))}</span></div><p>Escala: 0 a {Math.max(...valores)} tickets por día. Es actividad registrada, no una predicción.</p></figure>
  }
  const medida = ['faltantes', 'total', 'tickets_12m', 'resueltos', 'carga_asignados'].find(c => tabla.columnas.some(col => col.clave === c))
  const etiqueta = ['nombre', 'campo', 'oficina', 'zona', 'tipo', 'tecnico', 'categoria', 'intervalo', 'estado', 'fecha'].find(c => tabla.columnas.some(col => col.clave === c))
  if (!medida || !etiqueta) return null
  const filas = tabla.filas.slice(0, 5)
  const maximo = Math.max(1, ...filas.map(f => Number(f[medida]) || 0))
  return <figure className="datos-ranking" aria-label="Comparación de resultados"><figcaption><BarChart3 size={14} />Comparación · {tabla.columnas.find(c => c.clave === medida)?.titulo}</figcaption>{filas.map((fila, i) => <div className="datos-ranking-row" key={i}><span className="datos-ranking-name">{String(fila[etiqueta] ?? 'Sin identificar')}</span><strong>{Number(fila[medida]).toLocaleString('es-PE')}</strong><span className="datos-ranking-track"><span style={{ width: `${Math.max(0, Number(fila[medida]) || 0) / maximo * 100}%` }} /></span></div>)}<p>La barra más larga muestra la cantidad más alta. Se muestran hasta 5 resultados.</p></figure>
}

export function AsistenteAnalisis({ periodo }: { periodo: string }) {
  const [parametros, setParametros] = useSearchParams()
  const id = parametros.get('conversacion') || ''
  const consultas = useQueryClient()
  const preguntas = usePreguntasAsistente()
  const historial = useConversaciones()
  const conversacion = useQuery({ queryKey: ['asistente-conversacion', id], enabled: Boolean(id), placeholderData: undefined,
    queryFn: () => api.obtener<Conversacion>(`/ia/asistente/conversaciones/${id}`), retry: false })
  const [pregunta, setPregunta] = useState(() => parametros.get('pregunta')?.slice(0, 1000) || '')
  const [grupo, setGrupo] = useState('Tickets')
  const [mostrarTodas, setMostrarTodas] = useState(false)
  const [busquedaPreguntas, setBusquedaPreguntas] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [historialAbierto, setHistorialAbierto] = useState(false)
  const [sugerenciasAbiertas, setSugerenciasAbiertas] = useState(false)
  const [enviada, setEnviada] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [ultimoIntento, setUltimoIntento] = useState<Intento | null>(null)
  const [animada, setAnimada] = useState<{ id: string; indice: number } | null>(null)
  const [edicion, setEdicion] = useState<{ indice: number; texto: string } | null>(null)
  const [renombrar, setRenombrar] = useState<{ id: string; titulo: string; version?: number } | null>(null)
  const [porEliminar, setPorEliminar] = useState<{ id: string; titulo: string } | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [errorGestion, setErrorGestion] = useState<string | null>(null)
  const [copiada, setCopiada] = useState<number | null>(null)
  const [aviso, setAviso] = useState('')
  const ocupado = useRef(false)
  const presente = useRef(true)
  const vistaActual = useRef(id)
  vistaActual.current = id
  const { registro, seguirFinal, lejosDelFinal, onScroll: alDesplazar, interrumpir, irAlFinal, seguirEscritura, restaurarFinal } = useScrollChat()
  const respuestaPropia = useRef<string | null>(null)
  const restaurarHistorial = useRef<string | null>(id || null)
  const entrada = useRef<HTMLTextAreaElement>(null)
  const selectorPreguntas = useRef<HTMLButtonElement>(null)
  const mensajes = conversacion.data?.mensajes ?? []
  const version = conversacion.data?.version
  const borrador = parametros.get('pregunta')
  const terminarEscritura = useCallback(() => setAnimada(null), [])
  useEffect(() => { if (borrador) setPregunta(borrador.slice(0, 1000)) }, [borrador])
  useEffect(() => { presente.current = true; return () => { presente.current = false } }, [])
  useEffect(() => {
    setAnimada(actual => actual?.id === id ? actual : null); setEdicion(null); setCopiada(null)
    if (id !== respuestaPropia.current) restaurarHistorial.current = id || null
  }, [id])
  useEffect(() => {
    if (!id && !enviada) { restaurarFinal(0); return }
    if (restaurarHistorial.current === id && conversacion.data && !enviada && !animada) {
      restaurarHistorial.current = null
      restaurarFinal()
    } else seguirEscritura()
  }, [mensajes.length, enviada, id, preguntas.isPending, animada, conversacion.data, restaurarFinal, seguirEscritura])
  const seleccionar = (valor: string) => {
    if (ocupado.current || guardando) return
    setAnimada(null); setEdicion(null); setError(null); setUltimoIntento(null); setPregunta(''); setHistorialAbierto(false); setSugerenciasAbiertas(false)
    seguirFinal.current = true
    const siguientes = new URLSearchParams(parametros)
    siguientes.delete('pregunta')
    if (valor) siguientes.set('conversacion', valor)
    else siguientes.delete('conversacion')
    setParametros(siguientes)
  }
  const ejecutar = async (intento: Intento) => {
    const limpia = intento.texto.trim()
    if (ocupado.current || guardando || limpia.length < 2 || limpia.length > 1000 || (id && !conversacion.data)) return
    const origen = id
    const solicitudId = intento.solicitud_id || (!origen && intento.tipo === 'preguntar' ? nuevaSolicitud() : undefined)
    ocupado.current = true
    setAnimada(null); setEnviada(limpia); setError(null); setUltimoIntento({ ...intento, solicitud_id: solicitudId }); setAviso(''); setSugerenciasAbiertas(false)
    if (intento.tipo === 'preguntar') setPregunta(limpia)
    irAlFinal()
    try {
      const ruta = intento.tipo === 'preguntar' ? '/ia/asistente' : '/ia/asistente/conversaciones/' + origen + '/' + intento.tipo
      const cuerpo = intento.tipo === 'preguntar'
        ? { pregunta: limpia, filtros: { periodo }, conversacion_id: origen || undefined, version, solicitud_id: solicitudId }
        : { filtros: { periodo }, version, ...(intento.tipo === 'editar' ? { indice: intento.indice, pregunta: limpia } : {}) }
      const respuesta = await api.crear<Respuesta>(ruta, cuerpo)
      if (!respuesta.texto?.trim()) throw new Error('El asistente no devolvió una respuesta. Puedes reintentar tu pregunta.')
      if (!presente.current) return
      const base = intento.tipo === 'editar' ? mensajes.slice(0, intento.indice) : intento.tipo === 'regenerar' ? mensajes.slice(0, -2) : mensajes
      const guardados = respuesta.mensajes ?? [...base, { rol: 'user', texto: limpia }, { ...respuesta, rol: 'assistant' }]
      respuestaPropia.current = respuesta.conversacion_id
      restaurarHistorial.current = null
      consultas.setQueryData<Conversacion>(['asistente-conversacion', respuesta.conversacion_id], {
        id: respuesta.conversacion_id, titulo: conversacion.data?.titulo || limpia.slice(0, 60),
        mensajes: guardados, version: respuesta.version,
      })
      void consultas.invalidateQueries({ queryKey: ['ia', 'conversaciones'] })
      if (vistaActual.current !== origen) return
      setAnimada({ id: respuesta.conversacion_id, indice: guardados.length - 1 })
      setParametros(actuales => { const siguientes = new URLSearchParams(actuales); siguientes.set('conversacion', respuesta.conversacion_id); siguientes.delete('pregunta'); return siguientes }, { replace: true })
      setPregunta(''); setEdicion(null); setUltimoIntento(null)
    } catch (fallo) {
      if (!presente.current || vistaActual.current !== origen) return
      if (fallo instanceof ErrorPeticion && fallo.estado === 409 && origen) {
        await consultas.invalidateQueries({ queryKey: ['asistente-conversacion', origen] })
        setError('Esta conversación cambió en otra pestaña. Actualicé los mensajes; tu pregunta se conserva para reintentar.')
      } else setError(fallo instanceof Error ? fallo.message : 'No se pudo completar la consulta. Inténtalo de nuevo.')
    } finally {
      ocupado.current = false
      if (presente.current) setEnviada('')
    }
  }
  const preguntar = (texto: string) => ejecutar({ texto, tipo: 'preguntar' })
  const guardarNombre = async () => {
    if (!renombrar || !renombrar.titulo.trim() || guardando) return
    setGuardando(true)
    try {
      const resultado = await api.editar<{ titulo: string; version?: number }>(`/ia/asistente/conversaciones/${renombrar.id}`, { titulo: renombrar.titulo.trim(), version: renombrar.id === id ? version : renombrar.version })
      consultas.setQueryData<Conversacion>(['asistente-conversacion', renombrar.id], anterior => anterior ? { ...anterior, titulo: resultado.titulo, version: resultado.version } : anterior)
      await historial.refetch()
      setRenombrar(null); setAviso('Nombre actualizado.')
    } catch (fallo) {
      if (fallo instanceof ErrorPeticion && fallo.estado === 409) {
        try {
          const actual = await api.obtener<Conversacion>(`/ia/asistente/conversaciones/${renombrar.id}`)
          consultas.setQueryData(['asistente-conversacion', renombrar.id], actual)
          setRenombrar(anterior => anterior ? { ...anterior, version: actual.version } : anterior)
          await historial.refetch()
        } catch { /* El error original sigue visible y el nombre escrito se conserva. */ }
      }
      setErrorGestion(fallo instanceof Error ? fallo.message : 'No se pudo cambiar el nombre.')
    }
    finally { setGuardando(false) }
  }
  const eliminar = async () => {
    if (!porEliminar || guardando) return
    const objetivo = porEliminar.id
    setGuardando(true)
    try {
      await api.borrar(`/ia/asistente/conversaciones/${objetivo}`)
      consultas.removeQueries({ queryKey: ['asistente-conversacion', objetivo] })
      if (objetivo === id) {
        const siguientes = new URLSearchParams(parametros); siguientes.delete('conversacion'); siguientes.delete('pregunta'); setParametros(siguientes)
        setPregunta(''); setError(null); setUltimoIntento(null)
      }
      await historial.refetch()
      setPorEliminar(null); setAviso('Conversación eliminada.')
    } catch (fallo) { setErrorGestion(fallo instanceof Error ? fallo.message : 'No se pudo eliminar la conversación.') }
    finally { setGuardando(false) }
  }
  const copiar = async (mensaje: Mensaje, indice: number) => {
    try {
      await navigator.clipboard.writeText(textoVisible(mensaje.texto))
      setCopiada(indice); setAviso('Respuesta copiada.')
    } catch { setAviso('No se pudo copiar. Puedes seleccionar el texto y copiarlo manualmente.') }
  }
  const descargar = () => {
    const celda = (valor: unknown) => String(valor ?? 'Sin datos').replace(/\|/g, '\\|').replace(/[\r\n]+/g, ' ')
    const contenido = '# ' + (conversacion.data?.titulo || 'Consulta de datos') + '\n\n' + mensajes.map(m => {
      const filas = m.tabla?.filas.length ? '\n| ' + m.tabla.columnas.map(c => celda(c.titulo)).join(' | ') + ' |\n| ' + m.tabla.columnas.map(() => '---').join(' | ') + ' |\n' + m.tabla.filas.map(f => '| ' + m.tabla!.columnas.map(c => celda(f[c.clave])).join(' | ') + ' |').join('\n') + '\n' : ''
      const enlaces = (m.enlaces || []).filter(e => enlaceDeDatosSeguro(e.href)).map(e => '- [' + e.texto.replace(/\\/g, '\\\\').replace(/[[\]]/g, '\\$&').replace(/[\r\n]/g, ' ') + '](' + window.location.origin + e.href + ')').join('\n')
      return '## ' + (m.rol === 'user' ? 'Tú' : 'Asistente de datos') + '\n\n' + textoVisible(m.texto) + '\n' + (alcance(m) ? '\nFechas: ' + alcance(m) + '\n' : '') + (m.alcance_consulta ? '\nÁmbito: ' + m.alcance_consulta + '\n' : '') + filas + (enlaces ? '\nRegistros relacionados:\n' + enlaces + '\n' : '') + (m.fuentes?.length ? '\nFuentes: ' + m.fuentes.map(f => FUENTES[f] || f).join(', ') + '\n' : '')
    }).join('\n')
    const enlace = document.createElement('a')
    const url = URL.createObjectURL(new Blob([contenido], { type: 'text/markdown;charset=utf-8' }))
    enlace.href = url; enlace.download = 'consulta-datos.md'; enlace.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const bloqueado = Boolean(enviada) || guardando || (Boolean(id) && !conversacion.data)
  const navegacionBloqueada = Boolean(enviada) || guardando
  const todas = preguntas.data?.preguntas ?? []
  const agrupar = todas.length > 7
  const buscando = normalizarBusqueda(busquedaPreguntas.trim())
  const delGrupo = todas.filter(texto => buscando ? normalizarBusqueda(texto).includes(buscando) : !agrupar || (preguntas.data?.grupos?.[texto] || grupoPregunta(texto)) === grupo).sort((a, b) => Number(/resumen.*servicio/.test(b)) - Number(/resumen.*servicio/.test(a)))
  const visibles = agrupar && !mostrarTodas && !buscando ? delGrupo.slice(0, 4) : delGrupo
  const chats = (historial.data?.items ?? []).filter(c => c.titulo.toLocaleLowerCase().includes(busqueda.toLocaleLowerCase()))
  const opciones = preguntas.isPending ? <SkeletonPanel filas={3} /> : preguntas.isError ? <ErrorState compacto mensaje="No pudimos cargar las preguntas." alReintentar={() => void preguntas.refetch()} /> : <>{agrupar ? <><div className="datos-categories" role="group" aria-label="Tipo de consulta">{['Tickets', 'Equipos', 'Equipo TI', 'Entender'].map(tipo => <Button key={tipo} tamano="sm" disabled={Boolean(enviada)} aria-pressed={!buscando && grupo === tipo} onClick={() => { setGrupo(tipo); setMostrarTodas(false); setBusquedaPreguntas('') }}>{tipo}</Button>)}</div><div className="datos-question-search"><Search size={16} aria-hidden="true" /><input aria-label="Buscar preguntas" type="search" value={busquedaPreguntas} onChange={e => setBusquedaPreguntas(e.target.value)} placeholder="Busca: patrimonio, vencidos, guías…" />{busquedaPreguntas ? <button type="button" onClick={() => setBusquedaPreguntas('')}>Limpiar</button> : null}</div></> : null}<div className="datos-options">{visibles.map(texto => {
    const { titulo, subtitulo, Icono } = presentarPregunta(texto)
    return <Button key={texto} aria-label={texto} disabled={bloqueado} onClick={() => void preguntar(texto)} className="datos-suggestion"><span className="datos-suggestion-icon" aria-hidden="true"><Icono size={20} /></span><span><strong>{titulo}</strong><small>{subtitulo !== titulo ? subtitulo : 'Ver la respuesta en tus registros.'}</small></span><ArrowRight size={15} aria-hidden="true" /></Button>
  })}</div>{buscando && !visibles.length ? <p className="datos-search-empty">No hay preguntas con ese texto. Prueba con «equipos», «guías» o «tickets».</p> : null}{agrupar && delGrupo.length > 4 && !buscando ? <button type="button" className="datos-text-button" onClick={() => setMostrarTodas(!mostrarTodas)}>{mostrarTodas ? 'Ver menos preguntas' : 'Ver más preguntas'}</button> : null}</>
  return <div className="datos-lab">
    <aside className={'datos-sidebar' + (historialAbierto ? ' datos-sidebar-open' : '')} aria-label="Tus conversaciones">
      <div className="datos-history-title"><Layers3 size={20} aria-hidden="true" /><h2>Consultas de datos</h2></div>
      <label className="datos-search"><Search size={16} aria-hidden="true" /><span className="sr-only">Buscar conversaciones</span><input type="search" placeholder="Buscar conversación" value={busqueda} onChange={e => setBusqueda(e.target.value)} /></label>
      <div className="datos-history-list">
        <p className="datos-history-caption">Tus conversaciones</p>
        {historial.isError ? <ErrorState compacto mensaje="No pudimos cargar el historial." alReintentar={() => void historial.refetch()} /> : historial.isPending ? <SkeletonPanel filas={3} /> : chats.length ? <ul>{chats.map(c => <li key={c.id} className={c.id === id ? 'datos-history-active' : ''}>
          <button type="button" className="datos-open-chat" aria-label={'Abrir conversación: ' + c.titulo} aria-current={c.id === id ? 'true' : undefined} title={c.titulo} disabled={navegacionBloqueada} onClick={() => seleccionar(c.id)}>{c.titulo}</button>
          <button type="button" aria-label={'Renombrar conversación: ' + c.titulo} title="Renombrar" disabled={navegacionBloqueada} onClick={() => { setErrorGestion(null); setRenombrar({ ...c }) }}><Pencil size={14} aria-hidden="true" /></button>
          <button type="button" aria-label={'Eliminar conversación: ' + c.titulo} title="Eliminar" disabled={navegacionBloqueada} onClick={() => { setErrorGestion(null); setPorEliminar(c) }}><Trash2 size={14} aria-hidden="true" /></button>
        </li>)}</ul> : <p className="datos-history-empty">{busqueda ? 'No hay conversaciones con ese nombre.' : 'Tu próxima consulta quedará guardada aquí.'}</p>}
        {historial.data?.hay_mas ? <p className="datos-history-empty">Se buscan las 100 conversaciones más recientes.</p> : null}
      </div>
      <div className="datos-scope"><Clock3 size={15} aria-hidden="true" /><span>{PERIODOS[periodo] || periodo}</span><small>Cambia las fechas en «Periodo».</small></div>
      <details className="datos-query-guide"><summary>Qué puedes consultar</summary><p>Tickets, inventario, plazos y disponibilidad de TI según tus permisos.</p><p>Puedes indicar «hoy», «ayer» o «en la oficina [nombre]», y continuar con «explícame eso».</p><p>Las consultas reconocidas usan tus registros internos, sin tokens de Groq.</p></details>
    </aside>
    <section className="datos-workspace" aria-label="Chat de análisis interno" onKeyDown={e => {
      if (e.key === 'Escape' && sugerenciasAbiertas) {
        e.preventDefault(); e.stopPropagation()
        setSugerenciasAbiertas(false); selectorPreguntas.current?.focus()
      }
    }}>
      <header className="datos-chat-header">
        <button type="button" className="datos-history-toggle" aria-label={historialAbierto ? 'Ocultar historial' : 'Mostrar historial'} aria-expanded={historialAbierto} onClick={() => setHistorialAbierto(!historialAbierto)}><PanelLeft size={19} aria-hidden="true" /></button>
        <div><p className="datos-eyebrow">ASISTENTE DE DATOS</p><h2>{id ? conversacion.data?.titulo || (conversacion.isError ? 'Conversación no disponible' : 'Abriendo conversación…') : '¿Qué quieres saber?'}</h2></div>
        <span className="datos-safe"><ShieldCheck size={14} aria-hidden="true" />Solo lectura</span>
        <button ref={selectorPreguntas} type="button" className="datos-suggestions-toggle" aria-controls="datos-sugerencias" aria-expanded={sugerenciasAbiertas} onClick={() => setSugerenciasAbiertas(!sugerenciasAbiertas)}><ListChecks size={16} aria-hidden="true" />Preguntas sugeridas</button>
        <Button className="datos-new" tamano="sm" icono={<MessageSquarePlus size={16} />} disabled={navegacionBloqueada} onClick={() => seleccionar('')}>Nueva conversación</Button>
        {mensajes.length ? <button type="button" className="datos-icon-button" aria-label="Descargar conversación" title="Descargar conversación" onClick={descargar}><Download size={17} aria-hidden="true" /></button> : null}
      </header>
      <div className="datos-log-wrap">
        {sugerenciasAbiertas ? <section id="datos-sugerencias" className="datos-suggestions-panel" role="region" aria-label="Preguntas sugeridas"><header><h3>Elige qué quieres consultar</h3><button type="button" aria-label="Cerrar preguntas sugeridas" onClick={() => { setSugerenciasAbiertas(false); selectorPreguntas.current?.focus() }}>Cerrar</button></header>{opciones}</section> : null}
        <div ref={registro} inert={sugerenciasAbiertas} onScroll={alDesplazar} onWheel={interrumpir} onTouchMove={interrumpir} onPointerDown={interrumpir} onKeyDown={e => { if (['ArrowUp', 'PageUp', 'Home'].includes(e.key)) interrumpir() }} role="log" aria-label="Conversación con el asistente" aria-live="polite" aria-busy={Boolean(enviada) || Boolean(animada)} className="datos-log">
          {id && conversacion.isPending ? <SkeletonPanel filas={3} /> : conversacion.isError ? <ErrorState compacto mensaje="No pudimos abrir la conversación." alReintentar={() => void conversacion.refetch()} /> : null}
          {!id && !enviada ? <div className="datos-empty"><span className="datos-empty-symbol" aria-hidden="true"><Sparkles size={28} /></span><h2>Tus datos, fáciles de entender</h2><p className="datos-welcome">Pregunta, compara y encuentra qué necesita atención.</p><h3 className="datos-suggestion-heading">Empieza con un clic</h3>{opciones}<p className="datos-empty-note">O escribe lo que necesitas saber.</p></div> : null}
          {mensajes.map((mensaje, indice) => { const escribiendo = mensaje.rol === 'assistant' && animada?.id === id && animada.indice === indice; return <article key={indice} className={mensaje.rol === 'user' ? 'datos-question' : 'datos-result'}>
            {mensaje.rol === 'user' ? <p className="datos-question-label">Tú</p> : <div className="datos-result-header"><span><Sparkles size={17} aria-hidden="true" />{mensaje.fuentes?.includes('guia_analisis') ? 'Asistente interno' : 'Asistente de datos'}</span>{alcance(mensaje) ? <span className="datos-periodo">{alcance(mensaje)}</span> : null}</div>}
            {mensaje.alcance_consulta ? <p className="datos-query-scope"><Building2 size={12} aria-hidden="true" />{mensaje.alcance_consulta}</p> : null}
            {edicion?.indice === indice ? <div className="datos-edit-question"><Textarea etiqueta="Editar tu pregunta" value={edicion.texto} maxLength={1000} filas={3} disabled={bloqueado} onChange={e => setEdicion({ ...edicion, texto: e.target.value })} /><small>Al enviar se reemplazan esta pregunta y las respuestas posteriores.</small><div><Button tamano="sm" disabled={bloqueado} onClick={() => setEdicion(null)}>Cancelar edición</Button><Button tamano="sm" variante="primario" disabled={bloqueado || edicion.texto.trim().length < 2} onClick={() => void ejecutar({ texto: edicion.texto, tipo: 'editar', indice })}>Guardar y enviar</Button></div></div> : <TextoProgresivo key={escribiendo ? 'escribiendo' : 'guardado'} texto={textoVisible(mensaje.texto)} animar={escribiendo} alProgresar={seguirEscritura} alTerminar={terminarEscritura} />}
            {mensaje.rol === 'assistant' ? !escribiendo ? <>
              {mensaje.analisis ? <details className="datos-reading"><summary><Sparkles size={14} aria-hidden="true" />Entender este resultado</summary><p>{mensaje.analisis.significado}</p><dl><div><dt>Qué revisar</dt><dd>{mensaje.analisis.revision}</dd></div><div><dt>Ten en cuenta</dt><dd>{mensaje.analisis.limite}</dd></div></dl></details> : null}
              {mensaje.tabla?.filas.length ? <><VistaDatos tabla={mensaje.tabla} /><details className="datos-data"><summary>Ver datos de la respuesta</summary><div className="datos-table-scroll"><table><thead><tr>{mensaje.tabla.columnas.map(c => <th scope="col" key={c.clave}>{c.titulo}</th>)}</tr></thead><tbody>{mensaje.tabla.filas.map((fila, i) => <tr key={i}>{mensaje.tabla!.columnas.map(c => <td key={c.clave}>{fila[c.clave] == null ? 'Sin datos' : typeof fila[c.clave] === 'object' ? 'Ver detalle' : textoVisible(String(fila[c.clave]))}</td>)}</tr>)}</tbody></table></div></details></> : null}
              {mensaje.enlaces?.length ? <div className="datos-links">{mensaje.enlaces.filter(e => enlaceDeDatosSeguro(e.href)).map(e => <Link key={e.href} to={e.href}>{e.texto} ↗</Link>)}</div> : null}
              {mensaje.fuentes?.length || mensaje.explicacion ? <details className="datos-proof"><summary>De dónde sale esta respuesta</summary><div className="datos-sources">{mensaje.fuentes?.map(f => <span key={f}><Database size={12} aria-hidden="true" />{FUENTES[f] || f}</span>)}</div>{mensaje.explicacion ? <p>{mensaje.explicacion}</p> : null}</details> : null}
              <div className="datos-message-actions"><button type="button" aria-label="Copiar respuesta" title={copiada === indice ? 'Copiada' : 'Copiar respuesta'} onClick={() => void copiar(mensaje, indice)}>{copiada === indice ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}</button>{indice === mensajes.length - 1 && mensajes[indice - 1]?.rol === 'user' ? <button type="button" aria-label="Regenerar respuesta" title="Volver a consultar los datos" disabled={bloqueado} onClick={() => void ejecutar({ texto: mensajes[indice - 1].texto, tipo: 'regenerar' })}><RotateCcw size={15} aria-hidden="true" /></button> : null}</div>
              {indice === mensajes.length - 1 && mensaje.seguimientos?.length ? <div className="datos-followups" role="group" aria-label="Seguir consultando">{mensaje.analisis ? <Button disabled={bloqueado} tamano="sm" onClick={() => void preguntar('Explícame eso')}>Explícame este resultado</Button> : null}{mensaje.seguimientos.map(texto => <Button key={texto} disabled={bloqueado} tamano="sm" onClick={() => void preguntar(texto)}>{texto}</Button>)}</div> : null}
            </> : null : !edicion ? <button type="button" className="datos-edit-button" aria-label="Editar pregunta" title="Editar pregunta" disabled={bloqueado} onClick={() => setEdicion({ indice, texto: mensaje.texto })}><Pencil size={14} aria-hidden="true" /></button> : null}
          </article> })}
          {enviada ? <><div className="datos-question"><p>{enviada}</p></div><p role="status" className="datos-thinking"><span className="datos-thinking-dot" />Consultando tus registros…</p></> : null}
        </div>
        {lejosDelFinal && !sugerenciasAbiertas ? <button type="button" className="datos-jump" aria-label="Ir al último mensaje" title="Ir al último mensaje" onClick={irAlFinal}><ArrowDown size={18} aria-hidden="true" /></button> : null}
      </div>
      {error ? <div className="datos-error"><Nota tono="peligro" titulo="La consulta no se completó">{error}</Nota>{ultimoIntento ? <Button tamano="sm" disabled={bloqueado} onClick={() => void ejecutar(ultimoIntento)}>Reintentar consulta</Button> : null}</div> : null}
      <form className="datos-composer" onSubmit={e => { e.preventDefault(); void preguntar(pregunta) }}>
        <div className="datos-input-shell"><label className="sr-only" htmlFor="datos-pregunta">Tu pregunta</label><textarea id="datos-pregunta" ref={entrada} placeholder="Pregunta sobre tus tickets, equipos o atención…" rows={2} maxLength={1000} disabled={bloqueado} value={pregunta} onChange={e => setPregunta(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void preguntar(pregunta) } }} />
          {animada ? <button type="button" className="datos-send" aria-label="Detener escritura" title="Mostrar la respuesta completa" onClick={terminarEscritura}><Square size={16} aria-hidden="true" /></button> : <button type="submit" className="datos-send" aria-label="Preguntar" title="Enviar pregunta" disabled={bloqueado || pregunta.trim().length < 2}><Send size={18} aria-hidden="true" /></button>}
        </div><div className="datos-composer-note"><span>{pregunta.length}/1000 · Enter envía · Shift + Enter nueva línea</span><span>Datos de tu sistema · Solo lectura</span></div>
      </form>
      <p className="datos-feedback" role="status">{aviso}</p>
    </section>
    <DialogModal abierto={Boolean(renombrar)} alCerrar={() => { if (!guardando) setRenombrar(null) }} titulo="Renombrar conversación" tamano="sm" pie={<><Button disabled={guardando} onClick={() => setRenombrar(null)}>Cancelar</Button><Button variante="primario" cargando={guardando} disabled={!renombrar?.titulo.trim()} onClick={() => void guardarNombre()}>Guardar nombre</Button></>}>
      <label className="datos-rename-field">Nombre de la conversación<input value={renombrar?.titulo || ''} maxLength={100} disabled={guardando} onChange={e => { if (renombrar) setRenombrar({ ...renombrar, titulo: e.target.value }) }} /></label>
      {errorGestion ? <p role="alert" className="mt-3 text-sm text-destructive-strong">{errorGestion}</p> : null}
    </DialogModal>
    <ConfirmDialog abierto={Boolean(porEliminar)} alCerrar={() => { if (!guardando) setPorEliminar(null) }} alConfirmar={() => void eliminar()} titulo="Eliminar conversación" mensaje={<><p>{'Se eliminará «' + (porEliminar?.titulo || '') + '» de tu historial.'}</p>{errorGestion ? <p role="alert" className="mt-3 text-destructive-strong">{errorGestion}</p> : null}</>} textoConfirmar="Eliminar conversación" peligro cargando={guardando} />
  </div>
}
