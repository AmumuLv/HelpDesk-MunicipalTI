import { expect, test, type APIRequestContext, type Browser, type BrowserContext, type Page } from '@playwright/test'

const PASSWORD = 'Demo12345'
type Cuenta = { id: string; nombre: string; email: string; rol: string }
type Mundo = {
  principal: { id: string; headers: Record<string, string> }
  admin: Cuenta
  tecnico: Cuenta
  persona: Cuenta
}
type Sesion = {
  context: BrowserContext
  page: Page
  headers: Record<string, string>
  token: string
  errores: string[]
}

test.beforeEach(() => {
  expect(process.env.PRUEBA_API_URL, 'Solo se permite la instalación ficticia').toBe('http://127.0.0.1:18100')
})

async function preparar(request: APIRequestContext): Promise<Mundo> {
  const login = await request.post('/api/auth/login', { data: { correo: 'admin@demo.local', password: PASSWORD } })
  expect(login.status()).toBe(200)
  const principal = await login.json()
  expect(principal.administrador_principal).toBe(true)
  const headers = { Authorization: `Bearer ${principal.access_token}`, 'X-CSRF-Token': principal.csrf_token }
  const sufijo = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  const zona = await request.post('/api/zonas', { headers, data: { nombre: `Zona combinada ${sufijo}` } })
  expect(zona.ok()).toBe(true)
  const oficina = await request.post('/api/oficinas', { headers, data: {
    nombre: `Oficina combinada ${sufijo}`, zona_id: (await zona.json()).id,
  } })
  expect(oficina.ok()).toBe(true)
  const oficinaId = (await oficina.json()).id
  const cuentas: Record<string, Cuenta> = {}
  for (const [clave, rol] of [['admin', 'administrador'], ['tecnico', 'tecnico'], ['persona', 'usuario']]) {
    const alta = await request.post('/api/usuarios', { headers, data: {
      nombre: `Prueba combinada ${clave} ${sufijo}`, email: `combinada-${clave}-${sufijo}@prueba.local`,
      password: PASSWORD, rol, oficina_id: oficinaId,
    } })
    expect(alta.status(), await alta.text()).toBe(201)
    cuentas[clave] = await alta.json()
  }
  return { principal: { id: principal.id, headers }, admin: cuentas.admin, tecnico: cuentas.tecnico, persona: cuentas.persona }
}

async function sesion(browser: Browser, baseURL: string, cuenta: Cuenta, abiertas: BrowserContext[]): Promise<Sesion> {
  const context = await browser.newContext({ baseURL, locale: 'es-PE', timezoneId: 'America/Lima', viewport: { width: 1440, height: 1000 } })
  abiertas.push(context)
  const login = await context.request.post('/api/auth/login', { data: { correo: cuenta.email, password: PASSWORD } })
  expect(login.status()).toBe(200)
  const datos = await login.json()
  expect(datos.rol).toBe(cuenta.rol)
  await context.addInitScript(token => sessionStorage.setItem('ma.acceso', token), datos.access_token)
  const page = await context.newPage()
  const errores: string[] = []
  page.on('pageerror', error => errores.push(error.message))
  return { context, page, headers: { Authorization: `Bearer ${datos.access_token}`, 'X-CSRF-Token': datos.csrf_token }, token: datos.access_token, errores }
}

async function abrir(actor: Sesion, ruta: string) {
  // La primera pantalla puede necesitar compilar sus módulos. Capturar el rechazo
  // desde el principio evita una promesa sin atender mientras termina de navegar.
  const conectado = actor.page.waitForEvent('websocket', {
    predicate: socket => socket.url().includes('/ws/notificaciones'), timeout: 60_000,
  }).then(socket => socket.waitForEvent('framereceived', {
    predicate: frame => JSON.parse(frame.payload.toString()).tipo === 'sincronizacion', timeout: 60_000,
  })).then(() => ({ error: null })).catch((error: unknown) => ({ error }))
  try {
    await actor.page.goto(ruta, { waitUntil: 'domcontentloaded', timeout: 60_000 })
    const resultado = await conectado
    if (resultado.error) throw resultado.error
  } catch (error) {
    const diagnostico = await actor.page.evaluate(() => ({
      rutaActual: location.pathname,
      titulo: document.title,
      titulos: [...document.querySelectorAll('h1, h2')].map(nodo => nodo.textContent?.trim()).slice(0, 8),
      texto: (document.querySelector('main')?.textContent ?? document.body?.textContent ?? '').slice(0, 1000),
    })).catch(() => ({ pagina: 'La página ya no está disponible' }))
    const seguro = JSON.stringify({ rutaSolicitada: ruta, ...diagnostico })
      .replace(/Bearer\s+[^\s"<>]+/gi, 'Bearer [reservado]')
      .replace(/\beyJ[\w-]+\.[\w-]+\.[\w-]+\b/g, '[token reservado]')
    throw new Error(`No se completó la sincronización inicial: ${seguro}`, { cause: error })
  }
}

async function cambiarPermiso(admin: Sesion, tecnico: Cuenta, conceder: boolean) {
  const tarjeta = admin.page.getByRole('listitem').filter({ has: admin.page.getByText(tecnico.nombre, { exact: true }) })
  const permiso = tarjeta.getByLabel('Gestionar cuentas de usuarios', { exact: true })
  await expect(permiso).toBeEnabled()
  await permiso.setChecked(conceder)
  const guardado = admin.page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith(`/permisos/tecnicos/${tecnico.id}`))
  await tarjeta.getByRole('button', { name: /^Guardar cambios de / }).click()
  expect((await guardado).status()).toBe(200)
  if (conceder) await expect(permiso).toBeChecked()
  else await expect(permiso).not.toBeChecked()
}

async function rellenarAlta(page: Page, nombre: string, correo: string) {
  const formulario = page.getByRole('dialog', { name: 'Nuevo usuario', exact: true })
  await expect(formulario).toBeVisible()
  await formulario.getByLabel('Nombre completo').fill(nombre)
  await formulario.getByLabel('Correo').fill(correo)
  await formulario.getByLabel(/^Contraseña/).fill(PASSWORD)
  await formulario.getByLabel('Confirmar contraseña').fill(PASSWORD)
  return formulario
}

test('un mismo reporte pasa de usuario a técnico y administrador con las tres vistas abiertas', async ({ browser, request, baseURL }) => {
  if (!baseURL) throw new Error('Falta la URL de la interfaz ficticia')
  const mundo = await preparar(request)
  const abiertas: BrowserContext[] = []
  try {
    const usuario = await sesion(browser, baseURL, mundo.persona, abiertas)
    const tecnico = await sesion(browser, baseURL, mundo.tecnico, abiertas)
    const admin = await sesion(browser, baseURL, mundo.admin, abiertas)
    await abrir(usuario, '/reportar')
    const descripcion = `Ciclo combinado de atención ${Date.now()}`
    await usuario.page.getByRole('button', { name: /No enciende/ }).click()
    await usuario.page.getByLabel('¿Qué está pasando?').fill(descripcion)
    await usuario.page.getByRole('radio', { name: /Con dificultad/ }).check()
    const alta = usuario.page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/tickets'))
    await usuario.page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
    const respuestaAlta = await alta
    expect(respuestaAlta.status()).toBe(201)
    const ticket = (await respuestaAlta.json()).ticket
    await expect(usuario.page).toHaveURL(new RegExp(`/mis-tickets/${ticket.id}$`))
    await abrir(tecnico, `/panel/tickets/${ticket.id}`)
    await abrir(admin, `/panel/tickets/${ticket.id}`)
    const cargas = await Promise.all([usuario.page, tecnico.page, admin.page].map(p => p.evaluate(() => performance.timeOrigin)))

    await expect(tecnico.page.getByRole('button', { name: 'Cerrar ticket', exact: true })).toHaveCount(0)
    const selector = admin.page.getByLabel('Asignar a', { exact: true })
    await expect(selector.locator(`option[value="${mundo.tecnico.id}"]`)).toHaveCount(1)
    await selector.selectOption(mundo.tecnico.id)
    const asignacion = admin.page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith(`/tickets/${ticket.id}/asignar`))
    await admin.page.getByRole('button', { name: 'Asignar', exact: true }).click()
    expect((await asignacion).status()).toBe(200)
    await expect(tecnico.page.getByRole('button', { name: 'Cerrar ticket', exact: true })).toBeVisible({ timeout: 20_000 })
    await expect(usuario.page.getByRole('button', { name: `Ver perfil de ${mundo.tecnico.nombre}`, exact: true })).toBeVisible({ timeout: 20_000 })
    const avisosTecnico = await tecnico.context.request.get('/api/notificaciones', { headers: tecnico.headers })
    expect(avisosTecnico.ok()).toBe(true)
    expect((await avisosTecnico.json()).items.some((aviso: { ticket_id?: string; tipo?: string }) => aviso.ticket_id === ticket.id && aviso.tipo === 'asignacion')).toBe(true)

    await tecnico.page.getByRole('button', { name: 'Cerrar ticket', exact: true }).click()
    const cierre = tecnico.page.getByRole('dialog', { name: 'Cerrar ticket', exact: true })
    const solucion = `Verificación conjunta terminada ${Date.now()}`
    await cierre.getByLabel('Resultado de la atención', { exact: true }).fill(solucion)
    const cerrado = tecnico.page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith(`/tickets/${ticket.id}/estado`))
    await cierre.getByRole('button', { name: 'Cerrar ticket', exact: true }).click()
    expect((await cerrado).status()).toBe(200)
    await expect(usuario.page.getByRole('region', { name: 'Seguimiento del reporte', exact: true }).getByRole('heading', { name: 'Finalizado', exact: true })).toBeVisible({ timeout: 20_000 })
    await expect(usuario.page.getByText(solucion, { exact: true })).toBeVisible()
    await expect(admin.page.getByRole('button', { name: 'Reabrir ticket', exact: true })).toBeVisible({ timeout: 20_000 })
    const avisosUsuario = await usuario.context.request.get('/api/notificaciones', { headers: usuario.headers })
    expect((await avisosUsuario.json()).items.some((aviso: { ticket_id?: string }) => aviso.ticket_id === ticket.id)).toBe(true)

    await admin.page.getByRole('button', { name: 'Reabrir ticket', exact: true }).click()
    const reapertura = admin.page.getByRole('dialog', { name: 'Reabrir ticket', exact: true })
    const reabierto = admin.page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith(`/tickets/${ticket.id}/estado`))
    await reapertura.getByRole('button', { name: 'Reabrir ticket', exact: true }).click()
    expect((await reabierto).status()).toBe(200)
    await expect(usuario.page.getByRole('region', { name: 'Seguimiento del reporte', exact: true }).getByRole('heading', { name: 'En atención', exact: true })).toBeVisible({ timeout: 20_000 })
    const final = await (await admin.context.request.get(`/api/tickets/${ticket.id}`, { headers: admin.headers })).json()
    expect(final.estado).toBe('en_progreso')
    expect(final.reportante_id).toBe(mundo.persona.id)
    expect(final.tecnico_id).toBe(mundo.tecnico.id)
    expect(await Promise.all([usuario.page, tecnico.page, admin.page].map(p => p.evaluate(() => performance.timeOrigin)))).toEqual(cargas)
    expect([...usuario.errores, ...tecnico.errores, ...admin.errores]).toEqual([])
  } finally { await Promise.allSettled(abiertas.map(context => context.close())) }
})

test('conceder y retirar permisos afecta al técnico con el formulario abierto y el mismo token', async ({ browser, request, baseURL }) => {
  if (!baseURL) throw new Error('Falta la URL de la interfaz ficticia')
  const mundo = await preparar(request)
  const abiertas: BrowserContext[] = []
  try {
    const tecnico = await sesion(browser, baseURL, mundo.tecnico, abiertas)
    const admin = await sesion(browser, baseURL, mundo.admin, abiertas)
    await abrir(tecnico, '/panel/usuarios')
    await abrir(admin, '/panel/configuracion')
    await admin.page.getByRole('tab', { name: 'Permisos por rol', exact: true }).click()
    await admin.page.getByLabel('Buscar permisos, roles o personas', { exact: true }).fill(mundo.tecnico.nombre)
    const carga = await tecnico.page.evaluate(() => performance.timeOrigin)
    await expect(tecnico.page.getByRole('button', { name: 'Nuevo usuario', exact: true })).toHaveCount(0)
    await cambiarPermiso(admin, mundo.tecnico, true)
    await expect(tecnico.page.getByRole('button', { name: 'Nuevo usuario', exact: true })).toBeVisible({ timeout: 20_000 })
    await tecnico.page.getByRole('button', { name: 'Nuevo usuario', exact: true }).click()
    const correo = `rechazado-combinado-${Date.now()}@prueba.local`
    const formulario = await rellenarAlta(tecnico.page, 'Alta que debe rechazarse', correo)
    await cambiarPermiso(admin, mundo.tecnico, false)
    // Se comprueba la siguiente petición una vez guardada la retirada; no se
    // exige cancelar una petición que ya estuviera autorizada y en vuelo.
    const rechazo = tecnico.page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/usuarios'))
    await formulario.getByRole('button', { name: 'Crear usuario', exact: true }).click()
    expect((await rechazo).status()).toBe(403)
    await expect(formulario.getByText('No se pudo crear la cuenta', { exact: true })).toBeVisible()
    const noCreado = await admin.context.request.get(`/api/usuarios?texto=${encodeURIComponent(correo)}`, { headers: admin.headers })
    expect((await noCreado.json()).total).toBe(0)
    await formulario.getByRole('button', { name: 'Cancelar', exact: true }).click()
    await expect(tecnico.page.getByRole('button', { name: 'Nuevo usuario', exact: true })).toHaveCount(0)

    await cambiarPermiso(admin, mundo.tecnico, true)
    await expect(tecnico.page.getByRole('button', { name: 'Nuevo usuario', exact: true })).toBeVisible({ timeout: 20_000 })
    await tecnico.page.getByRole('button', { name: 'Nuevo usuario', exact: true }).click()
    const permitido = await rellenarAlta(tecnico.page, 'Alta tras recuperar permiso', correo)
    const alta = tecnico.page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/usuarios'))
    await permitido.getByRole('button', { name: 'Crear usuario', exact: true }).click()
    const creada = await alta
    expect(creada.status()).toBe(201)
    expect((await creada.json()).rol).toBe('usuario')
    await expect(permitido).toBeHidden()
    expect(await tecnico.page.evaluate(() => performance.timeOrigin)).toBe(carga)
    expect(await tecnico.page.evaluate(() => sessionStorage.getItem('ma.acceso'))).toBe(tecnico.token)
    expect([...tecnico.errores, ...admin.errores]).toEqual([])
  } finally { await Promise.allSettled(abiertas.map(context => context.close())) }
})

test('un ascenso por el principal retira al técnico la edición abierta de esa cuenta', async ({ browser, request, baseURL }) => {
  if (!baseURL) throw new Error('Falta la URL de la interfaz ficticia')
  const mundo = await preparar(request)
  const permiso = await request.put(`/api/permisos/tecnicos/${mundo.tecnico.id}`, { headers: mundo.principal.headers, data: { cambios: { 'usuarios.editar': true } } })
  expect(permiso.status()).toBe(200)
  const abiertas: BrowserContext[] = []
  try {
    const tecnico = await sesion(browser, baseURL, mundo.tecnico, abiertas)
    const admin = await sesion(browser, baseURL, mundo.admin, abiertas)
    await abrir(tecnico, `/panel/usuarios/${mundo.persona.id}`)
    await tecnico.page.getByRole('button', { name: 'Editar datos', exact: true }).click()
    const cargo = `Cambio obsoleto que no debe guardarse ${Date.now()}`
    await tecnico.page.getByLabel('Cargo', { exact: true }).fill(cargo)
    const carga = await tecnico.page.evaluate(() => performance.timeOrigin)
    const ascenso = await request.patch(`/api/usuarios/${mundo.persona.id}`, { headers: mundo.principal.headers, data: { rol: 'administrador' } })
    expect(ascenso.status()).toBe(200)
    await expect(tecnico.page.getByRole('button', { name: 'Editar datos', exact: true })).toHaveCount(0, { timeout: 20_000 })
    await expect(tecnico.page.getByRole('tab', { name: 'Cuenta y edición', exact: true })).toHaveCount(0)
    const intento = await tecnico.context.request.patch(`/api/usuarios/${mundo.persona.id}`, { headers: tecnico.headers, data: { cargo } })
    expect(intento.status()).toBe(403)
    const final = await (await request.get(`/api/usuarios/${mundo.persona.id}`, { headers: mundo.principal.headers })).json()
    expect(final.rol).toBe('administrador')
    expect(final.cargo).not.toBe(cargo)
    expect(final.administrador_principal).toBe(false)
    await abrir(admin, `/panel/usuarios/${mundo.persona.id}`)
    await expect(admin.page.getByRole('button', { name: 'Editar datos', exact: true })).toBeVisible()
    expect(await tecnico.page.evaluate(() => performance.timeOrigin)).toBe(carga)
    expect([...tecnico.errores, ...admin.errores]).toEqual([])
  } finally { await Promise.allSettled(abiertas.map(context => context.close())) }
})
