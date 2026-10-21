/**
 * Fotos de perfil.
 *
 * La foto no se pide como `<img src="/api/...">`: esa ruta lleva la cabecera de
 * autorización, y un `src` no puede mandar cabeceras. Se pide como blob —igual que
 * las descargas— y se pinta con una URL temporal.
 *
 * El caché está **en el módulo**, no en el componente, a propósito: la misma persona
 * aparece en el avatar del diálogo, en la fila de la tabla y en el perfil completo, y
 * sin esto se descargaría la imagen una vez por cada sitio. El precio de un caché así
 * es que hay que olvidarlo a mano, y por eso existe `olvidarFoto`.
 */

import { useEffect, useState, useSyncExternalStore } from 'react'

import { api } from './cliente'

const direcciones = new Map<string, string>()
const enCurso = new Map<string, Promise<string | null>>()
const versiones = new Map<string, number>()
const escuchas = new Set<() => void>()
const suscribir = (escucha: () => void) => { escuchas.add(escucha); return () => { escuchas.delete(escucha) } }

/** Recupera las fotos actuales al reconectar tras perder avisos. */
export function olvidarFotos(): void {
  const ids = new Set([...direcciones.keys(), ...enCurso.keys(), ...versiones.keys()])
  direcciones.forEach(url => URL.revokeObjectURL(url))
  direcciones.clear()
  enCurso.clear()
  ids.forEach(id => versiones.set(id, (versiones.get(id) ?? 0) + 1))
  escuchas.forEach(escucha => escucha())
}

/** Borra la foto de una persona para que la siguiente lectura la vuelva a pedir. */
export function olvidarFoto(usuarioId: string | undefined | null): void {
  if (!usuarioId) return
  const anterior = direcciones.get(usuarioId)
  if (anterior) {
    URL.revokeObjectURL(anterior)
    direcciones.delete(usuarioId)
  }
  enCurso.delete(usuarioId)
  versiones.set(usuarioId, (versiones.get(usuarioId) ?? 0) + 1)
  escuchas.forEach((escucha) => escucha())
}

async function descargar(usuarioId: string): Promise<string | null> {
  const pendiente = enCurso.get(usuarioId)
  if (pendiente) return pendiente
  const version = versiones.get(usuarioId) ?? 0
  const promesa = api
    .archivo(`/usuarios/${usuarioId}/foto`, { cache: 'no-store' })
    .then((contenido) => {
      if ((versiones.get(usuarioId) ?? 0) !== version) return null
      const url = URL.createObjectURL(contenido)
      direcciones.set(usuarioId, url)
      return url
    })
    .catch(() => {
      // 404 es el caso normal: la cuenta no tiene foto. No es un error que interese
      // mostrar en ninguna parte, así que aquí se traga y el avatar sigue con las
      // iniciales.
      if ((versiones.get(usuarioId) ?? 0) === version) direcciones.delete(usuarioId)
      return null
    })
    .finally(() => {
      if (enCurso.get(usuarioId) === promesa) enCurso.delete(usuarioId)
    })
  enCurso.set(usuarioId, promesa)
  return promesa
}

/**
 * URL de la foto de una persona, o `null` mientras llega o si no tiene.
 *
 * `tiene` viene del propio perfil (`tiene_foto`), así que no se pide una imagen
 * para las 267 cuentas de la municipalidad: solo para las que la tienen puesta.
 */
export function useFotoUsuario(usuarioId: string | undefined | null, tiene: boolean | undefined): string | null {
  const version = useSyncExternalStore(suscribir, () => usuarioId ? versiones.get(usuarioId) ?? 0 : 0)
  const [url, setUrl] = useState<string | null>(() => (usuarioId ? (direcciones.get(usuarioId) ?? null) : null))

  useEffect(() => {
    let vigente = true
    if (!usuarioId || !tiene) {
      setUrl(usuarioId ? (direcciones.get(usuarioId) ?? null) : null)
      return () => {
        vigente = false
      }
    }
    void descargar(usuarioId).then((resultado) => {
      if (vigente) setUrl(resultado)
    })
    return () => {
      vigente = false
    }
  }, [usuarioId, tiene, version])

  return url
}

/** Sube una foto. Mismo camino que los adjuntos, con su comprobación de contenido. */
export async function subirFoto(usuarioId: string, archivo: File): Promise<{ foto: boolean; mime: string }> {
  const datos = new FormData()
  datos.append('archivo', archivo)
  const resultado = await api.subir<{ foto: boolean; mime: string }>(`/usuarios/${usuarioId}/foto`, datos)
  olvidarFoto(usuarioId)
  return resultado
}

/** Quita la foto y limpia el caché para que el avatar vuelva a las iniciales. */
export async function quitarFoto(usuarioId: string): Promise<void> {
  await api.borrar(`/usuarios/${usuarioId}/foto`)
  olvidarFoto(usuarioId)
}

/** Lo que acepta el selector de archivos, dicho en el mismo sitio que el botón. */
export const TIPOS_FOTO = 'image/png,image/jpeg,image/webp,image/gif'
export const MAX_FOTO_MB = 15
