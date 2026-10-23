import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test('un técnico registra programas y formateo sobre una laptop individual real', async ({ page, request }) => {
  page.setDefaultTimeout(20_000)
  const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(acceso.ok()).toBe(true)
  const sesion = await acceso.json()
  const headers = { Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token }
  const oficinas = await (await request.get('/api/oficinas', { headers })).json()
  const nombre = `Persona laptop ficticia ${Date.now()}`
  const usuario = await request.post('/api/usuarios', { headers, data: { nombre, email: `laptop.${Date.now()}@demo.local`, password: 'Demo12345', rol: 'usuario', oficina_id: oficinas.items[0].id } })
  expect(usuario.status(), await usuario.text()).toBe(201)
  const persona = await usuario.json()
  const alta = await request.post('/api/activos', { headers, data: { tipo: 'Laptop', nombre_equipo: 'Laptop ficticia independiente', oficina_id: persona.oficina_id, responsable_id: persona.id } })
  expect(alta.status(), await alta.text()).toBe(201)
  const equipo = await alta.json()
  try {
    await entrar(page, 'tecnico')
    for (const categoria of ['Sistema / Programa', 'Formateo']) {
      await page.goto('/panel/tickets/nuevo')
      await page.getByLabel('Persona afectada', { exact: true }).fill(nombre)
      await page.locator('#resultados-persona button').filter({ hasText: nombre }).click()
      await page.getByRole('textbox', { name: 'Asunto', exact: true }).fill(`Verificar ${categoria} en laptop`)
      await page.getByRole('combobox', { name: 'Categoría', exact: true }).selectOption(categoria)
      const selector = page.getByRole('combobox', { name: categoria === 'Formateo' ? 'Equipo o computadora afectada' : 'Computadora afectada', exact: true })
      await expect(selector.locator(`option[value="equipo:${equipo.id}"]`)).toHaveCount(1)
      await selector.selectOption(`equipo:${equipo.id}`)
      if (categoria !== 'Formateo') await page.getByLabel('Programa, sistema o correo').fill('Office')
      const guardar = page.getByRole('button', { name: 'Registrar ticket', exact: true })
      await expect(guardar).toBeEnabled()
      const registro = page.waitForResponse(r => r.url().endsWith('/api/tickets/manual') && r.request().method() === 'POST')
      await guardar.click()
      const respuesta = await registro
      expect(respuesta.status(), await respuesta.text()).toBe(201)
      const creado = await respuesta.json()
      await expect(page).toHaveURL(new RegExp(`/panel/tickets/${creado.ticket.id}$`))
      const detalle = await (await request.get(`/api/tickets/${creado.ticket.id}`, { headers })).json()
      expect(detalle.activo_id).toBe(equipo.id)
      expect(detalle.conjunto_id).toBeFalsy()
      const borrado = await request.post(`/api/tickets/${creado.ticket.id}/eliminar`, { headers })
      expect(borrado.ok(), await borrado.text()).toBe(true)
    }
  } finally {
    await request.delete(`/api/activos/${equipo.id}`, { headers })
    await request.post(`/api/usuarios/${persona.id}/desactivar`, { headers })
  }
})
