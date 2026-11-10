import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const ID = 'aaaaaaaaaaaaaaaaaaaaaaaa'
const TICKET = 'bbbbbbbbbbbbbbbbbbbbbbbb'
const EQUIPO = 'cccccccccccccccccccccccc'
const OPCIONES = [
  ['¿Puedes darme un resumen del servicio?', 'Tickets'],
  ['Muéstrame los tickets sin asignar', 'Tickets'],
  ['Muéstrame los tickets vencidos', 'Tickets'],
  ['¿Cuántos tickets están abiertos y cerrados?', 'Tickets'],
  ['Muéstrame los tickets sin equipo vinculado', 'Tickets'],
  ['¿Qué datos faltan en el inventario?', 'Equipos'],
  ['¿Qué equipos tienen datos por completar?', 'Equipos'],
  ['¿Qué equipos no tienen código patrimonial?', 'Equipos'],
  ['¿Qué inventarios anuales están guardados?', 'Equipos'],
  ['¿Qué técnicos tienen horario mañana?', 'Equipo TI'],
  ['¿Qué guías están mejor valoradas?', 'Entender'],
  ['¿Qué cambios se registraron en el periodo?', 'Entender'],
] as const

async function preparar(page: Page) {
  const enviadas: string[] = []
  const mensajes: Record<string, unknown>[] = []
  await page.addInitScript(() => sessionStorage.setItem('ma.acceso', 'sesion-simulada'))
  await page.routeWebSocket('**/api/ws/**', () => {})
  await page.route('**/api/**', async ruta => {
    const url = new URL(ruta.request().url())
    if (!url.pathname.startsWith('/api/')) return ruta.continue()
    const camino = url.pathname.replace(/^\/api/, '')
    const usuario = { id: 'persona', nombre: 'Ana Prueba', rol: 'administrador', permisos: {}, csrf_token: 'csrf-simulado' }
    let json: unknown
    if (camino === '/auth/sesion' || camino === '/mi-perfil') json = usuario
    else if (camino === '/publico/configuracion') json = { institucion: 'Municipalidad Provincial de Casma' }
    else if (camino === '/notificaciones') json = { items: [], no_leidas: 0 }
    else if (camino === '/configuracion/estado-ia') json = { disponible: false }
    else if (camino === '/ia/chatbot/estado') json = { configurado: false }
    else if (camino === '/analitica/equipos-prediccion') json = { familias: [] }
    else if (camino === '/ia/asistente/preguntas') json = { preguntas: OPCIONES.map(([p]) => p), grupos: Object.fromEntries(OPCIONES) }
    else if (camino === '/ia/asistente/conversaciones') json = { items: mensajes.length ? [{ id: ID, titulo: 'Consulta ampliada', version: enviadas.length }] : [] }
    else if (camino === '/ia/asistente/conversaciones/' + ID) json = { id: ID, titulo: 'Consulta ampliada', version: enviadas.length, mensajes }
    else if (camino === '/ia/asistente') {
      const pregunta = String(ruta.request().postDataJSON().pregunta)
      enviadas.push(pregunta)
      const pendiente = pregunta.includes('tickets')
      const respuesta = {
        rol: 'assistant', texto: pendiente ? 'Hay 2 tickets sin asignar. Se muestran sus códigos y oficina.' : 'Hay 2 equipos con datos por completar. Un dato pendiente no indica una avería.',
        fuentes: [pendiente ? 'tickets_pendientes_detalle' : 'equipos_datos_pendientes'],
        periodo: pendiente ? '30d' : 'Inventario actual', alcance_consulta: 'Oficina: Soporte TI',
        tabla: { columnas: [{ clave: 'nombre', titulo: pendiente ? 'Ticket' : 'Equipo' }, { clave: 'pendientes', titulo: 'Pendientes' }], filas: [{ nombre: pendiente ? 'TKT-PRUEBA' : 'Laptop de prueba', pendientes: 2 }] },
        enlaces: [{ texto: pendiente ? 'TKT-PRUEBA' : 'Laptop de prueba', href: `/panel/${pendiente ? 'tickets/' + TICKET : 'equipos/' + EQUIPO}` },
          { texto: 'Enlace no permitido', href: 'javascript:alert(1)' }],
        analisis: { significado: 'Solo registros de prueba.', revision: 'Abre el registro correspondiente.', limite: 'Listado acotado con total indicado.' },
        seguimientos: pendiente ? [] : ['Muéstrame los tickets sin asignar'],
      }
      mensajes.push({ rol: 'user', texto: pregunta }, respuesta)
      json = { ...respuesta, conversacion_id: ID, mensajes, version: enviadas.length }
    }
    if (json === undefined) return ruta.fulfill({ status: 404, json: { mensaje: 'Ruta simulada no disponible' } })
    await ruta.fulfill({ json })
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  return enviadas
}

for (const tema of ['claro', 'oscuro']) for (const ancho of [320, 1440]) {
  test(`consultas ampliadas: buscar entre grupos y enviar una sola vez en ${tema}, ${ancho}px`, async ({ page }) => {
    const enviadas = await preparar(page)
    await page.setViewportSize({ width: ancho, height: 1000 })
    await page.evaluate(t => { document.documentElement.dataset.tema = t }, tema)
    await page.getByRole('button', { name: 'Preguntas sugeridas', exact: true }).click()
    const panel = page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })
    await panel.getByLabel('Buscar preguntas', { exact: true }).fill('patrimonio')
    await expect(panel.getByRole('button', { name: '¿Qué equipos no tienen código patrimonial?', exact: true })).toBeVisible()
    await panel.getByLabel('Buscar preguntas', { exact: true }).fill('GUÍAS')
    await expect(panel.getByRole('button', { name: '¿Qué guías están mejor valoradas?', exact: true })).toBeVisible()
    await panel.getByLabel('Buscar preguntas', { exact: true }).fill('sin coincidencias')
    await expect(panel.getByText(/No hay preguntas con ese texto/)).toBeVisible()
    await panel.getByRole('button', { name: 'Limpiar', exact: true }).click()
    await panel.getByRole('button', { name: 'Equipos', exact: true }).click()
    await expect(panel.getByRole('button', { name: '¿Qué inventarios anuales están guardados?', exact: true })).toBeVisible()
    await panel.getByRole('button', { name: '¿Qué equipos tienen datos por completar?', exact: true }).click()
    await expect(page.getByRole('log')).toContainText('2 equipos con datos por completar')
    await expect(page.getByRole('link', { name: 'Laptop de prueba', exact: false })).toHaveAttribute('href', '/panel/equipos/' + EQUIPO)
    await expect(page.getByRole('link', { name: /Enlace no permitido/ })).toHaveCount(0)
    expect(enviadas).toEqual(['¿Qué equipos tienen datos por completar?'])
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    expect((await new AxeBuilder({ page }).include('.datos-lab').analyze()).violations).toEqual([])
  })
}

test('las respuestas ampliadas conservan fuentes, tabla, seguimiento e historial al recargar', async ({ page }) => {
  const enviadas = await preparar(page)
  await page.getByRole('button', { name: 'Preguntas sugeridas', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })
  await panel.getByLabel('Buscar preguntas', { exact: true }).fill('por completar')
  await panel.getByRole('button', { name: '¿Qué equipos tienen datos por completar?', exact: true }).click()
  await page.getByText('Ver datos de la respuesta', { exact: true }).click()
  await expect(page.locator('.datos-data table')).toContainText('Laptop de prueba')
  await page.getByText('De dónde sale esta respuesta', { exact: true }).click()
  await expect(page.locator('.datos-proof')).toContainText('Datos pendientes por equipo')
  await page.getByRole('button', { name: 'Muéstrame los tickets sin asignar', exact: true }).click()
  await expect(page.getByRole('link', { name: /TKT-PRUEBA/ })).toHaveAttribute('href', '/panel/tickets/' + TICKET)
  expect(enviadas).toHaveLength(2)
  await page.reload()
  await expect(page.getByRole('log')).toContainText('2 tickets sin asignar')
  await expect(page.getByRole('log')).toContainText('2 equipos con datos por completar')
  await expect(page.locator('.datos-answer[aria-busy="true"]')).toHaveCount(0)
  const descargando = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar conversación', exact: true }).click()
  const descarga = await descargando
  const archivo = await readFile((await descarga.path())!, 'utf8')
  expect(archivo).toContain(`http://127.0.0.1:4321/panel/tickets/${TICKET}`)
  expect(archivo).toContain('Datos pendientes por equipo')
  expect(archivo).not.toContain('javascript:')
})

test('el gráfico de calidad compara datos pendientes y no la cantidad de equipos de la oficina', async ({ page }) => {
  await preparar(page)
  await page.route('**/api/ia/asistente', ruta => ruta.fulfill({ json: {
    conversacion_id: ID, version: 1, texto: 'Revisé los datos pendientes por oficina.',
    fuentes: ['oficinas_datos_pendientes'], periodo: 'Inventario actual',
    tabla: { columnas: [{ clave: 'oficina', titulo: 'Oficina' }, { clave: 'total', titulo: 'Equipos' }, { clave: 'faltantes', titulo: 'Datos pendientes' }],
      filas: [{ oficina: 'Oficina de prueba', total: 100, faltantes: 8 }] },
  } }))
  await page.getByLabel('Tu pregunta', { exact: true }).fill('¿Qué oficinas tienen más datos pendientes?')
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  const grafico = page.getByRole('figure', { name: 'Comparación de resultados' })
  await expect(grafico).toContainText('Comparación · Datos pendientes')
  await expect(grafico.locator('strong')).toHaveText('8')
  await page.getByText('Ver datos de la respuesta', { exact: true }).click()
  await expect(page.locator('.datos-data table')).toContainText('100')
})
