import type { ValorContexto } from '../estado/useSesion'

type Cuenta = { id: string; rol: string; administrador_principal?: boolean }

export function puedeEditarCuenta(sesion: ValorContexto, cuenta: Cuenta): boolean {
  if (cuenta.id === sesion.usuario?.id) return true
  if (cuenta.administrador_principal) return false
  return sesion.esAdmin || sesion.rol === 'tecnico' && cuenta.rol === 'usuario' && sesion.puede('usuarios.editar')
}

export function puedeRestablecerCuenta(sesion: ValorContexto, cuenta: Cuenta): boolean {
  if (cuenta.administrador_principal) return false
  return sesion.esAdmin || sesion.rol === 'tecnico' && cuenta.rol === 'usuario' && sesion.puede('usuarios.editar')
}

export function puedeCambiarEstadoCuenta(sesion: ValorContexto, cuenta: Cuenta): boolean {
  return cuenta.id !== sesion.usuario?.id && !cuenta.administrador_principal && puedeEditarCuenta(sesion, cuenta)
}
