/**
 * Flujos críticos, de principio a fin.
 *
 * Cada prueba hace lo que haría una persona: entra, rellena, envía y comprueba
 * que el resultado existe de verdad en la base de datos. No se limita a que el
 * botón exista.
 *
 * Los tickets de prueba se identifican con el prefijo «Prueba automatica».
 */

import { expect, test } from '@playwright/test'

async function entrar(page: import('@playwright/test').Page, correo: string) {
  await page.goto('/acceder')
  await page.getByLabel('Correo institucional').fill(correo)
  await page.getByLabel('Contraseña').fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await page.waitForURL((url) => !url.pathname.includes('/acceder'))
  await page.waitForTimeout(1200)
}

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (error) => console.log('Error de interfaz:', error.message))
  page.on('response', async (respuesta) => {
    if (respuesta.request().method() === 'POST' && /\/api\/tickets(?:\/manual)?$/.test(respuesta.url())) {
      console.log('Crear ticket:', respuesta.status(), await respuesta.text())
    }
  })
})

test('el usuario reporta un problema para un compañero', async ({ page }) => {
  await entrar(page, 'usuario1@demo.local')

  await page.goto('/reportar')
  await page.waitForURL('**/reportar')
  await page.waitForTimeout(1200)

  // Paso 1: tipo de problema
  await page.getByRole('button', { name: /No enciende/ }).click()

  // Paso 2: el detalle
  await page.getByLabel('¿Qué está pasando?').fill('Prueba automatica: no prende\n\nPrueba del flujo critico end to end.')
  await page.getByRole('radio', { name: /Con dificultad/ }).check()

  // Marca que es de otra persona
  await page.getByText('Equipo y persona afectada', { exact: false }).click()
  const cajaCompanero = page.getByRole('checkbox', { name: /Estoy reportando para un compañero/ })
  await cajaCompanero.check()
  await page.waitForTimeout(900)
  await page.getByLabel('Persona que necesita ayuda').selectOption({ index: 1 })

  await page.getByRole('button', { name: 'Enviar a soporte' }).click()

  // Debe llevar al ticket creado, con su código
  await page.waitForURL('**/mis-tickets/**', { timeout: 25_000 })
  const url = page.url()
  const texto = await page.locator('body').innerText()
  console.log(`REPORTE → ${url.replace(/.*\//, '')}`)
  console.log(`   código en pantalla: ${texto.match(/TKT-\d{4}-\d+/)?.[0] ?? 'NO APARECE'}`)

  expect(url).toMatch(/\/mis-tickets\/[a-f0-9]{24}/)
  expect(texto).toMatch(/TKT-\d{4}-\d+/)
})

test('el tecnico registra un ticket manual', async ({ page }) => {
  await entrar(page, 'jorge.castillo@municipalidad.gob.pe')

  await page.goto('/panel/tickets/nuevo')
  await page.waitForTimeout(1500)

  const titulo = await page.locator('h1').first().innerText()
  console.log(`MANUAL → pantalla: ${titulo}`)

  // Buscar a la persona afectada en el padrón
  await page.getByLabel('Persona afectada').fill('Ana Quispe')
  await page.waitForTimeout(1500)
  await page.getByRole('button', { name: /Ana Quispe/ }).first().click()
  await page.waitForTimeout(400)

  await page.getByLabel('Asunto').fill('Prueba automatica: ticket manual')
  await page.getByLabel('Descripción').fill('Registrado por el flujo critico.')
  await page.waitForTimeout(300)

  await page.getByRole('button', { name: 'Registrar ticket' }).click()

  await page.waitForURL(/\/panel\/tickets\/[a-f0-9]{24}$/, { timeout: 25_000 })
  const texto = await page.locator('body').innerText()
  console.log(`   código: ${texto.match(/TKT-\d{4}-\d+/)?.[0] ?? 'NO APARECE'}`)
  console.log(`   detectado por técnico (sin chat): ${!texto.includes('Conversación')}`)

  expect(texto).toMatch(/TKT-\d{4}-\d+/)
  // Un ticket del equipo TI no debe abrir chat con el usuario
  expect(texto).not.toContain('Conversación')
})
