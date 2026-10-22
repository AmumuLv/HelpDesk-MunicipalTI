import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

// Ejecutar contra una instalación efímera vacía, nunca contra producción.
// Desde la raíz: docker compose -f compose.pruebas.yml run -d --rm --service-ports
// --name helpdesk-registro-inicial -e MONGO_DB=helpdesk_test_registro api
// uvicorn app.main:app --host 0.0.0.0 --port 8000
// Desde frontend: PRUEBA_API_URL=http://127.0.0.1:18100 npx playwright test pruebas/registro-inicial.spec.ts
test.describe.configure({ mode: 'serial' })
test.beforeEach(async ({ page }) => { page.setDefaultTimeout(20_000) })
test.beforeAll(async ({ request }) => {
  expect(process.env.PRUEBA_API_URL, 'Se requiere la API aislada en el puerto 18100').toBe('http://127.0.0.1:18100')
  const estado = await request.get('/api/instalacion')
  expect(estado.ok()).toBe(true)
  const creada = await request.post('/api/instalacion/administrador', {
    data: { nombre: 'Administrador Demo', email: 'admin@demo.local', password: 'Demo12345' },
  })
  expect(creada.ok(), await creada.text()).toBe(true)
})

test('primera laptop: crea zona y oficina desde el registro sin perder los datos', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.goto('/panel/equipos')
  await page.getByRole('button', { name: 'Registrar equipo', exact: true }).first().click()
  const dialogo = page.getByRole('dialog', { name: 'Registrar equipo', exact: true })
  await dialogo.getByRole('button', { name: 'Laptop', exact: true }).click()
  await dialogo.getByLabel('Nombre del equipo', { exact: true }).fill('Laptop inicial ficticia')
  await dialogo.getByRole('button', { name: 'Continuar', exact: true }).click()
  await expect(dialogo.getByText('Primero necesitas una zona', { exact: true })).toBeVisible()
  await expect(dialogo.getByRole('button', { name: 'Continuar', exact: true })).toBeDisabled()
  await dialogo.getByLabel('Nombre de la nueva zona').fill('Zona inicial ficticia')
  await dialogo.getByRole('button', { name: 'Crear zona y continuar' }).click()
  await expect(dialogo.getByText('Esta zona todavía no tiene oficinas', { exact: true })).toBeVisible()
  await dialogo.getByLabel('Nombre de la nueva oficina').fill('Oficina inicial ficticia')
  await dialogo.getByRole('button', { name: 'Crear oficina y continuar' }).click()
  await expect(dialogo.getByRole('button', { name: 'Continuar', exact: true })).toBeEnabled()
  await dialogo.getByRole('button', { name: 'Continuar', exact: true }).click()
  await expect(dialogo.getByText('Laptop inicial ficticia', { exact: true })).toBeVisible()
  const respuesta = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/activos'))
  await dialogo.getByRole('button', { name: 'Guardar equipo', exact: true }).click()
  const alta = await respuesta
  expect(alta.status(), await alta.text()).toBe(201)
  const equipo = await alta.json()
  expect(equipo.conjunto_id).toBeFalsy()
  await expect(dialogo).toBeHidden()
  await expect(page.getByRole('table').getByText('Laptop inicial ficticia', { exact: true })).toBeVisible()
})

for (const tipo of ['CPU', 'Impresora']) {
  test(`${tipo}: completa y guarda con ubicación existente`, async ({ page }) => {
    await entrar(page, 'administrador')
    await page.goto('/panel/equipos')
    await page.getByRole('button', { name: 'Registrar equipo', exact: true }).first().click()
    const dialogo = page.getByRole('dialog', { name: 'Registrar equipo', exact: true })
    await dialogo.getByRole('button', { name: tipo, exact: true }).click()
    await dialogo.getByLabel('Nombre del equipo', { exact: true }).fill(`${tipo} inicial ficticio`)
    await dialogo.getByRole('button', { name: 'Continuar', exact: true }).click()
    await dialogo.getByRole('combobox', { name: 'Zona', exact: true }).selectOption({ label: 'Zona inicial ficticia · 1 oficinas' })
    await expect(dialogo.getByRole('combobox', { name: 'Oficina', exact: true })).toBeEnabled()
    await dialogo.getByRole('combobox', { name: 'Oficina', exact: true }).selectOption({ label: 'Oficina inicial ficticia' })
    if (tipo === 'CPU') {
      await expect(dialogo.getByLabel('Nombre del conjunto nuevo')).not.toBeEmpty()
    }
    await dialogo.getByRole('button', { name: 'Continuar', exact: true }).click()
    const respuesta = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/activos'))
    await dialogo.getByRole('button', { name: 'Guardar equipo', exact: true }).click()
    const alta = await respuesta
    expect(alta.status(), await alta.text()).toBe(201)
    const equipo = await alta.json()
    if (tipo === 'CPU') expect(equipo.conjunto_id).toBeTruthy()
    else expect(equipo.conjunto_id).toBeFalsy()
    await expect(dialogo).toBeHidden()
    await expect(page.getByRole('table').getByText(`${tipo} inicial ficticio`, { exact: true })).toBeVisible()
  })
}
