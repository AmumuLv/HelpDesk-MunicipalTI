import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test('La consulta natural de equipos coincide con el inventario real y no modifica sus registros', async ({ page, request }) => {
  const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(acceso.ok()).toBe(true)
  const sesion = await acceso.json()
  const headers = { Authorization: 'Bearer ' + sesion.access_token, 'X-CSRF-Token': sesion.csrf_token }
  const inventario = await request.get('/api/activos?por_pagina=1', { headers })
  expect(inventario.ok()).toBe(true)
  const inicial = await inventario.json()
  let id = ''
  await page.emulateMedia({ reducedMotion: 'reduce' })
  try {
    await entrar(page, 'administrador')
    await page.goto('/panel/analisis?tab=asistente')
    const pregunta = '¿Cuántos equipos hay en el sistema?'
    await page.getByLabel('Tu pregunta', { exact: true }).fill(pregunta)
    const respondiendo = page.waitForResponse(r => new URL(r.url()).pathname === '/api/ia/asistente' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
    const respuesta = await respondiendo
    expect(respuesta.ok()).toBe(true)
    const datos = await respuesta.json()
    id = datos.conversacion_id
    expect(datos.fuentes).toEqual(['resumen_inventario'])
    expect(datos.tabla.filas.reduce((suma: number, fila: { total: number }) => suma + fila.total, 0)).toBe(inicial.total)
    await expect(page.getByRole('log')).toContainText(pregunta)
    await expect(page.locator('.datos-result')).toContainText('Inventario actual')
    await page.getByText('Ver datos de la respuesta', { exact: true }).click()
    await expect(page.locator('.datos-data table')).toBeVisible()
    await page.getByText('De dónde sale esta respuesta', { exact: true }).click()
    await expect(page.locator('.datos-proof')).toContainText('Inventario')
    const posterior = await request.get('/api/activos?por_pagina=1', { headers })
    expect((await posterior.json()).total).toBe(inicial.total)
  } finally {
    if (id) await request.delete('/api/ia/asistente/conversaciones/' + id, { headers })
  }
})

test('Acceso con Casma y gráficos que se acomodan al desplegar las tablas', async ({ page }) => {
  page.setDefaultTimeout(20_000)
  await page.goto('/acceder/ti', { waitUntil: 'domcontentloaded', timeout: 60_000 })
  const fondo = page.locator('img[src="/identidad/casma-dia.jpg"]')
  await expect(fondo).toHaveCount(1)
  await expect.poll(() => fondo.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  await entrar(page, 'administrador')
  await page.setViewportSize({ width: 1600, height: 1000 })
  const panelListo = page.waitForResponse(r => r.url().includes('/api/analitica/panel?periodo=30d'), { timeout: 60_000 })
  await page.goto('/panel/analisis')
  expect((await panelListo).ok()).toBe(true)
  const mosaico = page.getByTestId('mosaico-graficos')
  await expect(mosaico.locator(':scope > div')).toHaveCount(7)
  const comprobar = async () => {
    await expect.poll(() => mosaico.evaluate((grid) => {
      const tarjetas = [...grid.children].map((hijo) => hijo.firstElementChild!.getBoundingClientRect())
      return tarjetas.every((tarjeta, i) => {
        const anteriores = tarjetas.filter((otra, j) => j !== i && Math.abs(otra.left - tarjeta.left) < 2 && otra.top < tarjeta.top)
        const finAnterior = anteriores.length ? Math.max(...anteriores.map((otra) => otra.bottom)) : grid.getBoundingClientRect().top
        const hueco = tarjeta.top - finAnterior
        return hueco >= -1 && hueco <= 56
      })
    })).toBe(true)
  }
  await comprobar()
  await page.getByText('Ver los datos en tabla', { exact: true }).first().click()
  await expect(page.getByRole('table').first()).toBeVisible()
  await comprobar()
  await page.setViewportSize({ width: 390, height: 844 })
  await comprobar()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('Análisis conserva periodos, muestra respuestas reales y permite retomar conversaciones', async ({ page, request }) => {
  page.setDefaultTimeout(20_000)
  const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(acceso.ok()).toBe(true)
  const sesion = await acceso.json()
  const headers = { Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token }
  const conversaciones = new Set<string>()
  const errores: string[] = []
  page.on('pageerror', (error) => errores.push(error.message))
  try {
    await entrar(page, 'administrador')
    await page.goto('/panel/analisis')
    await expect(page.getByRole('heading', { name: 'Análisis IA', exact: true })).toBeVisible()
    await expect(page.getByText('Tickets del periodo', { exact: true })).toBeVisible()
    const anual = page.waitForResponse((r) => r.url().includes('/analitica/panel?periodo=365d'))
    await page.getByLabel('Periodo', { exact: true }).selectOption('365d')
    const datos = await (await anual).json()
    expect(datos.tendencia.serie).toHaveLength(365)
    await expect(page.getByText(new RegExp(`Periodo: ${datos.kpis.periodo.desde.split('-').reverse().join('/')}`))).toBeVisible()
    await page.getByText('Ver los datos en tabla', { exact: true }).first().click()
    await expect(page.getByRole('table').first()).toBeVisible()
    const oficina = page.getByRole('button', { name: /Abrir detalle/ }).first()
    if (await oficina.count()) {
      await oficina.click()
      await expect(page).toHaveURL(/\/panel\/(oficinas|zonas)\//)
      await page.goBack()
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: '../docs/capturas/analisis-panel.png', fullPage: true })
    await page.getByRole('tab', { name: 'Consultas de datos', exact: true }).click()
    const peticion = page.waitForRequest((r) => r.url().endsWith('/ia/asistente') && r.method() === 'POST')
    const primera = page.waitForResponse((r) => r.url().endsWith('/ia/asistente') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '¿Qué oficina tiene más incidencias en el periodo seleccionado?', exact: true }).click()
    expect((await peticion).postDataJSON().filtros.periodo).toBe('365d')
    const respuesta = await primera
    expect(respuesta.ok()).toBe(true)
    const cuerpo = await respuesta.json()
    conversaciones.add(cuerpo.conversacion_id)
    expect(cuerpo.texto.trim()).not.toBe('')
    const log = page.getByRole('log', { name: 'Conversación con el asistente' })
    const comprobarRespuesta = async (texto: string) => {
      const lineas = texto.split('\n').filter(l => l.trim()).map(l => l.replace(/^\s*[-*]\s+/, ''))
      const respuesta = log.locator('.datos-result .datos-answer').filter({ hasText: lineas[0] }).last()
      await expect(respuesta).toBeVisible()
      for (const linea of lineas) await expect(respuesta).toContainText(linea)
    }
    await comprobarRespuesta(cuerpo.texto)
    await expect(log.locator('.datos-sources')).toContainText('Tickets por oficina')
    await page.getByLabel('Tu pregunta', { exact: true }).fill('¿Qué técnico está disponible ahora?')
    const segunda = page.waitForResponse((r) => r.url().endsWith('/ia/asistente') && r.request().method() === 'POST')
    await page.getByLabel('Tu pregunta', { exact: true }).press('Control+Enter')
    const segundoCuerpo = await (await segunda).json()
    expect(segundoCuerpo.conversacion_id).toBe(cuerpo.conversacion_id)
    await comprobarRespuesta(segundoCuerpo.texto)
    await page.reload()
    await expect(page.getByLabel('Periodo', { exact: true })).toHaveValue('365d')
    await comprobarRespuesta(segundoCuerpo.texto)
    await page.getByRole('tab', { name: 'Paneles', exact: true }).click()
    await expect(page.getByRole('tab', { name: 'Paneles', exact: true })).toHaveAttribute('aria-selected', 'true')
    await page.getByRole('tab', { name: 'Consultas de datos', exact: true }).click()
    await expect(page.getByRole('tab', { name: 'Consultas de datos', exact: true })).toHaveAttribute('aria-selected', 'true')
    await comprobarRespuesta(cuerpo.texto)
    await page.getByRole('button', { name: 'Nueva conversación', exact: true }).click()
    await expect(page).not.toHaveURL(/conversacion=/)
    await page.getByRole('button', { name: 'Abrir conversación: ' + '¿Qué oficina tiene más incidencias en el periodo seleccionado?'.slice(0, 60), exact: true }).click()
    await comprobarRespuesta(segundoCuerpo.texto)
    // El fallo se simula solo para comprobar recuperación: el resto usa la API real.
    await page.route('**/api/ia/asistente', async (ruta) => {
      await new Promise((resolver) => setTimeout(resolver, 150))
      await ruta.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ mensaje: 'Servicio temporalmente no disponible', codigo: 'no_disponible' }) })
    }, { times: 1 })
    await page.getByLabel('Tu pregunta', { exact: true }).fill('¿Cuáles son las causas más frecuentes?')
    await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
    await expect(page.getByText('La consulta no se completó', { exact: true })).toBeVisible()
    await expect(page.getByLabel('Tu pregunta', { exact: true })).toHaveValue('¿Cuáles son las causas más frecuentes?')
    const reintento = page.waitForResponse((r) => r.url().endsWith('/ia/asistente') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
    const recuperada = await (await reintento).json()
    await comprobarRespuesta(recuperada.texto)
    await expect(page.getByText('La consulta no se completó', { exact: true })).toHaveCount(0)
    await page.screenshot({ path: '../docs/capturas/analisis-asistente.png', fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await page.screenshot({ path: '../docs/capturas/analisis-asistente-movil.png', fullPage: true })
    await page.getByRole('tab', { name: 'Paneles', exact: true }).click()
    await expect(page.getByText('Tickets del periodo', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await page.screenshot({ path: '../docs/capturas/analisis-panel-movil.png', fullPage: true })
    expect(errores).toEqual([])
  } finally {
    for (const id of conversaciones) await request.delete(`/api/ia/asistente/conversaciones/${id}`, { headers })
  }
})

test('Un error del panel ofrece reintento y no presenta ceros como datos reales', async ({ page }) => {
  await entrar(page, 'administrador')
  let fallar = true
  await page.route('**/api/analitica/panel?*', ruta => fallar ? ruta.fulfill({ status: 503, json: { mensaje: 'No disponible', codigo: 'no_disponible' } }) : ruta.continue())
  await page.goto('/panel/analisis')
  await expect(page.getByText('No pudimos cargar el análisis.', { exact: true })).toBeVisible()
  await expect(page.getByText('Tickets del periodo', { exact: true })).toHaveCount(0)
  fallar = false
  await page.getByRole('button', { name: /Reintentar/ }).click()
  await expect(page.getByText('Tickets del periodo', { exact: true })).toBeVisible()
})

test('Chat de datos conserva una edición, regenera y administra el historial con la API real aislada', async ({ page, request }) => {
  const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(acceso.ok()).toBe(true)
  const sesion = await acceso.json()
  const headers = { Authorization: 'Bearer ' + sesion.access_token, 'X-CSRF-Token': sesion.csrf_token }
  let id = ''
  await page.emulateMedia({ reducedMotion: 'reduce' })
  try {
    await entrar(page, 'administrador')
    await page.goto('/panel/analisis?tab=asistente')
    await page.getByLabel('Tu pregunta', { exact: true }).fill('¿Puedes darme un resumen del servicio hoy?')
    const creando = page.waitForResponse(r => r.url().endsWith('/ia/asistente') && r.request().method() === 'POST')
    await page.getByLabel('Tu pregunta', { exact: true }).press('Enter')
    const creada = await creando
    expect(creada.ok()).toBe(true)
    const primerTurno = await creada.json()
    id = primerTurno.conversacion_id
    expect(primerTurno.mensajes).toHaveLength(2)
    for (const linea of primerTurno.texto.split('\n').filter((l: string) => l.trim())) await expect(page.getByRole('log')).toContainText(linea)
    await page.getByRole('button', { name: 'Regenerar respuesta', exact: true }).click()
    await expect.poll(async () => (await request.get('/api/ia/asistente/conversaciones/' + id, { headers })).json().then(c => c.version)).toBe(2)
    await expect(page.getByRole('button', { name: 'Editar pregunta', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Editar pregunta', exact: true }).click()
    await page.getByLabel('Editar tu pregunta', { exact: true }).fill('¿Cuántos tickets están abiertos y cerrados hoy?')
    const editando = page.waitForResponse(r => r.url().endsWith('/' + id + '/editar'))
    await page.getByRole('button', { name: 'Guardar y enviar', exact: true }).click()
    const editada = await editando
    expect(editada.ok()).toBe(true)
    const nuevoTurno = await editada.json()
    expect(nuevoTurno.mensajes).toHaveLength(2)
    expect(nuevoTurno.version).toBe(3)
    await expect(page.getByRole('log')).toContainText('¿Cuántos tickets están abiertos y cerrados hoy?')
    await page.reload()
    await expect(page.getByRole('log')).toContainText('¿Cuántos tickets están abiertos y cerrados hoy?')
    await page.getByRole('button', { name: 'Renombrar conversación: ¿Puedes darme un resumen del servicio hoy?', exact: true }).click()
    await page.getByLabel('Nombre de la conversación', { exact: true }).fill('Lectura de prueba aislada')
    await page.getByRole('button', { name: 'Guardar nombre', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Abrir conversación: Lectura de prueba aislada', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Eliminar conversación: Lectura de prueba aislada', exact: true }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Eliminar conversación', exact: true }).click()
    await expect(page).not.toHaveURL(/conversacion=/)
    expect((await request.get('/api/ia/asistente/conversaciones/' + id, { headers })).status()).toBe(403)
  } finally {
    if (id) await request.delete('/api/ia/asistente/conversaciones/' + id, { headers })
  }
})
