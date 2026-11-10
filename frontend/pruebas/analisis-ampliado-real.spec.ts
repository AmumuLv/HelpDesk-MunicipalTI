import { expect, test } from '@playwright/test'
import { entrar } from './utilidades'

test('el catálogo real permite buscar patrimonio y conserva la consulta de calidad al recargar', async ({ page, request }) => {
  const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(acceso.ok()).toBe(true)
  const sesion = await acceso.json()
  const headers = { Authorization: 'Bearer ' + sesion.access_token, 'X-CSRF-Token': sesion.csrf_token }
  let id = ''
  await page.emulateMedia({ reducedMotion: 'reduce' })
  try {
    await entrar(page, 'administrador')
    await page.goto('/panel/analisis?tab=asistente')
    await page.getByRole('button', { name: 'Preguntas sugeridas', exact: true }).click()
    const panel = page.getByRole('region', { name: 'Preguntas sugeridas', exact: true })
    await panel.getByLabel('Buscar preguntas', { exact: true }).fill('patrimonio')
    const respuestaPendiente = page.waitForResponse(r => new URL(r.url()).pathname === '/api/ia/asistente' && r.request().method() === 'POST')
    await panel.getByRole('button', { name: '¿Qué equipos no tienen código patrimonial?', exact: true }).click()
    const respuesta = await respuestaPendiente
    expect(respuesta.ok()).toBe(true)
    const datos = await respuesta.json()
    id = datos.conversacion_id
    expect(datos.fuentes).toEqual(['equipos_datos_pendientes'])
    expect(datos.contexto_consulta.argumentos.campo).toBe('codigo_patrimonial')
    await expect(page.getByRole('log')).toContainText('código patrimonial pendiente')
    await expect(page.getByRole('log')).toContainText('Inventario actual')
    await page.reload()
    await expect(page.getByRole('log')).toContainText('código patrimonial pendiente')
    await expect(page.getByRole('log')).toContainText('Inventario actual')
  } finally {
    if (id) await request.delete('/api/ia/asistente/conversaciones/' + id, { headers })
  }
})

test('un listado real abre el ticket desde su respuesta y vuelve al historial guardado', async ({ page, request }) => {
  const accesoUsuario = await request.post('/api/auth/login', { data: { correo: 'usuario1@demo.local', password: 'Demo12345', acceso: 'usuario' } })
  expect(accesoUsuario.ok()).toBe(true)
  const usuario = await accesoUsuario.json()
  const creado = await request.post('/api/tickets', { headers: { Authorization: 'Bearer ' + usuario.access_token, 'X-CSRF-Token': usuario.csrf_token }, data: {
    reporte_para: 'propio', persona: { es_para_mi: true }, tipo_problema: 'Otro problema',
    descripcion: 'Caso ficticio aislado para verificar navegación del asistente.',
  } })
  expect(creado.ok(), await creado.text()).toBe(true)
  const { ticket } = await creado.json()
  const acceso = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: 'Demo12345', acceso: 'ti' } })
  expect(acceso.ok()).toBe(true)
  const sesion = await acceso.json()
  const headers = { Authorization: 'Bearer ' + sesion.access_token, 'X-CSRF-Token': sesion.csrf_token }
  let id = ''
  await page.emulateMedia({ reducedMotion: 'reduce' })
  try {
    await entrar(page, 'administrador')
    await page.goto('/panel/analisis?tab=asistente')
    await page.getByLabel('Tu pregunta', { exact: true }).fill('Muéstrame los tickets sin equipo vinculado hoy')
    const respuestaPendiente = page.waitForResponse(r => new URL(r.url()).pathname === '/api/ia/asistente' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
    const respuesta = await respuestaPendiente
    expect(respuesta.ok()).toBe(true)
    const datos = await respuesta.json()
    id = datos.conversacion_id
    expect(datos.fuentes).toEqual(['tickets_pendientes_detalle'])
    expect(datos.enlaces.length).toBeGreaterThan(0)
    const enlace = datos.enlaces[0] as { texto: string; href: string }
    await page.getByRole('link', { name: enlace.texto + ' ↗', exact: true }).click()
    await expect(page).toHaveURL(enlace.href)
    await expect(page.getByRole('heading', { name: enlace.texto, exact: false }).first()).toBeVisible()
    await page.goBack()
    await expect(page).toHaveURL(new RegExp('conversacion=' + id))
    await expect(page.getByRole('log')).toContainText('sin dispositivo ni conjunto vinculado')
  } finally {
    if (id) await request.delete('/api/ia/asistente/conversaciones/' + id, { headers })
    await request.post('/api/tickets/' + ticket.id + '/eliminar', { headers })
  }
})
