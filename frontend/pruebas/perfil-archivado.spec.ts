import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'wait' })
})

test('el filtro vacío de archivados permite volver a cuentas activas', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.route('**/api/usuarios?**', async ruta => {
    if (new URL(ruta.request().url()).searchParams.get('estado') === 'archivados') {
      return ruta.fulfill({ json: { items: [], total: 0, pagina: 1, por_pagina: 25, total_paginas: 1 } })
    }
    await ruta.continue()
  })
  await page.goto('/panel/usuarios')
  await page.getByLabel('Estado de las cuentas').selectOption('archivados')
  await expect(page.getByText('No hay personas con estos filtros', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Quitar los filtros', exact: true }).click()
  await expect(page.getByLabel('Estado de las cuentas')).toHaveValue('activos')
  await expect(page.getByRole('table')).toBeVisible()
})

for (const autorizado of [false, true]) {
  test(`ficha archivada distingue fechas y ${autorizado ? 'permite reactivar' : 'respeta al técnico sin permiso'}`, async ({ page, request }) => {
    expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
    const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345' } })
    expect(login.ok()).toBe(true)
    const admin = await login.json()
    const headers = { Authorization: `Bearer ${admin.access_token}`, 'X-CSRF-Token': admin.csrf_token }
    const alta = await request.post('/api/usuarios', { headers, data: { nombre: `Archivo de prueba ${Date.now()}`, rol: 'usuario' } })
    expect(alta.status()).toBe(201)
    const persona = await alta.json()
    expect((await request.post(`/api/usuarios/${persona.id}/desactivar`, { headers })).ok()).toBe(true)
    // Se simula la presentación tras el archivo automático; las llamadas de permisos
    // y de reactivación se ejecutan realmente contra la API ficticia.
    await page.route(`**/api/usuarios/${persona.id}`, async ruta => {
      if (ruta.request().method() !== 'GET') return ruta.continue()
      const respuesta = await ruta.fetch()
      const datos = await respuesta.json()
      await ruta.fulfill({ json: datos.activo ? datos : { ...datos, archivado: true, desactivado_en: '2026-09-01T15:00:00Z', archivado_en: '2026-10-01T15:00:00Z' } })
    })
    await entrar(page, autorizado ? 'administrador' : 'tecnico')
    await page.goto(`/panel/usuarios/${persona.id}`)
    await expect(page.getByText('Archivada', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Fecha de baja', { exact: true })).toBeVisible()
    await expect(page.getByText('Fecha de archivo', { exact: true })).toBeVisible()
    if (!autorizado) {
      await expect(page.getByRole('tab', { name: 'Cuenta y edición', exact: true })).toHaveCount(0)
      const estado = await page.evaluate(async id => {
        const csrf = document.cookie.split('; ').find(c => c.startsWith('ma_csrf='))?.split('=')[1] ?? ''
        return (await fetch(`/api/usuarios/${id}`, { method: 'PATCH', headers: {
          Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}`, 'X-CSRF-Token': csrf,
          'Content-Type': 'application/json',
        }, body: JSON.stringify({ activo: true }) })).status
      }, persona.id)
      expect(estado).toBe(403)
      return
    }
    await page.getByRole('tab', { name: 'Cuenta y edición', exact: true }).click()
    await page.getByRole('button', { name: 'Reactivar cuenta', exact: true }).click()
    const confirmacion = page.getByRole('dialog', { name: 'Reactivar cuenta', exact: true })
    const guardado = page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(`/usuarios/${persona.id}`))
    await confirmacion.getByRole('button', { name: 'Reactivar', exact: true }).click()
    expect((await guardado).status()).toBe(200)
    await expect(page.getByRole('button', { name: 'Desactivar cuenta', exact: true })).toBeVisible()
    await page.getByRole('tab', { name: 'Resumen', exact: true }).click()
    await expect(page.getByText('Archivada', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Fecha de archivo', { exact: true })).toHaveCount(0)
    const final = await (await request.get(`/api/usuarios/${persona.id}`, { headers })).json()
    expect(final.id).toBe(persona.id)
    expect(final.nombre).toBe(persona.nombre)
    expect(final.activo).toBe(true)
    expect(final.archivado).toBe(false)
  })
}
