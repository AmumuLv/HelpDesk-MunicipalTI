/**
 * Comprobaciones visuales sin guardar capturas, por rol y tamaño.
 *
 *   npx playwright test
 *
 * Cada prueba recorre una pantalla: mide si desborda, si el foco se ve y si
 * axe encuentra violaciones graves. No guarda capturas.
 */

import { expect, test } from '@playwright/test'

import {
  entrar,
  revisar,
  RUTAS_POR_ROL,
  TAMANOS,
  vigilarConsola,
  type ClaveRol,
} from './utilidades'

for (const rol of Object.keys(RUTAS_POR_ROL) as ClaveRol[]) {
  for (const tamano of TAMANOS) {
    test.describe(`${rol} · ${tamano.nombre}`, () => {
      test.use({ viewport: { width: tamano.ancho, height: tamano.alto } })

      test('recorre las pantallas', async ({ page }) => {
        const errores = vigilarConsola(page)
        await entrar(page, rol)

        for (const destino of RUTAS_POR_ROL[rol]) {
          await page.goto(destino.ruta)
          await revisar(page, { rol, nombre: destino.nombre, tamano })
        }

        expect(
          errores,
          `errores de consola durante la vuelta de ${rol} en ${tamano.nombre}:\n${errores.join('\n')}`,
        ).toEqual([])
      })
    })
  }
}