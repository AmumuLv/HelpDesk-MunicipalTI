/**
 * Pantallas de formulario: contenedor centrado y nada recortado a la derecha.
 *
 * Se recorren los tres anchos que rompen cosas distintas (390, 820 y 1440 px) y,
 * en cada pantalla, se comprueba:
 * 1. que la página no se desborde horizontalmente,
 * 2. que exista el contenedor de formulario (`data-pantalla="formulario"`),
 *    centrado en su columna y de 1100 px como máximo,
 * 3. que el encabezado de página envuelva sus acciones (flex-wrap) en vez de
 *    empujarlas fuera de la ventana.
 *
 * Además deja una captura por pantalla y tamaño en `docs/capturas/`.
 */

import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'

import { TAMANOS, entrar, sinDesbordamiento, type ClaveRol } from './utilidades'

const CAPTURAS = process.env.PRUEBA_CAPTURAS ?? path.resolve(process.cwd(), '..', 'docs', 'capturas')

type Pantalla = { rol: ClaveRol; ruta: string; nombre: string }

/** Pantallas cuyo contenido principal es un formulario. */
const PANTALLAS: Pantalla[] = [
  { rol: 'administrador', ruta: '/panel/tickets/nuevo', nombre: 'panel-registrar-ticket' },
  { rol: 'administrador', ruta: '/panel/inventario-anual', nombre: 'panel-inventario-anual' },
  { rol: 'administrador', ruta: '/panel/equipos/importar', nombre: 'panel-importar-inventario' },
  { rol: 'administrador', ruta: '/panel/organizacion', nombre: 'panel-organizacion' },
  { rol: 'administrador', ruta: '/panel/configuracion', nombre: 'panel-configuracion' },
  { rol: 'usuario', ruta: '/reportar', nombre: 'portal-reportar' },
  { rol: 'usuario', ruta: '/perfil', nombre: 'portal-perfil' },
]

const MAXIMO_FORMULARIO = 1100

/** El contenedor existe, está centrado en su columna y no pasa del ancho máximo. */
async function contenedorDeFormulario(pagina: Page, donde: string): Promise<void> {
  const caja = await pagina.locator('[data-pantalla="formulario"]').first().evaluate((elemento) => {
    const propio = elemento.getBoundingClientRect()
    const padre = elemento.parentElement?.getBoundingClientRect()
    return {
      ancho: propio.width,
      izquierda: padre ? propio.left - padre.left : propio.left,
      derecha: padre ? padre.right - propio.right : window.innerWidth - propio.right,
    }
  })

  expect(caja.ancho, `${donde}: el contenedor no puede pasar de ${MAXIMO_FORMULARIO} px`).toBeLessThanOrEqual(
    MAXIMO_FORMULARIO + 1,
  )
  expect(caja.ancho, `${donde}: el contenedor tiene que ocupar el ancho disponible`).toBeGreaterThan(280)
  expect(
    Math.abs(caja.izquierda - caja.derecha),
    `${donde}: el contenedor no está centrado (izquierda ${Math.round(caja.izquierda)} px, derecha ${Math.round(caja.derecha)} px)`,
  ).toBeLessThanOrEqual(2)
}

/** El encabezado de página envuelve sus acciones. */
async function encabezadoEnvuelve(pagina: Page, donde: string): Promise<void> {
  const acciones = pagina.locator('[data-acciones="pagina"]')
  if ((await acciones.count()) === 0) return
  const envoltura = await acciones
    .first()
    .evaluate((elemento) => getComputedStyle(elemento).flexWrap)
  expect(envoltura, `${donde}: las acciones del encabezado tienen que envolver`).toBe('wrap')
}

/** Nada de lo que se ve puede quedar cortado por el borde derecho. */
async function nadaRecortado(pagina: Page, donde: string): Promise<void> {
  const ancho = pagina.viewportSize()?.width ?? 0
  const recortados = await pagina.evaluate((limite) => {
    const culpables: string[] = []
    // Lo que vive dentro de una franja con desplazamiento propio (pestañas,
    // tablas anchas) se alcanza desplazando: no está recortado.
    const dentroDeFranja = (elemento: HTMLElement): boolean => {
      let actual = elemento.parentElement
      while (actual && actual !== document.body) {
        const estilos = getComputedStyle(actual)
        if (estilos.overflowX === 'auto' || estilos.overflowX === 'scroll') return true
        actual = actual.parentElement
      }
      return false
    }

    for (const elemento of document.querySelectorAll<HTMLElement>('body *')) {
      const caja = elemento.getBoundingClientRect()
      if (caja.width === 0 || caja.height === 0) continue
      const estilos = getComputedStyle(elemento)
      if (estilos.overflowX === 'auto' || estilos.overflowX === 'scroll') continue
      if (caja.right <= 0) continue
      // Un texto puede desbordar su caja por elipsis: eso no es un recorte visible
      if (estilos.textOverflow === 'ellipsis') continue
      if (caja.right > limite + 1 && !dentroDeFranja(elemento)) {
        culpables.push(
          `${elemento.tagName.toLowerCase()}.${String(elemento.className).split(' ').slice(0, 2).join('.')} → ${Math.round(caja.right)} px`,
        )
      }
      if (culpables.length >= 5) break
    }
    return culpables
  }, ancho)
  expect(recortados, `${donde}: elementos recortados a la derecha → ${recortados.join(' | ')}`).toEqual([])
}

for (const tamano of TAMANOS) {
  for (const rol of ['administrador', 'usuario'] as ClaveRol[]) {
    const pantallas = PANTALLAS.filter((pantalla) => pantalla.rol === rol)
    if (pantallas.length === 0) continue

    test.describe(`${rol} en ${tamano.nombre}`, () => {
      test.use({ viewport: { width: tamano.ancho, height: tamano.alto } })

      test('los formularios no se recortan', async ({ page }, info) => {
        await entrar(page, rol)

        for (const pantalla of pantallas) {
          const donde = `${pantalla.nombre} (${tamano.nombre})`
          await page.goto(pantalla.ruta)
          await page.waitForLoadState('domcontentloaded')
          await page.waitForTimeout(1200)

          await sinDesbordamiento(page, donde)
          await nadaRecortado(page, donde)
          await contenedorDeFormulario(page, donde)
          await encabezadoEnvuelve(page, donde)

          await page.screenshot({
            path: path.join(CAPTURAS, `${pantalla.nombre}-${tamano.clave}.png`),
            fullPage: false,
          })
        }

        // La captura de la última pantalla queda adjunta a la prueba
        await info.attach('ultima-pantalla', {
          path: path.join(CAPTURAS, `${pantallas.at(-1)?.nombre}-${tamano.clave}.png`),
          contentType: 'image/png',
        })
      })
    })
  }
}
