import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

test('importar un relevo muestra el cambio y conserva el equipo al crear un solo perfil', async ({ page }) => {
  expect(process.env.PRUEBA_API_URL, 'Este recorrido solo admite la API ficticia').toBe('http://127.0.0.1:18100')
  const request = page.context().request
  const errores: string[] = []
  page.on('pageerror', error => errores.push(error.message))
  const acceso = await request.post('/api/auth/login', {
    data: { correo: 'admin@demo.local', password: 'Demo12345' },
  })
  expect(acceso.status()).toBe(200)
  const sesion = await acceso.json()
  expect(sesion.administrador_principal).toBe(true)
  const headers = { Authorization: `Bearer ${sesion.access_token}`, 'X-CSRF-Token': sesion.csrf_token }
  await page.context().addInitScript(token => sessionStorage.setItem('ma.acceso', token), sesion.access_token)
  const sufijo = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
  const zonaNombre = `RELEVO ${sufijo}`
  const zonaAlta = await request.post('/api/zonas', { headers, data: { nombre: zonaNombre } })
  expect(zonaAlta.status()).toBe(201)
  const zona = await zonaAlta.json()
  const oficinaAlta = await request.post('/api/oficinas', { headers, data: {
    nombre: 'OFICINA DE PRUEBA RELEVO', zona_id: zona.id,
  } })
  expect(oficinaAlta.status()).toBe(201)
  const oficina = await oficinaAlta.json()
  const nombreAnterior = `PERSONA ANTERIOR ${sufijo}`
  const nombreNuevo = `PERSONA REEMPLAZO ${sufijo}`
  const anteriorAlta = await request.post('/api/usuarios', { headers, data: {
    nombre: nombreAnterior, email: `anterior-${sufijo}@prueba.local`, password: 'Demo12345',
    rol: 'usuario', oficina_id: oficina.id,
  } })
  expect(anteriorAlta.status()).toBe(201)
  const anterior = await anteriorAlta.json()
  const codigo = `REL-${sufijo}`
  const nombreEquipo = `Laptop de relevo ${sufijo}`
  const equipoAlta = await request.post('/api/activos', { headers, data: {
    tipo: 'Laptop', oficina_id: oficina.id, responsable_id: anterior.id,
    codigo_patrimonial: codigo, nombre_equipo: nombreEquipo, marca: 'Marca anterior',
  } })
  expect(equipoAlta.status()).toBe(201)
  const equipo = await equipoAlta.json()

  // Solo genera un libro ficticio en memoria dentro de la API aislada. No
  // consulta la base, el entorno ni archivos de ninguna instalación operativa.
  const generarExcel = [
    'from io import BytesIO',
    'import json, sys',
    'from openpyxl import Workbook',
    'datos = json.load(sys.stdin)',
    'libro = Workbook()',
    'hoja = libro.active',
    'hoja.title = datos["zona"]',
    'hoja.append(["AREA", "Tipo de equipo", "Dispositivo", "Código patrimonial", "Nombre equipo", "Responsable", "Marca"])',
    'hoja.append([datos["oficina"], "Laptop", "Laptop", datos["codigo"], datos["equipo"], datos["persona"], "Marca revisada"])',
    'salida = BytesIO()',
    'libro.save(salida)',
    'sys.stdout.buffer.write(salida.getvalue())',
  ].join('\n')
  const contenido = execFileSync('docker', [
    'compose', '-f', fileURLToPath(new URL('../../compose.pruebas.yml', import.meta.url)),
    'exec', '-T', 'api', 'python', '-c', generarExcel,
  ], {
    input: JSON.stringify({ zona: zonaNombre, oficina: oficina.nombre, codigo, equipo: nombreEquipo, persona: nombreNuevo }),
    timeout: 30_000,
    maxBuffer: 2 * 1024 * 1024,
  })
  await page.goto('/panel/equipos/importar', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Importar inventario desde Excel', exact: true })).toBeVisible()
  const previaRecibida = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/previsualizar'))
  await page.getByLabel('Archivo de Excel con el inventario', { exact: true }).setInputFiles({
    name: `relevo-${sufijo}.xlsx`,
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: contenido,
  })
  const previa = await previaRecibida
  expect(previa.status()).toBe(200)
  const simulacion = await previa.json()
  expect(simulacion.crearia).toBe(0)
  expect(simulacion.actualizaria).toBe(1)
  expect(simulacion.filas[0].existente_id).toBe(equipo.id)
  const fila = page.getByRole('row').filter({ hasText: codigo })
  await expect(fila).toHaveCount(1)
  await expect(fila.getByText('Se actualizará', { exact: true })).toBeVisible()
  await expect(fila.getByText(`${nombreAnterior} → ${nombreNuevo}`, { exact: true })).toBeVisible()
  const crearPerfil = page.getByRole('checkbox', { name: /Crear los perfiles que faltan y asignarles sus equipos/ })
  await expect(crearPerfil).not.toBeChecked()
  await crearPerfil.check()
  const confirmacionRecibida = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/confirmar'))
  await page.getByRole('button', { name: 'Aplicar la importación', exact: true }).click()
  const confirmacion = await confirmacionRecibida
  expect(confirmacion.request().postDataJSON().crear_usuarios_faltantes).toBe(true)
  expect(confirmacion.status()).toBe(200)
  const resultado = await confirmacion.json()
  expect({ nuevos: resultado.creados, actualizados: resultado.actualizados, perfiles: resultado.usuarios_creados, errores: resultado.errores })
    .toEqual({ nuevos: 0, actualizados: 1, perfiles: 1, errores: 0 })
  await expect(page.getByRole('heading', { name: '3. Resultado de la importación', exact: true })).toBeVisible()

  const listado = await request.get('/api/activos', { headers, params: { oficina_id: oficina.id } })
  expect(listado.status()).toBe(200)
  const inventario = await listado.json()
  expect(inventario.total).toBe(1)
  expect(inventario.items[0].id).toBe(equipo.id)
  const personasRespuesta = await request.get('/api/usuarios', { headers, params: { oficina_id: oficina.id } })
  expect(personasRespuesta.status()).toBe(200)
  const personas = await personasRespuesta.json()
  expect(personas.total).toBe(2)
  const reemplazo = personas.items.find((persona: { nombre: string }) => persona.nombre === nombreNuevo)
  expect(reemplazo).toBeDefined()
  expect(reemplazo.id).not.toBe(anterior.id)
  expect(reemplazo.email).toBeNull()
  expect(personas.items.find((persona: { id: string }) => persona.id === anterior.id)?.nombre).toBe(nombreAnterior)
  const detalleRespuesta = await request.get(`/api/activos/${equipo.id}`, { headers })
  expect(detalleRespuesta.status()).toBe(200)
  const detalle = await detalleRespuesta.json()
  expect(detalle.responsable_id).toBe(reemplazo.id)
  expect(detalle.marca).toBe('Marca revisada')
  expect(detalle.historial_responsables.map((tramo: { responsable_id: string }) => tramo.responsable_id))
    .toEqual([reemplazo.id, anterior.id])
  expect(errores).toEqual([])
})
