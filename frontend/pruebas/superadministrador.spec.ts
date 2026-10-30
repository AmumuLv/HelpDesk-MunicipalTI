import { expect, test, type Page } from '@playwright/test'
import { entrar } from './utilidades'

// Solo datos ficticios del perfil navegador de compose.pruebas.yml.
test.describe.configure({ mode: 'serial' })
let titularId = ''
let administradorId = ''
const correoAdmin = `admin-limitado-${Date.now()}@prueba.local`

test.beforeAll(async ({ request }) => {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345' } })
  expect(login.ok()).toBe(true)
  const sesion = await login.json()
  expect(sesion.superadministrador).toBe(true)
  titularId = sesion.id
  const creado = await request.post('/api/usuarios', {
    headers: { Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token },
    data: { nombre: 'Administrador limitado de prueba', email: correoAdmin, rol: 'administrador', password: 'Demo12345' },
  })
  expect(creado.status()).toBe(201)
  administradorId = (await creado.json()).id
})

async function abrirAlta(page: Page) {
  await page.goto('/panel/usuarios')
  await page.getByRole('button', { name: 'Nuevo usuario', exact: true }).click()
  return page.getByRole('dialog')
}

test('titular: crea administradores y su cuenta no ofrece desactivacion', async ({ page }) => {
  await entrar(page, 'administrador')
  const dialogo = await abrirAlta(page)
  await expect(dialogo.getByLabel('Rol', { exact: true }).locator('option[value="administrador"]')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await page.goto(`/panel/usuarios/${titularId}`)
  await expect(page.getByText('Superadministrador', { exact: true }).first()).toBeVisible()
  await page.getByRole('tab', { name: 'Cuenta y edición' }).click()
  await expect(page.getByRole('button', { name: 'Desactivar cuenta', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Rol de la cuenta')).toHaveCount(0)
  await page.goto(`/panel/usuarios/${administradorId}`)
  await page.getByRole('tab', { name: 'Cuenta y edición' }).click()
  await page.getByRole('button', { name: 'Modificar información' }).click()
  await expect(page.getByLabel('Rol de la cuenta')).toBeVisible()
})

test('administrador normal: alta operativa sin rol admin y titular protegido', async ({ page }) => {
  await page.goto('/acceder/ti')
  await page.getByLabel('Correo institucional').fill(correoAdmin)
  await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Resumen', exact: true })).toBeVisible()
  const dialogo = await abrirAlta(page)
  await expect(dialogo.getByLabel('Rol', { exact: true }).locator('option[value="administrador"]')).toHaveCount(0)
  await expect(dialogo.getByLabel('Rol', { exact: true }).locator('option[value="tecnico"]')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await page.goto(`/panel/usuarios/${titularId}`)
  await expect(page.getByRole('tab', { name: 'Cuenta y edición' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Modificar información' })).toHaveCount(0)
  await page.goto('/panel/configuracion')
  await page.getByRole('tab', { name: 'Permisos por rol' }).click()
  await expect(page.getByText('Solo el superadministrador puede cambiar los permisos.', { exact: true })).toBeVisible()
  const controles = page.getByRole('tabpanel').getByRole('checkbox')
  await expect.poll(() => controles.count()).toBeGreaterThan(0)
  for (const control of await controles.all()) await expect(control).toBeDisabled()
})
