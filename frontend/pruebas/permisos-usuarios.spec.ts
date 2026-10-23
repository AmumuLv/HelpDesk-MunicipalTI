/**
 * Permisos de la pantalla Usuarios.
 *
 * Lo que se vigila, porque ya se rompió una vez:
 * 1. Con sesión de administrador, «Nuevo usuario» se ve y abre el formulario.
 * 2. Un técnico sin el permiso `usuarios.editar` no ve el botón.
 * 3. La seguridad no vive en la interfaz: al mismo técnico la API le responde
 *    403 con `sin_permiso` si intenta crear la cuenta por su cuenta.
 *
 * Se ejecuta contra un despliegue de pruebas (crea una cuenta y la desactiva al
 * terminar). No apuntar al inventario municipal.
 */

import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'

import { ROLES, entrar } from './utilidades'

test('un técnico consulta cerrados sin pedir exportaciones y necesita permiso para descargar', async ({ page }) => {
  await entrar(page, 'tecnico')
  const consultas: string[] = []
  page.on('request', peticion => {
    if (new URL(peticion.url()).pathname === '/api/exportaciones') consultas.push(peticion.method())
  })
  await page.goto('/panel/cerrados')
  await expect(page.getByRole('heading', { name: 'Historial cerrado', exact: true })).toBeVisible()
  await expect(page.getByRole('table').first()).toBeVisible()
  await expect(page.getByRole('button', { name: /^Descargas/ })).toHaveCount(0)
  // Simular solo la delegación de ver reportes: exportar sigue sin concederse.
  await page.route('**/api/auth/sesion', async ruta => {
    const respuesta = await ruta.fetch()
    const sesion = await respuesta.json()
    await ruta.fulfill({ response: respuesta, json: { ...sesion, permisos: [...sesion.permisos, 'reportes.ver'].filter((p: string) => p !== 'exportar') } })
  })
  await page.goto('/panel/reportes')
  await expect(page.getByText('No tienes acceso a la generación y descarga de reportes', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Generar archivo', exact: true })).toHaveCount(0)
  expect(consultas).toEqual([])
})

const CAPTURAS = process.env.PRUEBA_CAPTURAS ?? path.resolve(process.cwd(), '..', 'docs', 'capturas')
const NOMBRE_PRUEBA = 'Prueba automatica permisos'

type UsuarioApi = { id: string; nombre: string; email: string; rol: string; activo: boolean }

/** Llamada a la API con el token de la sesión abierta en la página. */
async function apiGet<T>(pagina: Page, ruta: string): Promise<T> {
  return pagina.evaluate(async (destino) => {
    const respuesta = await fetch(destino, {
      headers: { Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso') },
    })
    return respuesta.json()
  }, ruta)
}

/** Llamada que modifica datos: exige el token CSRF de doble envío, como la web. */
async function apiEnviar(
  pagina: Page,
  metodo: 'POST' | 'PUT',
  ruta: string,
  cuerpo: unknown,
): Promise<{ estado: number; cuerpo: Record<string, unknown> }> {
  return pagina.evaluate(
    async ({ metodo, ruta, cuerpo }) => {
      const csrf = document.cookie
        .split('; ')
        .find((parte) => parte.startsWith('ma_csrf='))
        ?.split('=')[1]
      const respuesta = await fetch(ruta, {
        method: metodo,
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + sessionStorage.getItem('ma.acceso'),
          'X-CSRF-Token': csrf ?? '',
        },
        body: JSON.stringify(cuerpo),
      })
      return { estado: respuesta.status, cuerpo: await respuesta.json() }
    },
    { metodo, ruta, cuerpo },
  )
}

test('el administrador ve «Nuevo usuario» y el formulario crea la cuenta', async ({ page }) => {
  await entrar(page, 'administrador')
  await page.goto('/panel/usuarios')

  const boton = page.getByRole('button', { name: 'Nuevo usuario' })
  await expect(boton, 'el administrador tiene que ver «Nuevo usuario» en Usuarios').toBeVisible()
  await page.screenshot({ path: path.join(CAPTURAS, 'usuarios-admin-boton.png') })

  // El botón tiene que estar dentro de la ventana, no recortado a la derecha
  const caja = await boton.boundingBox()
  const ancho = page.viewportSize()?.width ?? 0
  expect(caja, 'el botón no se pudo medir').not.toBeNull()
  expect((caja?.x ?? 0) + (caja?.width ?? 0)).toBeLessThanOrEqual(ancho + 1)

  await boton.click()
  const dialogo = page.getByRole('dialog')
  await expect(dialogo).toBeVisible()
  await expect(dialogo.getByText('Nuevo usuario', { exact: true })).toBeVisible()
  await expect(dialogo.getByLabel('Nombre completo')).toBeVisible()
  await expect(dialogo.getByLabel('Correo')).toBeVisible()
  await expect(dialogo.getByLabel(/^Contraseña/)).toBeVisible()
  await expect(dialogo.getByRole('button', { name: 'Crear usuario' })).toBeDisabled()
  await page.screenshot({ path: path.join(CAPTURAS, 'usuarios-admin-formulario.png') })

  // El formulario funciona de verdad: se crea la cuenta y aparece en el directorio
  const correo = `prueba.permisos.${Date.now()}@demo.local`
  await dialogo.getByLabel('Nombre completo').fill(NOMBRE_PRUEBA)
  await dialogo.getByLabel('Correo').fill(correo)
  await dialogo.getByLabel(/^Contraseña/).fill('Demo12345')
  await dialogo.getByLabel('Confirmar contraseña').fill('Demo12345')
  await expect(dialogo.getByRole('button', { name: 'Crear usuario' })).toBeEnabled()
  await dialogo.getByRole('button', { name: 'Crear usuario' }).click()

  await expect(page.getByText('Usuario creado', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
  await expect(dialogo).toBeHidden()

  await page.getByLabel('Buscar personas').fill(correo)
  // La tabla y la lista de tarjetas conviven: solo una está visible según el ancho
  await expect(page.getByText(correo).filter({ visible: true }).first()).toBeVisible({ timeout: 15_000 })

  // Se deja la cuenta desactivada: la prueba no debe llenar el directorio
  const encontrados = await apiGet<{ items: UsuarioApi[] }>(
    page,
    `/api/usuarios?texto=${encodeURIComponent(correo)}`,
  )
  const creada = encontrados.items.find((usuario) => usuario.email === correo)
  expect(creada, 'la cuenta creada tiene que existir en el directorio').toBeTruthy()
  const baja = await apiEnviar(page, 'POST', `/api/usuarios/${creada?.id}/desactivar`, {})
  expect(baja.estado).toBe(200)
})

test('un técnico sin usuarios.editar no ve el botón y la API le responde 403', async ({ page }) => {
  // El escenario se prepara con la sesión del administrador: el permiso delegable
  // `usuarios.editar` queda apagado para el técnico, que es su valor de fábrica.
  await entrar(page, 'administrador')
  const directorio = await apiGet<{ items: UsuarioApi[] }>(
    page,
    `/api/usuarios?texto=${encodeURIComponent(ROLES.tecnico.correo)}`,
  )
  const tecnico = directorio.items.find((usuario) => usuario.email === ROLES.tecnico.correo)
  expect(tecnico, `tiene que existir el técnico ${ROLES.tecnico.correo} en el despliegue de pruebas`).toBeTruthy()
  const quitar = await apiEnviar(page, 'PUT', `/api/permisos/tecnicos/${tecnico?.id}`, {
    cambios: { 'usuarios.editar': false },
  })
  expect(quitar.estado).toBe(200)

  // Cambio de persona en el mismo navegador: se cierra la sesión del administrador
  await page.evaluate(() => sessionStorage.clear())

  await entrar(page, 'tecnico')
  const sesion = await apiGet<{ rol: string; permisos: string[] }>(page, '/api/auth/sesion')
  expect(sesion.rol).toBe('tecnico')
  expect(sesion.permisos).not.toContain('usuarios.editar')

  await page.goto('/panel/usuarios')
  // El técnico sí entra al directorio (tiene `usuarios.ver`), pero no puede crear
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Nuevo usuario' })).toHaveCount(0)
  await page.screenshot({ path: path.join(CAPTURAS, 'usuarios-tecnico-sin-boton.png') })

  // Y el backend sigue mandando: sin permiso, la API rechaza la creación
  const intento = await apiEnviar(page, 'POST', '/api/usuarios', {
    nombre: 'No deberia crearse',
    email: `no.deberia.${Date.now()}@demo.local`,
    password: 'Demo12345',
    rol: 'usuario',
  })
  expect(intento.estado, 'la API no puede aceptar la creación sin permiso').toBe(403)
  expect(intento.cuerpo.codigo).toBe('sin_permiso')
})
