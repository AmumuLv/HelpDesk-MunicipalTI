import { expect, test } from '@playwright/test'

// Solo datos ficticios: nunca ejecutar contra la instalación municipal.
test.describe.configure({ mode: 'serial' })
const cuentas: Record<string, { id: string; correo: string }> = {}
const sufijo = Date.now()

test.beforeAll(async ({ request }) => {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345' } })
  expect(login.ok()).toBe(true)
  const admin = await login.json()
  const headers = { Authorization: `Bearer ${admin.access_token}`, 'X-CSRF-Token': admin.csrf_token }
  for (const clave of ['sin_permiso', 'con_permiso', 'usuario']) {
    const correo = `perfil-seguro-${clave}-${sufijo}@prueba.local`
    const alta = await request.post('/api/usuarios', { headers, data: {
      nombre: `Perfil seguro ${clave}`, email: correo, password: 'Demo12345',
      rol: clave === 'usuario' ? 'usuario' : 'tecnico',
    } })
    expect(alta.status()).toBe(201)
    cuentas[clave] = { id: (await alta.json()).id, correo }
  }
  const respuesta = await request.put(`/api/permisos/tecnicos/${cuentas.con_permiso.id}`, {
    headers, data: { cambios: { 'usuarios.editar': true } },
  })
  expect(respuesta.ok()).toBe(true)
})

for (const clave of ['sin_permiso', 'con_permiso']) {
  test(`técnico ${clave}: guarda su contacto sin poder cambiar su oficina`, async ({ page }) => {
    await page.goto('/acceder/ti')
    await page.getByLabel('Correo institucional').fill(cuentas[clave].correo)
    await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
    await page.getByRole('button', { name: 'Entrar', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Resumen', exact: true })).toBeVisible()
    await page.goto(`/panel/usuarios/${cuentas[clave].id}`)
    await page.getByRole('button', { name: 'Editar datos', exact: true }).click()
    await expect(page.getByLabel('Zona', { exact: true })).toBeDisabled()
    await expect(page.getByLabel('Oficina', { exact: true })).toBeDisabled()
    await page.getByLabel('Anexo', { exact: true }).fill('456')
    const guardado = page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(`/usuarios/${cuentas[clave].id}`))
    await page.getByRole('button', { name: 'Guardar datos', exact: true }).click()
    const respuesta = await guardado
    expect(respuesta.status()).toBe(200)
    expect(respuesta.request().postDataJSON()).not.toHaveProperty('oficina_id')
    expect(respuesta.request().postDataJSON()).not.toHaveProperty('zona_id')
    expect((await respuesta.json()).anexo).toBe('456')
    await page.reload()
    await page.getByRole('button', { name: 'Editar datos', exact: true }).click()
    await expect(page.getByLabel('Anexo', { exact: true })).toHaveValue('456')
    if (clave === 'con_permiso') {
      await page.goto(`/panel/usuarios/${cuentas.usuario.id}`)
      await page.getByRole('button', { name: 'Editar datos', exact: true }).click()
      await expect(page.getByLabel('Zona', { exact: true })).toBeEnabled()
      await expect(page.getByLabel('Oficina', { exact: true })).toBeEnabled()
    }
  })
}
