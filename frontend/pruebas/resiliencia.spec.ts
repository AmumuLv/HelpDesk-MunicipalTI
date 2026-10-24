import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test.beforeEach(() => {
  expect(process.env.PRUEBA_API_URL, 'Estas pruebas necesitan la instalación aislada').toBe('http://127.0.0.1:18100')
})

async function formulario(page: import('@playwright/test').Page, texto: string) {
  await entrar(page, 'usuario')
  await page.goto('/reportar')
  await page.getByRole('button', { name: /No enciende/ }).click()
  await page.getByLabel('¿Qué está pasando?').fill(texto)
  await page.getByRole('radio', { name: /Con dificultad/ }).check()
}

test('perder la respuesta después del guardado permite reintentar sin duplicar', async ({ page }) => {
  const texto = `Respuesta perdida ficticia ${Date.now()}`
  await formulario(page, texto)
  const claves: string[] = []
  let ticket = ''
  await page.route('**/api/tickets', async ruta => {
    if (ruta.request().method() !== 'POST') return ruta.continue()
    claves.push(ruta.request().headers()['idempotency-key'])
    const respuesta = await ruta.fetch()
    expect(respuesta.status()).toBe(201)
    const id = (await respuesta.json()).ticket.id
    if (!ticket) { ticket = id; return ruta.abort('connectionreset') }
    expect(id).toBe(ticket)
    return ruta.fulfill({ response: respuesta })
  })
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText(/conexión/i)
  await expect(page.getByLabel('¿Qué está pasando?')).toHaveValue(texto)
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/mis-tickets/${ticket}$`))
  expect(claves).toHaveLength(2)
  expect(claves[0]).toBeTruthy()
  expect(claves[1]).toBe(claves[0])
  const total = await page.evaluate(async texto => {
    const r = await fetch(`/api/tickets?texto=${encodeURIComponent(texto)}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` } })
    if (!r.ok) throw new Error(`Consulta: ${r.status}`)
    return (await r.json()).total
  }, texto)
  expect(total).toBe(1)
})

test('sin red conserva el formulario y se recupera al volver la conexión', async ({ page, context }) => {
  const texto = `Corte de red ficticio ${Date.now()}`
  await formulario(page, texto)
  await context.setOffline(true)
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText(/conexión/i)
  await expect(page.getByLabel('¿Qué está pasando?')).toHaveValue(texto)
  await context.setOffline(false)
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/\/mis-tickets\/[a-f0-9]{24}$/)
  await expect(page.getByRole('heading', { name: new RegExp('Corte de red ficticio') })).toBeVisible()
})

test('un cambio de otra cuenta aparece en el ticket sin recargar', async ({ page, playwright, baseURL }) => {
  const eventos: string[] = []
  const lecturas: string[] = []
  let objetivo = ''
  page.on('websocket', socket => socket.on('framereceived', frame => {
    try { eventos.push(JSON.parse(frame.payload.toString()).tipo) } catch { /* Otros canales no son parte del ensayo. */ }
  }))
  page.on('response', respuesta => {
    if (objetivo && respuesta.url().endsWith(`/api/tickets/${objetivo}`) && respuesta.request().method() === 'GET') {
      void respuesta.json().then(datos => lecturas.push(datos.asunto)).catch(() => {})
    }
  })
  const usuario = await playwright.request.newContext({ baseURL })
  const admin = await playwright.request.newContext({ baseURL })
  try {
    const u = await (await usuario.post('/api/auth/login', { data: { correo: 'usuario1@demo.local', password: 'Demo12345' } })).json()
    const creado = await usuario.post('/api/tickets', { headers: { Authorization: `Bearer ${u.access_token}`, 'X-CSRF-Token': u.csrf_token }, data: { descripcion: `Sincronización real ficticia ${Date.now()}` } })
    expect(creado.status()).toBe(201)
    const ticket = (await creado.json()).ticket.id
    objetivo = ticket
    await entrar(page, 'tecnico')
    const conectado = page.waitForEvent('websocket', socket => socket.url().includes(`/ws/ticket/${ticket}`)).then(socket =>
      socket.waitForEvent('framereceived', { predicate: frame => JSON.parse(frame.payload.toString()).tipo === 'sincronizacion' }))
    await page.goto(`/panel/tickets/${ticket}`)
    await conectado
    const ficha = page.getByLabel('Incidencia reportada', { exact: true })
    await expect(ficha).toBeVisible()
    const a = await (await admin.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })).json()
    const titulo = `Cambio remoto real ${Date.now()}`
    const cambio = await admin.patch(`/api/tickets/${ticket}`, { headers: { Authorization: `Bearer ${a.access_token}`, 'X-CSRF-Token': a.csrf_token }, data: { asunto: titulo } })
    expect(cambio.status()).toBe(200)
    try {
      await expect(ficha.getByRole('heading', { name: titulo, exact: true })).toBeVisible({ timeout: 4_000 })
    } catch (error) {
      throw new Error(`Sincronización: ${JSON.stringify({ eventos, lecturas })}`, { cause: error })
    }
  } finally { await usuario.dispose(); await admin.dispose() }
})

test('la descripción con HTML se presenta como texto y no ejecuta código', async ({ page }) => {
  const texto = '<img src=x onerror="window.ensayoXss=true"> Prueba ficticia de seguridad'
  await formulario(page, texto)
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/\/mis-tickets\/[a-f0-9]{24}$/)
  await expect(page.getByRole('heading').filter({ hasText: /Prueba ficticia|img src/ }).first()).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { ensayoXss?: boolean }).ensayoXss)).toBeUndefined()
  await expect(page.locator('main img[src="x"]')).toHaveCount(0)
})
