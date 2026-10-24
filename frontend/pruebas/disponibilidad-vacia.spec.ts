import { expect, test } from '@playwright/test'
import { entrar, vigilarConsola } from './utilidades'

test('la disponibilidad vacía no rompe el resumen ni el equipo TI', async ({ page }) => {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const errores = vigilarConsola(page)
  await page.route('**/api/equipo-ti/panel', async ruta => {
    const respuesta = await ruta.fetch()
    expect(respuesta.ok()).toBe(true)
    const datos = await respuesta.json()
    expect(datos.items.length).toBeGreaterThan(0)
    datos.items = datos.items.map((persona: Record<string, unknown>) => ({ ...persona, estado: null, etiqueta: null }))
    await ruta.fulfill({ response: respuesta, json: datos })
  })
  await entrar(page, 'tecnico')
  await expect(page.getByText('Sin dato', { exact: true }).first()).toBeVisible()
  await page.goto('/panel/equipo-ti')
  await expect(page.getByText('Sin dato', { exact: true }).first()).toBeVisible()
  expect(errores).toEqual([])
})
