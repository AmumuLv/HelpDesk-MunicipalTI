import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'

type Mensaje = { rol: 'user' | 'assistant'; texto: string; fuentes?: string[]; periodo?: string; alcance_consulta?: string; tabla?: unknown }
type Conversacion = { id: string; titulo: string; mensajes: Mensaje[]; version: number; actualizado_en: string }
const ID = 'aaaaaaaaaaaaaaaaaaaaaaaa'
const OTRO = 'bbbbbbbbbbbbbbbbbbbbbbbb'
const erroresPorPagina = new WeakMap<Page, string[]>()
test.beforeEach(({ page }) => {
  const errores: string[] = []
  erroresPorPagina.set(page, errores)
  page.on('pageerror', error => errores.push(error.message))
})
test.afterEach(({ page }) => { expect(erroresPorPagina.get(page)).toEqual([]) })
const RESPUESTA = '**Resultado comprobado:** hay 12 tickets.\n\n- Soporte TI: 8\n- Caja: 4\n\nConsulta `SLA` para revisar los plazos.\n\n```sql\nSELECT total FROM tickets;\n```\n\n| Oficina | Tickets |\n| --- | --- |\n| Soporte TI | 8 |\n| Caja | 4 |\n\n<script>window.__inseguro = true</script>\n\n<img src=x onerror="window.__inseguro=true">\n\n[Enlace inseguro](javascript:alert(1))'

// Intercepta toda la API y los sockets: ningún caso modifica la instalación real.
async function preparar(page: Page, opciones: { larga?: boolean; fallo?: boolean; conflicto?: boolean } = {}) {
  const conversaciones = new Map<string, Conversacion>([
    [ID, { id: ID, titulo: 'Balance de oficinas', mensajes: [{ rol: 'user', texto: 'Resumen del servicio' }, { rol: 'assistant', texto: RESPUESTA, fuentes: ['metricas_generales'], periodo: '30d', alcance_consulta: 'Todas las oficinas' }], version: 1, actualizado_en: '2026-11-08T15:00:00Z' }],
    [OTRO, { id: OTRO, titulo: 'Inventario de impresoras', mensajes: [{ rol: 'user', texto: 'Cuántos equipos tenemos' }, { rol: 'assistant', texto: 'Hay 4 impresoras activas.', fuentes: ['resumen_inventario'] }], version: 1, actualizado_en: '2026-11-07T15:00:00Z' }],
  ])
  const solicitudes: { metodo: string; ruta: string; cuerpo: Record<string, unknown> }[] = []
  const copias: string[] = []
  await page.exposeFunction('registrarCopiaDePrueba', (texto: string) => { copias.push(texto) })
  await page.addInitScript(() => {
    sessionStorage.setItem('ma.acceso', 'sesion-simulada')
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: (texto: string) => (window as unknown as { registrarCopiaDePrueba: (texto: string) => Promise<void> }).registrarCopiaDePrueba(texto) } })
  })
  await page.routeWebSocket('**/api/ws/**', () => {})
  let intentos = 0
  const usuario = { id: 'persona', nombre: 'Ana Prueba', email: 'ana@example.invalid', rol: 'administrador', permisos: [], csrf_token: 'csrf-simulado', institucion: 'Municipalidad Provincial de Casma' }
  await page.route('**/api/**', async ruta => {
    const url = new URL(ruta.request().url())
    if (!url.pathname.startsWith('/api/')) { await ruta.continue(); return }
    const camino = url.pathname.replace(/^\/api/, '')
    const metodo = ruta.request().method()
    const cuerpo = (ruta.request().postDataJSON() || {}) as Record<string, unknown>
    if (metodo !== 'GET') solicitudes.push({ metodo, ruta: camino, cuerpo })
    let json: unknown
    if (camino === '/auth/sesion') json = usuario
    else if (camino === '/publico/configuracion') json = { institucion: usuario.institucion }
    else if (camino === '/notificaciones') json = { items: [], no_leidas: 0 }
    else if (camino === '/mi-perfil') json = { ...usuario, tiene_foto: false }
    else if (camino === '/configuracion/estado-ia') json = { disponible: false }
    else if (camino === '/ia/chatbot/estado') json = { configurado: false }
    else if (camino === '/analitica/equipos-prediccion') json = { familias: [] }
    else if (camino === '/ia/asistente/preguntas') json = { preguntas: ['¿Puedes darme un resumen del servicio?', '¿Qué oficina tiene más incidencias en el periodo seleccionado?'] }
    else if (camino === '/ia/asistente/conversaciones') json = { items: [...conversaciones.values()].map(({ id, titulo, actualizado_en }) => ({ id, titulo, actualizado_en })) }
    else if (camino.startsWith('/ia/asistente/conversaciones/')) {
      const id = camino.split('/')[4]
      const chat = conversaciones.get(id)
      if (!chat) return ruta.fulfill({ status: 404, json: { mensaje: 'Conversación no encontrada.' } })
      if (metodo === 'GET') json = chat
      else if (metodo === 'DELETE') { conversaciones.delete(id); json = { mensaje: 'Conversación eliminada.' } }
      else if (metodo === 'PATCH') { chat.titulo = String(cuerpo.titulo); chat.version++; json = { id, titulo: chat.titulo, version: chat.version } }
      else if (camino.endsWith('/regenerar') || camino.endsWith('/editar')) {
        if (camino.endsWith('/editar')) {
          chat.mensajes = chat.mensajes.slice(0, Number(cuerpo.indice))
          chat.mensajes.push({ rol: 'user', texto: String(cuerpo.pregunta) })
        } else chat.mensajes = chat.mensajes.slice(0, -1)
        const respuesta: Mensaje = { rol: 'assistant', texto: camino.endsWith('/editar') ? 'La consulta corregida tiene 5 tickets.' : 'El resultado actualizado tiene 13 tickets.', fuentes: ['metricas_generales'], periodo: '30d' }
        chat.mensajes.push(respuesta)
        chat.version++
        json = { ...respuesta, conversacion_id: id, mensajes: chat.mensajes, version: chat.version }
      }
    } else if (camino === '/ia/asistente') {
      intentos++
      if (opciones.fallo && intentos === 1) return ruta.fulfill({ status: 503, json: { mensaje: 'Error temporal de lectura.', codigo: 'no_disponible' } })
      if (opciones.conflicto && intentos === 1) {
        const chat = conversaciones.get(ID)!
        chat.version++
        chat.mensajes.push({ rol: 'user', texto: 'Consulta de otra pestaña' }, { rol: 'assistant', texto: 'Respuesta de otra pestaña.', fuentes: ['metricas_generales'] })
        return ruta.fulfill({ status: 409, json: { mensaje: 'La conversación cambió en otra pestaña. Vuelve a intentarlo.', codigo: 'conflicto_conversacion' } })
      }
      const id = String(cuerpo.conversacion_id || 'cccccccccccccccccccccccc')
      const chat = conversaciones.get(id) || { id, titulo: String(cuerpo.pregunta), mensajes: [], version: 0, actualizado_en: '2026-11-08T16:00:00Z' }
      const respuesta: Mensaje = { rol: 'assistant', texto: opciones.larga ? 'Este resultado procede de tus registros. '.repeat(100) + 'Fin de la lectura.' : 'La consulta registra 12 tickets en el periodo elegido.', fuentes: ['metricas_generales'], periodo: '30d' }
      chat.mensajes.push({ rol: 'user', texto: String(cuerpo.pregunta) }, respuesta)
      chat.version++
      conversaciones.set(id, chat)
      json = { ...respuesta, conversacion_id: id, mensajes: chat.mensajes, version: chat.version }
    }
    if (json === undefined) return ruta.fulfill({ status: 404, json: { mensaje: `Ruta simulada no disponible: ${camino}` } })
    await ruta.fulfill({ json })
  })
  return { conversaciones, solicitudes, copias }
}

test('historial permite buscar, renombrar y eliminar únicamente la conversación elegida', async ({ page }) => {
  const estado = await preparar(page)
  await page.goto('/panel/analisis?tab=asistente')
  const buscar = page.getByLabel('Buscar conversaciones', { exact: true })
  await buscar.fill('impresoras')
  await expect(page.getByRole('button', { name: 'Abrir conversación: Inventario de impresoras', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Abrir conversación: Balance de oficinas', exact: true })).toHaveCount(0)
  await buscar.clear()
  await page.getByRole('button', { name: 'Abrir conversación: Balance de oficinas', exact: true }).click()
  await page.getByRole('button', { name: 'Renombrar conversación: Balance de oficinas', exact: true }).click()
  await page.getByLabel('Nombre de la conversación', { exact: true }).fill('Balance semanal')
  await page.getByRole('button', { name: 'Guardar nombre', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Abrir conversación: Balance semanal', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Abrir conversación: Balance semanal', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Eliminar conversación: Balance semanal', exact: true }).click()
  expect(estado.conversaciones.has(ID)).toBe(true)
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  expect(estado.conversaciones.has(ID)).toBe(true)
  await page.getByRole('button', { name: 'Eliminar conversación: Balance semanal', exact: true }).click()
  await page.getByRole('button', { name: 'Eliminar conversación', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Abrir conversación: Balance semanal', exact: true })).toHaveCount(0)
  expect(estado.conversaciones.has(ID)).toBe(false)
  expect(estado.conversaciones.has(OTRO)).toBe(true)
  await expect(page).not.toHaveURL(/conversacion=/)
})

test('respuestas muestran Markdown seguro, se pueden copiar y regenerar sin duplicar turnos', async ({ page }) => {
  const estado = await preparar(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  const log = page.getByRole('log', { name: 'Conversación con el asistente' })
  await expect(log.locator('strong').filter({ hasText: 'Resultado comprobado:' })).toBeVisible()
  await expect(log.locator('li')).toHaveCount(2)
  await expect(log.locator('code').filter({ hasText: 'SLA' })).toBeVisible()
  await expect(log.locator('script')).toHaveCount(0)
  await expect(log.locator('img')).toHaveCount(0)
  await expect(log.locator('a[href^="javascript:"]')).toHaveCount(0)
  await expect(log.getByRole('columnheader', { name: 'Oficina', exact: true })).toBeVisible()
  await log.getByRole('button', { name: 'Copiar código', exact: true }).click()
  await expect.poll(() => estado.copias.length).toBe(1)
  expect(estado.copias[0]).toBe('SELECT total FROM tickets;')
  expect(await page.evaluate(() => '__inseguro' in window)).toBe(false)
  await page.getByRole('button', { name: 'Copiar respuesta', exact: true }).click()
  await expect.poll(() => estado.copias.length).toBe(2)
  expect(estado.copias[1]).toContain('Resultado comprobado:')
  const pendienteDescarga = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar conversación', exact: true }).click()
  const descarga = await pendienteDescarga
  expect(descarga.suggestedFilename()).toBe('consulta-datos.md')
  const contenido = await readFile((await descarga.path())!, 'utf-8')
  expect(contenido).toContain('# Balance de oficinas')
  expect(contenido).toContain('Resultado comprobado:')
  expect(contenido).toContain('Indicadores del servicio')
  await page.getByRole('button', { name: 'Regenerar respuesta', exact: true }).click()
  await expect(log).toContainText('El resultado actualizado tiene 13 tickets.')
  expect(estado.conversaciones.get(ID)?.mensajes).toHaveLength(2)
  expect(estado.solicitudes.filter(s => s.ruta.endsWith('/regenerar'))).toHaveLength(1)
  await page.reload()
  await expect(log).toContainText('El resultado actualizado tiene 13 tickets.')
  await expect(log).not.toContainText('Resultado comprobado:')
})

test('editar una pregunta reemplaza la rama posterior y conserva los filtros', async ({ page }) => {
  const estado = await preparar(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  await page.getByRole('button', { name: 'Editar pregunta', exact: true }).first().click()
  await page.getByLabel('Editar tu pregunta', { exact: true }).fill('¿Cuántos tickets hay hoy?')
  await page.getByRole('button', { name: 'Guardar y enviar', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('La consulta corregida tiene 5 tickets.')
  expect(estado.conversaciones.get(ID)?.mensajes).toHaveLength(2)
  expect(estado.conversaciones.get(ID)?.mensajes[0].texto).toBe('¿Cuántos tickets hay hoy?')
  const solicitud = estado.solicitudes.find(s => s.ruta.endsWith('/editar'))!
  expect(solicitud.cuerpo.indice).toBe(0)
  expect(solicitud.cuerpo.filtros).toEqual({ periodo: '30d' })
  expect(solicitud.cuerpo.version).toBe(1)
})

test('Enter envía, Shift Enter crea una línea y un error conserva el borrador para reintentar', async ({ page }) => {
  const estado = await preparar(page, { fallo: true })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  const entrada = page.getByLabel('Tu pregunta', { exact: true })
  await entrada.fill('Resumen del servicio')
  await entrada.press('Shift+Enter')
  await entrada.press('a')
  await expect(entrada).toHaveValue('Resumen del servicio\na')
  expect(estado.solicitudes).toHaveLength(0)
  await entrada.fill('¿Cuántos tickets hay hoy?')
  await entrada.press('Enter')
  await expect(page.getByText('La consulta no se completó', { exact: true })).toBeVisible()
  await expect(entrada).toHaveValue('¿Cuántos tickets hay hoy?')
  await page.getByRole('button', { name: 'Reintentar consulta', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('La consulta registra 12 tickets')
  const peticiones = estado.solicitudes.filter(s => s.ruta === '/ia/asistente')
  expect(peticiones).toHaveLength(2)
  expect(typeof peticiones[0].cuerpo.solicitud_id).toBe('string')
  expect(peticiones[1].cuerpo.solicitud_id).toBe(peticiones[0].cuerpo.solicitud_id)
  await expect(entrada).toHaveValue('')
})

test('un conflicto entre pestañas recupera el historial sin sobrescribirlo ni perder la pregunta', async ({ page }) => {
  const estado = await preparar(page, { conflicto: true })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  const entrada = page.getByLabel('Tu pregunta', { exact: true })
  await entrada.fill('¿Y ayer?')
  await entrada.press('Enter')
  await expect(page.getByRole('log')).toContainText('Respuesta de otra pestaña.')
  await expect(entrada).toHaveValue('¿Y ayer?')
  await page.getByRole('button', { name: 'Reintentar consulta', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('La consulta registra 12 tickets')
  expect(estado.conversaciones.get(ID)?.mensajes).toHaveLength(6)
  const reintento = estado.solicitudes.filter(s => s.ruta === '/ia/asistente')[1]
  expect(reintento.cuerpo.version).toBe(2)
})

test('detener la escritura muestra la respuesta completa sin otra consulta y mantiene contraste en ambos temas', async ({ page }) => {
  const estado = await preparar(page, { larga: true })
  await page.goto('/panel/analisis?tab=asistente')
  await page.getByLabel('Tu pregunta', { exact: true }).fill('Resumen del servicio')
  await page.getByLabel('Tu pregunta', { exact: true }).press('Enter')
  await page.getByRole('button', { name: 'Detener escritura', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Fin de la lectura.')
  await expect(page.locator('.datos-answer').last()).toHaveAttribute('aria-busy', 'false')
  expect(estado.solicitudes.filter(s => s.ruta === '/ia/asistente')).toHaveLength(1)
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(t => { document.documentElement.dataset.tema = t }, tema)
    for (const ancho of [320, 1440]) {
      await page.setViewportSize({ width: ancho, height: 900 })
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      await expect(page.getByLabel('Tu pregunta', { exact: true })).toBeVisible()
      await page.screenshot({ path: `../.codex-pdf-tools/consultas-chat-${tema}-${ancho}.png`, fullPage: true })
    }
    expect((await new AxeBuilder({ page }).include('.datos-lab').analyze()).violations).toEqual([])
  }
  await page.reload()
  await expect(page.getByRole('log')).toContainText('Fin de la lectura.')
  expect(estado.solicitudes.filter(s => s.ruta === '/ia/asistente')).toHaveLength(1)
})

test('la escritura no arrastra al final a quien está leyendo mensajes anteriores', async ({ page }) => {
  const estado = await preparar(page, { larga: true })
  const chat = estado.conversaciones.get(ID)!
  chat.mensajes = Array.from({ length: 18 }, (_, i) => [
    { rol: 'user' as const, texto: `Consulta anterior ${i + 1}` },
    { rol: 'assistant' as const, texto: `Resultado anterior ${i + 1}. ` + 'Texto de lectura del historial. '.repeat(12), fuentes: ['metricas_generales'] },
  ]).flat()
  await page.goto(`/panel/analisis?tab=asistente&conversacion=${ID}`)
  const log = page.getByRole('log', { name: 'Conversación con el asistente' })
  await expect(log).toContainText('Consulta anterior 18')
  await page.getByLabel('Tu pregunta', { exact: true }).fill('Resumen del servicio')
  await page.getByLabel('Tu pregunta', { exact: true }).press('Enter')
  const respuesta = log.locator('.datos-answer').last()
  await expect(respuesta).toHaveAttribute('aria-busy', 'true')
  await log.evaluate(e => { e.scrollTop = 0; e.dispatchEvent(new Event('scroll')) })
  const longitud = (await respuesta.innerText()).length
  await expect.poll(async () => (await respuesta.innerText()).length).toBeGreaterThan(longitud)
  expect(await log.evaluate(e => e.scrollTop)).toBeLessThan(20)
  await expect(page.getByRole('button', { name: 'Ir al último mensaje', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Ir al último mensaje', exact: true }).click()
  await expect.poll(() => log.evaluate(e => e.scrollHeight - e.scrollTop - e.clientHeight)).toBeLessThan(80)
})

test('en móvil el historial se abre, selecciona una conversación y vuelve a dejar libre el chat', async ({ page }) => {
  await preparar(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/panel/analisis?tab=asistente')
  await expect(page.getByLabel('Buscar conversaciones', { exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: 'Mostrar historial', exact: true }).click()
  await expect(page.getByLabel('Buscar conversaciones', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Abrir conversación: Inventario de impresoras', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Hay 4 impresoras activas.')
  await expect(page.getByLabel('Buscar conversaciones', { exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: 'Mostrar historial', exact: true }).click()
  await page.getByRole('button', { name: 'Ocultar historial', exact: true }).click()
  await expect(page.getByLabel('Buscar conversaciones', { exact: true })).not.toBeVisible()
  await expect(page.getByLabel('Tu pregunta', { exact: true })).toBeEnabled()
})

test('una conversación inexistente muestra el error sin bloquear la navegación ni un chat nuevo', async ({ page }) => {
  const estado = await preparar(page)
  await page.goto('/panel/analisis?tab=asistente&conversacion=dddddddddddddddddddddddd')
  await expect(page.getByText('No pudimos abrir la conversación.', { exact: true })).toBeVisible()
  const nueva = page.getByRole('button', { name: 'Nueva conversación', exact: true })
  await expect(nueva).toBeEnabled()
  await nueva.click()
  await expect(page).not.toHaveURL(/conversacion=/)
  await expect(page.getByRole('heading', { name: 'Tus datos, fáciles de entender', exact: true })).toBeVisible()
  await expect(page.getByLabel('Tu pregunta', { exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Abrir conversación: Inventario de impresoras', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Hay 4 impresoras activas.')
  await expect(page.getByText('No pudimos abrir la conversación.', { exact: true })).toHaveCount(0)
  expect(estado.solicitudes).toHaveLength(0)
})
