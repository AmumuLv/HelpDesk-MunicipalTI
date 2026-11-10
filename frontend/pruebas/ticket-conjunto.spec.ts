import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

for (const rol of ['administrador', 'tecnico'] as const) {
  test(`${rol}: Computadora N°2 permanece vinculada al registrar, cancelar, editar y cerrar`, async ({ page, request }) => {
    expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
    const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
    expect(acceso.ok()).toBe(true)
    const sesion = await acceso.json()
    const headers = { Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token }
    const sufijo = `${rol}-${Date.now()}`
    const zona = await request.post('/api/zonas', { headers, data: { nombre: `Zona PC ${sufijo}` } })
    expect(zona.status(), await zona.text()).toBe(201)
    const oficina = await request.post('/api/oficinas', { headers, data: { nombre: `Oficina PC ${sufijo}`, zona_id: (await zona.json()).id } })
    expect(oficina.status(), await oficina.text()).toBe(201)
    const oficinaId = (await oficina.json()).id
    const personaNueva = await request.post('/api/usuarios', { headers, data: {
      nombre: `Persona PC ${sufijo}`, email: `pc-${sufijo}@prueba.local`, password: 'Demo12345',
      rol: 'usuario', oficina_id: oficinaId,
    } })
    expect(personaNueva.status(), await personaNueva.text()).toBe(201)
    const persona = await personaNueva.json()
    const computadoras: { id: string }[] = []
    for (const numero of [1, 2]) {
      const alta = await request.post('/api/conjuntos', { headers, data: {
        nombre: `Computadora N°${numero}`, numero, oficina_id: persona.oficina_id, responsable_id: persona.id,
      } })
      expect(alta.status(), await alta.text()).toBe(201)
      const pc = await alta.json()
      computadoras.push(pc)
      const cpu = await request.post('/api/activos', { headers, data: {
        tipo: 'CPU', nombre_equipo: `CPU ficticio ${numero} ${sufijo}`, oficina_id: persona.oficina_id,
        responsable_id: persona.id, conjunto_id: pc.id,
      } })
      expect(cpu.status(), await cpu.text()).toBe(201)
    }
    let id = ''
    try {
      await entrar(page, rol)
      await page.setViewportSize({ width: 1440, height: 1000 })
      await page.goto('/panel/tickets/nuevo')
      await page.getByLabel('Persona afectada', { exact: true }).fill(persona.nombre)
      await page.locator('#resultados-persona button').filter({ hasText: persona.nombre }).click()
      await page.getByRole('textbox', { name: 'Asunto', exact: true }).fill('Programa de prueba en computadora dos')
      await page.getByRole('combobox', { name: 'Categoría', exact: true }).selectOption('Sistema / Programa')
      await page.getByRole('combobox', { name: 'Computadora afectada', exact: true }).selectOption(`pc:${computadoras[1].id}`)
      await page.getByLabel('Programa, sistema o correo', { exact: true }).fill('Office')
      const enviado = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/tickets/manual')
      await page.getByRole('button', { name: 'Registrar ticket', exact: true }).click()
      const respuesta = await enviado
      expect(respuesta.status(), await respuesta.text()).toBe(201)
      const { ticket } = await respuesta.json()
      id = ticket.id
      await expect(page).toHaveURL(new RegExp(`/panel/tickets/${id}$`))
      await expect(page.getByText('Computadora N°2', { exact: true })).toBeVisible()
      await page.getByRole('region', { name: 'Incidencia reportada' }).getByRole('button', { name: 'Editar', exact: true }).click()
      await expect(page.getByRole('combobox', { name: 'Computadora afectada', exact: true })).toHaveValue(`pc:${computadoras[1].id}`)
      await page.getByLabel('Título de la incidencia', { exact: true }).fill('Cambio que se debe cancelar')
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
      await expect(page.getByRole('heading', { name: 'Programa de prueba en computadora dos', exact: true })).toBeVisible()
      await page.getByRole('region', { name: 'Incidencia reportada' }).getByRole('button', { name: 'Editar', exact: true }).click()
      await page.getByLabel('Título de la incidencia', { exact: true }).fill('Programa revisado en computadora dos')
      const editado = page.waitForResponse(r => r.request().method() === 'PATCH' && new URL(r.url()).pathname === `/api/tickets/${id}`)
      await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
      expect((await editado).ok()).toBe(true)
      await page.goto(`/panel/tickets?texto=${ticket.codigo}`)
      const fila = page.getByRole('row').filter({ hasText: ticket.codigo })
      await expect(fila).toContainText('Computadora N°2')
      await expect(fila).toContainText('PC de escritorio')
      await expect(fila).not.toContainText('Sin equipo')
      await page.reload()
      await expect(fila).toContainText('Computadora N°2')
      await fila.click()
      await page.getByRole('button', { name: 'Cerrar ticket', exact: true }).click()
      const cierre = page.getByRole('dialog', { name: 'Cerrar ticket', exact: true })
      await cierre.getByLabel('Resultado de la atención', { exact: true }).fill('Programa revisado y funcionando en la computadora seleccionada.')
      await cierre.getByRole('button', { name: 'Cerrar ticket', exact: true }).click()
      await expect(page.getByRole('button', { name: 'Reabrir ticket', exact: true })).toBeVisible()
      await page.goto(`/panel/cerrados?tab=cerrados&texto=${ticket.codigo}`)
      const cerrada = page.getByRole('row').filter({ hasText: ticket.codigo })
      await expect(cerrada).toContainText('Computadora N°2')
      await expect(cerrada).not.toContainText('Sin equipo')
      const detalle = await (await request.get(`/api/tickets/${id}`, { headers })).json()
      expect(detalle.activo_id).toBeNull()
      expect(detalle.conjunto_id).toBe(computadoras[1].id)
      expect(detalle.estado).toBe('cerrado')
    } finally {
      if (id) expect((await request.post(`/api/tickets/${id}/eliminar`, { headers })).ok()).toBe(true)
      // Las cuentas y el inventario son ficticios del proyecto aislado, retirado al terminar la suite.
    }
  })
}
