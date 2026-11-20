import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const ID = 'aaaaaaaaaaaaaaaaaaaaaaaa'
const columnas = [{ clave: 'oficina', titulo: 'Oficina' }, { clave: 'total', titulo: 'Equipos' }, { clave: 'faltantes', titulo: 'Datos pendientes' }, { clave: 'porcentaje', titulo: '% de datos faltantes' }]
const oficinas = (pagina: number) => Array.from({ length: 20 }, (_, i) => ({ id: (pagina * 100 + i).toString(16).padStart(24, '0'), oficina: `Oficina municipal de nombre largo ${pagina}-${i}`, total: 100, faltantes: i + 1, porcentaje: i + 1 }))

async function preparar(page: Page, modo: 'oficinas' | 'linea' | 'horarios' = 'oficinas') {
  let mensajes: Record<string, unknown>[] = []
  const consultas: Record<string, unknown>[] = []
  let envios = 0
  await page.addInitScript(() => sessionStorage.setItem('ma.acceso', 'simulada'))
  await page.routeWebSocket('**/api/ws/**', () => {})
  await page.route('**/api/**', async ruta => {
    const pathname = new URL(ruta.request().url()).pathname
    if (!pathname.startsWith('/api/')) return ruta.continue()
    const camino = pathname.slice(4)
    const cuenta = { id: ID, nombre: 'TI de prueba', rol: 'administrador', permisos: {}, csrf_token: 'csrf' }
    let json: unknown
    if (['/auth/sesion', '/mi-perfil'].includes(camino)) json = cuenta
    else if (camino === '/publico/configuracion') json = { institucion: 'Municipalidad de prueba' }
    else if (camino === '/notificaciones') json = { items: [], no_leidas: 0 }
    else if (camino === '/configuracion/estado-ia') json = { disponible: false }
    else if (camino === '/ia/chatbot/estado') json = { configurado: false }
    else if (camino === '/ia/asistente/preguntas') json = { preguntas: [] }
    else if (camino === '/analitica/equipos-prediccion') json = { familias: [] }
    else if (camino === '/ia/asistente/conversaciones') json = { items: [] }
    else if (camino === '/ia/asistente/conversaciones/' + ID) json = { id: ID, titulo: 'Consulta', version: 1, mensajes }
    else if (camino === '/ia/asistente/explorar') {
      const cuerpo = ruta.request().postDataJSON()
      consultas.push(cuerpo)
      const pagina = Number(cuerpo.pagina || 1)
      const detalle = cuerpo.vista === 'detalle'
      json = modo === 'horarios' ? { tabla: { columnas: [{ clave: 'fecha', titulo: 'Fecha' }], filas: [{ fecha: cuerpo.fecha }] }, total: 1, pagina: 1, total_paginas: 1 }
        : { tabla: detalle ? { columnas: [{ clave: 'nombre', titulo: 'Equipo' }, { clave: 'responsable', titulo: 'Responsable' }], filas: [{ nombre: 'Laptop real del desglose', responsable: 'Persona registrada' }] } : { columnas, filas: oficinas(pagina) }, total: detalle ? 1 : 60, pagina, total_paginas: detalle ? 1 : 3 }
    } else if (camino === '/ia/asistente') {
      envios++
      const tabla = modo === 'linea' ? { columnas: [{ clave: 'fecha', titulo: 'Fecha' }, { clave: 'valor', titulo: 'Tickets' }], filas: Array.from({ length: 7 }, (_, i) => ({ fecha: `2026-11-${String(i + 1).padStart(2, '0')}`, valor: i })) }
        : modo === 'horarios' ? { columnas: [{ clave: 'tecnico', titulo: 'Técnico' }, { clave: 'horario', titulo: 'Horario' }], filas: [{ tecnico: 'Técnico registrado', horario: '08:00–12:00' }], fecha_consulta: '2026-11-11', total: 1, exploracion: { herramienta: 'horarios_manana' } }
          : { columnas, filas: oficinas(1), total: 60, exploracion: { herramienta: 'oficinas_datos_pendientes', filtros: { periodo: '30d' }, argumentos: {} } }
      const respuesta = { rol: 'assistant', texto: 'Resultado de datos reales de prueba.', fuentes: ['oficinas_datos_pendientes'], tabla }
      mensajes = [{ rol: 'user', texto: 'Consultar' }, respuesta]
      json = { ...respuesta, conversacion_id: ID, version: 1, mensajes }
    }
    if (json === undefined) return ruta.fulfill({ status: 404, json: { mensaje: 'Sin ruta simulada' } })
    await ruta.fulfill({ json })
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/panel/analisis?tab=asistente')
  await page.getByLabel('Tu pregunta', { exact: true }).fill('Consultar datos de prueba')
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Resultado de datos reales de prueba.')
  return { consultas, envios: () => envios }
}

for (const tema of ['claro', 'oscuro']) for (const ancho of [320, 1440]) {
  test(`veinte barras, tooltip completo, detalle y paginación en ${tema}, ${ancho}px`, async ({ page }) => {
    await page.setViewportSize({ width: ancho, height: 1000 })
    const estado = await preparar(page)
    await page.evaluate(t => { document.documentElement.dataset.tema = t }, tema)
    const grafico = page.getByRole('figure', { name: 'Comparación de resultados' })
    await expect(grafico.getByRole('button')).toHaveCount(20)
    const scroll = grafico.locator('.datos-ranking-scroll')
    expect(await scroll.evaluate(e => e.scrollHeight > e.clientHeight)).toBe(true)
    expect(await scroll.evaluate(e => e.getBoundingClientRect().height)).toBeLessThanOrEqual(281)
    await grafico.getByRole('button').last().hover()
    await expect(grafico.getByRole('tooltip')).toContainText('Oficina municipal de nombre largo 1-19')
    await expect(grafico.getByRole('tooltip')).toContainText('% de datos faltantes: 20')
    await grafico.getByRole('button').last().press('Enter')
    const dialogo = page.getByRole('dialog')
    await expect(dialogo).toContainText('Laptop real del desglose')
    expect(estado.consultas.at(-1)?.oficina_id).toBe(oficinas(1)[19].id)
    await page.keyboard.press('Escape')
    await expect(dialogo).toHaveCount(0)
    const paginas = page.locator('.datos-explorable > .datos-result-pages')
    await paginas.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(paginas).toContainText('página 2 de 3')
    await expect(page.getByRole('log')).toContainText('Oficina municipal de nombre largo 2-19')
    expect(estado.envios()).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    expect((await new AxeBuilder({ page }).include('.datos-lab').analyze()).violations).toEqual([])
  })
}

test('el icono y la serie temporal mantienen tamaños compactos y los puntos abren detalle', async ({ page }) => {
  await preparar(page, 'linea')
  const grafico = page.locator('.datos-timeline')
  expect(await grafico.locator('figcaption svg').evaluate(e => e.getBoundingClientRect().height)).toBeLessThanOrEqual(20)
  expect(await grafico.locator('.datos-chart-line').evaluate(e => e.getBoundingClientRect().height)).toBeLessThanOrEqual(160)
  await grafico.locator('g[role="button"]').last().press('Enter')
  await expect(page.getByRole('dialog')).toContainText('2026-11-07')
})

test('la fecha programada cambia sin crear otra consulta ni consumir proveedor', async ({ page }) => {
  const estado = await preparar(page, 'horarios')
  const fecha = page.getByLabel('Fecha de programación', { exact: true })
  await expect(fecha).toHaveValue('2026-11-11')
  await fecha.fill('2026-11-13')
  await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('2026-11-13')
  expect(estado.consultas[0].fecha).toBe('2026-11-13')
  expect(estado.envios()).toBe(1)
})
