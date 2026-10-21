import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'

const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  page.on('pageerror', error => { throw error })
  await page.goto('http://localhost/acceder')
  await page.getByLabel('Correo institucional').fill('admin@demo.local')
  await page.getByLabel('Contraseña').fill('Demo12345')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await page.getByRole('link', { name: 'Usuarios', exact: true }).waitFor()
  const datos = await page.evaluate(async () => {
    const cab = { Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso') }
    return Promise.all(['/zonas', '/activos?por_pagina=1', '/tickets', '/usuarios'].map(async ruta => {
      const respuesta = await fetch('/api' + ruta, { headers: cab })
      if (!respuesta.ok) throw new Error(ruta + ': ' + respuesta.status)
      return respuesta.json()
    }))
  })
  assert.equal(datos[0].items.length, 5)
  assert.equal(datos[1].total, 875)
  assert.ok(datos[2].items.every(t => t.demo !== true), 'No deben aparecer tickets demo')
  assert.equal(datos[3].total, 2)
  if (datos[2].items.length) {
    const ticket = datos[2].items[0]
    await page.goto(`http://localhost/panel/tickets/${ticket.id}`)
    await page.locator(`a[href="/panel/usuarios/${ticket.reportante_id}"]`).first().click()
    const creador = datos[3].items.find(u => u.id === ticket.reportante_id)
    await page.getByRole('heading', { name: creador.nombre, exact: true }).waitFor()
  }
  await page.goto('http://localhost/panel/organizacion')
  for (const zona of datos[0].items) await page.locator(`[data-zona="${zona.nombre}"]`).waitFor()
  await page.goto('http://localhost/panel/equipo-ti')
  const admin = datos[3].items.find(u => u.rol === 'administrador')
  await page.locator(`a[href="/panel/equipo-ti/${admin.id}"]`).first().click()
  await page.getByRole('heading', { name: admin.nombre, exact: true }).waitFor()
  await page.getByRole('heading', { name: 'Horario laboral', exact: true }).waitFor()
  await page.getByRole('heading', { name: 'Ausencias', exact: true }).waitFor()
  console.log(`localhost: cinco zonas con color, 875 equipos, ${datos[2].total} tickets actuales y perfiles TI/horarios correctos.`)
  await page.evaluate(async () => {
    const autorizacion = 'Bearer ' + sessionStorage.getItem('ma.acceso')
    const sesion = await (await fetch('/api/auth/sesion', { headers: { Authorization: autorizacion } })).json()
    const salida = await fetch('/api/auth/logout', { method: 'POST', credentials: 'include', headers: {
      Authorization: autorizacion, 'Content-Type': 'application/json', 'X-CSRF-Token': sesion.csrf_token,
    }, body: '{}' })
    if (!salida.ok) throw new Error('No se cerró la sesión de verificación: ' + salida.status)
  })
} finally {
  await browser.close()
}
