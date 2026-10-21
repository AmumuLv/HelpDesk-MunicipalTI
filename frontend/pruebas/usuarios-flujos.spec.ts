import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test('crear, abrir perfil, editar correo y restablecer contraseña', async ({ page, request }) => {
  page.setDefaultTimeout(15_000)
  await entrar(page, 'administrador')
  await page.goto('/panel/usuarios')
  const nombre = `Revision Usuarios ${Date.now()}`
  const correo = `revision.${Date.now()}@demo.local`
  const correoNuevo = correo.replace('revision.', 'editado.')
  let usuarioId = ''
  try {
    await page.getByRole('button', { name: 'Nuevo usuario', exact: true }).click()
    const dialogo = page.getByRole('dialog')
    await dialogo.getByLabel('Nombre completo').fill(nombre)
    await dialogo.getByLabel('Correo institucional').fill(correo)
    await dialogo.getByLabel('Rol', { exact: true }).selectOption('tecnico')
    await dialogo.screenshot({ path: '../docs/capturas/registro-usuario-redisenado.png' })
    await dialogo.getByLabel(/^Contraseña/).fill('Inicial987!')
    await expect(dialogo.getByRole('button', { name: 'Crear usuario' })).toBeDisabled()
    await dialogo.getByLabel('Confirmar contraseña').fill('Inicial987!')
    const mostrar = dialogo.getByRole('button', { name: 'Mostrar contraseña' }).first()
    await mostrar.click()
    await expect(dialogo.getByLabel(/^Contraseña/)).toHaveAttribute('type', 'text')
    await dialogo.getByLabel('Correo institucional').fill('correo-invalido')
    await dialogo.getByRole('button', { name: 'Crear usuario' }).click()
    await expect(dialogo).toBeVisible()
    expect(await dialogo.getByLabel('Correo institucional').evaluate((campo: HTMLInputElement) => campo.validity.typeMismatch)).toBe(true)
    await dialogo.getByLabel('Correo institucional').fill(correo)
    await dialogo.getByRole('button', { name: 'Crear usuario' }).click()
    await expect(dialogo).toBeHidden()
    await page.getByLabel('Buscar personas').fill(correo)
    await page.getByText(nombre, { exact: true }).filter({ visible: true }).first().click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByLabel('Buscar personas')).toHaveValue(correo)
    await page.getByRole('link', { name: 'Abrir perfil completo' }).click()
    await expect(page).toHaveURL(/\/panel\/usuarios\/[a-f0-9]+$/)
    usuarioId = page.url().split('/').at(-1)!
    await expect(page.getByText(nombre, { exact: true })).toHaveCount(1)
    await expect(page.getByRole('tab', { name: 'Resumen', exact: true })).toHaveAttribute('aria-selected', 'true')
    await page.getByRole('button', { name: 'Editar datos' }).click()
    await expect(page.getByRole('tab', { name: 'Cuenta y edición' })).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    const archivoFoto = page.getByLabel(`Foto de ${nombre}`, { exact: true })
    let fotoAnterior = ''
    for (const color of ['#1d4ed8', '#dc2626']) {
      const imagen = await page.evaluate((fondo) => {
        const lienzo = document.createElement('canvas')
        lienzo.width = 80
        lienzo.height = 80
        const pincel = lienzo.getContext('2d')!
        pincel.fillStyle = fondo
        pincel.fillRect(0, 0, 80, 80)
        return lienzo.toDataURL('image/png').split(',')[1]
      }, color)
      await expect(page.getByRole('button', { name: 'Cambiar la foto', exact: true })).toBeEnabled()
      const subida = page.waitForResponse((respuesta) => respuesta.url().includes(`/usuarios/${usuarioId}/foto`) && respuesta.request().method() === 'POST', { timeout: 60_000 })
      const contenido = Buffer.from(imagen, 'base64')
      await archivoFoto.setInputFiles({ name: 'foto.png', mimeType: 'image/png', buffer: Buffer.concat([contenido, Buffer.alloc(1200000)]) })
      expect((await subida).status()).toBe(200)
      const avatar = page.locator('img[src^="blob:"]').first()
      await expect(avatar).toBeVisible()
      await expect.poll(() => avatar.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(80)
      if (fotoAnterior) await expect(avatar).not.toHaveAttribute('src', fotoAnterior)
      fotoAnterior = (await avatar.getAttribute('src'))!
      await expect(page.getByRole('button', { name: 'Cambiar la foto', exact: true })).toBeEnabled()
    }
    await archivoFoto.setInputFiles({ name: 'grande.png', mimeType: 'image/png', buffer: Buffer.alloc(15 * 1024 * 1024 + 1) })
    await expect(page.getByText(/grande.png.*límite son 15 MB/)).toBeVisible()
    await expect(page.locator('img[src^="blob:"]').first()).toBeVisible()
    await page.getByRole('button', { name: 'Quitar', exact: true }).click()
    await expect(page.locator('img[src^="blob:"]')).toHaveCount(0)
    await page.getByLabel('Correo', { exact: true }).fill('admin@demo.local')
    await page.getByRole('button', { name: 'Guardar datos' }).click()
    await expect(page.getByLabel('Correo', { exact: true })).toHaveAttribute('aria-invalid', 'true')
    await page.screenshot({ path: '../docs/capturas/usuarios-perfil-edicion.png', fullPage: true })
    await page.getByLabel('Correo', { exact: true }).fill(correoNuevo)
    await page.getByLabel('Cargo', { exact: true }).fill('Soporte TI')
    await page.getByRole('button', { name: 'Guardar datos' }).click()
    await expect(page.getByRole('button', { name: 'Modificar información' })).toBeVisible()
    await expect(page.getByText(correoNuevo, { exact: true })).toBeVisible()
    await page.getByLabel(/^Nueva contraseña/).fill('Actualizada987!')
    await page.getByLabel('Confirmar nueva contraseña').fill('Distinta987!')
    await expect(page.getByRole('button', { name: 'Restablecer contraseña', exact: true })).toBeDisabled()
    await page.getByLabel('Confirmar nueva contraseña').fill('Actualizada987!')
    await page.getByRole('button', { name: 'Mostrar contraseña' }).first().click()
    await expect(page.getByLabel(/^Nueva contraseña/)).toHaveAttribute('type', 'text')
    await page.getByRole('button', { name: 'Restablecer contraseña', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Contraseña actualizada' })).toBeVisible()
    const login = (email: string, password: string) => request.post('/api/auth/login', {
      data: { correo: email, password, acceso: 'ti' },
    })
    expect((await login(correo, 'Inicial987!')).status()).toBe(401)
    expect((await login(correoNuevo, 'Inicial987!')).status()).toBe(401)
    expect((await login(correoNuevo, 'Actualizada987!')).status()).toBe(200)
    await page.getByRole('tab', { name: 'Tickets', exact: true }).click()
    await expect(page.getByText('No hay nada que mostrar.', { exact: true }).filter({ visible: true })).toBeVisible()
    // La paginación visual se prueba con 23 registros sin llenar la base con incidencias.
    await page.route(`**/api/usuarios/${usuarioId}/tickets?**`, async (ruta) => {
      const pagina = Number(new URL(ruta.request().url()).searchParams.get('pagina') || 1)
      const items = Array.from({ length: 23 }, (_, indice) => ({
        id: `ticket-${indice}`, codigo: `PRUEBA-${indice + 1}`, asunto: `Incidencia de prueba ${indice + 1}`,
        estado: 'cerrado', prioridad: 'media', creado_en: '2026-10-14T12:00:00Z',
        tecnico_id: usuarioId, reportante_id: null, afectado_id: null,
        activo_id: 'equipo-prueba', activo_nombre: indice === 0 ? 'Mause' : 'Laptop de soporte',
        activo_tipo: indice === 0 ? 'Mouse' : 'Laptop', conjunto_nombre: indice === 0 ? 'Mouse' : null,
        activo_codigo_patrimonial: 'PAT-001',
      })).slice((pagina - 1) * 15, pagina * 15)
      await ruta.fulfill({ json: { items, total: 23, pagina, por_pagina: 15, total_paginas: 2 } })
    })
    await page.reload()
    await page.getByRole('tab', { name: 'Tickets', exact: true }).click()
    const lista = page.getByRole('table')
    const filas = lista.locator('tbody tr')
    await expect(filas).toHaveCount(15)
    expect((await filas.first().boundingBox())?.height).toBeLessThan(125)
    await expect(lista.getByText('Laptop de soporte', { exact: true })).toHaveCount(14)
    await expect(filas.first().getByText('Mouse', { exact: true })).toHaveCount(1)
    await page.getByLabel('Estado', { exact: true }).selectOption('cerrado')
    await expect(page.getByLabel('Estado', { exact: true })).toHaveValue('cerrado')
    await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(lista.getByRole('link').first()).toContainText('PRUEBA-16')
    await expect(filas).toHaveCount(8)
    await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
    for (const ancho of [1440, 390]) {
      await page.setViewportSize({ width: ancho, height: 900 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
      if (ancho === 390) {
        const descripcion = page.locator('[data-encabezado="pagina"] p').first()
        expect((await descripcion.boundingBox())?.width).toBeGreaterThan(300)
      }
    }
    await page.screenshot({ path: '../docs/capturas/usuarios-perfil-tickets-movil.png', fullPage: true })
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.getByRole('tab', { name: 'Cuenta y edición' }).click()
    await page.screenshot({ path: '../docs/capturas/usuarios-perfil-cuenta.png', fullPage: true })
    await page.getByRole('button', { name: 'Desactivar cuenta', exact: true }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Desactivar', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Reactivar cuenta', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Reactivar cuenta', exact: true }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Reactivar', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Desactivar cuenta', exact: true })).toBeVisible()
    await page.route(`**/api/usuarios/${usuarioId}`, async (ruta) => {
      if (ruta.request().method() !== 'GET') return ruta.continue()
      const respuesta = await ruta.fetch()
      await ruta.fulfill({ json: { ...await respuesta.json(), zona_id: 'zona-prueba', zona_nombre: 'PALACIO', equipos_responsable: [
        { id: 'monitor-prueba', nombre: 'Pantalla de soporte', tipo: 'Monitor', codigo_patrimonial: 'PAT-001', estado: 'operativo', oficina_nombre: 'Oficina TI' },
        { id: 'laptop-prueba', nombre: 'Laptop de soporte', tipo: 'Laptop', codigo_patrimonial: 'PAT-002', estado: 'operativo', oficina_nombre: 'Oficina TI' },
      ] } })
    })
    await page.route(/\/api\/zonas(?:\?|$)/, (ruta) => ruta.fulfill({ json: { items: [{ id: 'zona-prueba', nombre: 'PALACIO', color_indice: 1, activo: true }] } }))
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Datos de la persona', exact: true })).toBeVisible()
    await page.screenshot({ path: '../docs/capturas/usuarios-perfil-resumen.png', fullPage: true })
    await page.getByRole('tab', { name: 'Equipos (2)', exact: true }).click()
    const equipos = page.getByRole('list', { name: 'Equipos de esta persona' })
    await expect(equipos.getByRole('listitem')).toHaveCount(2)
    await expect(equipos.getByText('Monitor', { exact: true })).toBeVisible()
    expect((await equipos.getByRole('listitem').first().boundingBox())?.height).toBeLessThan(95)
    const colores = await equipos.getByRole('listitem').evaluateAll((filas) => filas.map((fila) => getComputedStyle(fila.querySelector('svg')!).color))
    expect(colores[0]).not.toBe(colores[1])
    await page.screenshot({ path: '../docs/capturas/usuarios-perfil-equipos.png', fullPage: true })
    await page.goto('/panel/usuarios')
    await page.getByLabel('Buscar personas').fill(correoNuevo)
    await page.getByText(nombre, { exact: true }).filter({ visible: true }).first().click()
    const perfilRapido = page.getByRole('dialog')
    await expect(perfilRapido.locator('footer').getByRole('link', { name: 'Abrir perfil completo' })).toBeVisible()
    await expect(perfilRapido.locator('footer').getByRole('button', { name: 'Desactivar cuenta' })).toBeVisible()
    await expect(perfilRapido.getByLabel('Confirmar nueva contraseña')).toBeHidden()
    await page.screenshot({ path: '../docs/capturas/usuarios-perfil-rapido.png', fullPage: true })
    await perfilRapido.locator('footer').getByRole('button', { name: 'Restablecer contraseña', exact: true }).click()
    await expect(perfilRapido.getByLabel('Confirmar nueva contraseña')).toBeVisible()
  } finally {
    if (usuarioId) {
      const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
      if (login.ok()) {
        const sesion = await login.json()
        await request.post(`/api/usuarios/${usuarioId}/desactivar`, { headers: {
          Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token,
        } })
      }
    }
  }
})
