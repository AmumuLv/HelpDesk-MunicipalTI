import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { leerAcceso, rutaApi } from './cliente'
import type { PreferenciaIaShape } from './hooks'
import type { UsuarioSesion } from './tipos'
import { olvidarFoto, olvidarFotos } from './fotos'
import { consultaAfectada } from './sincronizacion'

/** Eventos autorizados por la API; las consultas HTTP siguen siendo la fuente de datos. */
export function useTiempoReal(canal: 'notificaciones' | 'ticket', ticketId?: string, habilitado = true) {
  const cache = useQueryClient()
  useEffect(() => {
    if (!habilitado || (canal === 'ticket' && !ticketId)) return
    let activo = true
    let socket: WebSocket | null = null
    let reintento: number | undefined
    let refresco: number | undefined
    let intentos = 0
    let ultimaActividad = Date.now()
    let ultimoRefresco = 0
    const pendientes = new Set<string>()
    const actualizar = (dominios = ['tickets', 'notificaciones']) => {
      dominios.forEach(dominio => pendientes.add(dominio))
      if (!activo || refresco !== undefined) return
      refresco = window.setTimeout(() => {
        refresco = undefined
        if (!activo) return
        const afectados = new Set(pendientes)
        pendientes.clear()
        ultimoRefresco = Date.now()
        void cache.invalidateQueries({ predicate: consulta => consultaAfectada(consulta, afectados) })
      }, Math.max(100, 800 - (Date.now() - ultimoRefresco)))
    }
    const conectar = () => {
      if (!activo) return
      const token = leerAcceso()
      if (!token) return
      const ruta = canal === 'ticket' ? `/ws/ticket/${encodeURIComponent(ticketId!)}` : '/ws/notificaciones'
      const url = new URL(rutaApi(ruta), window.location.origin)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      url.searchParams.set('token', token)
      socket = new WebSocket(url)
      socket.onopen = () => { intentos = 0; ultimaActividad = Date.now(); actualizar(['*']) }
      socket.onmessage = mensaje => {
        ultimaActividad = Date.now()
        try {
          const evento = JSON.parse(mensaje.data)
          if (evento.tipo === 'latido') return
          if (evento.tipo === 'sincronizacion') {
            if (canal === 'notificaciones') olvidarFotos()
            actualizar(['*'])
            return
          }
          if (evento.tipo === 'datos_actualizados') {
            if (evento.fotos_todas) olvidarFotos()
            else if (Array.isArray(evento.fotos)) evento.fotos.filter((id: unknown) => typeof id === 'string').forEach((id: string) => olvidarFoto(id))
            actualizar(Array.isArray(evento.dominios) ? evento.dominios.filter((dominio: unknown) => typeof dominio === 'string') : ['*'])
            return
          }
          if (evento.tipo === 'ia_actualizada' || evento.tipo === 'ia_preferencia') {
            cache.setQueryData<PreferenciaIaShape>(['preferencia-ia'], anterior => {
              anterior ??= { recomendaciones_ia: cache.getQueryData<UsuarioSesion>(['sesion'])?.recomendaciones_ia ?? false, ia_global_activa: false, recomendaciones_globales: false, recomendaciones_personales: false, recomendaciones_visibles: false, aprendizaje_activo: false, proveedor_disponible: false, modelo: null }
              const global = evento.tipo === 'ia_actualizada' ? Boolean(evento.global_activa) : anterior.ia_global_activa
              const recomendaciones = evento.tipo === 'ia_actualizada' ? global && Boolean(evento.recomendaciones_activas) : anterior.recomendaciones_globales
              const personales = evento.tipo === 'ia_preferencia' ? Boolean(evento.recomendaciones_ia) : anterior.recomendaciones_ia
              return { ...anterior, ia_global_activa: global, recomendaciones_globales: recomendaciones, recomendaciones_ia: personales, recomendaciones_personales: personales, recomendaciones_visibles: global && recomendaciones && personales }
            })
            if (evento.tipo === 'ia_preferencia') cache.setQueryData<UsuarioSesion | null>(['sesion'], anterior => anterior ? { ...anterior, recomendaciones_ia: Boolean(evento.recomendaciones_ia) } : anterior)
            void cache.cancelQueries({ queryKey: ['sugerencia-reporte'] })
            void cache.invalidateQueries({ queryKey: ['preferencia-ia'] })
            void cache.invalidateQueries({ queryKey: ['sesion'] })
            void cache.invalidateQueries({ queryKey: ['sugerencia-reporte'], refetchType: 'none' })
          }
        } catch { /* Un evento desconocido no impide refrescar el reporte. */ }
        actualizar()
      }
      socket.onclose = evento => {
        if (activo && ![4400, 4403].includes(evento.code)) reintento = window.setTimeout(conectar, Math.min(30_000, 1000 * 2 ** intentos++))
      }
      socket.onerror = () => { /* El cierre reconecta; las consultas periódicas cubren una interrupción. */ }
    }
    // Evita abrir una conexión que StrictMode cierre antes de establecerse.
    reintento = window.setTimeout(conectar, 0)
    const alVolver = () => { if (document.visibilityState === 'visible') { if (socket?.readyState !== WebSocket.OPEN) olvidarFotos(); actualizar(['*']) } }
    const respaldo = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      if (socket?.readyState === WebSocket.OPEN && Date.now() - ultimaActividad > 60_000) socket.close()
      if (!socket || socket.readyState !== WebSocket.OPEN) actualizar(['*'])
    }, 15_000)
    document.addEventListener('visibilitychange', alVolver)
    return () => {
      activo = false
      window.clearTimeout(reintento)
      window.clearTimeout(refresco)
      window.clearInterval(respaldo)
      document.removeEventListener('visibilitychange', alVolver)
      socket?.close()
    }
  }, [cache, canal, ticketId, habilitado])
}
