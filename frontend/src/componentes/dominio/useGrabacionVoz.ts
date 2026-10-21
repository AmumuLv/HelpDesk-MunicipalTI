import { useEffect, useRef, useState } from 'react'
import { useAvisos } from '../../estado/Avisos'

export function useGrabacionVoz(alGrabar: (archivo: File) => Promise<void>) {
  const avisos = useAvisos()
  const [grabando, setGrabando] = useState(false)
  const [segundos, setSegundos] = useState(0)
  const [nivel, setNivel] = useState(0)
  const [detectado, setDetectado] = useState(false)
  const [dispositivos, setDispositivos] = useState<MediaDeviceInfo[]>([])
  const [dispositivo, setDispositivo] = useState('')
  const [preparando, setPreparando] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const contexto = useRef<AudioContext | null>(null)
  const animacion = useRef(0)
  const vivo = useRef(true)
  const ocupado = useRef(false)
  const callback = useRef(alGrabar)
  callback.current = alGrabar
  const liberar = () => {
    cancelAnimationFrame(animacion.current)
    stream.current?.getTracks().forEach(pista => pista.stop()); stream.current = null
    void contexto.current?.close().catch(() => undefined); contexto.current = null
  }
  useEffect(() => {
    vivo.current = true
    return () => { vivo.current = false; if (recorder.current?.state === 'recording') recorder.current.stop(); liberar() }
  }, [])
  useEffect(() => {
    if (!grabando) return
    const reloj = setInterval(() => setSegundos(valor => valor + 1), 1000)
    const limite = setTimeout(() => recorder.current?.stop(), 120_000)
    return () => { clearInterval(reloj); clearTimeout(limite) }
  }, [grabando])
  const obtenerStream = () => navigator.mediaDevices.getUserMedia({ audio: { ...(dispositivo ? { deviceId: { exact: dispositivo } } : {}), channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false })
  const listar = async () => {
    const entradas = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audioinput')
    if (vivo.current) setDispositivos(entradas)
  }
  const elegirMicrofono = async () => {
    if (ocupado.current) return
    if (!navigator.mediaDevices?.getUserMedia) { avisos.error('El micrófono requiere HTTPS o localhost. Puedes adjuntar un audio.'); return }
    ocupado.current = true; setPreparando(true)
    try {
      const prueba = await obtenerStream()
      prueba.getTracks().forEach(pista => pista.stop())
      await listar()
    } catch { avisos.error('No se pudo acceder al micrófono. Revisa los permisos de audio del navegador y del sistema.') }
    finally { ocupado.current = false; if (vivo.current) setPreparando(false) }
  }
  const iniciar = async () => {
    if (ocupado.current) return
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') { avisos.error('La grabación requiere HTTPS o localhost y un navegador compatible. Puedes adjuntar un audio.'); return }
    ocupado.current = true; setPreparando(true)
    try {
      const audio = new AudioContext()
      contexto.current = audio
      await audio.resume()
      const captura = await obtenerStream()
      if (!vivo.current) { captura.getTracks().forEach(pista => pista.stop()); liberar(); return }
      stream.current = captura
      const pista = captura.getAudioTracks()[0]
      if (!pista || !pista.enabled || pista.readyState !== 'live') throw new Error('Micrófono no disponible')
      await listar()
      const analizador = audio.createAnalyser()
      analizador.fftSize = 2048
      audio.createMediaStreamSource(captura).connect(analizador)
      const silencio = audio.createGain(); silencio.gain.value = 0
      analizador.connect(silencio); silencio.connect(audio.destination)
      const muestras = new Float32Array(analizador.fftSize)
      let pico = 0
      const medir = () => {
        if (!vivo.current || !stream.current) return
        analizador.getFloatTimeDomainData(muestras)
        const rms = Math.sqrt(muestras.reduce((suma, valor) => suma + valor * valor, 0) / muestras.length)
        pico = Math.max(pico, rms)
        if (pico >= 0.0003) setDetectado(true)
        setNivel(Math.min(100, Math.round(Math.sqrt(rms) * 250)))
        animacion.current = requestAnimationFrame(medir)
      }
      medir()
      const mime = ['audio/mp4;codecs=mp4a.40.2', 'audio/mp4', 'audio/webm;codecs=opus', 'audio/ogg;codecs=opus'].find(tipo => MediaRecorder.isTypeSupported(tipo))
      const grabador = new MediaRecorder(captura, { ...(mime ? { mimeType: mime } : {}), audioBitsPerSecond: 64000 })
      recorder.current = grabador
      const partes: Blob[] = []
      let fallo = false
      let bytes = 0
      grabador.ondataavailable = evento => {
        if (evento.data.size) { partes.push(evento.data); bytes += evento.data.size }
        if (bytes >= 5 * 1024 * 1024 && grabador.state === 'recording') grabador.stop()
        analizador.getFloatTimeDomainData(muestras)
        pico = Math.max(pico, Math.sqrt(muestras.reduce((suma, valor) => suma + valor * valor, 0) / muestras.length))
        if (pico >= 0.0003 && vivo.current) setDetectado(true)
      }
      grabador.onerror = () => { fallo = true; avisos.error('No se pudo completar la grabación'); liberar(); setGrabando(false); ocupado.current = false }
      grabador.onstop = () => {
        liberar(); ocupado.current = false
        if (!vivo.current) return
        setGrabando(false); setNivel(0)
        if (fallo) return
        if (bytes > 5 * 1024 * 1024) { avisos.error('El audio supera el límite de 5 MB. Graba una nota más corta.'); return }
        if (pico < 0.0003 || !partes.length) { avisos.error('No se detectó sonido. Elige otro micrófono o revisa que no esté silenciado.'); return }
        const tipo = grabador.mimeType || partes[0]?.type || 'audio/webm'
        const extension = tipo.includes('mp4') ? 'm4a' : tipo.includes('ogg') ? 'ogg' : 'webm'
        void callback.current(new File(partes, `nota-de-voz-${Date.now()}.${extension}`, { type: tipo }))
      }
      setSegundos(0); setDetectado(false); setGrabando(true); grabador.start(250)
    } catch (fallo) { liberar(); ocupado.current = false; if (vivo.current) avisos.error(fallo instanceof Error && fallo.name === 'NotAllowedError' ? 'Permite el micrófono en el navegador para grabar tu voz.' : 'No se pudo iniciar el micrófono seleccionado. Revisa el dispositivo y sus permisos.') }
    finally { if (vivo.current) setPreparando(false) }
  }
  return { grabando, segundos, nivel, detectado, dispositivos, dispositivo, setDispositivo, preparando, elegirMicrofono, iniciar, detener: () => { if (recorder.current?.state === 'recording') recorder.current.stop() } }
}
