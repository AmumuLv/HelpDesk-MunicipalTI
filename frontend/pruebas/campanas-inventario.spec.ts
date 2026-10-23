import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

// La verificación física se comprueba en test_inventario_anual.py.
test('el archivo anual se descarga y solo se elimina después de confirmar', async ({ page }) => {
  page.setDefaultTimeout(20_000)
  await entrar(page, 'administrador')
  const contar = () => page.evaluate(async () => {
    const r = await fetch('/api/activos?por_pagina=1', { headers: { Authorization: `Bearer ${sessionStorage.getItem('ma.acceso')}` } })
    if (!r.ok) throw new Error(`Inventario: ${r.status}`)
    return (await r.json()).total as number
  })
  const total = await contar()
  await page.goto('/panel/inventario-anual')
  await page.getByLabel('Año del inventario', { exact: true }).fill('2057')
  await page.getByLabel('Archivo Excel o CSV').setInputFiles({
    name: `verificacion-${Date.now()}.csv`, mimeType: 'text/csv',
    buffer: Buffer.from('AREA;Tipo de equipo;Dispositivo;Código patrimonial;Nombre Equipo\nSOPORTE;Laptop;Laptop;TEST-ANUAL-57;Laptop ficticia anual\n'),
  })
  await page.getByLabel('Zona del CSV', { exact: true }).fill('Zona ficticia')
  const alta = page.waitForResponse(r => r.url().endsWith('/campanas/anual/importar') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Registrar inventario anual', exact: true }).click()
  const respuesta = await alta
  expect(respuesta.status(), await respuesta.text()).toBe(201)
  const version = await respuesta.json()
  await expect(page.getByLabel('Año y versión del inventario').locator('option:checked')).toContainText('2057')
  await expect(page.getByRole('table').getByText('Laptop ficticia anual', { exact: true })).toBeVisible()
  const descarga = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar inventario', exact: true }).click()
  expect(await (await descarga).failure()).toBeNull()
  expect(await contar()).toBe(total)
  await page.getByRole('button', { name: 'Eliminar versión', exact: true }).click()
  const dialogo = page.getByRole('dialog', { name: 'Eliminar versión del inventario' })
  await dialogo.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await expect(page.getByLabel('Año y versión del inventario')).toHaveValue(version.id)
  await page.getByRole('button', { name: 'Eliminar versión', exact: true }).click()
  const borrado = page.waitForResponse(r => r.url().endsWith(`/campanas/versiones/${version.id}`) && r.request().method() === 'DELETE')
  await dialogo.getByRole('button', { name: 'Eliminar versión', exact: true }).click()
  expect((await borrado).ok()).toBe(true)
  await expect(dialogo).toBeHidden()
  await expect(page.getByLabel('Año y versión del inventario').locator(`option[value="${version.id}"]`)).toHaveCount(0)
  expect(await contar()).toBe(total)
})
