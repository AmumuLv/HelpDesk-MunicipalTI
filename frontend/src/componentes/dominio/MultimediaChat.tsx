import { ImagePlus, Mic, Paperclip, Send, SlidersHorizontal, Square, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { useAvisos } from '../../estado/Avisos'
import { Button } from '../base/Button'
import { useGrabacionVoz } from './useGrabacionVoz'

type Adjunto = { id: string; nombre: string; mime: string; url: string }

export function AdjuntosMensaje({ adjuntos }: { adjuntos?: unknown[] }) {
  return <>{adjuntos?.filter((id): id is string => typeof id === 'string').map(id => <ArchivoMensaje key={id} id={id} />)}</>
}

function ArchivoMensaje({ id }: { id: string }) {
  const archivo = useQuery({ queryKey: ['adjunto-chat', id], queryFn: () => api.archivo(`/adjuntos/${id}`), staleTime: Infinity, retry: false })
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!archivo.data) return
    const direccion = URL.createObjectURL(archivo.data)
    setUrl(direccion)
    return () => URL.revokeObjectURL(direccion)
  }, [archivo.data])
  if (archivo.isError) return <button type="button" className="mt-2 text-sm underline" onClick={() => void archivo.refetch()}>Reintentar cargar adjunto</button>
  if (!url || !archivo.data) return <p className="mt-2 text-xs text-muted-foreground">Cargando adjunto…</p>
  return <div className="mt-2 min-w-0">
    {archivo.data.type.startsWith('image/') ? <a href={url} target="_blank" rel="noreferrer" aria-label="Abrir foto adjunta"><img src={url} alt="Foto adjunta al mensaje" className="max-h-64 max-w-full rounded-lg border border-border object-contain" /></a> : archivo.data.type.startsWith('audio/') ? <audio controls preload="metadata" src={url} aria-label="Audio adjunto" className="h-10 w-64 max-w-full" /> : <a href={url} download="adjunto" className="inline-flex items-center gap-2 text-sm font-semibold underline"><Paperclip size={15} />Descargar adjunto</a>}
  </div>
}

export function CompositorMensaje({ valor, alCambiar, cargando, onEnviar, textoEnviar = 'Enviar' }: {
  valor: string; alCambiar: (valor: string) => void; cargando: boolean
  onEnviar: (adjuntos?: string[]) => Promise<boolean | void>; textoEnviar?: string
}) {
  const avisos = useAvisos()
  const [adjuntos, setAdjuntos] = useState<Adjunto[]>([])
  const [subiendo, setSubiendo] = useState(false)
  const entrada = useRef<HTMLInputElement>(null)
  const vivo = useRef(true)
  const urls = useRef(new Set<string>())
  const ocupado = useRef(false)
  const enviando = useRef(false)
  const bloqueado = cargando || subiendo

  useEffect(() => {
    vivo.current = true
    return () => {
      vivo.current = false
      urls.current.forEach(url => URL.revokeObjectURL(url))
    }
  }, [])

  const agregar = async (archivos: File[]) => {
    if (ocupado.current || !archivos.length) return
    if (adjuntos.length + archivos.length > 5) { avisos.error('Máximo 5 adjuntos por mensaje'); return }
    if (archivos.some(archivo => (archivo.type.startsWith('audio/') || /\.(webm|ogg|oga|wav|mp3|m4a)$/i.test(archivo.name)) && archivo.size > 5 * 1024 * 1024)) {
      avisos.error('Cada audio admite hasta 2 minutos y 5 MB'); return
    }
    if (archivos.some(archivo => archivo.size > 15 * 1024 * 1024 || !/\.(png|jpe?g|gif|webp|bmp|webm|ogg|oga|wav|mp3|m4a)$/i.test(archivo.name))) {
      avisos.error('Usa fotos o audios de hasta 15 MB por archivo'); return
    }
    ocupado.current = true; setSubiendo(true)
    try {
      for (const archivo of archivos) {
        const cuerpo = new FormData(); cuerpo.append('archivo', archivo)
        const resultado = await api.subir<Omit<Adjunto, 'url'>>('/adjuntos', cuerpo)
        if (!vivo.current) break
        const url = URL.createObjectURL(archivo); urls.current.add(url)
        setAdjuntos(anteriores => [...anteriores, { ...resultado, url }])
      }
    } catch (fallo) { if (vivo.current) avisos.desdeError(fallo) }
    finally { ocupado.current = false; if (vivo.current) setSubiendo(false) }
  }
  const voz = useGrabacionVoz(archivo => agregar([archivo]))
  const { grabando, segundos } = voz
  const grabar = () => {
    if (bloqueado || adjuntos.length >= 5) return
    void voz.iniciar()
  }

  const enviar = async () => {
    if (bloqueado || grabando || voz.preparando || enviando.current || (!valor.trim() && !adjuntos.length)) return
    enviando.current = true
    try {
      const exito = await onEnviar(adjuntos.map(adjunto => adjunto.id))
      if (exito === true) {
        adjuntos.forEach(adjunto => { URL.revokeObjectURL(adjunto.url); urls.current.delete(adjunto.url) })
        setAdjuntos([])
      }
    } finally { enviando.current = false }
  }
  return <div className="min-w-0">
    <label className="text-sm font-semibold">Escribe un mensaje
      <textarea value={valor} onChange={e => alCambiar(e.target.value)} rows={3} maxLength={8000} disabled={cargando} placeholder="Escribe o adjunta una foto o un audio…" onKeyDown={evento => { if (evento.key === 'Enter' && (evento.ctrlKey || evento.metaKey)) { evento.preventDefault(); void enviar() } }} className="mt-1.5 block w-full rounded-[var(--radius-control)] border border-input bg-surface p-2.5 focus-visible:outline-2 focus-visible:outline-ring" />
    </label>
    {adjuntos.length ? <ul aria-label="Adjuntos preparados" className="mt-2 flex flex-wrap gap-2">{adjuntos.map(adjunto => <li key={adjunto.id} className="flex min-w-0 max-w-full items-center gap-2 rounded-lg border border-border bg-surface-2 p-2">
      {adjunto.mime.startsWith('image/') ? <img src={adjunto.url} alt="Vista previa" className="size-10 rounded object-cover" /> : <audio controls src={adjunto.url} aria-label="Vista previa del audio" className="h-8 w-44 max-w-full" />}
      <span className="max-w-32 truncate text-xs" title={adjunto.nombre}>{adjunto.nombre}</span>
      <button type="button" aria-label={`Quitar ${adjunto.nombre}`} disabled={bloqueado} onClick={() => { URL.revokeObjectURL(adjunto.url); urls.current.delete(adjunto.url); setAdjuntos(anteriores => anteriores.filter(a => a.id !== adjunto.id)) }}><X size={15} /></button>
    </li>)}</ul> : null}
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <input ref={entrada} type="file" multiple accept="image/png,image/jpeg,image/gif,image/webp,image/bmp,audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4,.m4a,.oga" aria-label="Adjuntar fotos o audios" className="sr-only" onChange={e => { const archivos = [...(e.target.files ?? [])]; e.target.value = ''; void agregar(archivos) }} />
      <Button variante="secundario" aria-label="Adjuntar fotos o audios" title="Fotos y audios" disabled={bloqueado || grabando || adjuntos.length >= 5} onClick={() => entrada.current?.click()}><ImagePlus size={17} /></Button>
      <Button variante="secundario" aria-label={grabando ? 'Detener grabación' : 'Grabar audio'} title={grabando ? 'Detener' : 'Grabar audio · máximo 2 minutos y 5 MB'} disabled={bloqueado || voz.preparando} onClick={() => grabando ? voz.detener() : grabar()}>{grabando ? <Square size={16} className="text-destructive-strong" /> : <Mic size={17} />}</Button>
      <Button variante="secundario" aria-label="Elegir micrófono" title="Elegir micrófono" disabled={bloqueado || grabando || voz.preparando} onClick={() => void voz.elegirMicrofono()}><SlidersHorizontal size={16} /></Button>
      {voz.dispositivos.length ? <select aria-label="Micrófono" value={voz.dispositivo} disabled={grabando || voz.preparando} onChange={e => voz.setDispositivo(e.target.value)} className="max-w-44 rounded border border-input bg-surface px-2 py-1 text-xs"><option value="">Predeterminado</option>{voz.dispositivos.map((d, i) => <option key={d.deviceId} value={d.deviceId}>{d.label || `Micrófono ${i + 1}`}</option>)}</select> : null}
      {grabando ? <div className="flex min-w-0 items-center gap-2"><span role="status" className="text-xs text-destructive-strong">Grabando {Math.floor(segundos / 60)}:{String(segundos % 60).padStart(2, '0')}</span><meter aria-label="Nivel del micrófono" min={0} max={100} value={voz.nivel} className="h-3 w-20" />{segundos >= 3 && !voz.detectado ? <span className="text-2xs text-warning-strong">Sin señal del micrófono</span> : null}</div> : subiendo ? <span role="status" className="text-xs text-muted-foreground">Subiendo adjunto…</span> : voz.preparando ? <span role="status" className="text-xs text-muted-foreground">Preparando micrófono…</span> : null}
      <div className="ml-auto"><Button variante="primario" icono={<Send size={16} />} cargando={cargando} disabled={subiendo || grabando || voz.preparando || (!valor.trim() && !adjuntos.length)} onClick={() => void enviar()}>{textoEnviar}</Button></div>
    </div>
  </div>
}
