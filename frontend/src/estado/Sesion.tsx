/**
 * Sesión: quién está dentro y qué puede hacer.
 *
 * El backend es la autoridad. Aquí solo se refleja lo que devuelve
 * `GET /auth/sesion`: el rol, la lista de permisos y la persona. Ninguna regla de
 * negocio se decide en el cliente, así que un permiso que el backend no otorga
 * no abre nada, y un enlace que el backend rechaza no se muestra.
 *
 * El token vive en `sessionStorage`: al cerrar la pestaña se pierde.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react'

import { api, ErrorPeticion, alExpirarSesion, fijarCsrf, guardarAcceso, limpiarAcceso } from '../api/cliente'
import { claves } from '../api/consultas'
import type { Rol, UsuarioSesion } from '../api/tipos'

/** Lo que devuelve `POST /auth/login`: token + la misma sesión. */
type RespuestaLogin = UsuarioSesion & {
  access_token: string
  token_type: string
  csrf_token: string | null
}

type ValorContexto = {
  usuario: UsuarioSesion | null
  permisos: string[]
  rol: Rol | null
  esAdmin: boolean
  esTecnico: boolean
  /** `true` si el rol lo permite por naturaleza o si se lo delegaron. */
  puede: (permiso: string) => boolean
  cargando: boolean
  entrar: (correo: string, password: string, acceso?: 'usuario' | 'ti') => Promise<UsuarioSesion>
  salir: () => Promise<void>
  nombreInstitucion: string
  zonaHoraria: string
}

const Contexto = createContext<ValorContexto | null>(null)

const CLAVE_INSTITUCION = 'ma.institucion'
const CLAVE_ACCESO_PREVIO = 'ma.acceso'

function leerInstitucion(): string {
  try {
    return sessionStorage.getItem(CLAVE_INSTITUCION) || 'Mesa de Ayuda TI'
  } catch {
    return 'Mesa de Ayuda TI'
  }
}

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const consulta = useQuery({
    queryKey: claves.sesion,
    queryFn: async () => {
      // Sin token no hay nada que preguntar: se responde null sin llamar a la API
      if (!sessionStorage.getItem(CLAVE_ACCESO_PREVIO)) return null
      let datos: UsuarioSesion
      try {
        datos = await api.obtener<UsuarioSesion>('/auth/sesion')
      } catch (fallo) {
        // Una cuenta desactivada devuelve 403 también al refrescar su sesión.
        // No conservar el usuario anterior en caché como si siguiera autorizado.
        if (fallo instanceof ErrorPeticion && fallo.esPermiso) {
          limpiarAcceso()
          return null
        }
        throw fallo
      }
      fijarCsrf(datos.csrf_token)
      sessionStorage.setItem(CLAVE_INSTITUCION, datos.institucion)
      return datos
    },
    // La sesión no caduca sola: se renueva sola desde el cliente HTTP
    staleTime: 60_000,
    retry: false,
  })

  const invalidar = useQueryClient()

  useEffect(() => {
    // Cuando el token expira y no se puede renovar, se limpia todo el estado
    alExpirarSesion(() => {
      limpiarAcceso()
      void invalidar.cancelQueries()
      invalidar.removeQueries({ predicate: (consulta) => consulta.queryKey[0] !== claves.sesion[0] })
      invalidar.setQueryData(claves.sesion, null)
    })
    return () => alExpirarSesion(null)
  }, [invalidar])

  const entrar = useCallback(
    async (correo: string, password: string, acceso?: 'usuario' | 'ti') => {
      const respuesta = await api.crear<RespuestaLogin>('/auth/login', { correo, password, ...(acceso ? { acceso } : {}) })
      await invalidar.cancelQueries()
      guardarAcceso(respuesta.access_token)
      fijarCsrf(respuesta.csrf_token)
      sessionStorage.setItem(CLAVE_INSTITUCION, respuesta.institucion)
      // Conserva la consulta observada de sesión al limpiar los datos de otra persona.
      invalidar.removeQueries({ predicate: (consulta) => consulta.queryKey[0] !== claves.sesion[0] })
      invalidar.setQueryData(claves.sesion, respuesta)
      return respuesta
    },
    [invalidar],
  )

  const salir = useCallback(async () => {
    try {
      await api.crear('/auth/logout', {})
    } catch {
      // Si la sesión ya estaba cerrada, se limpia igual
    }
    await invalidar.cancelQueries()
    limpiarAcceso()
    invalidar.setQueryData(claves.sesion, null)
    invalidar.removeQueries({ predicate: (consulta) => consulta.queryKey[0] !== claves.sesion[0] })
  }, [invalidar])

  const usuario = consulta.data ?? null

  const valor = useMemo<ValorContexto>(() => {
    const rol = normalizarRol(usuario?.rol)
    const permisos = usuario?.permisos ?? []
    // El backend marca al administrador con el comodín «*» en su lista de
    // permisos, además de su rol. Se aceptan las dos señales para que el panel
    // completo no desaparezca si el rol llega escrito de otra forma.
    const esAdmin = rol === 'administrador' || permisos.includes('*')
    return {
      usuario,
      permisos,
      rol,
      esAdmin,
      // El administrador entra también al panel: ve todo lo que ve un técnico
      esTecnico: esAdmin || rol === 'tecnico',
      puede: (permiso: string) => esAdmin || permisos.includes(permiso),
      cargando: consulta.isLoading,
      entrar,
      salir,
      nombreInstitucion: usuario?.institucion ?? leerInstitucion(),
      zonaHoraria: 'America/Lima',
    }
  }, [usuario, consulta.isLoading, entrar, salir])

  useEffect(() => {
    if (valor.rol) {
      document.documentElement.dataset.rol = valor.rol
    } else {
      delete document.documentElement.dataset.rol
    }
  }, [valor.rol])

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useSesion(): ValorContexto {
  const valor = useContext(Contexto)
  if (!valor) throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  return valor
}

/**
 * Normaliza el rol que llega en `GET /auth/sesion`.
 *
 * El backend guarda el rol en minúsculas, pero la interfaz no debe depender de
 * eso: si llegara «Administrador», «ADMIN» o con espacios, la cuenta seguiría
 * siendo la misma y el panel tiene que comportarse igual. Sin esto, una
 * diferencia de mayúsculas dejaba al administrador sin ver los botones de
 * gestión —como «Nuevo usuario»— aunque el backend sí lo autorizara.
 */
function normalizarRol(valor: unknown): Rol | null {
  const texto = String(valor ?? '')
    .trim()
    .toLowerCase()
  if (texto === 'administrador' || texto === 'admin') return 'administrador'
  if (texto === 'tecnico' || texto === 'técnico') return 'tecnico'
  if (texto === 'usuario') return 'usuario'
  return null
}

/** `true` cuando la consulta de sesión terminó con un error de permisos o red. */
export function useErrorSesion(): ErrorPeticion | null {
  const consulta = useQuery({
    queryKey: ['error-sesion'],
    queryFn: async () => {
      if (!sessionStorage.getItem(CLAVE_ACCESO_PREVIO)) return null
      try {
        await api.obtener('/auth/sesion')
        return null
      } catch (fallo) {
        return fallo instanceof ErrorPeticion && !fallo.esSesion ? fallo : null
      }
    },
    enabled: false,
    retry: false,
  })
  return consulta.data ?? null
}
