import { createContext, useContext } from 'react'

export type ValorContexto = {
  exito: (texto: string, detalle?: string) => void
  error: (texto: string, detalle?: string) => void
  aviso: (texto: string, detalle?: string) => void
  info: (texto: string, detalle?: string) => void
  /** Traduce el error de la API a un aviso legible, sin perder el detalle. */
  desdeError: (fallo: unknown, contexto?: string) => void
}

export const Contexto = createContext<ValorContexto | null>(null)

export function useAvisos(): ValorContexto {
  const valor = useContext(Contexto)
  if (!valor) throw new Error('useAvisos debe usarse dentro de ProveedorAvisos')
  return valor
}
