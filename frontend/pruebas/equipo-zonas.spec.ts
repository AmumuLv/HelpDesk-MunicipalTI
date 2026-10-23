import { expect, test } from '@playwright/test'

test('los perfiles TI abren desde disponibilidad y horarios, y se guarda el horario real', async ({ page }) => {
  await page.goto('/acceder')
  await page.getByLabel('Correo institucional').fill('admin@demo.local')
  await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Equipo TI', exact: true })).toBeVisible()
  const tecnico = await page.evaluate(async () => {
    const cab = { Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso') }
    const lista = await (await fetch('/api/equipo-ti/tecnicos', { headers: cab })).json()
    const persona = lista.items.find((t: { nombre: string }) => t.nombre === 'Jorge Castillo Vera')
    const detalle = await (await fetch(`/api/equipo-ti/${persona.id}`, { headers: cab })).json()
    return { ...persona, horario: detalle.horario }
  })
  await page.goto('/panel/equipo-ti')
  await page.locator(`a[href="/panel/equipo-ti/${tecnico.id}"]`).first().click()
  await expect(page.getByRole('heading', { name: 'Perfil TI', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Horario', exact: true }).click()
  const tarjeta = page.getByRole('form', { name: `Horario de ${tecnico.nombre}`, exact: true })
  await tarjeta.getByRole('button', { name: 'Editar horario', exact: true }).click()
  const [indice, dia] = Object.entries(tecnico.horario.dias).find(([, configuracion]) => {
    const c = configuracion as { libre: boolean; tramos: unknown[] }
    return !c.libre && c.tramos.length
  })! as [string, { tramos: { entrada: string; salida: string }[] }]
  const nombreDia = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][Number(indice)]
  const entrada = tarjeta.getByRole('textbox', { name: `Entrada ${nombreDia} 1`, exact: true })
  await expect(entrada).toHaveValue(dia.tramos[0].entrada)
  // Guardar el mismo horario permite comprobar persistencia sin dejar datos de prueba.
  await entrada.fill(dia.tramos[0].entrada === '09:00' ? '08:00' : '09:00')
  await entrada.fill(dia.tramos[0].entrada)
  const guardado = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith(`/api/equipo-ti/${tecnico.id}/horario`))
  await tarjeta.getByRole('button', { name: 'Guardar horario', exact: true }).click()
  expect((await guardado).status()).toBe(200)
  await page.reload()
  await page.getByRole('tab', { name: 'Horario', exact: true }).click()
  await tarjeta.getByRole('button', { name: 'Editar horario', exact: true }).click()
  await expect(tarjeta.getByRole('textbox', { name: `Entrada ${nombreDia} 1`, exact: true })).toHaveValue(dia.tramos[0].entrada)
  await page.locator(`a[href="/panel/usuarios/${tecnico.id}"]`).click()
  await expect(page.getByRole('heading', { name: 'Datos de la persona', exact: true })).toBeVisible()
})

test('las zonas de la demo tienen colores distintos y estables entre organización y equipos', async ({ page }) => {
  await page.goto('/acceder')
  await page.getByLabel('Correo institucional').fill('admin@demo.local')
  await page.getByLabel('Contraseña', { exact: true }).fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Usuarios', exact: true })).toBeVisible()
  await page.goto('/panel/organizacion')
  const colores = []
  for (const zona of ['Zona Complejo', 'Zona Mercado']) {
    const etiqueta = page.locator(`[data-zona="${zona.toUpperCase()}"]`).first()
    await expect(etiqueta).toBeVisible()
    colores.push(await etiqueta.locator('span').first().evaluate(el => getComputedStyle(el).backgroundColor))
  }
  expect(new Set(colores).size).toBe(2)
  await page.goto('/panel/equipos')
  const palacio = page.locator('[data-zona="ZONA COMPLEJO"]').first()
  await expect(palacio).toBeVisible()
  expect(await palacio.locator('span').first().evaluate(el => getComputedStyle(el).backgroundColor)).toBe(colores[0])
})
