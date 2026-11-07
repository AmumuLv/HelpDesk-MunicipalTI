import { expect, test } from '@playwright/test'

const PASSWORD = 'Demo12345'

test('Aplicar técnico envía su ID a la API real y respeta el permiso de reasignación', async ({ browser, request, baseURL }) => {
  expect(process.env.PRUEBA_API_URL, 'Solo se permite la instalación ficticia').toBe('http://127.0.0.1:18100')
  if (!baseURL) throw new Error('Falta la URL de la interfaz ficticia')
  const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: PASSWORD } })
  expect(login.status()).toBe(200)
  const principal = await login.json()
  expect(principal.administrador_principal).toBe(true)
  const headers = { Authorization: `Bearer ${principal.access_token}`, 'X-CSRF-Token': principal.csrf_token }
  const sufijo = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  const cuentas: Record<string, { id: string; nombre: string; email: string }> = {}
  for (const [clave, rol] of [['actor', 'tecnico'], ['destino', 'tecnico'], ['persona', 'usuario']]) {
    const alta = await request.post('/api/usuarios', { headers, data: {
      nombre: `IA ${clave} ${sufijo}`, email: `ia-${clave}-${sufijo}@prueba.local`, password: PASSWORD, rol,
    } })
    expect(alta.status(), await alta.text()).toBe(201)
    cuentas[clave] = await alta.json()
  }
  const accesoPersona = await request.post('/api/auth/login', { data: { correo: cuentas.persona.email, password: PASSWORD } })
  expect(accesoPersona.status()).toBe(200)
  const persona = await accesoPersona.json()
  const altaTicket = await request.post('/api/tickets', { headers: {
    Authorization: `Bearer ${persona.access_token}`, 'X-CSRF-Token': persona.csrf_token,
  }, data: { descripcion: 'Revisión de asignación sugerida en navegador' } })
  expect(altaTicket.status()).toBe(201)
  const ticketId = (await altaTicket.json()).ticket.id
  const rutaIA = `/api/tickets/${ticketId}/ia`
  const permiso = async (conceder: boolean) => {
    const respuesta = await request.put(`/api/permisos/tecnicos/${cuentas.actor.id}`, {
      headers, data: { cambios: { 'tickets.reasignar': conceder } },
    })
    expect(respuesta.status()).toBe(200)
  }
  await permiso(false)

  // El destino dispone de horario para el instante del ensayo. El único doble
  // de prueba es la recomendación GET; la decisión POST usa reglas y datos reales.
  const dias = Object.fromEntries(Array.from({ length: 7 }, (_, dia) => [String(dia), {
    libre: false, tramos: [{ entrada: '00:00', salida: '23:59' }],
  }]))
  const horario = await request.put(`/api/equipo-ti/${cuentas.destino.id}/horario`, { headers, data: { dias } })
  expect(horario.status()).toBe(200)
  const feriados = await request.get('/api/configuracion/feriados', { headers })
  expect(feriados.status()).toBe(200)
  const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  for (const feriado of (await feriados.json()).items as { id: string; fecha: string }[]) {
    if (feriado.fecha.slice(0, 10) === hoy) {
      const quitar = await request.delete(`/api/configuracion/feriados/${feriado.id}`, { headers })
      expect(quitar.status()).toBe(200)
    }
  }

  const context = await browser.newContext({ baseURL, locale: 'es-PE', timezoneId: 'America/Lima' })
  try {
    const acceso = await context.request.post('/api/auth/login', { data: { correo: cuentas.actor.email, password: PASSWORD } })
    expect(acceso.status()).toBe(200)
    const actor = await acceso.json()
    const actorHeaders = { Authorization: `Bearer ${actor.access_token}`, 'X-CSRF-Token': actor.csrf_token }
    const preferencia = await context.request.post('/api/auth/preferencia-ia', { headers: actorHeaders, data: { recomendaciones_ia: true } })
    expect(preferencia.status()).toBe(200)
    await context.addInitScript(token => sessionStorage.setItem('ma.acceso', token), actor.access_token)
    const page = await context.newPage()
    const errores: string[] = []
    page.on('pageerror', error => errores.push(error.message))
    let puedeAplicar = false
    await page.route(`**${rutaIA}`, async route => {
      if (route.request().method() !== 'GET') return route.continue()
      await route.fulfill({ json: {
        disponible: true, activa: true, confianza: 0.8, confianza_suficiente: true,
        categoria: null, prioridad: null, decisiones: {}, articulos: [],
        tecnico_sugerido_id: cuentas.destino.id, tecnico_sugerido_nombre: cuentas.destino.nombre,
        tecnico_sugerido_aplicable: puedeAplicar, explicacion_asignacion: 'Destino controlado para la prueba.',
      } })
    })
    await page.goto(`/panel/tickets/${ticketId}`, { waitUntil: 'domcontentloaded' })
    const panel = page.getByRole('region', { name: 'Sugerencias IA', exact: true })
    await expect(panel.getByText(cuentas.destino.nombre, { exact: true })).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Aplicar', exact: true })).toHaveCount(0)
    const prohibida = await context.request.post(rutaIA, { headers: actorHeaders, data: {
      accion: 'aplicar', clave: 'tecnico_sugerido_id', valor: cuentas.destino.id,
    } })
    expect(prohibida.status()).toBe(403)

    await permiso(true)
    puedeAplicar = true
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(panel.getByRole('button', { name: 'Aplicar', exact: true })).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Editar', exact: true })).toHaveCount(0)
    const aplicada = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith(rutaIA))
    await panel.getByRole('button', { name: 'Aplicar', exact: true }).click()
    const respuesta = await aplicada
    expect(respuesta.request().postDataJSON()).toMatchObject({
      clave: 'tecnico_sugerido_id', valor: cuentas.destino.id, accion: 'aplicar',
    })
    expect(respuesta.status(), await respuesta.text()).toBe(200)
    const guardado = await context.request.get(`/api/tickets/${ticketId}`, { headers: actorHeaders })
    expect(guardado.status()).toBe(200)
    const ticket = await guardado.json()
    expect(ticket.tecnico_id).toBe(cuentas.destino.id)
    expect(ticket.tecnico_nombre).toBe(cuentas.destino.nombre)
    expect(ticket.estado).toBe('en_progreso')
    expect(ticket.reportante_id).toBe(cuentas.persona.id)
    expect(errores).toEqual([])
  } finally {
    await context.close()
  }
})
