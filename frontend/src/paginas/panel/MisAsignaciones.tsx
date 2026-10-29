/**
 * Mis asignaciones: los tickets que me tocó.
 *
 * Es la bandeja con un filtro fijo por técnico, que es la definición de la
 * vista. Reutiliza el mismo componente que la bandeja general, así el
 * comportamiento (orden, columnas, tarjetas en móvil) no se duplica.
 */

import { useEffect } from 'react'

import { useSesion } from '../../estado/useSesion'
import { Bandeja } from './Bandeja'

export function MisAsignaciones() {
  const sesion = useSesion()

  useEffect(() => {
    document.title = 'Mis asignaciones · Mesa de Ayuda TI'
  }, [])

  return (
    <Bandeja
      vistaInicial="mios"
      soloTecnico={sesion.usuario?.id}
      titulo="Mis asignaciones"
    />
  )
}