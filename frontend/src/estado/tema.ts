/**
 * Tema claro/oscuro del sistema.
 *
 * El tema vive en `data-tema` sobre `<html>` y se alterna entre `claro` y
 * `oscuro`. Ambos redefinen los mismos tokens, así que ningún componente conoce
 * el tema actual. La preferencia del usuario se guarda en `localStorage`; en la
 * primera visita se sigue la preferencia del sistema (`prefers-color-scheme`).
 */

const CLAVE_TEMA = 'ma.tema'

export type Tema = 'claro' | 'oscuro'

export function leerTemaGuardado(): Tema | null {
  try {
    const guardado = localStorage.getItem(CLAVE_TEMA)
    return guardado === 'claro' || guardado === 'oscuro' ? guardado : null
  } catch {
    return null
  }
}

export function preferenciaSistema(): Tema {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'
  } catch {
    return 'claro'
  }
}

/** Tema actual aplicado en el documento (nunca falla si no hay uno). */
export function temaActual(): Tema {
  return document.documentElement.dataset.tema === 'oscuro' ? 'oscuro' : 'claro'
}

export function aplicarTema(tema: Tema): void {
  document.documentElement.dataset.tema = tema
  // `color-scheme` solo entiende `light` y `dark`: escribir «claro» o «oscuro»
  // hace que el navegador descarte el valor y los controles nativos del sistema
  // (barras de desplazamiento, casillas, campos) queden con el aspecto errado.
  const meta = document.querySelector('meta[name="color-scheme"]')
  if (meta) meta.setAttribute('content', tema === 'oscuro' ? 'dark' : 'light')
  try {
    localStorage.setItem(CLAVE_TEMA, tema)
  } catch {
    // Sin almacenamiento local la elección solo dura esta pestaña
  }
}

export function alternarTema(): Tema {
  const siguiente: Tema = temaActual() === 'oscuro' ? 'claro' : 'oscuro'
  aplicarTema(siguiente)
  return siguiente
}
