import { expect, test, type Page } from '@playwright/test'
import { entrar } from './utilidades'

test.describe.configure({ mode: 'serial' })
const sufijo = Date.now()
const correos = { admin: `admin-escala-${sufijo}@prueba.local`, tecnico: `tec-escala-${sufijo}@prueba.local`, persona: `persona-escala-${sufijo}@prueba.local` }
const ids: Record<string, string> = {}

test.beforeAll(async ({ request }) => {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345' } })
  expect(login.ok()).toBe(true)
  const principal = await login.json()
  expect(principal.administrador_principal).toBe(true)
  ids.principal = principal.id
  const headers = { Authorization: `Bearer ${principal.access_token}`, 'X-CSRF-Token': principal.csrf_token }
  for (const [clave, rol] of [['admin', 'administrador'], ['tecnico', 'tecnico'], ['persona', 'usuario']] as const) {
    const alta = await request.post('/api/usuarios', { headers, data: {
      nombre: `Cuenta escala ${clave}`, email: correos[clave], rol, password: 'Demo12345',
    } })
    expect(alta.status()).toBe(201)
    ids[clave] = (await alta.json()).id
  }
  const matriz = await (await request.get('/api/permisos/matriz', { headers })).json()
  const cambios = Object.fromEntries(matriz.flatMap((g: { permisos: { clave: string }[] }) => g.permisos.map(p => [p.clave, true])))
  expect((await request.put(`/api/permisos/tecnicos/${ids.tecnico}`, { headers, data: { cambios } })).ok()).toBe(true)
})

async function loginCuenta(page: Page, clave: 'admin' | 'tecnico') {
  await page.goto('/acceder/ti')
  await page.getByLabel('Correo institucional').fill(correos[clave])
  await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Resumen', exact: true })).toBeVisible()
}

async function alta(page: Page) {
  await page.goto('/panel/usuarios')
  await page.getByRole('button', { name: 'Nuevo usuario', exact: true }).click()
  return page.getByRole('dialog').getByLabel('Rol', { exact: true })
}

test('principal: primera cuenta protegida y autoriza administradores', async ({ page }) => {
  await entrar(page, 'administrador')
  const rol = await alta(page)
  await expect(rol.locator('option[value="administrador"]')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await page.goto(`/panel/usuarios/${ids.principal}`)
  await expect(page.getByText('Administrador principal', { exact: true }).first()).toBeVisible()
  await page.getByRole('tab', { name: 'Cuenta y edición' }).click()
  await expect(page.getByRole('button', { name: 'Desactivar cuenta', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Restablecer contraseña', exact: true })).toHaveCount(0)
})

test('administrador: conserva permisos y altas de tecnicos, sin intervenir al principal', async ({ page }) => {
  await loginCuenta(page, 'admin')
  const rol = await alta(page)
  await expect(rol.locator('option[value="administrador"]')).toHaveCount(0)
  await expect(rol.locator('option[value="tecnico"]')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await page.goto(`/panel/usuarios/${ids.principal}`)
  await expect(page.getByRole('tab', { name: 'Cuenta y edición' })).toHaveCount(0)
  await page.goto('/panel/configuracion')
  await page.getByRole('tab', { name: 'Permisos por rol' }).click()
  await page.getByLabel('Buscar permisos, roles o personas').fill('Cuenta escala tecnico')
  const casilla = page.getByRole('tabpanel').getByRole('checkbox').first()
  await expect(casilla).toBeEnabled()
})

test('tecnico con todo: solo alta de usuarios y restablecimiento de usuario', async ({ page }) => {
  await loginCuenta(page, 'tecnico')
  const rol = await alta(page)
  await expect(rol.locator('option[value="administrador"]')).toHaveCount(0)
  await expect(rol.locator('option[value="tecnico"]')).toHaveCount(0)
  await expect(rol.locator('option[value="usuario"]')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await page.goto('/panel/equipo-ti')
  await expect(page.getByRole('link', { name: 'Registrar técnico', exact: true })).toHaveCount(0)
  await page.goto(`/panel/usuarios/${ids.admin}`)
  await expect(page.getByRole('tab', { name: 'Cuenta y edición' })).toHaveCount(0)
  await page.goto(`/panel/usuarios/${ids.persona}`)
  await page.getByRole('tab', { name: 'Cuenta y edición' }).click()
  await page.getByLabel(/^Nueva contraseña/).fill('NuevaClave987!')
  await page.getByLabel(/^Confirmar nueva contraseña/).fill('NuevaClave987!')
  const respuesta = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/restablecer-password'))
  await page.getByRole('button', { name: 'Restablecer contraseña', exact: true }).click()
  expect((await respuesta).status()).toBe(200)
  await expect(page.getByText('Contraseña actualizada. La persona puede iniciar sesión con la nueva clave.', { exact: true })).toBeVisible()
})
