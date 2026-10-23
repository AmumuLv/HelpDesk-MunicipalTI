import { expect, test } from '@playwright/test'
import { entrar, sinDesbordamiento } from './utilidades'
import path from 'node:path'

test.beforeEach(async ({ page }) => { page.setDefaultTimeout(15_000) })

test('PC y celular conservan conexiones independientes de la misma cuenta', async ({ request }) => {
  const agentes = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0', 'Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile']
  const sesiones = []
  for (const agente of agentes) {
    const respuesta = await request.post('/api/auth/login', { headers: { 'User-Agent': agente }, data: { correo: 'usuario1@demo.local', password: 'Demo12345' } })
    expect(respuesta.ok()).toBe(true)
    sesiones.push(await respuesta.json())
  }
  const conexiones = await request.get('/api/auth/dispositivos', { headers: { Authorization: `Bearer ${sesiones[1].access_token}` } })
  expect(conexiones.ok()).toBe(true)
  const datos = await conexiones.json()
  const pc = datos.items.find((item: { agente: string }) => item.agente === agentes[0])
  const celular = datos.items.find((item: { agente: string }) => item.agente === agentes[1])
  expect(pc).toBeTruthy()
  expect(celular).toBeTruthy()
  expect(pc.id).not.toBe(celular.id)
  expect(datos.total).toBeLessThanOrEqual(3)
})

test('conexiones distingue celular, tablet y computadora con su navegador', async ({ page }) => {
  await entrar(page, 'usuario')
  await page.route('**/api/auth/dispositivos', route => route.fulfill({ json: { total: 3, limite: 3, items: [
    { id: 'pc', agente: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36 Edg/130.0', inicio: '2026-10-16T12:00:00Z', actual: true },
    { id: 'celular', agente: 'Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36', inicio: '2026-10-16T12:00:00Z', actual: false },
    { id: 'tablet', agente: 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Version/17.0 Mobile Safari/604.1', inicio: '2026-10-16T12:00:00Z', actual: false },
  ] } }))
  await page.goto('/perfil')
  await page.getByText('Dispositivos conectados a mi cuenta', { exact: true }).click()
  await expect(page.getByText('Computadora', { exact: true })).toBeVisible()
  await expect(page.getByText('Windows · Edge', { exact: true })).toBeVisible()
  await expect(page.getByText('Celular', { exact: true })).toBeVisible()
  await expect(page.getByText('Android · Chrome', { exact: true })).toBeVisible()
  await expect(page.getByText('Tablet', { exact: true })).toBeVisible()
  await expect(page.getByText('iOS / iPadOS · Safari', { exact: true })).toBeVisible()
})

test('fichas de organización paginan todas sus listas sin ocultar registros', async ({ page }) => {
  await entrar(page, 'administrador')
  const equipos = Array.from({ length: 12 }, (_, i) => ({ id: `equipo-${i}`, nombre: `Dispositivo ${i + 1}`, tipo: 'CPU', estado: 'OPERATIVO', responsable_id: 'persona' }))
  const base = { id: 'paginada', nombre: 'Oficina paginada', zona_id: 'zona', zona_nombre: 'PALACIO', zona_color_indice: 0, total_equipos: 24, total_usuarios: 12, tickets_abiertos: 12, completitud_inventario: 100 }
  await page.route('**/api/oficinas/paginada', route => route.fulfill({ json: { ...base,
    usuarios: equipos.map((_, i) => ({ id: `persona-${i}`, nombre: `Persona ${i + 1}`, tiene_foto: i === 0 })), equipos_uso_comun: equipos,
    equipos_por_usuario: [{ responsable_id: 'persona', responsable: 'Responsable', equipos: [...equipos, ...Array.from({ length: 6 }, (_, i) => ({ ...equipos[0], id: `extra-${i}`, nombre: `Dispositivo ${i + 13}` }))] }],
    tickets_recientes: equipos.map((_, i) => ({ id: `ticket-${i}`, codigo: `TKT-${i + 1}`, asunto: `Incidencia ${i + 1}`, estado: 'nuevo' })),
    tendencia: equipos.map((_, i) => ({ mes: `2026-10-${String(i + 1).padStart(2, '0')}`, total: 1 })),
    incidencias_recurrentes: equipos.map((_, i) => ({ categoria: `Categoria ${i + 1}`, total: 1 })),
  } }))
  await page.route('**/api/usuarios/persona-0/foto', route => route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9xoAAAAASUVORK5CYII=', 'base64') }))
  await page.goto('/panel/oficinas/paginada')
  await expect(page.getByRole('listitem').filter({ has: page.getByRole('link', { name: 'Persona 1', exact: true }) }).locator('img')).toBeVisible()
  const avanzar = async (titulo: string, ultimo: string) => {
    const panel = page.locator('section').filter({ has: page.getByRole('heading', { name: titulo, exact: true }) }).last()
    await expect(panel.getByText(ultimo, { exact: true })).toHaveCount(0)
    await panel.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(panel.getByText(ultimo, { exact: true })).toBeVisible()
  }
  await avanzar('Personas', 'Persona 12')
  await page.getByRole('tab', { name: 'Equipos asignados' }).click()
  await expect(page.getByRole('link', { name: 'Dispositivo 16', exact: true })).toBeVisible()
  await avanzar('Equipos asignados', 'Dispositivo 18')
  await page.getByRole('tab', { name: 'Uso común' }).click()
  await avanzar('Equipos de uso común', 'Dispositivo 12')
  // La tabla actual consulta y pagina 25 tickets en su propia API.
  await expect(page.getByRole('heading', { name: 'Tickets abiertos', exact: true })).toBeVisible()
  await avanzar('Tendencia de los últimos 30 días', '12 oct 2026')
  await avanzar('Incidencias recurrentes', 'Categoria 12')
  await page.route('**/api/zonas/paginada', route => route.fulfill({ json: { ...base, nombre: 'Zona paginada', color_indice: 0, total_oficinas: 26, oficinas: Array.from({ length: 26 }, (_, i) => ({ id: `oficina-${i}`, nombre: `Oficina ${i + 1}`, total_usuarios: 0, total_equipos: 0 })),
    categorias_frecuentes: equipos.map((_, i) => ({ categoria: `Categoria ${i + 1}`, total: 1 })),
    oficinas_con_mas_fallas: equipos.map((e) => ({ id: e.id, nombre: e.nombre, tickets: 1 })),
  } }))
  await page.goto('/panel/zonas/paginada')
  await expect(page.getByRole('link', { name: 'Oficina 25', exact: true })).toBeVisible()
  await avanzar('Oficinas', 'Oficina 26')
  await avanzar('Categorías frecuentes', 'Categoria 12')
  await avanzar('Oficinas con más fallas', 'Dispositivo 12')
})

test('equipos asignados enlaza al perfil del responsable', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.route('**/api/oficinas/revision-responsable', route => route.fulfill({ json: {
    id: 'revision-responsable', nombre: 'Oficina de prueba', zona_id: 'zona-prueba', zona_nombre: 'PALACIO', zona_color_indice: 0,
    total_equipos: 1, total_usuarios: 1, tickets_abiertos: 0, completitud_inventario: 100,
    usuarios: [{ id: 'dueno-prueba', nombre: 'Responsable de prueba' }], equipos_uso_comun: [],
    equipos_por_usuario: [{ responsable_id: 'dueno-prueba', responsable: 'Responsable de prueba', equipos: [{ id: 'pc-prueba', nombre: 'PC de prueba', tipo: 'CPU', estado: 'OPERATIVO', responsable_id: 'dueno-prueba' }] }],
    tickets_recientes: [], tendencia: [], incidencias_recurrentes: [],
  } }))
  await page.goto('/panel/oficinas/revision-responsable')
  await page.getByRole('tab', { name: 'Equipos asignados' }).click()
  await expect(page.getByRole('link', { name: 'Responsable de prueba', exact: true })).toHaveAttribute('href', '/panel/usuarios/dueno-prueba')
  await expect(page.getByRole('link', { name: 'PC de prueba', exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await sinDesbordamiento(page, 'equipos por responsable en móvil')
})

test('Excel anual se registra al primer intento y compara dos años', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.goto('/panel/inventario-anual')
  for (const anio of [2026, 2027]) {
    await page.getByLabel('Año del inventario', { exact: true }).fill(String(anio))
    await page.getByLabel('Archivo Excel o CSV').setInputFiles(path.resolve(`pruebas/fixtures/inventario-${anio}.xlsx`))
    const respuesta = page.waitForResponse(r => r.url().endsWith('/campanas/anual/importar') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Registrar inventario anual', exact: true }).click()
    expect((await respuesta).status()).toBe(201)
    await expect(page.getByRole('table').getByText('Pantalla anual')).toBeVisible()
    await expect(page.getByLabel('Año y versión del inventario').locator('option:checked')).toContainText(String(anio))
  }
  await page.getByLabel('Año de origen').selectOption('2026')
  await page.getByLabel('Año de destino').selectOption('2027')
  await page.getByRole('button', { name: 'Comparar años', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Altas (1)', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Traslados (1)', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Traslados (1)', exact: true }).click()
  await expect(page.getByText('PALACIO · SISTEMAS → PALACIO · SOPORTE', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await sinDesbordamiento(page, 'archivo anual móvil')
})

test('reporte en dos pasos, chat, campana y solicitud de cambio de contraseña', async ({ page }) => {
  await entrar(page, 'administrador')
  const correo = `panico.${Date.now()}@demo.local`
  const creado = await page.evaluate(async correo => {
    const csrf = document.cookie.split('; ').find(p => p.startsWith('ma_csrf='))?.split('=')[1] || ''
    const r = await fetch('/api/usuarios', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}`, 'X-CSRF-Token': csrf }, body: JSON.stringify({ nombre: 'Prueba del portal', email: correo, password: 'Inicial987!', rol: 'usuario' }) })
    return { status: r.status, cuerpo: await r.json() }
  }, correo)
  expect(creado.status).toBe(201)
  const cabeceraAdmin = await page.evaluate(() => ({ Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}`, 'X-CSRF-Token': document.cookie.split('; ').find(p => p.startsWith('ma_csrf='))?.split('=')[1] || '' }))
  await page.context().clearCookies()
  await page.evaluate(() => sessionStorage.clear())
  await page.goto('/acceder')
  await page.getByLabel('Correo institucional').fill(correo)
  await page.getByLabel('Contraseña', { exact: true }).fill('Inicial987!')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Necesito ayuda', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Necesito ayuda', exact: true }).click()
  await page.getByRole('group', { name: 'Tipo de problema' }).getByRole('button').first().click()
  await page.getByRole('radio', { name: /Con dificultad/ }).check()
  await page.getByLabel('¿Qué está pasando?').fill('Problema de conexión de prueba\n\nLa conexión dejó de funcionar y necesito ayuda de soporte.')
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/\/mis-tickets\/[a-f0-9]+$/)
  await expect(page.getByRole('heading', { name: /^Problema de conexión de prueba/ })).toBeVisible()
  await page.getByLabel('Escribe un mensaje', { exact: true }).fill('Mensaje inicial desde el usuario')
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page.getByText('Mensaje inicial desde el usuario', { exact: true })).toBeVisible()
  const ticketId = page.url().split('/').at(-1)
  const respuestaSoporte = await page.request.post(`/api/tickets/${ticketId}/mensajes`, { headers: cabeceraAdmin, data: { cuerpo: 'Respuesta de soporte para revisar la campana' } })
  expect(respuestaSoporte.status()).toBe(201)
  await page.getByRole('button', { name: /^Notificaciones/ }).click()
  await expect(page.getByText('Notificaciones', { exact: true })).toBeVisible()
  await page.getByRole('button').filter({ hasText: 'Respuesta de soporte para revisar la campana' }).click()
  await expect(page.getByText('Respuesta de soporte para revisar la campana', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Notificaciones', exact: true })).toBeVisible()
  await page.goto('/perfil')
  await page.getByText('Dispositivos conectados a mi cuenta', { exact: true }).click()
  await expect(page.getByRole('heading', { name: /Dispositivos conectados/ })).toBeVisible()
  await expect(page.getByLabel('Contraseña actual')).toHaveCount(0)
  await page.getByRole('link', { name: 'Solicitar cambio de contraseña' }).click()
  await expect(page).toHaveURL(/solicitud=password/)
  await expect(page.getByLabel('¿Qué está pasando?')).toHaveValue(/administrador restablezca/)

})

test('fichas de equipos y oficinas y enlace independiente al responsable', async ({ page }) => {
  await entrar(page, 'administrador')
  const datos = await page.evaluate(async () => {
    const headers = { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` }
    const equipos = await (await fetch('/api/activos?por_pagina=100', { headers })).json()
    const oficinas = await (await fetch('/api/oficinas', { headers })).json()
    return { equipo: equipos.items.find((e: { responsable_id?: string; nombre_equipo?: string }) => e.responsable_id && e.nombre_equipo), oficina: oficinas.items[0] }
  })
  expect(datos.equipo).toBeTruthy()
  await page.goto(`/panel/equipos/${datos.equipo.id}`)
  await expect(page.getByRole('heading', { name: 'Ficha del equipo', exact: true })).toBeVisible()
  await expect(page.getByText(datos.equipo.nombre_equipo, { exact: true })).toHaveCount(1)
  await page.goto(`/panel/oficinas/${datos.oficina.id}`)
  await expect(page.getByRole('heading', { name: 'Ficha de la oficina', exact: true })).toBeVisible()
  await expect(page.locator('section > header').getByText(datos.oficina.nombre, { exact: true })).toBeVisible()
  await page.goto('/panel/equipos')
  const responsable = page.getByRole('table').locator(`a[href="/panel/usuarios/${datos.equipo.responsable_id}"]`).first()
  await expect(responsable).toBeVisible()
  await responsable.click()
  await expect(page).toHaveURL(new RegExp(`/panel/usuarios/${datos.equipo.responsable_id}$`))
})



