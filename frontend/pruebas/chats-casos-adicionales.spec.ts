import { expect, test, type Page } from '@playwright/test'

type Mensaje = { rol: 'user' | 'assistant'; texto: string; fuentes?: string[] }
type Solicitud = { ruta: string; metodo: string; cuerpo: Record<string, unknown> }
const ID = 'aaaaaaaaaaaaaaaaaaaaaaaa'
const TI = 'bbbbbbbbbbbbbbbbbbbbbbbb'
const PREGUNTAS = [
  '¿Puedes darme un resumen del servicio?',
  '¿Qué oficina tiene más incidencias en el periodo seleccionado?',
  '¿Qué zona tiene más tickets?',
  '¿Cuáles son las causas más frecuentes?',
  '¿Cuántos tickets abiertos y cerrados hay?',
  '¿Cuántos equipos tenemos?',
  '¿Qué técnico está disponible ahora?',
  '¿Para qué sirve este asistente?',
]
const INICIALES: Mensaje[] = [
  { rol: 'user', texto: 'Consulta original' },
  { rol: 'assistant', texto: 'Resultado original: 4 tickets.\n\n```text\ndato de prueba\n```', fuentes: ['metricas_generales'] },
  { rol: 'user', texto: '¿Y los cerrados?' },
  { rol: 'assistant', texto: 'Resultado posterior: 2 tickets cerrados.', fuentes: ['estados_tickets'] },
]

// Solo datos ficticios y respuestas simuladas; no se contacta al proveedor ni al Mongo operativo.
async function preparar(page: Page, opciones: { fallo?: 'editar' | 'regenerar' | 'vacia'; retrasar?: boolean; renombradoEnConflicto?: boolean; rol?: 'administrador' | 'tecnico'; permisos?: string[] } = {}) {
  const solicitudes: Solicitud[] = []
  const lecturas: string[] = []
  const conversacion = { id: ID, titulo: 'Consulta guardada', mensajes: structuredClone(INICIALES), version: 1, actualizado_en: '2026-11-09T12:00:00Z' }
  const chatbot = { id: TI, titulo: 'Consulta TI', mensajes: [] as Mensaje[], consumo: { consultas: 0, tokens: 0, conTokens: 0 }, limite: 15 }
  let liberar!: () => void
  const pendiente = new Promise<void>(resolve => { liberar = resolve })
  let falloUsado = false
  let conflictoUsado = false
  await page.addInitScript(() => sessionStorage.setItem('ma.acceso', 'sesion-simulada'))
  await page.routeWebSocket('**/api/ws/**', () => {})
  await page.route('**/api/**', async ruta => {
    const url = new URL(ruta.request().url())
    if (!url.pathname.startsWith('/api/')) { await ruta.continue(); return }
    const camino = url.pathname.replace(/^\/api/, '')
    const metodo = ruta.request().method()
    const cuerpo = (ruta.request().postDataJSON() || {}) as Record<string, unknown>
    if (metodo !== 'GET') solicitudes.push({ ruta: camino, metodo, cuerpo })
    else lecturas.push(camino)
    let json: unknown
    const usuario = { id: 'persona', nombre: 'Ana Prueba', email: 'ana@example.invalid', rol: opciones.rol ?? 'administrador', permisos: opciones.permisos ?? [], csrf_token: 'csrf-simulado', institucion: 'Municipalidad Provincial de Casma' }
    if (camino === '/auth/sesion') json = usuario
    else if (camino === '/mi-perfil') json = { ...usuario, tiene_foto: false }
    else if (camino === '/publico/configuracion') json = { institucion: usuario.institucion }
    else if (camino === '/notificaciones') json = { items: [], no_leidas: 0 }
    else if (camino === '/configuracion/estado-ia') json = { disponible: false }
    else if (camino === '/ia/chatbot/estado') json = { configurado: true, proveedor: 'Groq', limite_consultas: 15 }
    else if (camino === '/analitica/equipos-prediccion') json = { familias: [] }
    else if (camino === '/ia/asistente/preguntas') json = { preguntas: PREGUNTAS }
    else if (camino === '/ia/asistente/conversaciones') json = { items: [conversacion] }
    else if (camino === '/ia/chatbot/conversaciones') json = { items: chatbot.mensajes.length ? [chatbot] : [] }
    else if (camino === `/ia/chatbot/conversaciones/${TI}`) json = chatbot
    else if (camino === `/ia/asistente/conversaciones/${ID}`) {
      if (metodo === 'PATCH') {
        if (opciones.renombradoEnConflicto && !conflictoUsado) {
          conflictoUsado = true
          conversacion.version = 2
          conversacion.titulo = 'Título de otra pestaña'
          return ruta.fulfill({ status: 409, json: { mensaje: 'La conversación cambió en otra pestaña.' } })
        }
        conversacion.titulo = String(cuerpo.titulo)
        conversacion.version++
      }
      json = conversacion
    } else if (camino.endsWith('/editar') || camino.endsWith('/regenerar')) {
      const editar = camino.endsWith('/editar')
      if (!falloUsado && opciones.fallo === (editar ? 'editar' : 'regenerar')) {
        falloUsado = true
        return ruta.fulfill({ status: 503, json: { mensaje: 'Lectura temporalmente no disponible.' } })
      }
      if (editar) conversacion.mensajes = [...conversacion.mensajes.slice(0, Number(cuerpo.indice)), { rol: 'user', texto: String(cuerpo.pregunta) }]
      else conversacion.mensajes = conversacion.mensajes.slice(0, -1)
      const respuesta: Mensaje = { rol: 'assistant', texto: editar ? 'Respuesta de la pregunta corregida.' : 'Respuesta regenerada correctamente.', fuentes: ['metricas_generales'] }
      conversacion.mensajes.push(respuesta)
      conversacion.version++
      json = { ...respuesta, conversacion_id: ID, mensajes: conversacion.mensajes, version: conversacion.version }
    } else if (camino === '/ia/asistente' || camino === '/ia/chatbot') {
      if (opciones.retrasar) await pendiente
      if (opciones.fallo === 'vacia' && !falloUsado) {
        falloUsado = true
        return ruta.fulfill({ json: { texto: '   ', conversacion_id: ID, version: 2 } })
      }
      const respuesta: Mensaje = { rol: 'assistant', texto: 'Respuesta comprobada de la consulta.', fuentes: ['metricas_generales'] }
      if (camino === '/ia/asistente') {
        conversacion.mensajes.push({ rol: 'user', texto: String(cuerpo.pregunta) }, respuesta)
        conversacion.version++
        json = { ...respuesta, conversacion_id: ID, mensajes: conversacion.mensajes, version: conversacion.version }
      } else {
        chatbot.mensajes.push({ rol: 'user', texto: String(cuerpo.pregunta) }, respuesta)
        chatbot.consumo.consultas++
        chatbot.consumo.tokens += 35
        chatbot.consumo.conTokens++
        json = { disponible: true, texto: respuesta.texto, fuentes: [], conversacion_id: TI, consumo: chatbot.consumo, limite: 15 }
      }
    } else if (['/tickets', '/zonas', '/oficinas', '/equipo-ti/tecnicos'].includes(camino)) json = { items: [], total: 0, pagina: 1, por_pagina: 20, total_paginas: 1 }
    if (json === undefined) return ruta.fulfill({ status: 404, json: { mensaje: `Ruta simulada no disponible: ${camino}` } })
    await ruta.fulfill({ json })
  })
  return { solicitudes, lecturas, conversacion, liberar }
}

const errores = new WeakMap<Page, string[]>()
test.beforeEach(({ page }) => {
  const lista: string[] = []
  errores.set(page, lista)
  page.on('pageerror', error => lista.push(error.message))
})
test.afterEach(({ page }) => { expect(errores.get(page)).toEqual([]) })

test('un error al editar conserva la rama anterior y el borrador; reintentar reemplaza solo al guardar', async ({ page }) => {
  const estado = await preparar(page, { fallo: 'editar' })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  const log = page.getByRole('log', { name: 'Conversación con el asistente', exact: true })
  await page.getByRole('button', { name: 'Editar pregunta', exact: true }).first().click()
  await page.getByLabel('Editar tu pregunta', { exact: true }).fill('Pregunta corregida')
  await page.getByRole('button', { name: 'Guardar y enviar', exact: true }).click()
  await expect(page.getByText('La consulta no se completó', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Editar tu pregunta', { exact: true })).toHaveValue('Pregunta corregida')
  await expect(log).toContainText('Resultado posterior: 2 tickets cerrados.')
  expect(estado.conversacion.mensajes).toEqual(INICIALES)
  await page.getByRole('button', { name: 'Reintentar consulta', exact: true }).click()
  await expect(log).toContainText('Respuesta de la pregunta corregida.')
  await expect(log).not.toContainText('Resultado posterior:')
  expect(estado.conversacion.mensajes.map(m => m.texto)).toEqual(['Pregunta corregida', 'Respuesta de la pregunta corregida.'])
  expect(estado.solicitudes.filter(s => s.ruta.endsWith('/editar')).map(s => s.cuerpo.version)).toEqual([1, 1])
})

test('regenerar conserva la respuesta guardada cuando falla y no duplica turnos al reintentar', async ({ page }) => {
  const estado = await preparar(page, { fallo: 'regenerar' })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  await page.getByRole('button', { name: 'Regenerar respuesta', exact: true }).click()
  await expect(page.getByText('La consulta no se completó', { exact: true })).toBeVisible()
  await expect(page.getByRole('log')).toContainText('Resultado posterior: 2 tickets cerrados.')
  expect(estado.conversacion.mensajes).toEqual(INICIALES)
  await page.getByRole('button', { name: 'Reintentar consulta', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Respuesta regenerada correctamente.')
  await expect(page.getByRole('log')).not.toContainText('Resultado posterior:')
  expect(estado.conversacion.mensajes).toHaveLength(4)
  expect(estado.conversacion.mensajes.slice(0, 3)).toEqual(INICIALES.slice(0, 3))
})

test('Escape cierra las preguntas sugeridas desde el botón que las abre y conserva el foco', async ({ page }) => {
  const estado = await preparar(page)
  await page.goto('/panel/analisis?tab=asistente')
  const boton = page.getByRole('button', { name: 'Preguntas sugeridas', exact: true })
  await boton.click()
  await expect(page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })).toHaveCount(0)
  await expect(boton).toHaveAttribute('aria-expanded', 'false')
  await expect(boton).toBeFocused()
  expect(estado.solicitudes).toHaveLength(0)
})

test('los grupos y ver más muestran preguntas completas y envían únicamente la opción elegida', async ({ page }) => {
  const estado = await preparar(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  await page.getByRole('button', { name: 'Preguntas sugeridas', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })
  await expect(panel.getByRole('button', { name: '¿Cuántos tickets abiertos y cerrados hay?', exact: true })).toHaveCount(0)
  await panel.getByRole('button', { name: 'Ver más preguntas', exact: true }).click()
  await expect(panel.getByRole('button', { name: '¿Cuántos tickets abiertos y cerrados hay?', exact: true })).toBeVisible()
  await panel.getByRole('button', { name: 'Ver menos preguntas', exact: true }).click()
  await expect(panel.getByRole('button', { name: '¿Cuántos tickets abiertos y cerrados hay?', exact: true })).toHaveCount(0)
  await panel.getByRole('button', { name: 'Equipos', exact: true }).click()
  await panel.getByRole('button', { name: '¿Cuántos equipos tenemos?', exact: true }).click()
  await expect(panel).toHaveCount(0)
  await expect(page.getByRole('log')).toContainText('Respuesta comprobada de la consulta.')
  expect(estado.solicitudes.map(s => s.cuerpo.pregunta)).toEqual(['¿Cuántos equipos tenemos?'])
})

test('un portapapeles denegado ofrece una alternativa y no modifica la respuesta', async ({ page }) => {
  const estado = await preparar(page)
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new DOMException('No permitido', 'NotAllowedError')) } })
  })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  await page.getByRole('button', { name: 'Copiar respuesta', exact: true }).first().click()
  await expect(page.getByText('No se pudo copiar. Puedes seleccionar el texto y copiarlo manualmente.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Copiar código', exact: true }).click()
  await expect(page.getByText('No se pudo copiar. Selecciona el código y cópialo manualmente.', { exact: true })).toBeVisible()
  expect(estado.conversacion.mensajes).toEqual(INICIALES)
  expect(estado.solicitudes).toHaveLength(0)
})

for (const chat of ['datos', 'ti'] as const) {
  test(`${chat}: Enter repetido durante una petición no duplica la consulta ni los mensajes`, async ({ page }) => {
    const estado = await preparar(page, { retrasar: true })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto(chat === 'datos' ? `/panel/analisis?tab=asistente&conversacion=${ID}` : '/panel/tickets')
    if (chat === 'ti') await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
    const entrada = page.getByLabel(chat === 'datos' ? 'Tu pregunta' : 'Tu consulta al asistente TI', { exact: true })
    await expect(entrada).toBeEnabled()
    await entrada.fill('Consulta enviada una sola vez')
    await entrada.press('Enter')
    await page.keyboard.press('Enter')
    await expect.poll(() => estado.solicitudes.length).toBe(1)
    await expect(entrada).toBeDisabled()
    estado.liberar()
    const log = page.getByRole('log')
    await expect(log).toContainText('Respuesta comprobada de la consulta.')
    await expect(log.getByText('Consulta enviada una sola vez', { exact: true })).toHaveCount(1)
    expect(estado.solicitudes).toHaveLength(1)
    if (chat === 'ti') await expect(page.getByLabel('Consumo de esta conversación')).toContainText('1 consulta')
  })
}

test('cerrar el chatbot mientras responde conserva el resultado y consumo al volver a abrir', async ({ page }) => {
  const estado = await preparar(page, { retrasar: true })
  await page.goto('/panel/tickets')
  await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
  const entrada = page.getByLabel('Tu consulta al asistente TI', { exact: true })
  await expect(entrada).toBeEnabled()
  await entrada.fill('Consulta mientras cierro')
  await entrada.press('Enter')
  await expect.poll(() => estado.solicitudes.length).toBe(1)
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click()
  const recibida = page.waitForResponse(r => new URL(r.url()).pathname === '/api/ia/chatbot' && r.request().method() === 'POST')
  estado.liberar()
  await recibida
  await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Respuesta comprobada de la consulta.')
  await expect(page.locator('.ti-answer-progressive')).toHaveAttribute('aria-busy', 'false')
  await expect(page.getByLabel('Consumo de esta conversación')).toContainText('1 consulta')
  await expect(entrada).toHaveValue('')
  expect(estado.solicitudes).toHaveLength(1)
})

test('una respuesta interna vacía muestra el error y conserva la pregunta para reintentar', async ({ page }) => {
  const estado = await preparar(page, { fallo: 'vacia' })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  const entrada = page.getByLabel('Tu pregunta', { exact: true })
  await entrada.fill('Resumen del servicio')
  await entrada.press('Enter')
  await expect(page.getByText('La consulta no se completó', { exact: true })).toBeVisible()
  await expect(page.getByText('El asistente no devolvió una respuesta. Puedes reintentar tu pregunta.', { exact: true })).toBeVisible()
  await expect(entrada).toHaveValue('Resumen del servicio')
  await expect(page).not.toHaveURL(/conversacion=/)
  await expect(page.locator('.datos-result')).toHaveCount(0)
  await page.getByRole('button', { name: 'Reintentar consulta', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Respuesta comprobada de la consulta.')
  expect(estado.solicitudes).toHaveLength(2)
  expect(estado.solicitudes[1].cuerpo.solicitud_id).toBe(estado.solicitudes[0].cuerpo.solicitud_id)
})

test('un conflicto al renombrar conserva el nombre escrito y reintenta con la versión actual', async ({ page }) => {
  const estado = await preparar(page, { renombradoEnConflicto: true })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  await page.getByRole('button', { name: 'Renombrar conversación: Consulta guardada', exact: true }).click()
  const nombre = page.getByLabel('Nombre de la conversación', { exact: true })
  await nombre.fill('Balance elegido por mí')
  await page.getByRole('button', { name: 'Guardar nombre', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('La conversación cambió en otra pestaña.')
  await expect(nombre).toHaveValue('Balance elegido por mí')
  await page.getByRole('button', { name: 'Guardar nombre', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Abrir conversación: Balance elegido por mí', exact: true })).toBeVisible()
  const cambios = estado.solicitudes.filter(s => s.metodo === 'PATCH')
  expect(cambios.map(s => s.cuerpo)).toEqual([{ titulo: 'Balance elegido por mí', version: 1 }, { titulo: 'Balance elegido por mí', version: 2 }])
  expect(estado.conversacion.mensajes).toEqual(INICIALES)
})

test('el técnico con permiso de análisis puede consultar datos y utilizar el chatbot TI', async ({ page }) => {
  const estado = await preparar(page, { rol: 'tecnico', permisos: ['tickets.operar', 'analitica.ver'] })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  const pregunta = page.getByLabel('Tu pregunta', { exact: true })
  await expect(pregunta).toBeEnabled()
  await pregunta.fill('Resumen del servicio')
  await pregunta.press('Enter')
  await expect(page.getByRole('log')).toContainText('Respuesta comprobada de la consulta.')
  expect(estado.lecturas).toContain('/ia/asistente/conversaciones')
  await page.goto('/panel/tickets')
  await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
  const chatbot = page.getByLabel('Tu consulta al asistente TI', { exact: true })
  await expect(chatbot).toBeEnabled()
  await chatbot.fill('Cómo preparo mi inventario')
  await chatbot.press('Enter')
  await expect(page.getByRole('log')).toContainText('Respuesta comprobada de la consulta.')
  expect(estado.solicitudes.map(s => s.ruta)).toEqual(['/ia/asistente', '/ia/chatbot'])
})

test('el técnico sin permiso de análisis no carga datos ni historial interno y conserva el chatbot TI', async ({ page }) => {
  const estado = await preparar(page, { rol: 'tecnico', permisos: ['tickets.operar'] })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  await expect(page.getByText('No tienes acceso a esta sección', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Tu pregunta', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Buscar conversaciones', { exact: true })).toHaveCount(0)
  expect(estado.lecturas.filter(ruta => ruta.startsWith('/ia/asistente'))).toEqual([])
  await page.getByRole('button', { name: 'Abrir asistente TI', exact: true }).click()
  const chatbot = page.getByLabel('Tu consulta al asistente TI', { exact: true })
  await expect(chatbot).toBeEnabled()
  await chatbot.fill('Cómo preparo mi inventario')
  await chatbot.press('Enter')
  await expect(page.getByRole('log')).toContainText('Respuesta comprobada de la consulta.')
  expect(estado.solicitudes.map(s => s.ruta)).toEqual(['/ia/chatbot'])
  expect(estado.lecturas.filter(ruta => ruta.startsWith('/ia/asistente'))).toEqual([])
})
