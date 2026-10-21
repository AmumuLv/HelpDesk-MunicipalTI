/**
 * Campañas de inventario anual: crear → verificar → cerrar.
 *
 * Lo que se vigila:
 * 1. Si el alcance elegido no tiene equipos, el motivo se lee EN PANTALLA
 *    («No hay equipos en ese alcance. Importa el inventario o elige otro
 *    alcance») y el formulario no se cierra.
 * 2. Con un alcance que sí tiene equipos, la campaña se crea, se verifica un
 *    equipo y se cierra, y el año queda en el histórico.
 *
 * Se ejecuta contra un despliegue de pruebas: crea una zona vacía y una campaña.
 */

import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'

import { entrar } from './utilidades'

const CAPTURAS = process.env.PRUEBA_CAPTURAS ?? path.resolve(process.cwd(), '..', 'docs', 'capturas')

const SIN_EQUIPOS = 'No hay equipos en ese alcance. Importa el inventario o elige otro alcance'
const ANIO = '2033'
const NOMBRE = `Prueba automatica campana ${Date.now()}`

async function crearZonaVacia(pagina: Page): Promise<string> {
  const nombre = `Prueba automatica zona sin equipos ${Date.now()}`
  const respuesta = await pagina.evaluate(async (nombreZona) => {
    const csrf = document.cookie
      .split('; ')
      .find((parte) => parte.startsWith('ma_csrf='))
      ?.split('=')[1]
    const r = await fetch('/api/zonas', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso'),
        'X-CSRF-Token': csrf ?? '',
      },
      body: JSON.stringify({ nombre: nombreZona }),
    })
    return { estado: r.status, cuerpo: await r.json() }
  }, nombre)
  expect(respuesta.estado, `no se pudo crear la zona de prueba: ${JSON.stringify(respuesta.cuerpo)}`).toBeLessThan(300)
  return nombre
}

test('la campaña avisa si el alcance no tiene equipos y el flujo completo funciona', async ({ page }) => {
  await entrar(page, 'administrador')
  const zonaVacia = await crearZonaVacia(page)

  await page.goto('/panel/inventario-anual')
  await expect(page.getByRole('heading', { name: 'Inventario anual' })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))

  // ── 1. Alcance sin equipos: el motivo se ve en pantalla ────
  await page.getByRole('button', { name: 'Nueva campaña' }).click()
  const dialogo = page.getByRole('dialog')
  await expect(dialogo).toBeVisible()
  await dialogo.getByLabel('Nombre').fill(NOMBRE)
  await dialogo.getByLabel('Año').fill(ANIO)
  await dialogo.getByLabel('Alcance').selectOption('zonas')
  await dialogo.getByRole('checkbox', { name: zonaVacia }).check()
  await dialogo.getByRole('button', { name: 'Crear campaña' }).click()

  const aviso = dialogo.getByRole('alert')
  await expect(aviso).toBeVisible()
  await expect(aviso).toContainText(SIN_EQUIPOS)
  await expect(dialogo, 'el formulario sigue abierto para corregir el alcance').toBeVisible()
  await page.screenshot({ path: path.join(CAPTURAS, 'campana-sin-equipos.png') })

  // ── 2. Se cambia el alcance y la campaña se crea ───────────
  await dialogo.getByLabel('Alcance').selectOption('institucion')
  await dialogo.getByRole('button', { name: 'Crear campaña' }).click()
  await expect(page.getByText('Campaña creada', { exact: true }).first()).toBeVisible({ timeout: 20_000 })
  await expect(dialogo).toBeHidden()

  const chip = page.getByRole('button', { name: new RegExp(NOMBRE) }).first()
  await expect(chip).toHaveAttribute('aria-pressed', 'true')

  // ── 3. Verificación física de un equipo ────────────────────
  const valorVerificados = page.locator('p:text-is("Verificados")').first().locator('xpath=../..').locator('p').nth(1)
  await expect(valorVerificados).toHaveText('0')
  await page.getByRole('button', { name: 'Encontrado' }).first().click()
  await expect(valorVerificados).toHaveText('1', { timeout: 20_000 })
  // La campaña pasa a «verificacion» en cuanto hay un equipo revisado
  await expect(chip).toContainText('(verificacion)')
  await page.screenshot({ path: path.join(CAPTURAS, 'campana-verificada.png') })

  // ── 4. Cierre con confirmación y versión histórica ─────────
  await page.getByRole('button', { name: 'Cerrar campaña' }).click()
  const cierre = page.getByRole('dialog')
  await expect(cierre).toBeVisible()
  await cierre.getByRole('checkbox', { name: /Confirmo que revisé/ }).check()
  await cierre.getByRole('button', { name: 'Confirmar cierre' }).click()
  await expect(page.getByText('Campaña cerrada', { exact: true }).first()).toBeVisible({ timeout: 20_000 })

  // El histórico muestra el año recién cerrado
  const historico = page.locator('section', { hasText: 'Histórico' }).last()
  await expect(historico.getByText(ANIO, { exact: true }).first()).toBeVisible({ timeout: 20_000 })
  await page.screenshot({ path: path.join(CAPTURAS, 'campana-cerrada.png'), fullPage: true })
})
