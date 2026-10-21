import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

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
    await expect(log.getByText(cuerpo.texto, { exact: true })).toBeVisible()
    await expect(log.locator('.datos-sources')).toContainText('Tickets por oficina')
    await page.getByLabel('Tu pregunta', { exact: true }).fill('¿Qué técnico está disponible ahora?')
    const segunda = page.waitForResponse((r) => r.url().endsWith('/ia/asistente') && r.request().method() === 'POST')
    await page.getByLabel('Tu pregunta', { exact: true }).press('Control+Enter')
    const segundoCuerpo = await (await segunda).json()
    expect(segundoCuerpo.conversacion_id).toBe(cuerpo.conversacion_id)
    await expect(log.getByText(segundoCuerpo.texto, { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByLabel('Periodo', { exact: true })).toHaveValue('365d')
    await expect(log.getByText(segundoCuerpo.texto, { exact: true })).toBeVisible()
    await page.getByRole('tab', { name: 'Paneles', exact: true }).click()
    await page.getByRole('tab', { name: 'Consultas de datos', exact: true }).click()
    await expect(log.getByText(cuerpo.texto, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Nueva conversación', exact: true }).click()
    await expect(page).not.toHaveURL(/conversacion=/)
    await page.getByLabel('Abrir conversación').selectOption(cuerpo.conversacion_id)
    await expect(log.getByText(segundoCuerpo.texto, { exact: true })).toBeVisible()
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
    await expect(log.getByText(recuperada.texto, { exact: true })).toBeVisible()
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
