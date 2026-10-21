import type { HorarioSemanal } from '../api/tipos'

export const DIAS_TI = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
export function horarioBaseTI(): NonNullable<HorarioSemanal['dias']> {
  return Object.fromEntries(DIAS_TI.map((_, dia) => [dia, { libre: dia >= 5,
    tramos: dia < 5 ? [{ entrada: '08:00', salida: '13:00' }, { entrada: '14:00', salida: '17:00' }] : [],
  }]))
}
