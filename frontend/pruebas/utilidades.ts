/**
 * Utilidades de la verificación visual.
 *
 * Tres tamaños porque los tres rompen cosas distintas: el móvil por el
 * desbordamiento, la tableta por el shell a iconos, el escritorio por el
 * densidad de la tabla.
 */

import AxeBuilder from '@axe-core/playwright'
import { expect, type ConsoleMessage, type Page } from '@playwright/test'

export type Tamano = {
  clave: string
  nombre: string
  ancho: number
  alto: number
}

export const TAMANOS: Tamano[] = [
  { clave: 'movil', nombre: '390x844', ancho: 390, alto: 844 },
  { clave: 'tableta', nombre: '820x1180', ancho: 820, alto: 1180 },
  { clave: 'escritorio', nombre: '1440x900', ancho: 1440, alto: 900 },
]

/** Roles de la demo, con su correo y contraseña. */
export const ROLES = {
  administrador: { correo: 'admin@demo.local', password: 'Demo12345' },
  tecnico: { correo: 'jorge.castillo@municipalidad.gob.pe', password: 'Demo12345' },
  usuario: { correo: 'usuario1@demo.local', password: 'Demo12345' },
} as const

export type ClaveRol = keyof typeof ROLES

/** Ruta → nombre legible para los mensajes de validación. */
export const RUTAS_POR_ROL: Record<ClaveRol, { ruta: string; nombre: string }[]> = {
  administrador: [
    { ruta: '/panel', nombre: 'panel-resumen' },
    { ruta: '/panel/tickets', nombre: 'panel-bandeja' },
    { ruta: '/panel/tickets/nuevo', nombre: 'panel-registrar-ticket' },
    { ruta: '/panel/mis-asignaciones', nombre: 'panel-mis-asignaciones' },
    { ruta: '/panel/cerrados', nombre: 'panel-cerrados' },
    { ruta: '/panel/equipos', nombre: 'panel-equipos' },
    { ruta: '/panel/equipos/calidad', nombre: 'panel-calidad-inventario' },
    { ruta: '/panel/equipos/importar', nombre: 'panel-importar' },
    { ruta: '/panel/inventario-anual', nombre: 'panel-inventario-anual' },
    { ruta: '/panel/organizacion', nombre: 'panel-organizacion' },
    { ruta: '/panel/usuarios', nombre: 'panel-usuarios' },
    { ruta: '/panel/equipo-ti', nombre: 'panel-equipo-ti' },
    { ruta: '/panel/analisis', nombre: 'panel-analisis' },
    { ruta: '/panel/reportes', nombre: 'panel-reportes' },
    { ruta: '/panel/conocimiento', nombre: 'panel-conocimiento' },
    { ruta: '/panel/auditoria', nombre: 'panel-auditoria' },
    { ruta: '/panel/configuracion', nombre: 'panel-configuracion' },
    { ruta: '/dev/componentes', nombre: 'galeria-componentes' },
  ],
  tecnico: [
    { ruta: '/panel', nombre: 'tecnico-resumen' },
    { ruta: '/panel/tickets', nombre: 'tecnico-bandeja' },
    { ruta: '/panel/mis-asignaciones', nombre: 'tecnico-mis-asignaciones' },
    { ruta: '/panel/equipos', nombre: 'tecnico-equipos' },
  ],
  usuario: [
    { ruta: '/', nombre: 'portal-inicio' },
    { ruta: '/reportar', nombre: 'portal-reportar' },
    { ruta: '/mis-tickets', nombre: 'portal-mis-tickets' },
    { ruta: '/mis-equipos', nombre: 'portal-mis-equipos' },
    { ruta: '/ayuda', nombre: 'portal-ayuda' },
    { ruta: '/perfil', nombre: 'portal-perfil' },
  ],
}

/** Errores de consola que no son culpa de la aplicación. */
const IGNORAR_CONSOLA = [
  /favicon/i,
  /Download the React DevTools/i,
  /React Router Future Flag/i,
]

export function vigilarConsola(pagina: Page): string[] {
  const errores: string[] = []
  pagina.on('console', (mensaje: ConsoleMessage) => {
    if (mensaje.type() !== 'error') return
    // React usa %s: con text() no se ve el valor, así que se arma a mano
    const argumentos = mensaje.args().map((argumento) => String(argumento.jsonValue()))
    const texto = argumentos.length
      ? argumentos.reduce((texto, parte) => texto.replace('%s', parte), mensaje.text())
      : mensaje.text()
    if (IGNORAR_CONSOLA.some((patron) => patron.test(texto))) return
    errores.push(texto)
  })
  pagina.on('pageerror', (fallo) => {
    const texto = String(fallo)
    if (IGNORAR_CONSOLA.some((patron) => patron.test(texto))) return
    errores.push(texto)
  })
  return errores
}

export async function entrar(pagina: Page, rol: ClaveRol): Promise<void> {
  const { correo, password } = ROLES[rol]
  pagina.setDefaultNavigationTimeout(60_000)
  await pagina.goto('/acceder', { waitUntil: 'domcontentloaded' })
  await pagina.getByLabel('Correo institucional').fill(correo)
  await pagina.getByLabel('Contraseña', { exact: true }).fill(password)
  await pagina.getByRole('button', { name: 'Entrar' }).click()
  await pagina.waitForURL((url) => !url.pathname.includes('/acceder'), { timeout: 30_000 })
  // El portal mantiene consultas en vivo; esperar a que toda la red esté ociosa
  // no representa que el formulario o la sesión estén listos.
  await expect(pagina.locator('main')).toBeVisible()
}

/** Comprueba que nada se sale del ancho de la ventana. */
export async function sinDesbordamiento(pagina: Page, donde: string): Promise<void> {
  const desborde = await pagina.evaluate(() => {
    const ancho = document.documentElement.clientWidth
    const culpables: string[] = []
    for (const elemento of document.querySelectorAll<HTMLElement>('body *')) {
      const caja = elemento.getBoundingClientRect()
      if (caja.width === 0 || caja.height === 0) continue
      // Se ignoran los contenedores con scroll horizontal propio
      const estilos = getComputedStyle(elemento)
      if (estilos.overflowX === 'auto' || estilos.overflowX === 'scroll') continue
      // Un cajón cerrado queda fuera de pantalla a la izquierda: eso no es un
      // desbordamiento. Solo cuenta lo que se sale por la derecha.
      if (caja.right <= 0) continue
      if (caja.right > ancho + 1 || caja.left > ancho + 1) {
        culpables.push(
          `${elemento.tagName.toLowerCase()}.${String(elemento.className).split(' ').slice(0, 3).join('.')} (${Math.round(caja.left)}→${Math.round(caja.right)} de ${ancho})`,
        )
      }
      if (culpables.length >= 5) break
    }
    return { desborde: document.documentElement.scrollWidth > ancho + 1, culpables }
  })

  expect(desborde.desborde, `${donde}: la página se desborda horizontalmente → ${desborde.culpables.join(' | ')}`).toBe(
    false,
  )
}

/**
 * El foco tiene que verse: anillo de 2 px en el elemento activo.
 *
 * Se enfoca cada control con teclado y se comprueba su anillo. No se simula
 * Tab porque el recorrido automático depende del navegador; lo que importa es
 * que cualquier control al que se llegue con el teclado muestre dónde está.
 */
export async function focoVisible(pagina: Page, donde: string): Promise<void> {
  const controles = pagina.locator(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )
  const total = await controles.count()
  const sinAnillo: string[] = []

  for (let indice = 0; indice < Math.min(total, 12); indice += 1) {
    const control = controles.nth(indice)
    if (!(await control.isVisible().catch(() => false))) continue
    await control.focus().catch(() => undefined)
    await pagina.waitForTimeout(40)
    // La pantalla puede redibujarse entre pasos: si el control ya no está, se sigue
    const estado = await control
      .evaluate((elemento) => {
        const estilos = getComputedStyle(elemento)
        const ancho = Number.parseFloat(estilos.outlineWidth || '0')
        return {
          texto: (elemento.textContent ?? elemento.getAttribute('aria-label') ?? elemento.tagName).trim().slice(0, 30),
          ok: (ancho >= 1.5 && estilos.outlineStyle !== 'none') || estilos.boxShadow !== 'none',
        }
      })
      .catch(() => null)
    if (!estado) continue
    if (!estado.ok) sinAnillo.push(estado.texto || 'sin nombre')
  }

  expect(sinAnillo.length, `${donde}: estos controles no muestran anillo de foco → ${sinAnillo.join(', ')}`).toBe(0)
  expect(total, `${donde}: la pantalla no tiene ningún control interactivo`).toBeGreaterThan(0)
}

/** axe-core: solo interesa lo grave, que es lo que hay que arreglar ya. */
export async function sinViolacionesGraves(pagina: Page, donde: string): Promise<void> {
  let resultado
  try {
    resultado = await new AxeBuilder({ page: pagina })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
  } catch (fallo) {
    // Los SVG de los gráficos a veces cortan el recorrido de axe. No es una
    // violación de accesibilidad, pero hay que enterarse en vez de seguir.
    throw new Error(`${donde}: axe-core no pudo analizar la pantalla → ${String(fallo)}`)
  }
  const graves = resultado.violations.filter((violacion) =>
    ['serious', 'critical'].includes(violacion.impact ?? ''),
  )
  const resumen = graves
    .map((violacion) => `${violacion.id}: ${violacion.nodes.length} nodo(s) — ${violacion.help}`)
    .join(' | ')
  expect(graves.length, `${donde}: axe-core encontró ${graves.length} violaciones graves → ${resumen}`).toBe(0)
}

/** Ejecuta todas las comprobaciones de una pantalla sin guardar archivos. */
export async function revisar(pagina: Page, opciones: { rol: ClaveRol; nombre: string; tamano: Tamano }): Promise<void> {
  const { nombre, tamano } = opciones
  const donde = `${nombre} (${tamano.nombre})`

  // No se espera `networkidle`: el panel mantiene un websocket de tiempo real
  // abierto, así que la red nunca queda quieta. Se espera a que el contenido
  // principal esté y luego se da un respiro para los gráficos.
  await pagina.waitForLoadState('domcontentloaded')
  await pagina.waitForTimeout(900)

  await sinDesbordamiento(pagina, donde)
  await focoVisible(pagina, donde)
  await sinViolacionesGraves(pagina, donde)
}
