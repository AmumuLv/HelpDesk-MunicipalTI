import { expect, test } from '@playwright/test'

test('el administrador entra por TI y el portal de trabajadores rechaza esa cuenta', async ({ page }) => {
  await page.goto('/acceder/usuarios')
  await page.getByLabel('Correo institucional').fill('admin@demo.local')
  await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
  const rechazo = page.waitForResponse(r => r.url().endsWith('/api/auth/login') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  expect((await rechazo).status()).toBe(403)
  await expect(page.getByRole('alert')).toContainText('equipo TI')
  expect(await page.evaluate(() => sessionStorage.getItem('ma.acceso'))).toBeNull()
  await page.getByRole('link', { name: /Equipo TI/ }).click()
  await page.getByLabel('Correo institucional').fill('admin@demo.local')
  await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await page.waitForURL('**/panel')
  await expect(page.getByRole('link', { name: 'Tickets', exact: true })).toBeVisible()
  await page.goto('/instalacion')
  await expect(page.getByRole('link', { name: 'Registrar técnico', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Registrar técnico', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('Rol', { exact: true }).last()).toHaveValue('tecnico')
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await page.goto('/instalacion')
  await page.getByRole('link', { name: 'Vincular responsables', exact: true }).click()
  await expect(page.getByRole('checkbox', { name: 'El responsable no tiene cuenta', exact: true })).toBeChecked()
  const listado = await page.evaluate(async () => {
    const r = await fetch('/api/activos?responsables_pendientes=true', { headers: { Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso') } })
    if (!r.ok) throw new Error(`Inventario: ${r.status}`)
    const datos = await r.json()
    const activos = await Promise.all(datos.items.map(async (a: { responsable_id?: string }) => {
      if (!a.responsable_id) return false
      const persona = await fetch(`/api/usuarios/${a.responsable_id}`, { headers: { Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso') } })
      if (persona.status === 404) return false
      if (!persona.ok) throw new Error(`Responsable: ${persona.status}`)
      return (await persona.json()).activo
    }))
    return { ...datos, activos }
  })
  expect(listado.total).toBeGreaterThanOrEqual(0)
  expect(Array.isArray(listado.items)).toBe(true)
  expect(listado.items.every((a: { responsable_nombre: string | null }) => Boolean(a.responsable_nombre))).toBeTruthy()
  expect(listado.activos.every((activo: boolean) => activo === false)).toBe(true)
  await page.goto('/instalacion')
  await page.getByRole('link', { name: 'Definir horarios', exact: true }).click()
  await expect(page.getByRole('form', { name: 'Horario de Administrador Demo', exact: true })).toBeVisible()
})
