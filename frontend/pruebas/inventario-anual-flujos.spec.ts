import { expect, test } from '@playwright/test'
import path from 'node:path'
import { readFileSync } from 'node:fs'
import { entrar, sinDesbordamiento } from './utilidades'

test.use({ launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }, permissions: ['microphone'] })

test.beforeEach(async ({ page }) => { page.setDefaultTimeout(20_000) })

test('nota de voz limita adjuntos a cinco MB y se detiene a los dos minutos', async ({ page }) => {
  await entrar(page, 'usuario')
  const ticket = await page.evaluate(async () => {
    const lista = await (await fetch('/api/tickets?por_pagina=100', { headers: { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` } })).json()
    return lista.items.find((t: { tiene_chat?: boolean }) => t.tiene_chat)
  })
  await page.goto(`/mis-tickets/${ticket.id}`)
  await page.locator('input[type="file"]').setInputFiles({ name: 'grande.wav', mimeType: 'audio/wav', buffer: Buffer.alloc(5 * 1024 * 1024 + 1) })
  await expect(page.getByText('Cada audio admite hasta 2 minutos y 5 MB', { exact: true })).toBeVisible()
  await expect(page.getByRole('list', { name: 'Adjuntos preparados' })).toHaveCount(0)
  await page.clock.install()
  await page.getByRole('button', { name: 'Grabar audio', exact: true }).click()
  const registroVoz = page.getByRole('status').filter({ hasText: /^Grabando \d+:\d{2}$/ })
  await expect(registroVoz).toBeVisible()
  // Signal detection can take more than two seconds on a busy machine. Check
  // elapsed recording time instead of requiring an already elapsed time window.
  await expect.poll(async () => {
    const tiempo = /Grabando (\d+):(\d{2})/.exec(await registroVoz.textContent() ?? '')
    return tiempo ? Number(tiempo[1]) * 60 + Number(tiempo[2]) : 0
  }).toBeGreaterThanOrEqual(1)
  await page.clock.fastForward(120_100)
  await expect(page.getByRole('button', { name: 'Grabar audio', exact: true })).toBeVisible()
  await expect(page.getByRole('list', { name: 'Adjuntos preparados' }).locator('audio')).toBeVisible()
})

test('audio detecta un micrófono sin señal y evita enviar una nota silenciosa', async ({ page }) => {
  await entrar(page, 'usuario')
  const ticket = await page.evaluate(async () => {
    const headers = { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` }
    const lista = await (await fetch('/api/tickets?por_pagina=100', { headers })).json()
    return lista.items.find((t: { tiene_chat?: boolean }) => t.tiene_chat)
  })
  await page.goto(`/mis-tickets/${ticket.id}`)
  await page.evaluate(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      const contexto = new AudioContext()
      const destino = contexto.createMediaStreamDestination()
      const fuente = contexto.createConstantSource()
      fuente.offset.value = 0
      fuente.connect(destino); fuente.start()
      return destino.stream
    }
  })
  await page.getByRole('button', { name: 'Grabar audio', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: /Grabando 0:0[12]/ })).toBeVisible()
  await page.getByRole('button', { name: 'Detener grabación', exact: true }).click()
  await expect(page.getByText('No se detectó sonido. Elige otro micrófono o revisa que no esté silenciado.', { exact: true })).toBeVisible()
  await expect(page.getByRole('list', { name: 'Adjuntos preparados' })).toHaveCount(0)
})

test('presentación del equipo distingue estado operativo y disponibilidad de cada dato', async ({ page }) => {
  await entrar(page, 'administrador')
  const id = await page.evaluate(async () => {
    const lista = await (await fetch('/api/activos?por_pagina=1', { headers: { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` } })).json()
    return lista.items[0].id
  })
  await page.route(`**/api/activos/${id}`, async ruta => {
    const r = await ruta.fetch()
    const datos = await r.json()
    await ruta.fulfill({ json: { ...datos, tipo: 'Monitor', estado: 'OPERATIVO', marca: 'DELL', modelo: 'Valor anterior excluido', codigo_patrimonial: null, observaciones: null, campos: { ...datos.campos, marca: { estado: 'completo', valor: 'DELL' }, modelo: { estado: 'no_aplica', valor: 'Valor anterior excluido' }, codigo_patrimonial: { estado: 'pendiente', valor: null }, observaciones: { estado: 'no_disponible', valor: null } } } })
  })
  await page.goto(`/panel/equipos/${id}`)
  const disponibilidad = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Disponibilidad de los datos', exact: true }) })
  for (const [campo, estado] of [['Marca', 'Dato registrado'], ['Modelo', 'No aplica'], ['Código patrimonial', 'Pendiente'], ['Observaciones', 'No disponible']]) {
    const fila = disponibilidad.getByRole('listitem').filter({ hasText: campo })
    await expect(fila.getByText(estado, { exact: true })).toBeVisible()
    expect(await fila.locator('svg').count()).toBeGreaterThanOrEqual(2)
  }
  await expect(page.locator('main')).not.toContainText('Valor anterior excluido')
  await expect(page.getByText('Operativo', { exact: true }).first()).toBeVisible()
  await page.screenshot({ path: '../docs/capturas/equipo-presentacion-profesional.png', fullPage: true })
  await page.getByRole('button', { name: 'Cambiar a tema oscuro', exact: true }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  await sinDesbordamiento(page, 'Ficha y disponibilidad de equipo en móvil')
  await page.getByRole('button', { name: 'Editar equipo', exact: true }).click()
  await expect(page.getByRole('combobox', { name: 'Disponibilidad: Modelo', exact: true })).toHaveValue('no_aplica')
})

test('importación anual recupera una respuesta perdida sin recargar ni duplicar', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.goto('/panel/inventario-anual')
  await expect(page.getByRole('button', { name: 'Nueva campaña', exact: true })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'Verificación física', exact: true })).toHaveCount(0)
  await page.getByLabel('Año del inventario', { exact: true }).fill('2038')
  await page.getByLabel('Archivo Excel o CSV').setInputFiles(path.resolve('pruebas/fixtures/inventario-2026.xlsx'))
  await page.route('**/api/campanas/anual/importar', async ruta => {
    const cabeceras = ruta.request().headers()
    const guardado = await page.request.post(ruta.request().url(), { headers: { Authorization: cabeceras.authorization, 'X-CSRF-Token': cabeceras['x-csrf-token'] }, multipart: { anio: '2038', archivo: { name: 'inventario-2026.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: readFileSync('pruebas/fixtures/inventario-2026.xlsx') } } })
    expect(guardado.status(), await guardado.text()).toBe(201)
    await ruta.fulfill({ status: 502, json: { mensaje: 'Respuesta perdida después de guardar' } })
  }, { times: 1 })
  await page.getByRole('button', { name: 'Registrar inventario anual', exact: true }).click()
  await expect(page.getByRole('table').getByText('Pantalla anual', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Año y versión del inventario').locator('option:checked')).toContainText('2038')
  await expect(page.getByText('Revisa el archivo', { exact: true })).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await sinDesbordamiento(page, 'Inventario anual')
})

test('equipo abre en presentación, permite editar y confirma descartar cambios', async ({ page }) => {
  await entrar(page, 'administrador')
  const equipo = await page.evaluate(async () => {
    const lista = await (await fetch('/api/activos?por_pagina=100', { headers: { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` } })).json()
    return lista.items.find((e: { codigo_patrimonial?: string; direccion_ip?: string; direccion_mac?: string }) => !e.codigo_patrimonial && !e.direccion_ip && !e.direccion_mac)
  })
  await page.goto(`/panel/equipos/${equipo.id}`)
  await expect(page.getByRole('heading', { name: 'Información del equipo', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar cambios', exact: true })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Disponibilidad de los datos', exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: /^Disponibilidad:/ })).toHaveCount(0)
  await page.getByRole('button', { name: 'Editar equipo', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Guardar cambios', exact: true })).toBeVisible()
  await page.getByLabel('Observaciones', { exact: true }).fill('Cambio sin guardar para comprobar la presentación')
  await page.getByRole('button', { name: 'Volver a presentación', exact: true }).click()
  const dialogo = page.getByRole('dialog', { name: 'Descartar cambios', exact: true })
  await expect(dialogo).toBeVisible()
  await dialogo.getByRole('button', { name: 'Descartar cambios', exact: true }).click()
  await expect(page.getByText('Cambio sin guardar para comprobar la presentación', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Editar equipo', exact: true }).click()
  await page.getByLabel('Observaciones', { exact: true }).fill('Presentación comprobada después de guardar')
  const guardado = page.waitForResponse(r => r.url().endsWith(`/activos/${equipo.id}`) && r.request().method() === 'PATCH')
  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  expect((await guardado).status()).toBe(200)
  await expect(page.getByRole('button', { name: 'Editar equipo', exact: true })).toBeVisible()
  await expect(page.getByText('Presentación comprobada después de guardar', { exact: true })).toBeVisible()
  await page.screenshot({ path: '../docs/capturas/equipo-presentacion.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await sinDesbordamiento(page, 'Presentación del equipo')
})


test('chat envía fotos y notas de voz sin texto, y soporte las recibe', async ({ page }) => {
  await page.addInitScript(() => {
    const Nativo = window.MediaRecorder
    window.MediaRecorder = class extends Nativo {
      constructor(stream: MediaStream, opciones?: MediaRecorderOptions) {
        super(stream, opciones)
        ;(window as unknown as { bitrateVoz: number | undefined }).bitrateVoz = opciones?.audioBitsPerSecond
      }
    }
  })
  await entrar(page, 'usuario')
  const ticket = await page.evaluate(async () => {
    const csrf = document.cookie.split('; ').find(p => p.startsWith('ma_csrf='))?.split('=')[1] || ''
    const r = await fetch('/api/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}`, 'X-CSRF-Token': csrf }, body: JSON.stringify({ tipo_problema: 'Prueba de multimedia', persona: { es_para_mi: true } }) })
    if (r.status !== 201) throw new Error(await r.text())
    return (await r.json()).ticket
  })
  await page.goto(`/mis-tickets/${ticket.id}`)
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF1cAAAAASUVORK5CYII=', 'base64')
  await page.locator('input[type="file"]').setInputFiles({ name: 'foto-chat.png', mimeType: 'image/png', buffer: png })
  const preparados = page.getByRole('list', { name: 'Adjuntos preparados' })
  await expect(preparados.getByText('foto-chat.webp', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Grabar audio', exact: true }).click()
  await expect.poll(() => page.evaluate(() => (window as unknown as { bitrateVoz: number }).bitrateVoz)).toBe(64000)
  await expect.poll(() => page.getByRole('meter', { name: 'Nivel del micrófono' }).getAttribute('value')).not.toBe('0')
  await expect(page.getByRole('status').filter({ hasText: /Grabando 0:0[12]/ })).toBeVisible()
  await page.getByRole('button', { name: 'Detener grabación', exact: true }).click()
  await expect(preparados.locator('li')).toHaveCount(2)
  const amplitud = await preparados.locator('audio').evaluate(async elemento => {
    const audio = new AudioContext()
    try {
      const contenido = await (await fetch((elemento as HTMLAudioElement).src)).arrayBuffer()
      const decodificado = await audio.decodeAudioData(contenido)
      let pico = 0
      for (const valor of decodificado.getChannelData(0)) pico = Math.max(pico, Math.abs(valor))
      return pico
    } finally { await audio.close() }
  })
  expect(amplitud).toBeGreaterThan(0.001)
  const respuesta = page.waitForResponse(r => r.url().endsWith(`/tickets/${ticket.id}/mensajes`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  const r = await respuesta
  expect(r.status(), await r.text()).toBe(201)
  expect(r.request().postDataJSON().cuerpo).toBe('')
  expect(r.request().postDataJSON().adjuntos).toHaveLength(2)
  await expect(page.getByRole('img', { name: 'Foto adjunta al mensaje', exact: true })).toBeVisible()
  await expect(page.locator('audio[aria-label="Audio adjunto"]')).toBeVisible()
  await page.reload()
  await expect.poll(() => page.locator('audio[aria-label="Audio adjunto"]').evaluate((e) => (e as HTMLAudioElement).readyState)).toBeGreaterThan(0)
  await page.locator('audio[aria-label="Audio adjunto"]').evaluate((e) => (e as HTMLAudioElement).play())
  await expect.poll(() => page.locator('audio[aria-label="Audio adjunto"]').evaluate((e) => (e as HTMLAudioElement).currentTime)).toBeGreaterThan(0)
  await page.context().clearCookies()
  await page.evaluate(() => sessionStorage.clear())
  await entrar(page, 'administrador')
  await page.goto(`/panel/tickets/${ticket.id}`)
  await expect(page.getByRole('img', { name: 'Foto adjunta al mensaje', exact: true })).toBeVisible()
  await expect(page.locator('audio[aria-label="Audio adjunto"]')).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles({ name: 'respuesta-foto.png', mimeType: 'image/png', buffer: png })
  await expect(page.getByRole('list', { name: 'Adjuntos preparados' }).getByText('respuesta-foto.webp')).toBeVisible()
  await page.getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('img', { name: 'Foto adjunta al mensaje', exact: true })).toHaveCount(2)
  await page.setViewportSize({ width: 390, height: 844 })
  await sinDesbordamiento(page, 'Chat con audio y fotos')
})
