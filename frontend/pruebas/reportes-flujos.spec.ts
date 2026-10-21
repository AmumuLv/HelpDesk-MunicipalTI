import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import AxeBuilder from '@axe-core/playwright'
import { entrar } from './utilidades'

for (const tema of ['claro', 'oscuro']) {
  test(`Reportes es accesible y adaptable en tema ${tema}`, async ({ page }, testInfo) => {
    await page.addInitScript(tema => localStorage.setItem('ma.tema', tema), tema)
    await entrar(page, 'administrador')
    await page.goto('/panel/reportes')
    await expect(page.getByText('Contenido del archivo', { exact: true })).toBeVisible()
    for (const tipo of ['tickets', 'inventario', 'carga_equipo', 'analitica', 'auditoria']) {
      await page.getByLabel('Reporte', { exact: true }).selectOption(tipo)
      await expect(page.getByLabel('Desde')).toHaveCount(tipo === 'inventario' ? 0 : 1)
      await expect(page.getByLabel('Zona', { exact: true })).toHaveCount(tipo === 'auditoria' ? 0 : 1)
    }
    await page.getByLabel('Reporte', { exact: true }).selectOption('tickets')
    await page.getByRole('button', { name: 'Hoy', exact: true }).click()
    const hoy = await page.evaluate(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima' }).format(new Date()))
    await expect(page.getByLabel('Desde')).toHaveValue(hoy)
    await expect(page.getByLabel('Hasta')).toHaveValue(hoy)
    for (const width of [1440, 820, 390]) {
      await page.setViewportSize({ width, height: 900 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      await expect(page.getByRole('button', { name: 'Generar archivo', exact: true })).toBeEnabled()
      if (process.env.REVISION_REPORTES_VISUAL === '1' && width !== 820) {
        await page.screenshot({ path: testInfo.outputPath(`reportes-${tema}-${width}.png`), fullPage: true })
      }
    }
    const accesibilidad = await new AxeBuilder({ page }).analyze()
    expect(accesibilidad.violations.filter(v => ['serious', 'critical'].includes(v.impact || ''))).toEqual([])
  })
}

test('Análisis muestra fechas locales, convierte minutos y alinea los controles', async ({ page }) => {
  await entrar(page, 'administrador')
  // Solo el tiempo se fija en 60 para comprobar el ejemplo pedido.
  await page.route('**/api/analitica/panel?periodo=30d', async (ruta) => {
    const respuesta = await ruta.fetch()
    const datos = await respuesta.json()
    datos.kpis.tiempo_medio_resolucion_min = 60
    await ruta.fulfill({ response: respuesta, json: datos })
  })
  await page.goto('/panel/analisis')
  await expect(page.getByText('1 hora', { exact: true })).toBeVisible()
  await expect(page.getByText(/^Periodo: \d{2}\/\d{2}\/\d{4} — \d{2}\/\d{2}\/\d{4}/)).toBeVisible()
  const boton = await page.getByRole('button', { name: 'Actualizar datos', exact: true }).boundingBox()
  const selector = await page.getByLabel('Periodo', { exact: true }).boundingBox()
  expect(Math.abs((boton!.y + boton!.height) - (selector!.y + selector!.height))).toBeLessThanOrEqual(2)
  const tendencia = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Tickets por día', exact: true }) }).last()
  await tendencia.getByText('Ver los datos en tabla', { exact: true }).click()
  await expect(tendencia.getByRole('table').locator('tbody tr').first().locator('td').first()).toHaveText(/^\d{2}\/\d{2}\/\d{4}$/)
})

test('Reportes genera y descarga PDF, Excel por zonas y carga TI con filtros correctos', async ({ page }) => {
  page.setDefaultTimeout(30_000)
  await entrar(page, 'administrador')
  await page.goto('/panel/reportes')
  await expect(page.getByRole('button', { name: 'Imprimir', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Reporte', { exact: true })).toHaveValue('tickets')
  for (const tipo of ['tickets', 'inventario', 'carga_equipo', 'analitica', 'auditoria']) {
    for (const formato of ['pdf', 'excel', 'csv']) {
    await page.getByLabel('Reporte', { exact: true }).selectOption(tipo)
    await page.getByLabel('Formato', { exact: true }).selectOption(formato)
    if (tipo === 'inventario') {
      await expect(page.getByLabel('Desde')).toHaveCount(0)
      await expect(page.getByText('Incluir notas internas', { exact: true })).toHaveCount(0)
    }
    const envio = page.waitForRequest((r) => r.url().endsWith('/exportaciones') && r.method() === 'POST')
    const resultado = page.waitForResponse((r) => r.url().endsWith('/exportaciones') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Generar archivo', exact: true }).click()
    const cuerpo = (await envio).postDataJSON()
    expect(cuerpo.tipo).toBe(tipo)
    expect(cuerpo.formato).toBe(formato)
    if (tipo === 'inventario') expect(cuerpo.filtros.fecha_desde).toBeUndefined()
    const respuesta = await resultado
    expect(respuesta.ok(), await respuesta.text()).toBe(true)
    await expect(page.getByRole('button', { name: 'Generar archivo', exact: true })).toBeEnabled()
    const archivo = await respuesta.json()
    const fila = page.getByRole('listitem').filter({ has: page.locator(`[title="${archivo.nombre}"]`) })
    await expect(fila).toHaveCount(1)
    const descarga = page.waitForEvent('download')
    await fila.getByRole('button', { name: 'Descargar', exact: true }).click()
    const descargado = await descarga
    const ruta = await descargado.path()
    expect(ruta).toBeTruthy()
    const contenido = await readFile(ruta!)
    expect(contenido.length).toBeGreaterThan(formato === 'csv' ? 0 : 100)
    if (formato === 'pdf') expect(contenido.subarray(0, 4).toString()).toBe('%PDF')
    else if (formato === 'excel') expect(contenido.subarray(0, 2).toString()).toBe('PK')
    else expect(contenido.toString('utf8')).toContain(';')
    }
  }
  await page.getByLabel('Reporte', { exact: true }).selectOption('tickets')
  const acceso = await page.evaluate(() => sessionStorage.getItem('ma.acceso'))
  const listado = await (await page.request.get('/api/oficinas', { headers: { Authorization: `Bearer ${acceso}` } })).json()
  const zonas = await page.getByLabel('Zona', { exact: true }).locator('option').evaluateAll((opciones) => opciones.map((o) => (o as HTMLOptionElement).value))
  const oficinaPrueba = listado.items.find((o: { zona_id: string }) => zonas.includes(o.zona_id))
  expect(oficinaPrueba).toBeDefined()
  await page.getByLabel('Zona', { exact: true }).selectOption(oficinaPrueba.zona_id)
  await expect(page.getByLabel('Oficina', { exact: true })).toBeEnabled()
  await page.getByLabel('Oficina', { exact: true }).selectOption(oficinaPrueba.id)
  await page.getByLabel('Zona', { exact: true }).selectOption('')
  await expect(page.getByLabel('Oficina', { exact: true })).toHaveValue('')
  await page.getByLabel('Desde').fill('2026-10-20')
  await page.getByLabel('Hasta').fill('2026-10-01')
  await expect(page.getByRole('button', { name: 'Generar archivo', exact: true })).toBeDisabled()
  await page.getByLabel('Desde').fill('2026-10-01')
  await page.getByLabel('Hasta').fill('2026-10-20')
  await page.route('**/api/exportaciones', async (ruta) => ruta.request().method() === 'POST' ? ruta.fulfill({ status: 503, json: { codigo: 'no_disponible', mensaje: 'No se pudo generar el archivo' } }) : ruta.continue(), { times: 1 })
  await page.getByRole('button', { name: 'Generar archivo', exact: true }).click()
  await expect(page.getByText('No se pudo generar el reporte', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Desde')).toHaveValue('2026-10-01')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.evaluate(() => window.scrollTo(0, 0))
})

test('Auditoría filtra la acción real y traslada el alcance al reporte', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.goto('/panel/auditoria')
  await expect(page.getByRole('heading', { name: 'Auditoría', exact: true })).toBeVisible()
  await expect(page.getByLabel('Acción', { exact: true })).toBeEnabled()
  const respuesta = page.waitForResponse((r) => r.url().includes('/auditoria?') && r.url().includes('accion=kb.crear'))
  await page.getByLabel('Acción', { exact: true }).selectOption('kb.crear')
  const datos = await (await respuesta).json()
  expect(datos.items.every((r: { accion: string }) => r.accion === 'kb.crear')).toBe(true)
  await page.getByRole('link', { name: 'Reporte de auditoría' }).click()
  await expect(page.getByLabel('Reporte', { exact: true })).toHaveValue('auditoria')
  await expect(page.getByLabel('Zona', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Acción: kb.crear', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Quitar filtro', exact: true }).click()
  await expect(page).not.toHaveURL(/accion=/)
})
