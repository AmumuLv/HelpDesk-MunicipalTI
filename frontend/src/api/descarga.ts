import { api } from './cliente'

/**
 * Descarga un archivo de la API con la sesión iniciada.
 *
 * **Por qué no vale un `<a href>`**: la API autentica con la cabecera
 * `Authorization`, y un enlace normal no la manda. Al pulsar «Descargar» en una
 * lista de exportaciones, el navegador pedía `/api/exportaciones/…/descargar` sin
 * nada y recibía un `401`: el enlace parecía funcionar —se abría la descarga— pero
 * no bajaba ningún archivo. Es un fallo silencioso, de los que hacen dudar de si
 * el botón está mal o el servidor.
 *
 * Con `fetch` se manda el token, y el archivo se entrega como un `Blob` que se
 * guarda con un enlace temporal.
 *
 * @param ruta      Ruta de la API, con o sin el prefijo `/api`.
 * @param nombre    Nombre con el que se guardará el archivo.
 */
export async function descargarDeLaApi(ruta: string, nombre: string): Promise<void> {
  const contenido = await api.archivo(ruta)
  const url = URL.createObjectURL(contenido)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  enlace.rel = 'noopener'
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  // Se revoca pasado un momento: si se hace antes, el navegador todavía no ha
  // empezado a leer el archivo y la descarga sale vacía.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Quita lo que un nombre de archivo no admite en Windows. */
export function nombreDeArchivo(texto: string, porDefecto = 'descarga'): string {
  const limpio = texto.replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim()
  return limpio || porDefecto
}