/**
 * Cliente HTTP: el único lugar de la interfaz que habla con la API.
 *
 * Hace tres cosas que no queremos repetir en cada pantalla:
 * 1. Añade el token de acceso y el de CSRF (doble envío).
 * 2. Renueva la sesión una sola vez si el token expiró, sin bucle.
 * 3. Convierte cualquier error en `ErrorPeticion` con el mensaje que el backend
 *    ya escribió en lenguaje claro.
 */

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

export class ErrorPeticion extends Error {
  readonly codigo: string
  readonly estado: number
  readonly detalles: unknown

  constructor(codigo: string, mensaje: string, estado: number, detalles?: unknown) {
    super(mensaje)
    this.name = 'ErrorPeticion'
    this.codigo = codigo
    this.estado = estado
    this.detalles = detalles
  }

  /** `true` cuando el problema es de sesión y hay que volver a entrar. */
  get esSesion(): boolean {
    return this.estado === 401
  }

  /** `true` cuando es falta de permisos: no tiene sentido reintentar. */
  get esPermiso(): boolean {
    return this.estado === 403
  }
}

export function erroresDeValidacion(fallo: unknown): Record<string, string> {
  if (!(fallo instanceof ErrorPeticion) || fallo.estado !== 422 || !Array.isArray(fallo.detalles)) return {}
  return fallo.detalles.reduce<Record<string, string>>((errores, detalle) => {
    if (!detalle || typeof detalle !== 'object') return errores
    const campo = 'campo' in detalle && typeof detalle.campo === 'string' ? detalle.campo : ''
    const mensaje = 'mensaje' in detalle && typeof detalle.mensaje === 'string' ? detalle.mensaje : ''
    if (campo && mensaje) errores[campo] = mensaje
    return errores
  }, {})
}

let csrf: string | null = null
let alExpirar: (() => void) | null = null
let renovando: Promise<boolean> | null = null

const CLAVE_ACCESO = 'ma.acceso'

export function fijarCsrf(token: string | null): void {
  csrf = token
}

export function leerCsrf(): string | null {
  return csrf
}

export function alExpirarSesion(escucha: (() => void) | null): void {
  alExpirar = escucha
}

export function guardarAcceso(token: string): void {
  sessionStorage.setItem(CLAVE_ACCESO, token)
}

export function leerAcceso(): string | null {
  return sessionStorage.getItem(CLAVE_ACCESO)
}

export function limpiarAcceso(): void {
  sessionStorage.removeItem(CLAVE_ACCESO)
  csrf = null
}

/** Une la base con una ruta de la API sin duplicar el prefijo. */
export function rutaApi(ruta: string): string {
  if (!ruta) return BASE
  if (/^https?:\/\//i.test(ruta)) return ruta
  return ruta.startsWith('/') ? `${BASE}${ruta}` : `${BASE}/${ruta}`
}

type Opciones = Omit<RequestInit, 'body'> & {
  cuerpo?: unknown
  formato?: 'json' | 'blob'
  /** `false` en GET y HEAD: no se manda cuerpo. */
  conCuerpo?: boolean
}

/** Renueva el token con la cookie de refresco. Nunca en paralelo. */
async function renovar(): Promise<boolean> {
  if (!renovando) {
    renovando = (async () => {
      try {
        const respuesta = await fetch(rutaApi('/auth/refresh'), {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        })
        if (!respuesta.ok) return false
        const datos = (await respuesta.json()) as { access_token?: string; csrf_token?: string }
        if (datos.access_token) guardarAcceso(datos.access_token)
        if (datos.csrf_token) csrf = datos.csrf_token
        return Boolean(datos.access_token)
      } catch {
        return false
      } finally {
        renovando = null
      }
    })()
  }
  return renovando
}

async function aErrorPeticion(respuesta: Response): Promise<ErrorPeticion> {
  let cuerpo: Record<string, unknown> = {}
  try {
    cuerpo = (await respuesta.json()) as Record<string, unknown>
  } catch {
    cuerpo = {}
  }

  const detalle = cuerpo.detail
  if (respuesta.status === 413 && !cuerpo.mensaje && !detalle) {
    return new ErrorPeticion('archivo_demasiado_grande', 'El archivo supera el límite permitido por el servidor. Usa uno más pequeño.', 413)
  }
  // FastAPI: {detail: {codigo, mensaje, detalles}}
  if (detalle && typeof detalle === 'object' && 'mensaje' in detalle) {
    const d = detalle as { codigo?: string; mensaje?: string; detalles?: unknown }
    return new ErrorPeticion(d.codigo ?? 'error', d.mensaje ?? 'Ocurrió un error inesperado.', respuesta.status, d.detalles)
  }
  if (respuesta.status === 422 && Array.isArray(cuerpo.detalles)) {
    return new ErrorPeticion(
      String(cuerpo.codigo ?? 'validacion'),
      String(cuerpo.mensaje ?? 'Revisa los campos indicados.'),
      respuesta.status,
      cuerpo.detalles,
    )
  }
  // Validación de pydantic: {detail: [{campo, mensaje}]}
  if (Array.isArray(detalle)) {
    const primero = detalle[0] as { msg?: string; loc?: unknown[] } | undefined
    const campo = Array.isArray(primero?.loc) ? String(primero.loc.at(-1) ?? '') : ''
    const mensaje = primero?.msg?.replace(/^Value error,\s*/, '') ?? 'Revisa los datos ingresados.'
    return new ErrorPeticion('validacion', campo ? `${campo.replace(/_/g, ' ')}: ${mensaje}` : mensaje, respuesta.status, detalle)
  }
  return new ErrorPeticion(
    'error',
    (cuerpo.mensaje as string) ?? (cuerpo.detail as string) ?? 'Ocurrió un error inesperado.',
    respuesta.status,
  )
}

export async function peticion<T>(ruta: string, opciones: Opciones = {}): Promise<T> {
  const { cuerpo, conCuerpo = true, formato = 'json', ...resto } = opciones
  const metodo = (resto.method ?? 'GET').toUpperCase()

  const cabeceras = new Headers(resto.headers)
  const token = leerAcceso()
  if (token) cabeceras.set('Authorization', `Bearer ${token}`)
  if (csrf && conCuerpo && !['GET', 'HEAD'].includes(metodo)) cabeceras.set('X-CSRF-Token', csrf)

  const argumentos: RequestInit = { ...resto, credentials: 'include', headers: cabeceras }
  if (conCuerpo && cuerpo !== undefined) {
    if (cuerpo instanceof FormData) {
      argumentos.body = cuerpo
    } else {
      cabeceras.set('Content-Type', 'application/json')
      argumentos.body = JSON.stringify(cuerpo)
    }
  }

  let respuesta: Response
  try {
    respuesta = await fetch(rutaApi(ruta), argumentos)
  } catch {
    throw new ErrorPeticion(
      'sin_conexion',
      'No hay conexión con el servidor. Revisa tu red e inténtalo otra vez.',
      0,
    )
  }

  // 401: se renueva una vez y se reintenta. Si no, se limpia la sesión.
  if (respuesta.status === 401 && !['/auth/login', '/auth/refresh', '/auth/logout'].includes(ruta)) {
    if (await renovar()) {
      cabeceras.set('Authorization', `Bearer ${leerAcceso() ?? ''}`)
      if (csrf && !['GET', 'HEAD'].includes(metodo)) cabeceras.set('X-CSRF-Token', csrf)
      respuesta = await fetch(rutaApi(ruta), argumentos)
    } else {
      limpiarAcceso()
      alExpirar?.()
    }
  }

  if (!respuesta.ok) throw await aErrorPeticion(respuesta)

  if (respuesta.status === 204) return undefined as T
  if (formato === 'blob') return (await respuesta.blob()) as T
  const tipo = respuesta.headers.get('content-type') ?? ''
  if (tipo.includes('application/json')) return (await respuesta.json()) as T
  return (await respuesta.text()) as unknown as T
}

export const api = {
  archivo: (ruta: string, opciones?: Opciones) => peticion<Blob>(ruta, { ...opciones, method: 'GET', conCuerpo: false, formato: 'blob' }),
  obtener: <T,>(ruta: string, opciones?: Opciones) =>
    peticion<T>(ruta, { ...opciones, method: 'GET', conCuerpo: false }),
  crear: <T,>(ruta: string, cuerpo?: unknown, opciones?: Opciones) =>
    peticion<T>(ruta, { ...opciones, method: 'POST', cuerpo }),
  editar: <T,>(ruta: string, cuerpo?: unknown, opciones?: Opciones) =>
    peticion<T>(ruta, { ...opciones, method: 'PATCH', cuerpo }),
  reemplazar: <T,>(ruta: string, cuerpo?: unknown, opciones?: Opciones) =>
    peticion<T>(ruta, { ...opciones, method: 'PUT', cuerpo }),
  borrar: <T,>(ruta: string, cuerpo?: unknown, opciones?: Opciones) =>
    peticion<T>(ruta, { ...opciones, method: 'DELETE', cuerpo }),
  subir: <T,>(ruta: string, datos: FormData, opciones?: Opciones) =>
    peticion<T>(ruta, { ...opciones, method: 'POST', cuerpo: datos }),
}

/** Query string omitting empty values. */
export function consulta(
  params: Record<string, string | number | boolean | readonly (string | number | boolean)[] | undefined | null>,
): string {
  const partes = Object.entries(params).flatMap(([clave, valor]) => {
    if (valor === undefined || valor === null || valor === '') return []
    const valores = Array.isArray(valor) ? valor : [valor]
    return valores.map((elemento) =>
      `${encodeURIComponent(clave)}=${encodeURIComponent(String(elemento))}`,
    )
  })
  return partes.length ? `?${partes.join('&')}` : ''
}

/** `true` si el error es de permisos: la pantalla muestra NoPermission. */
export function esPermiso(fallo: unknown): boolean {
  return fallo instanceof ErrorPeticion && fallo.esPermiso
}

/** `true` si el error es 404: la pantalla puede mostrar "no existe". */
export function esNoEncontrado(fallo: unknown): boolean {
  return fallo instanceof ErrorPeticion && fallo.estado === 404
}

/** `true` si no hay conexión o el servidor no responde. */
export function esSinConexion(fallo: unknown): boolean {
  return fallo instanceof ErrorPeticion && fallo.codigo === 'sin_conexion'
}
