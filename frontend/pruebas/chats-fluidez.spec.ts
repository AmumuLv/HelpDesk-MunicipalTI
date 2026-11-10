import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'

type Mensaje = { rol: 'user' | 'assistant'; texto: string; fuentes?: string[] }
type Chat = 'datos' | 'ti'
type Muestra = { tiempo: number; posicion: number; altura: number; escribiendo: boolean }
type Muestreo = { activo: boolean; muestras: Muestra[] }

const ID_DATOS = 'aaaaaaaaaaaaaaaaaaaaaaaa'
const ID_TI = 'bbbbbbbbbbbbbbbbbbbbbbbb'
const PREGUNTAS = [
  '¿Puedes darme un resumen del servicio?',
  '¿Qué oficina tiene más incidencias en el periodo seleccionado?',
  '¿Qué zona tiene más tickets?',
  '¿Qué técnico está disponible ahora?',
  '¿Cuáles son las causas más frecuentes?',
]
const RESPUESTA = Array.from({ length: 28 }, (_, i) => `Resultado ${i + 1}. Los tickets del servicio se revisan con los datos registrados. Cada oficina conserva su historial y sus plazos de atención.`).join('\n\n') + '\n\nFin de la respuesta de prueba.'
const erroresPorPagina = new WeakMap<Page, string[]>()

test.beforeEach(({ page }) => {
  const errores: string[] = []
  erroresPorPagina.set(page, errores)
  page.on('pageerror', error => errores.push(error.message))
})
test.afterEach(({ page }) => { expect(erroresPorPagina.get(page)).toEqual([]) })

// Toda petición de API y todo socket quedan simulados. La exclusión del pathname
// permite cargar /src/api/*.ts desde Vite sin tratarlos como peticiones al backend.
async function preparar(page: Page, conHistorial = false) {
  const anteriores: Mensaje[] = conHistorial ? Array.from({ length: 14 }, (_, i) => [
    { rol: 'user' as const, texto: `Consulta anterior ${i + 1}` },
    { rol: 'assistant' as const, texto: `Resultado anterior ${i + 1}. ` + 'Información guardada para leer con calma. '.repeat(16) },
  ]).flat() : []
  const usuario = { id: 'persona', nombre: 'Ana Prueba', email: 'ana@example.invalid', rol: 'administrador', permisos: [], csrf_token: 'csrf-simulado', institucion: 'Municipalidad Provincial de Casma' }
  const conversaciones = {
    datos: { id: ID_DATOS, titulo: 'Lectura del servicio', mensajes: [...anteriores], version: 1, actualizado_en: '2026-11-09T12:00:00Z' },
    ti: { id: ID_TI, titulo: 'Lectura del inventario', mensajes: [...anteriores], consumo: { consultas: anteriores.length / 2, tokens: 0, conTokens: 0 }, limite: 100 },
  }
  const solicitudes: { chat: Chat; cuerpo: Record<string, unknown> }[] = []
  let liberarRespuesta!: () => void
  const respuestaPendiente = new Promise<void>(resolve => { liberarRespuesta = resolve })
  await page.addInitScript(() => sessionStorage.setItem('ma.acceso', 'sesion-simulada'))
  await page.routeWebSocket('**/api/ws/**', () => {})
  await page.route('**/api/**', async ruta => {
    const url = new URL(ruta.request().url())
    if (!url.pathname.startsWith('/api/')) { await ruta.continue(); return }
    const camino = url.pathname.replace(/^\/api/, '')
    let json: unknown
    if (camino === '/auth/sesion') json = usuario
    else if (camino === '/mi-perfil') json = { ...usuario, tiene_foto: false }
    else if (camino === '/publico/configuracion') json = { institucion: usuario.institucion }
    else if (camino === '/notificaciones') json = { items: [], no_leidas: 0 }
    else if (camino === '/configuracion/estado-ia') json = { disponible: false }
    else if (camino === '/ia/chatbot/estado') json = { configurado: true, proveedor: 'Groq', limite_consultas: 100 }
    else if (camino === '/analitica/equipos-prediccion') json = { familias: [] }
    else if (camino === '/ia/asistente/preguntas') json = { preguntas: PREGUNTAS }
    else if (camino === '/ia/asistente/conversaciones') json = { items: conversaciones.datos.mensajes.length ? [conversaciones.datos] : [] }
    else if (camino === `/ia/asistente/conversaciones/${ID_DATOS}`) json = conversaciones.datos
    else if (camino === '/ia/chatbot/conversaciones') json = { items: conversaciones.ti.mensajes.length ? [conversaciones.ti] : [] }
    else if (camino === `/ia/chatbot/conversaciones/${ID_TI}`) json = conversaciones.ti
    else if (camino === '/ia/asistente' || camino === '/ia/chatbot') {
      const chat: Chat = camino === '/ia/asistente' ? 'datos' : 'ti'
      const cuerpo = ruta.request().postDataJSON() as Record<string, unknown>
      solicitudes.push({ chat, cuerpo })
      await respuestaPendiente
      const conversacion = conversaciones[chat]
      conversacion.mensajes.push({ rol: 'user', texto: String(cuerpo.pregunta) }, { rol: 'assistant', texto: RESPUESTA })
      if (chat === 'datos') {
        conversaciones.datos.version++
        const complemento = {
          fuentes: ['ranking_oficinas'], periodo: '30d', explicacion: 'Recuento de tickets de las oficinas.',
          tabla: { columnas: [{ clave: 'oficina', titulo: 'Oficina' }, { clave: 'total', titulo: 'Tickets' }], filas: [{ oficina: 'Soporte TI', total: 12 }, { oficina: 'Caja', total: 4 }] },
        }
        Object.assign(conversacion.mensajes.at(-1)!, complemento)
        json = { texto: RESPUESTA, conversacion_id: ID_DATOS, mensajes: conversacion.mensajes, version: conversaciones.datos.version, ...complemento }
      } else {
        conversaciones.ti.consumo.consultas++
        json = { disponible: true, texto: RESPUESTA, fuentes: [], conversacion_id: ID_TI, consumo: conversaciones.ti.consumo, limite: 100 }
      }
    } else if (['/tickets', '/zonas', '/oficinas', '/equipo-ti/tecnicos'].includes(camino)) json = { items: [], total: 0, pagina: 1, por_pagina: 20, total_paginas: 1 }
    if (json === undefined) { await ruta.fulfill({ status: 404, json: { mensaje: `Ruta simulada no disponible: ${camino}` } }); return }
    await ruta.fulfill({ json })
  })
  return { solicitudes, liberarRespuesta }
}

async function abrir(page: Page, chat: Chat, conHistorial = false) {
  if (chat === 'datos') {
    await page.goto(`/panel/analisis?tab=asistente${conHistorial ? `&conversacion=${ID_DATOS}` : ''}`)
  } else {
    await page.goto('/panel/tickets')
    await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
    await expect(page.getByLabel('Tu consulta al asistente TI', { exact: true })).toBeEnabled()
  }
  const registro = page.getByRole('log', { name: chat === 'datos' ? 'Conversación con el asistente' : 'Conversación con el asistente TI', exact: true })
  await expect(registro).toBeVisible()
  if (conHistorial) await expect(registro).toContainText('Resultado anterior 14.')
  return {
    registro,
    entrada: page.getByLabel(chat === 'datos' ? 'Tu pregunta' : 'Tu consulta al asistente TI', { exact: true }),
    respuesta: registro.locator(chat === 'datos' ? '.datos-result .datos-answer' : '.ti-answer-progressive').last(),
  }
}

async function iniciarMuestreo(registro: Locator) {
  await registro.evaluate(elemento => {
    const estado: Muestreo = { activo: true, muestras: [] }
    ;(window as unknown as { __chatMuestreo: Muestreo }).__chatMuestreo = estado
    const tomar = (tiempo: number) => {
      estado.muestras.push({ tiempo, posicion: elemento.scrollTop, altura: elemento.scrollHeight, escribiendo: Boolean(elemento.querySelector('.datos-answer[aria-busy="true"], .ti-answer-progressive[aria-busy="true"]')) })
      if (estado.activo) requestAnimationFrame(tomar)
    }
    requestAnimationFrame(tomar)
  })
}

async function terminarMuestreo(page: Page) {
  return page.evaluate(() => {
    const estado = (window as unknown as { __chatMuestreo: Muestreo }).__chatMuestreo
    estado.activo = false
    return estado.muestras
  })
}

async function comprobarAcentoVerde(elemento: Locator) {
  const color = await elemento.evaluate(e => getComputedStyle(e).color)
  const [rojo, verde, azul] = color.match(/[\d.]+/g)!.slice(0, 3).map(Number)
  expect(verde, color).toBeGreaterThan(rojo)
  expect(verde, color).toBeGreaterThan(azul)
}

async function comprobarAcentoAzul(elemento: Locator) {
  const color = await elemento.evaluate(e => getComputedStyle(e).color)
  const [rojo, verde, azul] = color.match(/[\d.]+/g)!.slice(0, 3).map(Number)
  expect(azul, color).toBeGreaterThan(rojo)
  expect(azul, color).toBeGreaterThan(verde)
}

for (const chat of ['datos', 'ti'] as const) {
  test(`${chat}: la respuesta se escribe a la vista y sigue el final sin saltos al enviar`, async ({ page }) => {
    const estado = await preparar(page)
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setViewportSize({ width: 1440, height: 1000 })
    const { registro, entrada, respuesta } = await abrir(page, chat)
    expect(await registro.evaluate(e => e.scrollTop)).toBeLessThanOrEqual(1)
    await entrada.fill('Resume los tickets del servicio')
    await iniciarMuestreo(registro)
    await entrada.press('Enter')
    await expect.poll(() => estado.solicitudes.length).toBe(1)
    if (chat === 'ti') await expect(registro.locator('.ti-message-pending')).toContainText('Resume los tickets del servicio')
    else await expect(registro).toContainText('Consultando tus registros')
    estado.liberarRespuesta()
    await expect(respuesta).toHaveAttribute('aria-busy', 'true')
    await expect.poll(async () => (await respuesta.innerText()).length).toBeGreaterThan(30)
    const parcial = await respuesta.innerText()
    expect(parcial.length).toBeLessThan(RESPUESTA.length)
    expect(parcial).not.toContain('Fin de la respuesta de prueba.')
    if (chat === 'datos') {
      await expect(registro.getByRole('figure', { name: 'Comparación de resultados', exact: true })).toHaveCount(0)
      await expect(registro.getByText('De dónde sale esta respuesta', { exact: true })).toHaveCount(0)
    }
    await expect(respuesta).toHaveAttribute('aria-busy', 'false')
    await expect(respuesta).toContainText('Fin de la respuesta de prueba.')
    if (chat === 'datos') {
      await expect(registro.getByRole('figure', { name: 'Comparación de resultados', exact: true })).toBeVisible()
      await expect(registro.getByText('De dónde sale esta respuesta', { exact: true })).toBeVisible()
    }
    await expect.poll(() => registro.evaluate(e => e.scrollHeight - e.clientHeight - e.scrollTop)).toBeLessThan(50)
    const muestras = await terminarMuestreo(page)
    const saltos = muestras.slice(1).map((muestra, i) => Math.abs(muestra.posicion - muestras[i].posicion))
    const resumen = {
      maximoSalto: Math.max(...saltos),
      maximoDuranteEscritura: Math.max(0, ...saltos.filter((_, i) => muestras[i + 1].escribiendo)),
      maximoTrasEscritura: Math.max(0, ...saltos.filter((_, i) => !muestras[i + 1].escribiendo && muestras.slice(0, i + 1).some(m => m.escribiendo))),
      cuadros: muestras.length,
      posicionesDistintas: new Set(muestras.map(m => Math.round(m.posicion))).size,
    }
    await test.info().attach(`scroll-${chat}.json`, { body: JSON.stringify({ resumen, muestras }, null, 2), contentType: 'application/json' })
    console.log(`${chat}: salto máximo ${resumen.maximoSalto}px; durante escritura ${resumen.maximoDuranteEscritura}px; al terminar ${resumen.maximoTrasEscritura}px; ${resumen.cuadros} cuadros.`)
    expect(muestras.length).toBeGreaterThan(20)
    expect(Math.max(...saltos), 'El mayor cambio de scrollTop entre cuadros debe ser menor de 300 px').toBeLessThan(300)
    expect(new Set(muestras.map(m => Math.round(m.posicion))).size).toBeGreaterThan(8)
    expect(muestras.at(-1)!.posicion).toBeGreaterThan(150)
    expect(estado.solicitudes.map(s => s.chat)).toEqual([chat])
  })

  test(`${chat}: leer mensajes anteriores detiene el seguimiento durante la escritura`, async ({ page }) => {
    const estado = await preparar(page, true)
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setViewportSize({ width: 1440, height: 1000 })
    const { registro, entrada, respuesta } = await abrir(page, chat, true)
    await expect.poll(() => registro.evaluate(e => e.scrollHeight - e.clientHeight - e.scrollTop)).toBeLessThan(50)
    await entrada.fill('Continúa el resumen')
    await entrada.press('Enter')
    await expect.poll(() => estado.solicitudes.length).toBe(1)
    estado.liberarRespuesta()
    await expect(respuesta).toHaveAttribute('aria-busy', 'true')
    await expect.poll(async () => (await respuesta.innerText()).length).toBeGreaterThan(30)
    await registro.hover()
    await page.mouse.wheel(0, -600)
    await registro.evaluate(e => { e.scrollTop = 0; e.dispatchEvent(new Event('scroll')) })
    await iniciarMuestreo(registro)
    const parcial = (await respuesta.innerText()).length
    await expect.poll(async () => (await respuesta.innerText()).length).toBeGreaterThan(parcial + 40)
    expect(await registro.evaluate(e => e.scrollTop)).toBeLessThan(2)
    await expect(respuesta).toHaveAttribute('aria-busy', 'false')
    const muestras = await terminarMuestreo(page)
    expect(Math.max(...muestras.map(m => m.posicion))).toBeLessThan(2)
    await expect(registro).toContainText('Fin de la respuesta de prueba.')
    expect(estado.solicitudes).toHaveLength(1)
    if (chat === 'ti') {
      await page.getByRole('button', { name: 'Cerrar', exact: true }).click()
      await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
      await expect(registro).toContainText('Fin de la respuesta de prueba.')
      expect(await registro.evaluate(e => e.scrollTop)).toBeLessThan(2)
      await expect(respuesta).toHaveAttribute('aria-busy', 'false')
    }
  })

  test(`${chat}: movimiento reducido muestra la respuesta completa sin esperar la escritura`, async ({ page }) => {
    const estado = await preparar(page)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const { entrada, respuesta } = await abrir(page, chat)
    await entrada.fill('Resume el servicio')
    await entrada.press('Enter')
    await expect.poll(() => estado.solicitudes.length).toBe(1)
    estado.liberarRespuesta()
    await expect(respuesta).toContainText('Fin de la respuesta de prueba.', { timeout: 1000 })
    await expect(respuesta).toHaveAttribute('aria-busy', 'false')
    expect(estado.solicitudes).toHaveLength(1)
  })
}

for (const tema of ['claro', 'oscuro']) {
  for (const ancho of [320, 1440]) {
    test(`datos: bienvenida y sugerencias legibles en ${tema}, ${ancho}px`, async ({ page }) => {
      const estado = await preparar(page)
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await page.setViewportSize({ width: ancho, height: 1000 })
      const { registro, entrada, respuesta } = await abrir(page, 'datos')
      await page.evaluate(t => { document.documentElement.dataset.tema = t }, tema)
      await expect(registro.getByRole('heading', { name: 'Tus datos, fáciles de entender', exact: true })).toBeVisible()
      expect(await registro.evaluate(e => e.scrollTop)).toBeLessThanOrEqual(1)
      const bienvenida = await registro.getByRole('heading', { name: 'Tus datos, fáciles de entender', exact: true }).boundingBox()
      const cajaRegistro = await registro.boundingBox()
      expect(bienvenida!.y).toBeGreaterThanOrEqual(cajaRegistro!.y)
      expect(bienvenida!.y + bienvenida!.height).toBeLessThanOrEqual(cajaRegistro!.y + cajaRegistro!.height)
      const opcion = registro.getByRole('button', { name: PREGUNTAS[0], exact: true })
      await expect(opcion).toContainText('Cómo está el servicio')
      const cajaOpcion = await opcion.boundingBox()
      expect(cajaOpcion!.y).toBeGreaterThanOrEqual(cajaRegistro!.y)
      expect(cajaOpcion!.y).toBeLessThan(cajaRegistro!.y + cajaRegistro!.height)
      await comprobarAcentoVerde(opcion.locator('.datos-suggestion-icon'))
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      expect((await new AxeBuilder({ page }).include('.datos-lab').analyze()).violations).toEqual([])
      await page.screenshot({ path: test.info().outputPath(`datos-inicio-${tema}-${ancho}.png`), fullPage: true })
      await opcion.click()
      await expect.poll(() => estado.solicitudes.length).toBe(1)
      estado.liberarRespuesta()
      await expect(respuesta).toContainText('Fin de la respuesta de prueba.')
      const sugerencias = page.getByRole('button', { name: 'Preguntas sugeridas', exact: true })
      await expect(sugerencias).toHaveAttribute('aria-expanded', 'false')
      const id = await sugerencias.getAttribute('aria-controls')
      expect(id).toBeTruthy()
      await sugerencias.click()
      await expect(sugerencias).toHaveAttribute('aria-expanded', 'true')
      const region = page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })
      await expect(region).toHaveAttribute('id', id!)
      await expect(region.getByRole('button', { name: PREGUNTAS[0], exact: true })).toBeVisible()
      const cajaRegion = await region.boundingBox()
      const cajaEntrada = await entrada.boundingBox()
      expect(cajaRegion!.y + cajaRegion!.height).toBeLessThanOrEqual(cajaEntrada!.y + 1)
      expect(await region.evaluate(e => e.scrollWidth <= e.clientWidth + 1)).toBe(true)
      await expect(entrada).toBeVisible()
      expect((await new AxeBuilder({ page }).include('.datos-lab').analyze()).violations).toEqual([])
      await page.screenshot({ path: test.info().outputPath(`datos-sugerencias-${tema}-${ancho}.png`), fullPage: true })
      await sugerencias.click()
      await expect(region).not.toBeVisible()
      expect(estado.solicitudes[0].cuerpo.pregunta).toBe(PREGUNTAS[0])
    })

    test(`ti: bienvenida, acento azul y formulario legibles en ${tema}, ${ancho}px`, async ({ page }) => {
      await preparar(page)
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await page.setViewportSize({ width: ancho, height: 1000 })
      const { registro, entrada } = await abrir(page, 'ti')
      await page.evaluate(t => { document.documentElement.dataset.tema = t }, tema)
      const dialogo = page.getByRole('dialog')
      await expect(registro.getByRole('heading', { name: /Tu siguiente idea/ })).toBeVisible()
      expect(await registro.evaluate(e => e.scrollTop)).toBeLessThanOrEqual(1)
      const bienvenida = await registro.getByRole('heading', { name: /Tu siguiente idea/ }).boundingBox()
      const cajaRegistro = await registro.boundingBox()
      expect(bienvenida!.y).toBeGreaterThanOrEqual(cajaRegistro!.y)
      expect(bienvenida!.y + bienvenida!.height).toBeLessThanOrEqual(cajaRegistro!.y + cajaRegistro!.height)
      const opcion = registro.getByRole('button', { name: /Resolver una duda/ })
      await expect(opcion).toBeVisible()
      const cajaOpcion = await opcion.boundingBox()
      expect(cajaOpcion!.y).toBeGreaterThanOrEqual(cajaRegistro!.y)
      expect(cajaOpcion!.y).toBeLessThan(cajaRegistro!.y + cajaRegistro!.height)
      await comprobarAcentoAzul(registro.locator('.ti-chat-welcome em'))
      expect(await dialogo.evaluate(e => e.scrollWidth <= e.clientWidth + 1)).toBe(true)
      expect(await dialogo.evaluate(e => e.scrollHeight <= e.clientHeight + 1)).toBe(true)
      await expect(entrada).toBeInViewport()
      await expect(dialogo.getByRole('button', { name: 'Enviar', exact: true })).toBeInViewport()
      expect((await new AxeBuilder({ page }).include('.ti-chat').analyze()).violations).toEqual([])
      await page.screenshot({ path: test.info().outputPath(`ti-inicio-${tema}-${ancho}.png`) })
    })
  }
}
