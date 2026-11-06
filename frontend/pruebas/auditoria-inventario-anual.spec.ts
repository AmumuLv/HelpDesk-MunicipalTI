import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { sinDesbordamiento } from './utilidades'

// Estos años y este archivo pertenecen exclusivamente a los escenarios de abajo.
// Cada ejecución elimina sus versiones antes y después: una revisión anterior
// del mismo CSV no debe cambiar cuál versión compara el siguiente ensayo.
const ANIOS_FICTICIOS = new Set([2040, 2041, 2042, 2043, 2044, 2045, 2046])
const sesiones = new WeakMap<Page, Record<string, string>>()
test.describe.configure({ mode: 'serial' })

async function limpiarVersionesFicticias(page: Page, headers: Record<string, string>) {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const respuesta = await page.request.get('/api/campanas/versiones/historico', { headers })
  expect(respuesta.ok()).toBe(true)
  const historial: { items: { id: string; anio: number; fuente?: string; archivo_nombre?: string }[] } = await respuesta.json()
  for (const version of historial.items) {
    if (!ANIOS_FICTICIOS.has(version.anio) || version.fuente !== 'archivo_anual' || version.archivo_nombre !== 'revision.csv') continue
    const borrado = await page.request.delete(`/api/campanas/versiones/${version.id}`, { headers })
    expect(borrado.ok(), await borrado.text()).toBe(true)
  }
}

test.beforeEach(async ({ page }) => {
  expect(process.env.PRUEBA_API_URL).toBe('http://127.0.0.1:18100')
  const respuesta = await page.request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345' } })
  expect(respuesta.status()).toBe(200)
  const sesion = await respuesta.json()
  const headers = { Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token }
  sesiones.set(page, headers)
  await limpiarVersionesFicticias(page, headers)
  await page.addInitScript(token => sessionStorage.setItem('ma.acceso', token), sesion.access_token)
  await page.goto('/panel/inventario-anual', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Inventario anual', exact: true })).toBeVisible()
})

test.afterEach(async ({ page }) => {
  const headers = sesiones.get(page)
  if (headers) await limpiarVersionesFicticias(page, headers)
})

const encabezado = 'AREA;Tipo de equipo;Dispositivo;Código patrimonial;Marca;Nombre Equipo;Estado;Responsable\n'
function csv(filas: string[]) { return { name: 'revision.csv', mimeType: 'text/csv', buffer: Buffer.from(encabezado + filas.join('\n'), 'utf8') } }
function fila(i: number, area = 'SOPORTE') { return `${area};Laptop;Laptop;REV-${i};LENOVO;Portátil revisión ${i};OPERATIVO;Responsable ${i}` }
async function cargar(page: Page, anio: string, filas: string[]) {
  await page.getByLabel('Año del inventario', { exact: true }).fill(anio)
  await page.getByLabel('Archivo Excel o CSV').setInputFiles(csv(filas))
  await page.getByLabel('Zona del CSV', { exact: true }).fill('PALACIO')
  const peticion = page.waitForResponse(r => r.url().endsWith('/campanas/anual/importar') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Registrar inventario anual', exact: true }).click()
  const respuesta = await peticion
  expect(respuesta.status(), await respuesta.text()).toBe(201)
  await expect(page.getByLabel('Año y versión del inventario').locator('option:checked')).toContainText(anio)
  await expect(page.getByRole('button', { name: 'Registrar inventario anual', exact: true })).toBeDisabled()
}

test('validaciones visibles, reintento, plantilla y protección contra doble envío', async ({ page }) => {
  const boton = page.getByRole('button', { name: 'Registrar inventario anual', exact: true })
  await expect(boton).toBeDisabled()
  const plantilla = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar plantilla', exact: true }).click()
  const descargado = await plantilla
  expect(readFileSync((await descargado.path())!).subarray(0, 2).toString()).toBe('PK')
  await page.getByLabel('Archivo Excel o CSV').setInputFiles(csv([fila(101)]))
  await expect(boton).toBeDisabled()
  await page.getByLabel('Zona del CSV', { exact: true }).fill('PALACIO')
  await page.getByLabel('Año del inventario', { exact: true }).fill('1999')
  await expect(boton).toBeDisabled()
  await page.getByLabel('Año del inventario', { exact: true }).fill('2040')
  let intentos = 0
  await page.route('**/api/campanas/anual/importar', async ruta => {
    intentos++
    if (intentos === 1) return ruta.fulfill({ status: 422, json: { mensaje: 'Archivo de revisión rechazado para probar el reintento.' } })
    await ruta.continue()
  })
  await boton.click()
  await expect(page.getByRole('alert')).toContainText('Archivo de revisión rechazado')
  await expect(page.getByLabel('Archivo Excel o CSV')).not.toHaveValue('')
  await boton.dblclick()
  await expect(page.getByRole('table').getByText('Portátil revisión 101', { exact: true })).toBeVisible()
  expect(intentos).toBe(2)
  const archivo = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar inventario', exact: true }).click()
  const guardado = await archivo
  expect(guardado.suggestedFilename()).toBe('inventario-2040.xlsx')
  expect(readFileSync((await guardado.path())!).subarray(0, 2).toString()).toBe('PK')
})

test('paginación, búsqueda, versiones anteriores, comparación y todos sus grupos', async ({ page }) => {
  const originales = Array.from({ length: 31 }, (_, i) => fila(200 + i))
  await cargar(page, '2041', originales)
  const panel = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Inventarios guardados', exact: true }) }).last()
  await expect(panel.getByRole('table').getByText('Portátil revisión 230', { exact: true })).toHaveCount(0)
  await panel.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect(panel.getByRole('table').getByText('Portátil revisión 230', { exact: true })).toBeVisible()
  await panel.getByRole('button', { name: 'Anterior', exact: true }).click()
  await page.getByLabel('Buscar en el año seleccionado', { exact: true }).fill('Portátil revisión 230')
  await expect(panel.getByRole('table').getByText('Portátil revisión 230', { exact: true })).toBeVisible()
  await page.getByLabel('Buscar en el año seleccionado', { exact: true }).fill('No existe este dispositivo')
  await expect(panel.getByRole('table').getByText('Portátil revisión 230', { exact: true })).toHaveCount(0)
  await page.getByLabel('Buscar en el año seleccionado', { exact: true }).fill('')
  await cargar(page, '2042', [fila(200, 'CAJA'), fila(999)])
  await page.getByLabel('Año de origen', { exact: true }).selectOption('2041')
  await page.getByLabel('Año de destino', { exact: true }).selectOption('2042')
  await page.getByRole('button', { name: 'Comparar años', exact: true }).click()
  await page.getByRole('button', { name: 'Altas (1)', exact: true }).click()
  await expect(page.getByText('REV-999 · Portátil revisión 999', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'No aparecen en el destino (30)', exact: true }).click()
  const comparacion = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Comparar inventarios de dos años', exact: true }) }).last()
  await comparacion.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect(comparacion.getByText(/REV-21\d ·/).first()).toBeVisible()
  await page.getByRole('button', { name: 'Traslados (1)', exact: true }).click()
  await expect(page.getByText('PALACIO · SOPORTE → PALACIO · CAJA', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Cambios de datos (1)', exact: true }).click()
  await expect(comparacion.getByText('SOPORTE → CAJA', { exact: false }).first()).toBeVisible()
  await page.getByLabel('Año de origen', { exact: true }).selectOption('2042')
  await expect(page.getByRole('button', { name: 'Comparar años', exact: true })).toBeDisabled()
  const anterior = await page.getByLabel('Año y versión del inventario').locator('option').filter({ hasText: '2041' }).first().getAttribute('value')
  await page.getByLabel('Año y versión del inventario').selectOption(anterior!)
  await expect(panel.getByRole('table').getByText('Portátil revisión 200', { exact: true })).toBeVisible()
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Inventario anual', exact: true })).toBeVisible()
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(tema => document.documentElement.setAttribute('data-tema', tema), tema)
    for (const ancho of [320, 820, 1440]) {
      await page.setViewportSize({ width: ancho, height: 1000 })
      await sinDesbordamiento(page, `Inventario anual ${tema} ${ancho}`)
    }
  }
  await expect(page.getByRole('button', { name: 'Eliminar versión', exact: true })).toBeVisible()
})

test('comparación se actualiza al registrar una nueva revisión del mismo año', async ({ page }) => {
  await page.routeWebSocket('**/api/ws/**', socket => socket.close())
  await cargar(page, '2043', [fila(301)])
  await cargar(page, '2044', [fila(301), fila(302)])
  await page.getByLabel('Año de origen', { exact: true }).selectOption('2043')
  await page.getByLabel('Año de destino', { exact: true }).selectOption('2044')
  await page.getByRole('button', { name: 'Comparar años', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Altas (1)', exact: true })).toBeVisible()
  await cargar(page, '2044', [fila(301), fila(302), fila(303)])
  await page.getByRole('button', { name: 'Comparar años', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Altas (2)', exact: true })).toBeVisible({ timeout: 7000 })
  await cargar(page, '2046', [fila(401)])
  await expect(page.getByLabel('Año de origen', { exact: true })).toHaveValue('2043')
  await expect(page.getByLabel('Año de destino', { exact: true })).toHaveValue('2044')
})

test('CSV recupera una respuesta perdida y permite corregir su zona sin duplicar', async ({ page }) => {
  const contenido = csv([fila(888)])
  await page.getByLabel('Año del inventario', { exact: true }).fill('2045')
  await page.getByLabel('Archivo Excel o CSV').setInputFiles(contenido)
  await page.getByLabel('Zona del CSV', { exact: true }).fill('PALACIO')
  await page.route('**/api/campanas/anual/importar', async ruta => {
    const respuesta = await ruta.fetch()
    expect(respuesta.status()).toBe(201)
    await ruta.fulfill({ status: 502, json: { mensaje: 'Respuesta perdida después de guardar.' } })
  }, { times: 1 })
  await page.getByRole('button', { name: 'Registrar inventario anual', exact: true }).click()
  await expect(page.getByRole('table').getByText('Portátil revisión 888', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Registrar inventario anual', exact: true })).toBeDisabled()
  const primera = await page.getByLabel('Año y versión del inventario').inputValue()
  await page.getByLabel('Archivo Excel o CSV').setInputFiles(contenido)
  await page.getByLabel('Zona del CSV', { exact: true }).fill('SEDE CORREGIDA')
  await page.getByRole('button', { name: 'Registrar inventario anual', exact: true }).click()
  await expect(page.getByRole('table').getByText('SEDE CORREGIDA', { exact: true })).toBeVisible()
  expect(await page.getByLabel('Año y versión del inventario').inputValue()).not.toBe(primera)
  expect(await page.getByLabel('Año y versión del inventario').locator('option').filter({ hasText: '2045' }).count()).toBe(2)
})
