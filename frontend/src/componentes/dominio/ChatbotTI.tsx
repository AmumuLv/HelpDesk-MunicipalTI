import { ArrowDown, ArrowUpRight, Bot, MessageCirclePlus, Send, ShieldCheck, Sparkles, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../../api/cliente'
import { useSesion } from '../../estado/useSesion'
import * as Dialog from '@radix-ui/react-dialog'
import { useScrollChat } from './useScrollChat'
import './ChatbotTI.css'

type Mensaje = { rol: 'user' | 'assistant'; texto: string; fuentes?: { titulo: string; ruta: string }[] }
type Uso = { entrada: number; salida: number; razonamiento: number; total: number }
type Consumo = { consultas: number; tokens: number; conTokens: number }
type Conversacion = { id?: string; titulo?: string; mensajes: Mensaje[]; consumo: Consumo; limite?: number }
type ChatGuardado = { id: string; titulo: string; consumo: Consumo; limite: number; en_curso?: boolean }
type Respuesta = { disponible: boolean; texto: string; fuentes: { titulo: string; ruta: string }[]; uso?: Uso | null; conversacion_id?: string; consumo?: Consumo; limite?: number }

export function ChatbotTI() {
  const sesion = useSesion()
  const ubicacion = useLocation()
  const cache = useQueryClient()
  const claveConversacion = useMemo(() => ['chatbot-ti', 'conversacion', sesion.usuario?.id], [sesion.usuario?.id])
  const permitido = sesion.rol === 'tecnico' || sesion.rol === 'administrador'
  const [abierto, setAbierto] = useState(false)
  const [pregunta, setPregunta] = useState('')
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [animarIndice, setAnimarIndice] = useState<number | null>(null)
  const [consumo, setConsumo] = useState<Consumo>({ consultas: 0, tokens: 0, conTokens: 0 })
  const [enviando, setEnviando] = useState(false)
  const [enviada, setEnviada] = useState('')
  const [chatId, setChatId] = useState<string | undefined>()
  const [cargandoChat, setCargandoChat] = useState(false)
  const [limiteChat, setLimiteChat] = useState<number | undefined>()
  const restaurada = useRef(false)
  const [error, setError] = useState('')
  const bloqueo = useRef(false)
  const cuenta = useRef(sesion.usuario?.id)
  cuenta.current = sesion.usuario?.id
  const { registro, seguirFinal, lejosDelFinal, onScroll, interrumpir, seguirEscritura, irAlFinal, restaurarFinal } = useScrollChat()
  const panelAbierto = useRef(abierto)
  panelAbierto.current = abierto
  const posicionGuardada = useRef<number | undefined>(undefined)
  const restauracionPendiente = useRef<number | 'final' | null>(null)
  const terminarEscritura = useCallback(() => setAnimarIndice(null), [])
  const cambiarAbierto = useCallback((valor: boolean) => {
    if (valor && (mensajes.length || enviada)) restauracionPendiente.current = posicionGuardada.current ?? 'final'
    if (!valor) {
      posicionGuardada.current = seguirFinal.current ? undefined : registro.current?.scrollTop
      setAnimarIndice(null)
      interrumpir()
    }
    panelAbierto.current = valor
    setAbierto(valor)
  }, [mensajes.length, enviada, registro, interrumpir, seguirFinal])
  const estado = useQuery({ queryKey: ['chatbot-ti', 'estado', sesion.usuario?.id], queryFn: () => api.obtener<{ configurado: boolean; proveedor?: string; modelo?: string; limite_consultas?: number }>('/ia/chatbot/estado'), enabled: permitido && abierto, retry: false })
  const historial = useQuery({ queryKey: ['chatbot-ti', 'historial', sesion.usuario?.id], queryFn: () => api.obtener<{ items: ChatGuardado[] }>('/ia/chatbot/conversaciones'), enabled: permitido && abierto, retry: false, refetchInterval: abierto ? 15000 : false })
  const limite = limiteChat ?? estado.data?.limite_consultas
  const agotado = limite !== undefined && consumo.consultas >= limite
  const abrirChat = useCallback(async (id: string, conservarPosicion = false) => {
    if (bloqueo.current) return
    const propietario = cuenta.current
    const posicionActual = conservarPosicion ? registro.current?.scrollTop : undefined
    setCargandoChat(true); setError(''); setAnimarIndice(null)
    try {
      const chat = await api.obtener<Conversacion>(`/ia/chatbot/conversaciones/${id}`)
      if (cuenta.current !== propietario) return
      posicionGuardada.current = undefined
      restauracionPendiente.current = posicionActual ?? 'final'
      setChatId(id); setMensajes(chat.mensajes); setConsumo(chat.consumo); setLimiteChat(chat.limite); setPregunta('')
      cache.setQueryData(claveConversacion, { ...chat, id })
    } catch (fallo) { if (cuenta.current === propietario) setError(fallo instanceof Error ? fallo.message : 'No se pudo abrir la conversación.') }
    finally { if (cuenta.current === propietario) setCargandoChat(false) }
  }, [cache, claveConversacion, registro])
  const nuevaConsulta = useCallback(() => {
    if (bloqueo.current || cargandoChat) return
    restaurada.current = true
    const vacia = { mensajes: [], consumo: { consultas: 0, tokens: 0, conTokens: 0 } }
    cache.setQueryData(claveConversacion, vacia)
    setMensajes([]); setConsumo(vacia.consumo); setError('')
    setAnimarIndice(null)
    interrumpir()
    seguirFinal.current = true
    posicionGuardada.current = undefined
    restauracionPendiente.current = null
    setChatId(undefined); setLimiteChat(undefined); setPregunta('')
  }, [cache, claveConversacion, cargandoChat, interrumpir, seguirFinal])
  useEffect(() => {
    if (!abierto || !historial.isFetched || restaurada.current) return
    restaurada.current = true
    if (!chatId && !mensajes.length && historial.data?.items?.length) void abrirChat(historial.data.items[0].id)
  }, [abierto, historial.isFetched, historial.data, chatId, mensajes.length, abrirChat])
  useEffect(() => {
    if (!abierto || !chatId || enviando || cargandoChat || historial.isFetching || historial.isError || !historial.data?.items) return
    const remoto = historial.data.items.find(chat => chat.id === chatId)
    if (!remoto) { nuevaConsulta(); return }
    // A cached list may lag behind the detail just loaded. Never reopen the
    // same chat repeatedly to replace newer messages with that older snapshot.
    if (!remoto.en_curso && (remoto.consumo.consultas > consumo.consultas || remoto.consumo.tokens > consumo.tokens)) void abrirChat(chatId, true)
  }, [abierto, historial.data, historial.isFetching, historial.isError, chatId, enviando, cargandoChat, consumo.consultas, consumo.tokens, abrirChat, nuevaConsulta])
  useEffect(() => {
    cache.setQueryDefaults(['chatbot-ti', 'conversacion'], { gcTime: Infinity })
    const guardada = cache.getQueryData<Conversacion>(['chatbot-ti', 'conversacion', sesion.usuario?.id])
    setMensajes(guardada?.mensajes ?? [])
    setConsumo(guardada?.consumo ?? { consultas: 0, tokens: 0, conTokens: 0 })
    setChatId(guardada?.id); setLimiteChat(guardada?.limite); restaurada.current = Boolean(guardada)
    setCargandoChat(false)
    setAnimarIndice(null); setEnviada('')
    posicionGuardada.current = undefined
    restauracionPendiente.current = null
    setPregunta(''); setAbierto(false); setError('')
  }, [sesion.usuario?.id, cache])
  useLayoutEffect(() => {
    if (!abierto || cargandoChat || restauracionPendiente.current === null) return
    let marco = 0
    const restaurar = () => {
      if (!registro.current) { marco = requestAnimationFrame(restaurar); return }
      const destino = restauracionPendiente.current
      if (destino === null) return
      restauracionPendiente.current = null
      restaurarFinal(destino === 'final' ? undefined : destino)
    }
    // El contenido del diálogo se monta en un portal después del padre.
    marco = requestAnimationFrame(restaurar)
    return () => cancelAnimationFrame(marco)
  }, [abierto, cargandoChat, mensajes, registro, restaurarFinal])
  useEffect(() => {
    if (abierto && !cargandoChat && (mensajes.length || enviada)) seguirEscritura()
  }, [abierto, cargandoChat, mensajes.length, enviada, animarIndice, seguirEscritura])
  const eliminarChat = async () => {
    if (!chatId || bloqueo.current || cargandoChat) return
    const propietario = cuenta.current
    setCargandoChat(true); setError('')
    try {
      await api.borrar(`/ia/chatbot/conversaciones/${chatId}`)
      if (cuenta.current !== propietario) return
      const vacia = { mensajes: [], consumo: { consultas: 0, tokens: 0, conTokens: 0 } }
      cache.setQueryData(claveConversacion, vacia)
      setAnimarIndice(null)
      interrumpir()
      seguirFinal.current = true
      posicionGuardada.current = undefined
      restauracionPendiente.current = null
      setChatId(undefined); setMensajes([]); setConsumo(vacia.consumo); setLimiteChat(undefined); setPregunta(''); restaurada.current = true
      void historial.refetch()
    } catch (fallo) { if (cuenta.current === propietario) setError(fallo instanceof Error ? fallo.message : 'No se pudo eliminar la conversación.') }
    finally { if (cuenta.current === propietario) setCargandoChat(false) }
  }
  if (!permitido) return null
  const enviar = async (texto: string) => {
    const limpia = texto.trim()
    if (bloqueo.current || cargandoChat || agotado || limpia.length < 2 || limpia.length > 1500 || !estado.data?.configurado) return
    bloqueo.current = true
    setEnviando(true)
    setEnviada(limpia)
    setAnimarIndice(null)
    setPregunta(limpia)
    setError('')
    irAlFinal()
    const cuentaAlEnviar = cuenta.current
    try {
      const parametros = new URLSearchParams(ubicacion.search)
      const filtros: Record<string, string> = {}
      for (const campo of ['periodo', 'desde', 'hasta', 'fecha_desde', 'fecha_hasta', 'estado', 'zona_id', 'oficina_id', 'tecnico_id', 'activo_id', 'conjunto_id']) {
        const valor = campo === 'estado' ? parametros.getAll(campo).join(',') : parametros.get(campo)
        if (valor) filtros[campo] = valor.slice(0, 80)
      }
      const respuesta = await api.crear<Respuesta>('/ia/chatbot', { pregunta: limpia, historial: mensajes.slice(-6).map(({ rol, texto }) => ({ rol, texto })), pagina: ubicacion.pathname, filtros, ...(chatId ? { conversacion_id: chatId } : {}) })
      if (cuenta.current !== cuentaAlEnviar) return
      const siguienteConsumo = respuesta.consumo ?? { consultas: consumo.consultas + 1, tokens: consumo.tokens + (respuesta.uso?.total ?? 0), conTokens: consumo.conTokens + (respuesta.uso ? 1 : 0) }
      const id = respuesta.conversacion_id ?? chatId
      setChatId(id); setLimiteChat(respuesta.limite ?? limiteChat)
      setConsumo(siguienteConsumo)
      cache.setQueryData(claveConversacion, { id, mensajes, consumo: siguienteConsumo, limite: respuesta.limite ?? limiteChat })
      void historial.refetch()
      if (!respuesta.disponible) { setError(respuesta.texto); return }
      const siguientes = [...mensajes, { rol: 'user', texto: limpia }, { rol: 'assistant', texto: respuesta.texto, fuentes: respuesta.fuentes }] as Mensaje[]
      cache.setQueryData(claveConversacion, { id, mensajes: siguientes, consumo: siguienteConsumo, limite: respuesta.limite ?? limiteChat })
      setMensajes(siguientes); setConsumo(siguienteConsumo)
      setAnimarIndice(panelAbierto.current ? siguientes.length - 1 : null)
      setPregunta('')
    } catch (fallo) { if (cuenta.current === cuentaAlEnviar) setError(fallo instanceof Error ? fallo.message : 'No se pudo completar la consulta. Puedes reintentar.') }
    finally { bloqueo.current = false; setEnviando(false); if (cuenta.current === cuentaAlEnviar) setEnviada('') }
  }
  return <>
    <button type="button" aria-label="Abrir asistente TI" onClick={() => cambiarAbierto(true)} className="ti-launcher"><Bot size={27} /><span className="ti-launcher-spark" aria-hidden="true"><Sparkles size={11} /></span></button>
    <Dialog.Root open={abierto} onOpenChange={cambiarAbierto}>
      <Dialog.Portal>
        <Dialog.Overlay className="ti-chat-overlay" />
        <Dialog.Content className="ti-chat">
          <header className="ti-chat-header">
            <span className="ti-chat-avatar" aria-hidden="true"><Bot size={25} /></span>
            <div className="ti-chat-heading"><span className="ti-chat-eyebrow">TU ESPACIO DE CONSULTAS</span><Dialog.Title>Asistente TI<span className="ti-gemini">{estado.data?.proveedor ?? 'IA'}</span></Dialog.Title><Dialog.Description>Conecta ideas. Encuentra respuestas.</Dialog.Description></div>
            <button type="button" className="ti-chat-icon" aria-label="Nueva consulta" title="Nueva conversación" disabled={enviando || cargandoChat || (!chatId && !mensajes.length)} onClick={nuevaConsulta}><MessageCirclePlus size={19} /></button>
            <button type="button" className="ti-chat-icon" aria-label="Eliminar conversación" title="Eliminar conversación" disabled={enviando || cargandoChat || !chatId} onClick={() => void eliminarChat()}><Trash2 size={18} /></button>
            <Dialog.Close className="ti-chat-icon" aria-label="Cerrar"><X size={20} /></Dialog.Close>
          </header>
          <div className="ti-chat-toolbar"><span><ShieldCheck size={13} /> Solo lectura</span><span title={ubicacion.pathname}>Contexto: {ubicacion.pathname.split('/').filter(Boolean).slice(1).join(' / ') || 'Resumen'}</span></div>
          <div className="ti-chat-history"><label htmlFor="chats-guardados">Tus conversaciones</label><select id="chats-guardados" value={chatId ?? ''} disabled={enviando || cargandoChat} onChange={e => { restaurada.current = true; if (e.target.value) void abrirChat(e.target.value); else nuevaConsulta() }}><option value="">Nueva conversación</option>{historial.data?.items?.map(chat => <option key={chat.id} value={chat.id}>{chat.titulo} ({chat.consumo.consultas}/{chat.limite})</option>)}</select></div>
          <div className="ti-chat-log-wrap">
          <div ref={registro} onScroll={onScroll} onWheel={interrumpir} onTouchStart={e => { if (!(e.target as Element).closest('button, a')) interrumpir() }} onPointerDown={e => { if (!(e.target as Element).closest('button, a')) interrumpir() }} onKeyDown={e => { if (!(e.target as Element).closest('button, a') && ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(e.key)) interrumpir() }} tabIndex={0} role="log" aria-label="Conversación con el asistente TI" aria-live="polite" aria-busy={enviando || cargandoChat || animarIndice !== null} className="ti-chat-log">
            {!mensajes.length && !enviada ? <div className="ti-chat-welcome">
              <div className="ti-chat-orbit" aria-hidden="true"><span><Sparkles size={31} /></span></div>
              <span className="ti-chat-kicker">MENOS BÚSQUEDAS. MÁS RESPUESTAS.</span>
              <h2>Tu siguiente idea<br /><em>empieza aquí.</em></h2>
              <p>Desde una duda del sistema hasta el siguiente paso de una incidencia. Cuéntame qué necesitas.</p>
              <div className="ti-chat-prompts">{[{ titulo: 'Resolver una duda', texto: '¿Cómo vinculo un ticket al conjunto?' }, { titulo: 'Preparar mi inventario', texto: '¿Qué debe incluir el Excel de inventario?' }, { titulo: 'Explorar los datos', texto: '¿Qué oficinas tienen más incidencias?' }].map(opcion => <button key={opcion.titulo} type="button" disabled={!estado.data?.configurado || enviando || cargandoChat || agotado} onClick={() => void enviar(opcion.texto)}><span>{opcion.titulo}</span><span>{opcion.texto}</span><ArrowUpRight size={17} aria-hidden="true" /></button>)}</div>
            </div> : mensajes.map((m, i) => <article key={i} className={m.rol === 'user' ? 'ti-message ti-message-user' : 'ti-message ti-message-assistant'}>
              <div className="ti-message-label">{m.rol === 'assistant' ? <Bot size={16} aria-hidden="true" /> : null}{m.rol === 'user' ? 'Tú' : 'Asistente TI'}</div>
              <div className="ti-message-content">{m.rol === 'assistant' ? <RespuestaProgresiva key={i === animarIndice ? 'escribiendo' : 'guardada'} texto={m.texto} animar={abierto && i === animarIndice} alAvanzar={seguirEscritura} alTerminar={terminarEscritura} /> : <p>{m.texto}</p>}</div>
              {i !== animarIndice && m.fuentes?.length ? <div className="ti-chat-sources">{m.fuentes.map((f, indice) => /^https:\/\//.test(f.ruta) ? <a key={indice} href={f.ruta} target="_blank" rel="noopener noreferrer">{f.titulo}<ArrowUpRight size={12} /></a> : <Link key={indice} to={f.ruta} onClick={() => cambiarAbierto(false)}>{f.titulo}<ArrowUpRight size={12} /></Link>)}</div> : null}
            </article>)}
            {enviada ? <article className="ti-message ti-message-user ti-message-pending"><div className="ti-message-label">Tú</div><div className="ti-message-content"><p>{enviada}</p></div></article> : null}
            {enviando ? <div role="status" className="ti-chat-thinking"><span aria-hidden="true"><i /><i /><i /></span>Consultando…</div> : null}
            {cargandoChat ? <p role="status">Cargando conversación…</p> : null}
          </div>
          {lejosDelFinal && (mensajes.length || enviada) ? <button type="button" className="ti-chat-jump" aria-label="Ir al último mensaje" title="Ir al último mensaje" onClick={irAlFinal}><ArrowDown size={16} aria-hidden="true" /><span>Último mensaje</span></button> : null}
          </div>
          <div className="ti-chat-bottom">
            <div className="ti-chat-consumo" aria-label="Consumo de esta conversación"><span>{consumo.consultas} {consumo.consultas === 1 ? 'consulta' : 'consultas'}</span><span>{consumo.conTokens ? `${consumo.tokens.toLocaleString('es-PE')} tokens usados${consumo.conTokens < consumo.consultas ? ' (parcial)' : ''}` : 'Tokens: sin datos'}</span><a href={estado.data?.proveedor === 'Gemini' ? 'https://aistudio.google.com/' : 'https://console.groq.com/dashboard/limits'} target="_blank" rel="noopener noreferrer" title="Consultar las cuotas de tu cuenta">Ver cuota en {estado.data?.proveedor ?? 'Groq'} <ArrowUpRight size={11} /></a></div>
            {estado.isPending ? <p role="status" className="ti-chat-notice">Comprobando configuración…</p> : estado.isError ? <p role="alert" className="ti-chat-notice">No se pudo comprobar el asistente. <button onClick={() => void estado.refetch()}>Reintentar</button></p> : !estado.data?.configurado ? <p role="status" className="ti-chat-notice">Falta configurar la clave de {estado.data?.proveedor ?? 'Groq'} en el servidor. Consulta la guía de configuración.</p> : null}
            {limite !== undefined ? <p className="ti-chat-footnote">{consumo.consultas}/{limite} consultas en esta conversación{agotado ? ' · Límite alcanzado. Inicia una nueva conversación.' : ''}</p> : null}
            {error ? <p role="alert" className="ti-chat-notice">{error}</p> : null}
            <form onSubmit={e => { e.preventDefault(); void enviar(pregunta) }} className="ti-chat-composer">
              <label htmlFor="consulta-chatbot-ti" className="sr-only">Tu consulta al asistente TI</label>
              <textarea id="consulta-chatbot-ti" value={pregunta} onChange={e => setPregunta(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void enviar(pregunta) } }} maxLength={1500} rows={2} placeholder="Pregunta, explora, encuentra una respuesta…" disabled={enviando || cargandoChat || agotado || !estado.data?.configurado} />
              <div className="ti-chat-composer-actions"><span>{pregunta.length ? `${pregunta.length}/1500` : 'Enter para enviar · Shift + Enter para otra línea'}</span><button type="submit" aria-label="Enviar" title="Enviar" disabled={enviando || cargandoChat || agotado || pregunta.trim().length < 2 || !estado.data?.configurado}><Send size={18} /></button></div>
            </form>
            <p className="ti-chat-footnote"><ShieldCheck size={12} /> No compartas contraseñas. Verifica las recomendaciones.</p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </>
}

function RespuestaProgresiva({ texto, animar, alAvanzar, alTerminar }: { texto: string; animar: boolean; alAvanzar: () => void; alTerminar: () => void }) {
  const [longitud, setLongitud] = useState(animar ? 0 : texto.length)
  useEffect(() => {
    if (!animar || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setLongitud(texto.length); return }
    let posicion = 0
    setLongitud(0)
    const paso = Math.max(2, Math.ceil(texto.length / 180))
    const reloj = window.setInterval(() => {
      posicion = Math.min(texto.length, posicion + paso)
      setLongitud(posicion)
      if (posicion === texto.length) window.clearInterval(reloj)
    }, 24)
    return () => window.clearInterval(reloj)
  }, [texto, animar])
  useEffect(() => { if (animar) alAvanzar() }, [longitud, animar, alAvanzar])
  useEffect(() => { if (animar && longitud >= texto.length) alTerminar() }, [animar, longitud, texto.length, alTerminar])
  const escribiendo = animar && longitud < texto.length
  return <div className="ti-answer-progressive" aria-busy={escribiendo}><RespuestaFormateada texto={animar ? texto.slice(0, longitud) : texto} />{escribiendo ? <span className="ti-writing-cursor" aria-hidden="true">▍</span> : null}</div>
}

function RespuestaFormateada({ texto }: { texto: string }) {
  return <>{texto.split(/```/).map((bloque, i) => i % 2 ? <pre key={i}><code>{bloque.replace(/^[a-zA-Z0-9_-]+\n/, '').trim()}</code></pre> : bloque.split(/\n\s*\n/).filter(p => p.trim()).map((parrafo, j) => <p key={`${i}-${j}`}>{parrafo.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((parte, k) => parte.startsWith('**') && parte.endsWith('**') ? <strong key={k}>{parte.slice(2, -2)}</strong> : parte.startsWith('`') && parte.endsWith('`') ? <code key={k}>{parte.slice(1, -1)}</code> : parte)}</p>))}</>
}
