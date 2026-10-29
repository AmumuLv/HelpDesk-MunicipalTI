import { createContext, useContext } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, ErrorPeticion } from '../api/cliente'
import type { Rol, UsuarioSesion } from '../api/tipos'

export type ValorContexto = {
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

export const Contexto = createContext<ValorContexto | null>(null)

export function useSesion(): ValorContexto {
  const valor = useContext(Contexto)
  if (!valor) throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  return valor
}

/** `true` cuando la consulta de sesión terminó con un error de permisos o red. */
export function useErrorSesion(): ErrorPeticion | null {
  const consulta = useQuery({
    queryKey: ['error-sesion'],
    queryFn: async () => {
      if (!sessionStorage.getItem('ma.acceso')) return null
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
