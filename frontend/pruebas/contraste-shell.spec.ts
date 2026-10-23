import { expect, test, type Locator } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { entrar } from './utilidades'

async function contraste(texto: Locator, fondo: Locator) {
  const color = await texto.evaluate((e) => getComputedStyle(e).color)
  const base = await fondo.evaluate((e) => getComputedStyle(e).backgroundColor)
  const luminancia = (valor: string) => {
    const canales = valor.match(/[\d.]+/g)!.slice(0, 3).map(Number).map((n) => { const c = n / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 })
    return canales[0] * 0.2126 + canales[1] * 0.7152 + canales[2] * 0.0722
  }
  const a = luminancia(color)
  const b = luminancia(base)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

for (const tema of ['claro', 'oscuro'] as const) {
  test(`Menú expandido y contraído conserva contraste en tema ${tema}`, async ({ page }) => {
    await page.addInitScript((t) => { localStorage.setItem('ma.tema', t); localStorage.setItem('ma.barra', 'expandida') }, tema)
    await entrar(page, 'administrador')
    await page.goto('/panel/usuarios')
    const nav = page.getByRole('navigation', { name: 'Navegación del panel', exact: true })
    const usuarios = nav.getByRole('link', { name: 'Usuarios', exact: true })
    const escudo = nav.getByRole('img', { name: 'Escudo de Casma · Mesa de Ayuda', exact: true })
    await expect(escudo).toBeVisible()
    expect(await escudo.locator('..').evaluate((e) => getComputedStyle(e).backgroundColor)).toBe('rgba(0, 0, 0, 0)')
    await expect.poll(() => escudo.evaluate((e) => (e as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
    await expect(usuarios).toBeVisible()
    expect(await contraste(usuarios, nav)).toBeGreaterThanOrEqual(4.5)
    const tabla = page.getByRole('table')
    await expect(tabla).toBeVisible()
    const relieve = await tabla.evaluate((e) => { const caja = e.parentElement!; const s = getComputedStyle(caja); return { sombra: s.boxShadow, borde: s.borderTopWidth } })
    expect(relieve.sombra).not.toBe('none')
    expect(parseFloat(relieve.borde)).toBeGreaterThanOrEqual(1)
    await page.getByRole('button', { name: 'Reducir el menú a iconos', exact: true }).click()
    for (const enlace of await nav.getByRole('link').all()) {
      if (await enlace.isVisible()) expect(await contraste(enlace.locator('svg'), nav)).toBeGreaterThanOrEqual(4.5)
    }
    await usuarios.hover()
    const tooltip = page.getByRole('tooltip', { name: 'Usuarios', exact: true })
    await expect(tooltip).toBeVisible()
    expect(await contraste(tooltip, tooltip.locator('..'))).toBeGreaterThanOrEqual(4.5)
    await page.mouse.move(500, 150)
    const tickets = nav.getByRole('button', { name: 'Tickets', exact: true })
    await tickets.hover()
    await expect(page.getByRole('tooltip', { name: 'Tickets', exact: true })).toBeVisible()
    await tickets.click()
    const opciones = page.getByRole('dialog', { name: 'Opciones de Tickets', exact: true })
    await expect(opciones).toBeVisible()
    const abiertos = opciones.getByRole('link', { name: 'Abiertos', exact: true })
    expect(await contraste(abiertos, opciones)).toBeGreaterThanOrEqual(4.5)
    await mkdir('../docs/muestras-contraste', { recursive: true })
    await page.screenshot({ path: `../docs/muestras-contraste/menu-${tema}.png` })
    await abiertos.click()
    await expect(page).toHaveURL(/\/panel\/tickets$/)
    await expect(page.getByRole('heading', { name: 'Abiertos', exact: true })).toBeVisible()
    await expect(opciones).toHaveCount(0)
    await page.getByRole('button', { name: 'Ampliar el menú', exact: true }).click()
    await expect(nav.getByRole('link', { name: 'Usuarios', exact: true })).toBeVisible()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('button', { name: 'Abrir el menú', exact: true }).click()
    await expect.poll(() => nav.evaluate(el => el.getBoundingClientRect().left)).toBe(0)
    await expect(usuarios).toBeVisible()
    expect(await contraste(usuarios, nav)).toBeGreaterThanOrEqual(4.5)
    await usuarios.click()
    await expect(page).toHaveURL(/\/panel\/usuarios$/)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
