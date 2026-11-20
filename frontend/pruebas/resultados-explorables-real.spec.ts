import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test('consulta real identifica 23 dispositivos, pagina, abre el desglose y conserva el historial', async ({ page, request }) => {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(login.ok()).toBe(true)
  const sesion = await login.json()
  const headers = { Authorization: 'Bearer ' + sesion.access_token, 'X-CSRF-Token': sesion.csrf_token }
  const nombre = 'OficinaDesglose' + Date.now()
  const zona = await request.post('/api/zonas', { headers, data: { nombre } })
  expect(zona.status(), await zona.text()).toBe(201)
  const oficina = await request.post('/api/oficinas', { headers, data: { nombre, zona_id: (await zona.json()).id } })
  expect(oficina.status(), await oficina.text()).toBe(201)
  const oid = (await oficina.json()).id
  for (let i = 0; i < 23; i++) {
    const equipo = await request.post('/api/activos', { headers, data: { nombre_equipo: `LaptopDesglose ${i}`, tipo: 'Laptop', oficina_id: oid, uso_comun: true } })
    expect(equipo.status(), await equipo.text()).toBe(201)
  }
  let cid = ''
  try {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await entrar(page, 'administrador')
    await page.goto('/panel/analisis?tab=asistente')
    await expect(page.getByRole('button', { name: 'Preguntas sugeridas', exact: true })).toBeEnabled()
    const pregunta = `Qué equipos no tienen código patrimonial en la oficina ${nombre}`
    await page.getByLabel('Tu pregunta', { exact: true }).fill(pregunta)
    await expect(page.getByLabel('Tu pregunta', { exact: true })).toHaveValue(pregunta)
    const respuesta = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/ia/asistente')
    await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
    const respuestaApi = await respuesta
    expect(respuestaApi.ok(), await respuestaApi.text()).toBe(true)
    const datos = await respuestaApi.json()
    cid = datos.conversacion_id
    expect(datos.tabla.total).toBe(23)
    expect(datos.tabla.filas).toHaveLength(20)
    const resultado = page.locator('.datos-explorable').last()
    await expect(resultado.locator(':scope > .datos-table-scroll tbody tr')).toHaveCount(20)
    const paginador = resultado.locator(':scope > .datos-result-pages')
    await expect(paginador).toContainText('Mostrando 20 de 23')
    await paginador.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(paginador).toContainText('Mostrando 3 de 23')
    await expect(resultado.locator(':scope > .datos-table-scroll tbody tr')).toHaveCount(3)
    await expect(resultado).toContainText('Responsable no registrado')
    await resultado.getByRole('figure').getByRole('button').click()
    const modal = page.getByRole('dialog')
    await expect(modal).toContainText('Mostrando 20 de 23')
    await modal.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(modal).toContainText('Mostrando 3 de 23')
    await page.keyboard.press('Escape')
    await page.reload()
    await expect(page.getByRole('log')).toContainText('Hay 23 equipos con código patrimonial pendiente')
    await expect(page.locator('.datos-explorable').last().locator(':scope > .datos-table-scroll tbody tr')).toHaveCount(20)
    const actuales = await request.get('/api/activos?oficina_id=' + oid + '&por_pagina=1', { headers })
    expect((await actuales.json()).total).toBe(23)
  } finally {
    if (cid) expect((await request.delete('/api/ia/asistente/conversaciones/' + cid, { headers })).ok()).toBe(true)
    // El inventario ficticio completo se retira junto al proyecto aislado.
  }
})
