import { expect, test, type Page, type WebSocketRoute } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.setTimeout(90_000)

test('equipos de oficina pagina responsables sin separar sus componentes ni alterar el total', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/tickets?*', ruta => ruta.fulfill({ json: { items: [{ id: 'caso', codigo: 'TKT-2026-000001', asunto: 'Impresora compartida', estado: 'nuevo', prioridad: 'media', reporte_para: 'oficina', afectado_nombre: 'Ana Prueba', oficina_nombre: 'Soporte' }], total: 1, pagina: 1, total_paginas: 1 } }))
  const grupos = Array.from({ length: 6 }, (_, i) => ({ responsable_id: `responsable-${i}`, responsable: i === 5 ? 'Verónica Sánchez' : `Responsable ${i}`, equipos: Array.from({ length: i === 5 ? 4 : 3 }, (_, j) => ({ id: `equipo-${i}-${j}`, nombre: i === 5 ? ['CPU Verónica', 'Monitor Verónica', 'Mouse Verónica', 'Teclado Verónica'][j] : `Dispositivo ${i}-${j}`, tipo: ['CPU', 'Monitor', 'Mouse', 'Teclado'][j], estado: 'OPERATIVO' })) }))
  await page.route('**/api/oficinas/oficina', ruta => ruta.fulfill({ json: { id: 'oficina', nombre: 'Soporte', zona_id: 'zona', zona_nombre: 'Palacio', zona_color_indice: 1, total_equipos: 19, total_usuarios: 6, tickets_abiertos: 0, completitud_inventario: 100, usuarios: [], equipos_por_usuario: grupos, equipos_uso_comun: [], tendencia: [], incidencias_recurrentes: [] } }))
  await page.goto('/panel/oficinas/oficina')
  await expect(page.getByRole('heading', { name: 'Historial de tickets', exact: true })).toBeVisible()
  await expect(page.getByLabel('Mostrar tickets')).toHaveValue('todos')
  await expect(page.getByLabel('Mostrar tickets').getByRole('option', { name: 'Solo cerrados', exact: true })).toHaveCount(1)
  await expect(page.getByRole('table').getByText('Reporte de oficina', { exact: true })).toBeVisible()
  const cerrados = page.waitForRequest(peticion => {
    const url = new URL(peticion.url())
    return url.pathname === '/api/tickets' && url.searchParams.get('oficina_id') === 'oficina' && url.searchParams.get('vista') === 'cerrados' && url.searchParams.get('direccion') === 'desc'
  })
  await page.getByLabel('Mostrar tickets').selectOption('cerrados')
  await cerrados
  const abiertos = page.waitForRequest(peticion => {
    const url = new URL(peticion.url())
    return url.pathname === '/api/tickets' && url.searchParams.get('solo_abiertos') === 'true' && !url.searchParams.has('vista')
  })
  await page.getByLabel('Mostrar tickets').selectOption('abiertos')
  await abiertos
  await page.getByRole('tab', { name: /Equipos asignados/ }).click()
  const panel = page.getByRole('tabpanel').filter({ has: page.getByRole('heading', { name: 'Equipos asignados', exact: true }) })
  await expect(panel.getByText('Verónica Sánchez', { exact: true })).toHaveCount(0)
  await panel.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect(panel.getByText('Verónica Sánchez', { exact: true })).toBeVisible()
  await expect(panel.getByText('4 equipos', { exact: true })).toBeVisible()
  for (const nombre of ['CPU Verónica', 'Monitor Verónica', 'Mouse Verónica', 'Teclado Verónica']) await expect(panel.getByText(nombre, { exact: true })).toBeVisible()
  await panel.getByRole('button', { name: 'Anterior', exact: true }).click()
  await expect(panel.getByText('Verónica Sánchez', { exact: true })).toHaveCount(0)
})

test('resultado de responsables permite recorrer todos los perfiles, buscar y abrir su ficha', async ({ page }) => {
  await portal(page, false, 'administrador')
  const detalle = Array.from({ length: 25 }, (_, i) => ({ clave: `p${i}`, usuario_id: `persona-${i}`, nombre_excel: `Responsable ${String(i).padStart(2, '0')}`, nombre_asignado: `Responsable ${String(i).padStart(2, '0')}`, accion: 'creado', oficina_nombre: i === 24 ? 'Alcaldía' : 'Soporte', zona_nombre: 'Palacio', equipos: 1, coincidencia: null, similitud: null, nombre_parece_oficina: false }))
  await page.route('**/api/importacion**', ruta => {
    const camino = new URL(ruta.request().url()).pathname
    let json: unknown = { items: [] }
    if (camino.endsWith('/subir')) json = { lote_id: 'lote' }
    else if (camino.endsWith('/previsualizar')) json = { lote_id: 'lote', filas: [], total_filas: 1, validas: 1, crearia: 1, actualizaria: 0, omitiria: 0, con_error: 0, con_advertencia: 0 }
    else if (camino.endsWith('/responsables-excel/confirmar')) json = { personas_creadas: 25, equipos_vinculados: 25, detalle }
    else if (camino.endsWith('/responsables-excel')) json = { items: detalle.map(fila => ({ clave: fila.clave, oficina_id: 'oficina', oficina_nombre: fila.oficina_nombre, nombre_original: fila.nombre_excel, nombres_originales: [fila.nombre_excel], equipos: 1, candidatos: [] })) }
    else if (camino.endsWith('/confirmar')) json = { creados: 1, actualizados: 0, omitidos: 0, errores: 0, detalle: [], reversible: false }
    else if (camino.endsWith('/lote')) json = { lote_id: 'lote', nombre_archivo: 'revision.csv', estado: 'analizado', analisis: { hojas: [], columnas_por_hoja: {} } }
    return ruta.fulfill({ json })
  })
  await page.goto('/panel/equipos/importar')
  await page.getByLabel('Archivo de Excel con el inventario').setInputFiles({ name: 'revision.csv', mimeType: 'text/csv', buffer: Buffer.from('AREA;Tipo de equipo\nSoporte;Laptop') })
  await page.getByRole('button', { name: 'Aplicar la importación', exact: true }).click()
  await page.getByRole('checkbox', { name: /Crear un perfil para las que faltan/ }).check()
  await page.getByRole('button', { name: 'Continuar', exact: true }).click()
  const lista = page.getByRole('list', { name: 'Perfiles creados y vinculados' })
  await expect(lista.getByRole('listitem')).toHaveCount(20)
  await expect(page.getByText(/casos que podrían estar mal/)).toHaveCount(0)
  await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect(lista.getByRole('listitem')).toHaveCount(5)
  await expect(lista.getByText('Responsable 24', { exact: true })).toBeVisible()
  await page.getByLabel('Buscar perfiles del resultado').fill('alcaldia')
  await expect(lista.getByRole('listitem')).toHaveCount(1)
  await expect(lista.getByRole('link')).toHaveAttribute('href', '/panel/usuarios/persona-24')
  await lista.getByRole('link').click()
  await expect(page).toHaveURL(/\/panel\/usuarios\/persona-24$/)
})

for (const rol of ['tecnico', 'administrador']) {
  test(`${rol} cambia y quita su foto desde Mi perfil sin cambiar de portal`, async ({ page }) => {
    await portal(page, false, rol)
    let tieneFoto = false
    let subidas = 0
    let borrados = 0
    const imagen = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=', 'base64')
    await page.route('**/api/mi-perfil', ruta => ruta.fulfill({ json: { id: 'persona', nombre: 'Ana Prueba', email: 'ana@example.invalid', rol, tiene_foto: tieneFoto, equipos_responsable: [] } }))
    await page.route('**/api/usuarios/persona/foto', ruta => {
      if (ruta.request().method() === 'POST') { tieneFoto = true; subidas++; return ruta.fulfill({ json: { foto: true, mime: 'image/png' } }) }
      if (ruta.request().method() === 'DELETE') { tieneFoto = false; borrados++; return ruta.fulfill({ json: { foto: false } }) }
      return tieneFoto ? ruta.fulfill({ contentType: 'image/png', body: imagen }) : ruta.fulfill({ status: 404 })
    })
    await page.goto('/panel/perfil')
    await expect(page.getByRole('button', { name: 'Cambiar la foto', exact: true })).toBeVisible()
    await page.getByLabel('Foto de Ana Prueba', { exact: true }).setInputFiles({ name: 'perfil.png', mimeType: 'image/png', buffer: imagen })
    await expect(page.locator('main img')).toHaveCount(1)
    await expect(page.getByRole('button', { name: 'Cambiar la foto', exact: true })).toBeEnabled()
    expect(subidas).toBe(1)
    await page.getByRole('button', { name: 'Quitar', exact: true }).click()
    await expect(page.locator('main img')).toHaveCount(0)
    expect(borrados).toBe(1)
    await expect(page).toHaveURL(/\/panel\/perfil$/)
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  })
}

test('eliminar una versión anual exige confirmar y conserva los otros años', async ({ page }) => {
  await portal(page, false, 'administrador')
  let items = [2026, 2025].map(anio => ({ id: String(anio), anio, fuente: 'archivo_anual', archivo_nombre: `inventario-${anio}.xlsx`, cerrado_en: `${anio}-10-20T14:00:00Z`, total_items: 1 }))
  let borrados = 0
  await page.route('**/api/campanas/versiones/historico', ruta => ruta.fulfill({ json: { items } }))
  await page.route('**/api/campanas/versiones/*/equipos?*', ruta => ruta.fulfill({ json: { items: [], total: 0, pagina: 1, total_paginas: 1 } }))
  await page.route('**/api/campanas/versiones/2026', ruta => {
    expect(ruta.request().method()).toBe('DELETE')
    borrados++; items = items.filter(v => v.id !== '2026')
    return ruta.fulfill({ json: { eliminada: true } })
  })
  await page.goto('/panel/inventario-anual')
  await page.getByRole('button', { name: 'Eliminar versión', exact: true }).click()
  const dialogo = page.getByRole('dialog')
  await expect(dialogo).toContainText('inventario-2026.xlsx')
  await dialogo.getByRole('button', { name: 'Cancelar', exact: true }).click()
  expect(borrados).toBe(0)
  await page.getByRole('button', { name: 'Eliminar versión', exact: true }).click()
  await dialogo.getByRole('button', { name: 'Eliminar versión', exact: true }).click()
  await expect(dialogo).toBeHidden()
  await expect(page.getByLabel('Año y versión del inventario')).toHaveValue('2025')
  await expect(page.locator('.anual-years').getByRole('button', { name: /2026/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Comparar años', exact: true })).toBeDisabled()
  expect(borrados).toBe(1)
})

test('archivo anual: acceso por año, comparación y diseño adaptable', async ({ page }) => {
  await portal(page, false, 'administrador')
  const items = [2026, 2025].map(anio => ({ id: String(anio), anio, codigo_campana: String(anio), archivo_nombre: `inventario-${anio}.xlsx`, fuente: 'archivo_anual', cerrado_en: `${anio}-10-20T14:00:00Z`, cerrado_por: 'Equipo TI', total_items: 1 }))
  await page.route('**/api/campanas/versiones/historico', ruta => ruta.fulfill({ json: { items } }))
  await page.route('**/api/campanas/versiones/*/equipos?*', ruta => ruta.fulfill({ json: { items: [{ nombre: `Laptop ${ruta.request().url().includes('/2025/') ? 2025 : 2026}`, tipo: 'Laptop', oficina: 'Soporte', zona: 'Palacio', responsable: 'Ana', campos: {} }], total: 1, pagina: 1, total_paginas: 1 } }))
  await page.route('**/api/campanas/versiones/comparar?*', ruta => ruta.fulfill({ json: { suficiente_datos: true, versiones: [], totales: { '2025': 1, '2026': 1 }, altas: [], bajas: [], traslados: [], cambios: [], sin_cambios: 1 } }))
  await page.goto('/panel/inventario-anual')
  await expect(page.getByText('Laptop 2026', { exact: true }).filter({ visible: true })).toBeVisible()
  await page.locator('.anual-years').getByRole('button', { name: /2025/ }).click()
  await expect(page.getByText('Laptop 2025', { exact: true }).filter({ visible: true })).toBeVisible()
  await page.getByRole('button', { name: 'Comparar años', exact: true }).click()
  await expect(page.getByText('Sin cambios', { exact: true })).toBeVisible()
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(t => document.documentElement.setAttribute('data-tema', t), tema)
    for (const width of [1440, 820, 320]) {
      await page.setViewportSize({ width, height: 1000 })
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
    await page.setViewportSize({ width: 1440, height: 1000 })
    const auditoria = await new AxeBuilder({ page }).include('.anual-workspace').analyze()
    expect(auditoria.violations.filter(v => ['serious', 'critical'].includes(v.impact ?? ''))).toEqual([])
    await page.screenshot({ path: `../.codex-pdf-tools/anual-diseno-${tema}.png`, fullPage: true })
  }
})

test('los cambios remotos no borran una edición de ticket sin guardar', async ({ page }) => {
  const vivo = await portal(page, false, 'administrador')
  let descripcion = 'La impresora no imprime documentos'
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: { id: 'caso', codigo: 'TKT-2026-000001', estado: 'nuevo', prioridad: 'media', categoria: 'Impresora', asunto: 'La impresora no imprime', descripcion, creado_en: '2026-10-19T22:00:00Z', tiene_chat: true, adjuntos: [], eventos: [] } }))
  await page.goto('/panel/tickets/caso')
  const ficha = page.getByLabel('Incidencia reportada', { exact: true })
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await ficha.getByLabel('Título de la incidencia', { exact: true }).fill('Este título todavía no está guardado')
  descripcion = 'Descripción actualizada desde otra cuenta'
  vivo.publicarCambio(['tickets'])
  await expect(ficha.getByText(descripcion, { exact: true })).toBeVisible()
  await expect(ficha.getByLabel('Título de la incidencia', { exact: true })).toHaveValue('Este título todavía no está guardado')
})

test('una cuenta desactivada abandona su sesión al recibir el aviso remoto', async ({ page }) => {
  const vivo = await portal(page, false, 'administrador')
  await page.goto('/panel/perfil')
  await expect(page.getByRole('heading', { name: 'Mi cuenta', exact: true })).toBeVisible()
  await expect.poll(() => vivo.avisosConectados()).toBe(true)
  await page.route('**/api/auth/sesion', ruta => ruta.fulfill({ status: 403, json: { mensaje: 'Esta cuenta está desactivada.' } }))
  vivo.publicarCambio(['usuarios'])
  await expect(page).toHaveURL(/\/acceder\/ti$/)
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeVisible()
})

test('cambios remotos actualizan nombre, foto y compañeros en cuentas abiertas', async ({ page, context }) => {
  const otra = await context.newPage()
  const administrador = await portal(page, false, 'administrador')
  const trabajador = await portal(otra)
  let nombre = 'Ana Prueba'
  let nuevoCompanero = false
  let fotos = 0
  await page.route('**/api/mi-perfil', ruta => ruta.fulfill({ json: { id: 'persona', nombre, email: 'ana@example.invalid', rol: 'administrador', tiene_foto: true, equipos_responsable: [], oficina_nombre: 'SOPORTE' } }))
  await page.route('**/api/usuarios/persona/foto', ruta => { fotos++; return ruta.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=', 'base64') }) })
  await otra.route('**/api/usuarios/companeros', ruta => ruta.fulfill({ json: { items: [{ id: 'companero', nombre: 'Luis Prueba' }, ...(nuevoCompanero ? [{ id: 'nuevo', nombre: 'Trabajador recién agregado' }] : [])] } }))
  await page.goto('/panel/perfil')
  await otra.goto('/reportar?tipo=Impresora')
  await otra.getByRole('button', { name: 'Para un compañero', exact: true }).click()
  await expect(page.locator('main').getByText('Ana Prueba', { exact: true })).toBeVisible()
  await expect.poll(() => fotos).toBeGreaterThan(0)
  await expect.poll(() => administrador.avisosConectados() && trabajador.avisosConectados()).toBe(true)
  const fotosAntes = fotos
  nombre = 'Ana Actualizada'
  nuevoCompanero = true
  administrador.publicarCambio(['usuarios'], ['persona'])
  trabajador.publicarCambio(['usuarios'], ['persona'])
  await expect(page.locator('main').getByText('Ana Actualizada', { exact: true })).toBeVisible()
  await expect.poll(() => fotos).toBeGreaterThan(fotosAntes)
  await expect(otra.getByLabel('Persona que necesita ayuda').getByRole('option', { name: 'Trabajador recién agregado', exact: true })).toHaveCount(1)
  await expect(page).toHaveURL(/\/panel\/perfil$/)
  await expect(otra).toHaveURL(/\/reportar\?tipo=Impresora$/)
  await otra.close()
})

test('inventario remoto se refresca y recupera cambios al reconectar sin recargar', async ({ page }) => {
  const vivo = await portal(page, false, 'administrador')
  let nombre = 'Laptop inicial'
  await page.route('**/api/equipos/mis', ruta => ruta.fulfill({ json: { por_conjunto: [{ conjunto: 'Equipos individuales', equipos: [{ id: 'laptop', nombre_equipo: nombre, tipo: 'Laptop', estado: 'Operativo' }] }], uso_comun_oficina: [] } }))
  await page.goto('/panel/mis-equipos')
  await expect(page.getByText('Laptop inicial', { exact: true })).toBeVisible()
  await expect.poll(() => vivo.avisosConectados()).toBe(true)
  nombre = 'Laptop recién agregada'
  vivo.publicarCambio(['equipos'])
  await expect(page.getByText('Laptop recién agregada', { exact: true })).toBeVisible()
  nombre = 'Laptop editada durante desconexión'
  vivo.reconectarAvisos()
  await expect(page.getByText('Laptop editada durante desconexión', { exact: true })).toBeVisible({ timeout: 10_000 })
  await expect(page).toHaveURL(/\/panel\/mis-equipos$/)
})

test('historial destaca cambios reales y oculta ruido interno y asignaciones repetidas', async ({ page }) => {
  await portal(page, false, 'administrador')
  const actor = { nombre: 'Jose Leyva', rol: 'administrador' }
  const evento = (id: string, tipo: string, detalle = {}, resumen = '') => ({ id, tipo, detalle, resumen, actor, fecha: '2026-10-19T22:25:00Z' })
  const eventos = [
    evento('1', 'creado', {}, 'Ticket reportado por Jose Leyva'),
    evento('2', 'actualizado', { campos: ['asunto_editado_ti', 'actualizado_en', 'categoria'], antes: { categoria: 'Hardware' }, despues: { categoria: 'Hardware' } }, 'actualizo: asunto_editado_ti, actualizado_en'),
    evento('3', 'asignado', { tecnico: 'Jose Leyva' }, 'Asignado a Jose Leyva'),
    evento('4', 'asignado', { tecnico: 'Jose Leyva' }, 'Asignado a Jose Leyva'),
    evento('5', 'mensaje', {}, 'Escribió en el chat'),
    evento('6', 'actualizado', { campos: ['activo_id', 'activo_nombre', 'actualizado_en'], antes: { activo_id: null }, despues: { activo_id: 'equipo', activo_nombre: 'Impresora' } }, 'actualizo: activo_id, activo_nombre, actualizado_en'),
    evento('7', 'estado', { estado_nuevo: 'cerrado' }, 'Cerrado'),
  ]
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: { id: 'caso', codigo: 'TKT-2026-000001', estado: 'cerrado', prioridad: 'media', asunto: 'No imprime', descripcion: 'La impresora no imprime', creado_en: '2026-10-19T22:00:00Z', tiene_chat: true, adjuntos: [], eventos } }))
  await page.goto('/panel/tickets/caso')
  const historial = page.getByRole('list', { name: 'Cambios importantes del ticket' })
  await expect(historial.getByRole('listitem')).toHaveCount(4)
  await expect(historial.getByText('Asignado a Jose Leyva', { exact: true })).toHaveCount(1)
  await expect(historial.getByText('Equipo afectado actualizado', { exact: true })).toBeVisible()
  await expect(historial.getByText('Ticket finalizado', { exact: true })).toBeVisible()
  await expect(historial).not.toContainText('actualizado_en')
  await expect(historial).not.toContainText('Escribió en el chat')
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(valor => { document.documentElement.dataset.tema = valor }, tema)
    await historial.screenshot({ path: `../.codex-pdf-tools/historial-importante-${tema}.png` })
  }
})

test('usuario abre el perfil de su tecnico sin salir del reporte', async ({ page }) => {
  await portal(page)
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: { id: 'caso', codigo: 'TKT-2026-000001', estado: 'en_progreso', prioridad: 'media', asunto: 'Office no abre', descripcion: 'Necesito ayuda con Office', tecnico_id: 'tecnico', tecnico_nombre: 'Jose Leyva', tiene_chat: true, creado_en: '2026-10-17T14:00:00Z', adjuntos: [] } }))
  await page.route('**/api/tickets/caso/tecnico-perfil', ruta => ruta.fulfill({ json: { nombre: 'Jose Leyva', cargo: 'Técnico de soporte', oficina: 'OFICINA DE TECNOLOGÍAS DE LA INFORMACIÓN Y COMUNICACIÓN', especialidades: ['Redes', 'Equipos'] } }))
  await page.goto('/mis-tickets/caso')
  await page.getByRole('button', { name: 'Ver perfil de Jose Leyva', exact: true }).click()
  const ficha = page.getByRole('dialog')
  await expect(ficha.getByRole('heading', { name: 'Jose Leyva', exact: true })).toBeVisible()
  await expect(ficha.getByText('Técnico de soporte', { exact: true })).toBeVisible()
  await expect(ficha.getByText('Redes', { exact: true })).toBeVisible()
  await expect(ficha.getByText('OFICINA DE TECNOLOGÍAS DE LA INFORMACIÓN Y COMUNICACIÓN', { exact: true })).toBeVisible()
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(valor => { document.documentElement.dataset.tema = valor }, tema)
    await ficha.screenshot({ path: `../.codex-pdf-tools/perfil-tecnico-${tema}.png` })
  }
  await page.setViewportSize({ width: 320, height: 900 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await ficha.getByRole('button', { name: 'Cerrar', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page).toHaveURL(/\/mis-tickets\/caso$/)
})

for (const rol of ['administrador', 'tecnico'] as const) test(`mi cuenta conserva el panel de ${rol} al abrir equipos y ayuda`, async ({ page }) => {
  await portal(page, false, rol)
  await page.route('**/api/kb/articulos/guia', ruta => ruta.fulfill({ json: { id: 'guia', titulo: 'Guía de impresora', cuerpo: 'Revisa el papel de la impresora.', pasos: [], etiquetas: [], relacionados: [], actualizado_en: '2026-10-18T14:00:00Z' } }))
  await page.route('**/api/kb/articulos?**', ruta => ruta.fulfill({ json: { items: [{ id: 'guia', titulo: 'Guía de impresora', resumen: 'Ayuda para imprimir', categoria: 'Impresora', visualizaciones: 1 }], total: 1 } }))
  await page.goto('/panel/perfil')
  await page.getByRole('link', { name: 'Mis equipos', exact: true }).click()
  await expect(page).toHaveURL(/\/panel\/mis-equipos$/)
  await expect(page.getByRole('heading', { name: 'Mis equipos', exact: true })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Navegación del panel' })).toBeVisible()
  await page.goto('/panel/perfil')
  await page.getByRole('link', { name: 'Guías de ayuda', exact: true }).click()
  await expect(page).toHaveURL(/\/panel\/ayuda$/)
  await page.getByRole('link', { name: /Guía de impresora/ }).click()
  await expect(page).toHaveURL(/\/panel\/ayuda\/guia$/)
  await expect(page.getByRole('navigation', { name: 'Navegación del panel' })).toBeVisible()
  await page.getByRole('link', { name: 'Ayuda', exact: true }).click()
  await expect(page).toHaveURL(/\/panel\/ayuda$/)
  for (const ruta of ['/mis-equipos', '/ayuda', '/ayuda/guia', '/perfil']) {
    await page.goto(ruta)
    await expect(page.getByRole('navigation', { name: 'Navegación del panel' })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Navegación del portal' })).toHaveCount(0)
  }
})

for (const reportePara of ['propio', 'oficina'] as const) test(`detalle distingue destino ${reportePara} sin duplicar el nombre`, async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: {
    id: 'caso', codigo: 'TKT-2026-000001', asunto: 'No imprime', descripcion: 'No imprime los documentos',
    estado: 'nuevo', prioridad: 'media', origen: 'usuario', reporte_para: reportePara,
    reportante_id: 'persona', afectado_id: 'persona', reportante_nombre: 'Ana Prueba', afectado_nombre: 'Ana Prueba',
    oficina_id: 'oficina', oficina_nombre: 'SOPORTE', creado_en: '2026-10-17T14:00:00Z', tiene_chat: true, adjuntos: [],
  } }))
  await page.goto('/panel/tickets/caso')
  const incidencia = page.getByLabel('Incidencia reportada', { exact: true })
  await expect(incidencia.getByText('Ana Prueba', { exact: true })).toHaveCount(1)
  await expect(incidencia.getByText(reportePara === 'oficina' ? 'La oficina · equipo compartido' : 'Para sí mismo', { exact: true })).toBeVisible()
  if (reportePara === 'oficina') await expect(page.getByText('Reportado para la oficina', { exact: true })).toBeVisible()
})

test('oficina muestra tipos compactos y reporta sin vincular un dispositivo', async ({ page }) => {
  const api = await portal(page)
  await page.route('**/api/portal/equipos-oficina-tipos', ruta => ruta.fulfill({ json: { tipos: ['Impresora', 'Monitor'] } }))
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto('/reportar?tipo=Impresora')
  await expect(page.getByRole('button', { name: 'Para mí', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('¿La impresora la comparten en tu oficina?', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Para la oficina', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Para la oficina', exact: true })).toHaveAttribute('aria-pressed', 'true')
  const opciones = page.getByRole('group', { name: 'Tipo de equipo de la oficina', exact: true })
  await expect(opciones.getByRole('button', { name: 'Impresora', exact: true })).toHaveCount(1)
  await opciones.getByRole('button', { name: 'Impresora', exact: true }).click()
  await page.getByLabel('¿Qué está pasando?').fill('La impresora de la oficina no imprime los documentos')
  await page.getByRole('radio', { name: /No puedo trabajar/ }).check()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  expect(api.solicitudes[0]).toMatchObject({ reporte_para: 'oficina', activo_no_identificado: 'Impresora' })
  expect(api.solicitudes[0]).not.toHaveProperty('activo_id')
  expect(api.solicitudes[0]).not.toHaveProperty('conjunto_id')
})

test('calidad muestra porcentaje de faltantes y porcentaje por campo', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/calidad-inventario*', ruta => ruta.fulfill({ json: { total_activos: 10, esperados_totales: 100, faltantes_totales: 25, porcentaje_datos: 75, porcentaje_global: 75, con_datos_completos: 5, por_campo: [{ campo: 'direccion_ip', faltantes: 5 }], por_zona: [], por_tipo: [], por_oficina: [] } }))
  await page.goto('/panel/equipos/calidad')
  await expect(page.getByText('25%', { exact: true })).toBeVisible()
  await expect(page.getByText('25 de 100 casillas esperadas', { exact: true })).toBeVisible()
  const barra = page.getByRole('meter', { name: 'Equipos sin Dirección IP', exact: true })
  await expect(barra).toHaveAttribute('aria-valuenow', '50')
  await expect(barra.locator('div')).toHaveAttribute('style', /width: 50%/)
  await expect(page.getByText('5 equipos', { exact: true })).toBeVisible()
  await expect(page.getByText('50%', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 320, height: 900 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})

test('reporte propio no pide identificar equipos ni asigna automáticamente la PC', async ({ page }) => {
  const api = await portal(page)
  await page.goto('/reportar?tipo=Sistema%2Fprograma')
  await expect(page.getByRole('button', { name: 'Para mí', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('¿En qué equipo te pasa?')).toHaveCount(0)
  await page.getByLabel('¿Qué está pasando?').fill('No puedo abrir Office y necesito ayuda')
  await page.getByRole('radio', { name: /No puedo trabajar/ }).check()
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  expect(api.solicitudes[0]).not.toHaveProperty('activo_id')
  expect(api.solicitudes[0]).not.toHaveProperty('conjunto_id')
})

test('TI puede elegir laptop independiente para programas y para formateo', async ({ page }) => {
  const api = await portal(page, false, 'administrador')
  await page.route('**/api/usuarios/*/destinos-ticket', ruta => ruta.fulfill({ json: { equipos: [{ id: 'laptop', nombre: 'Laptop Lenovo', tipo: 'Laptop', grupo: 'propios', conjunto_id: null }, { id: 'cpu', nombre: 'CPU de escritorio', tipo: 'CPU', grupo: 'propios', conjunto_id: 'conjunto' }], conjuntos: [{ id: 'conjunto', nombre: 'Computadora N°1', grupo: 'propios' }] } }))
  await page.goto('/panel/tickets/nuevo')
  await page.getByRole('combobox', { name: 'Persona afectada' }).fill('Ana')
  await page.getByRole('button', { name: /Ana Prueba.*SOPORTE/ }).click()
  await page.getByLabel('Asunto').fill('Office no abre en laptop')
  await page.getByLabel('Categoría', { exact: true }).selectOption('Sistema / Programa')
  await page.getByLabel('Computadora afectada').selectOption('equipo:laptop')
  await expect(page.getByLabel('Computadora afectada')).toHaveValue('equipo:laptop')
  await page.getByLabel('Categoría', { exact: true }).selectOption('Formateo')
  await expect(page.getByLabel('Equipo o computadora afectada')).toHaveValue('equipo:laptop')
  await page.getByRole('button', { name: 'Registrar ticket', exact: true }).click()
  await expect(page).toHaveURL(/panel\/tickets\/caso$/)
  expect(api.solicitudes[0]).toMatchObject({ categoria: 'Formateo', activo_id: 'laptop' })
  expect(api.solicitudes[0]).not.toHaveProperty('conjunto_id')
})

test('chatbot revela la respuesta progresivamente con una sola consulta', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  let consultas = 0
  const respuesta = 'Puedes consultar los equipos y tickets. '.repeat(40) + 'Fin de la respuesta.'
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true } }))
  await page.route('**/api/ia/chatbot', ruta => { consultas++; return ruta.fulfill({ json: { disponible: true, texto: respuesta, fuentes: [] } }) })
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await page.getByLabel('Tu consulta al asistente TI').fill('Como consulto los equipos')
  await page.getByRole('button', { name: 'Enviar', exact: true }).click()
  const texto = page.locator('.ti-message-assistant .ti-message-content')
  await expect(texto).toBeVisible()
  expect((await texto.innerText()).length).toBeLessThan(respuesta.length)
  await expect(texto).toContainText('Fin de la respuesta.')
  expect(consultas).toBe(1)
})

test('chatbot conserva mensajes, consumo y ultima posicion al cerrar y cambiar de pagina', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true } }))
  await page.route('**/api/ia/chatbot', ruta => ruta.fulfill({ json: { disponible: true, texto: 'Detalle del sistema.\n\n'.repeat(60) + 'Ultimo mensaje de la respuesta.', fuentes: [{ titulo: 'Ver tickets', ruta: '/panel/tickets' }], uso: { entrada: 100, salida: 200, razonamiento: 50, total: 350 } } }))
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await page.getByLabel('Tu consulta al asistente TI').fill('Como se usa el inventario')
  await page.getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('dialog').getByText('350 tokens usados')).toBeVisible()
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click()
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  const registro = page.getByRole('log')
  await expect.poll(() => registro.evaluate(e => e.scrollHeight - e.clientHeight - e.scrollTop)).toBeLessThan(2)
  await page.getByRole('link', { name: 'Ver tickets', exact: true }).click()
  await expect(page.getByText('Filtra por estado, prioridad, zona o persona. Guarda las combinaciones que repites.')).toBeVisible()
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await expect(page.getByRole('dialog').getByText('350 tokens usados')).toBeVisible()
  await expect(page.getByRole('log')).toContainText('Ultimo mensaje de la respuesta.')
  await expect.poll(() => registro.evaluate(e => e.scrollHeight - e.clientHeight - e.scrollTop)).toBeLessThan(2)
  await page.getByRole('button', { name: 'Nueva consulta', exact: true }).click()
  await expect(page.getByRole('dialog').getByText('0 consultas')).toBeVisible()
})

test('bordes de cabecera y menu quedan alineados', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/panel')
  const nav = page.getByRole('navigation', { name: 'Navegación del panel' })
  await expect(nav).toBeVisible()
  const bordeMenu = await nav.locator(':scope > div').first().evaluate(e => e.getBoundingClientRect().bottom)
  const bordeCabecera = await page.locator('.ti-barra-superior').evaluate(e => e.getBoundingClientRect().bottom)
  expect(Math.abs(bordeMenu - bordeCabecera)).toBeLessThan(1)
})

test('login azul adapta superficies, contraste y formulario en ambos temas', async ({ page }) => {
  await page.route('**/api/**', async ruta => {
    const url = new URL(ruta.request().url())
    if (!url.pathname.startsWith('/api/')) return ruta.continue()
    return ruta.fulfill({ json: url.pathname.endsWith('/instalacion') ? { hay_admin: true } : { institucion: 'Municipalidad Provincial de Casma' } })
  })
  await page.goto('/acceder/usuarios')
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeVisible()
  const fondos: string[] = []
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(valor => { document.documentElement.dataset.tema = valor }, tema)
    for (const ancho of [320, 1440]) {
      await page.setViewportSize({ width: ancho, height: 900 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
      await expect(page.getByLabel('Correo institucional')).toBeVisible()
      await page.screenshot({ path: `../.codex-pdf-tools/login-azul-${tema}-${ancho}.png` })
    }
    fondos.push(await page.locator('.acceso-tarjeta').evaluate(e => getComputedStyle(e).backgroundImage))
    const accesibilidad = await new AxeBuilder({ page }).include('.acceso-tarjeta').analyze()
    expect(accesibilidad.violations).toEqual([])
  }
  expect(fondos[0]).not.toBe(fondos[1])
  await page.getByRole('button', { name: 'Cambiar a tema claro', exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'claro')
})

test('barra superior verde y grupos del menu se contraen y extienden', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/panel')
  const nav = page.getByRole('navigation', { name: 'Navegación del panel' })
  for (const [grupo, enlace] of [['Equipos', 'Inventario'], ['Tickets', 'Abiertos'], ['Más', 'Base de conocimiento']]) {
    await nav.getByRole('button', { name: `Contraer ${grupo}`, exact: true }).click()
    await expect(nav.getByRole('link', { name: enlace, exact: true })).toHaveCount(0)
    const extender = nav.getByRole('button', { name: `Extender ${grupo}`, exact: true })
    await expect(extender).toHaveAttribute('aria-expanded', 'false')
    await extender.click()
    await expect(nav.getByRole('link', { name: enlace, exact: true })).toBeVisible()
  }
  await page.screenshot({ path: '../.codex-pdf-tools/cabecera-verde-grupos.png' })
  await nav.getByRole('button', { name: 'Contraer Equipos', exact: true }).click()
  await nav.getByRole('link', { name: 'Equipos', exact: true }).click()
  await expect(page).toHaveURL(/\/panel\/equipos$/)
  await expect(nav.getByRole('link', { name: 'Inventario', exact: true })).toBeVisible()
})

test('navegacion verde conserva menus expandidos, contraidos y el cajon movil', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/panel')
  const navegacion = page.getByRole('navigation', { name: 'Navegación del panel' })
  await expect(navegacion.getByRole('link', { name: 'Tickets', exact: true })).toBeVisible()
  await page.screenshot({ path: '../.codex-pdf-tools/navegacion-verde-escritorio.png' })
  await page.getByRole('button', { name: /Reducir el/ }).click()
  await navegacion.getByRole('button', { name: 'Tickets', exact: true }).click()
  await page.getByRole('link', { name: 'Abiertos', exact: true }).click()
  await expect(page).toHaveURL(/\/panel\/tickets$/)
  await expect(page.getByText('Filtra por estado, prioridad, zona o persona. Guarda las combinaciones que repites.')).toBeVisible()
  await page.getByRole('button', { name: /Ampliar el/ }).click()
  await page.setViewportSize({ width: 390, height: 850 })
  await page.getByRole('button', { name: 'Abrir el menú', exact: true }).click()
  await expect(navegacion).toBeInViewport()
  expect(await navegacion.evaluate(e => e.scrollWidth <= e.clientWidth + 1)).toBe(true)
  await page.screenshot({ path: '../.codex-pdf-tools/navegacion-verde-movil.png' })
  await navegacion.getByRole('link', { name: 'Usuarios', exact: true }).click()
  await expect(page).toHaveURL(/\/panel\/usuarios$/)
  await expect(navegacion).not.toBeInViewport()
})

test('consultas internas muestran resultado, comparación y fuentes en ambos temas', async ({ page }) => {
  await portal(page, false, 'administrador')
  const pregunta = '¿Qué oficina tiene más incidencias en el periodo seleccionado?'
  let mensajes: Record<string, unknown>[] = []
  let solicitudes = 0
  const respuesta = { texto: 'Soporte TI registra 30 tickets, entre el 01/10/2026 y el 20/10/2026.\n\nEl volumen no mide por sí solo la gravedad.', fuentes: ['ranking_oficinas'], periodo: '30d', explicacion: 'Consulta directa de solo lectura.', tabla: { columnas: [{ clave: 'oficina', titulo: 'Oficina' }, { clave: 'total', titulo: 'Tickets' }], filas: [{ oficina: 'Soporte TI', total: 30 }, { oficina: 'Caja', total: 1 }] } }
  await page.route('**/api/analitica/equipos-prediccion', ruta => ruta.fulfill({ json: { familias: [] } }))
  await page.route('**/api/ia/asistente/preguntas', ruta => ruta.fulfill({ json: { preguntas: [pregunta, '¿Qué zona tiene más tickets?', '¿Qué técnico está disponible ahora?', '¿Cuáles son las causas más frecuentes?', '¿Qué familias de equipos tienen más fallas?'] } }))
  await page.route('**/api/ia/asistente/conversaciones', ruta => ruta.fulfill({ json: { items: mensajes.length ? [{ id: 'consulta', titulo: pregunta }] : [] } }))
  await page.route('**/api/ia/asistente/conversaciones/consulta', ruta => ruta.fulfill({ json: { id: 'consulta', titulo: pregunta, mensajes } }))
  await page.route('**/api/ia/asistente', ruta => {
    solicitudes++
    expect(ruta.request().postDataJSON().pregunta).toBe(pregunta)
    expect(ruta.request().postDataJSON().filtros).toEqual({ periodo: '30d' })
    mensajes = [{ rol: 'user', texto: pregunta }, { rol: 'assistant', ...respuesta }]
    return ruta.fulfill({ json: { conversacion_id: 'consulta', ...respuesta } })
  })
  await page.goto('/panel/analisis?tab=asistente')
  await expect(page.getByRole('heading', { name: 'Tus datos, fáciles de entender' })).toBeVisible()
  await expect(page.getByRole('button', { name: pregunta })).toContainText('Oficinas con más problemas')
  await expect(page.locator('.datos-options button')).toHaveCount(5)
  for (const ancho of [320, 1440]) {
    await page.setViewportSize({ width: ancho, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const titulo = await page.getByRole('heading', { name: '¿Qué quieres saber?', exact: true }).boundingBox()
    const nueva = await page.getByRole('button', { name: 'Nueva conversación', exact: true }).boundingBox()
    expect(titulo && nueva && (titulo.y + titulo.height <= nueva.y || titulo.x + titulo.width <= nueva.x)).toBeTruthy()
    expect(await page.locator('.datos-suggestion small').evaluateAll(elementos => elementos.every(e => e.scrollWidth <= e.clientWidth + 1))).toBe(true)
    const bienvenida = await page.getByRole('heading', { name: 'Empieza con un clic' }).boundingBox()
    const registro = await page.getByRole('log').boundingBox()
    expect(bienvenida && registro && bienvenida.y >= registro.y).toBeTruthy()
    await page.screenshot({ path: `../.codex-pdf-tools/asistente-interno-inicio-${ancho}.png`, fullPage: true })
  }
  expect((await new AxeBuilder({ page }).include('.datos-lab').analyze()).violations).toEqual([])
  await page.getByRole('button', { name: pregunta }).click()
  await expect(page.getByRole('log')).toContainText('Soporte TI registra 30 tickets')
  await expect(page.getByRole('figure', { name: 'Comparación de resultados' })).toBeVisible()
  await expect(page.getByText('Tickets por oficina', { exact: true })).not.toBeVisible()
  await page.getByText('De dónde sale esta respuesta', { exact: true }).click()
  await expect(page.getByText('Tickets por oficina', { exact: true })).toBeVisible()
  await page.getByText('Ver datos de la respuesta', { exact: true }).click()
  await expect(page.getByRole('cell', { name: '30', exact: true })).toBeVisible()
  expect(solicitudes).toBe(1)
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(tema => document.documentElement.setAttribute('data-tema', tema), tema)
    for (const ancho of [320, 1440]) {
      await page.setViewportSize({ width: ancho, height: 1000 })
      await expect(page.locator('.datos-lab')).toBeVisible()
      expect(await page.locator('.datos-workspace').evaluate(e => e.getBoundingClientRect().height)).toBeLessThanOrEqual(760)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await page.screenshot({ path: `../.codex-pdf-tools/consultas-datos-${tema}-${ancho}.png`, fullPage: true })
    }
    const accesibilidad = await new AxeBuilder({ page }).include('.datos-lab').analyze()
    expect(accesibilidad.violations).toEqual([])
  }
  await page.reload()
  await expect(page.getByRole('log')).toContainText('Soporte TI registra 30 tickets')
  expect(solicitudes).toBe(1)
})

test('asistente interno escribe progresivamente sin repetir consultas y respeta movimiento reducido', async ({ page }) => {
  await portal(page, false, 'administrador')
  let solicitudes = 0
  const texto = 'Puedo consultar tus datos del servicio. '.repeat(35) + 'Fin de la respuesta interna.'
  const mensajes = [{ rol: 'user', texto: 'Para qué sirves' }, { rol: 'assistant', texto, fuentes: ['guia_analisis'] }]
  await page.route('**/api/analitica/equipos-prediccion', ruta => ruta.fulfill({ json: { familias: [] } }))
  await page.route('**/api/ia/asistente/preguntas', ruta => ruta.fulfill({ json: { preguntas: [] } }))
  await page.route('**/api/ia/asistente/conversaciones', ruta => ruta.fulfill({ json: { items: [{ id: 'escritura', titulo: 'Ayuda' }] } }))
  await page.route('**/api/ia/asistente/conversaciones/escritura', ruta => ruta.fulfill({ json: { id: 'escritura', titulo: 'Ayuda', mensajes } }))
  await page.route('**/api/ia/asistente', ruta => { solicitudes++; return ruta.fulfill({ json: { conversacion_id: 'escritura', texto, fuentes: ['guia_analisis'] } }) })
  await page.goto('/panel/analisis?tab=asistente')
  await page.getByLabel('Tu pregunta', { exact: true }).fill('Para qué sirves')
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  const respuesta = page.locator('.datos-result .datos-answer').last()
  await expect(respuesta).toHaveAttribute('aria-busy', 'true')
  expect((await respuesta.innerText()).length).toBeLessThan(texto.length)
  await expect(respuesta).toHaveText(texto)
  expect(solicitudes).toBe(1)
  await page.reload()
  await expect(respuesta).toHaveText(texto)
  await expect(respuesta).toHaveAttribute('aria-busy', 'false')
  expect(solicitudes).toBe(1)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: 'Nueva conversación', exact: true }).click()
  await page.getByLabel('Tu pregunta', { exact: true }).fill('Para qué sirves')
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  await expect(respuesta).toHaveText(texto)
  await expect(respuesta).toHaveAttribute('aria-busy', 'false')
  expect(solicitudes).toBe(2)
})

test('asistente interno explica su función con formato de chat y sin datos inventados', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/analitica/equipos-prediccion', ruta => ruta.fulfill({ json: { familias: [] } }))
  await page.route('**/api/ia/asistente/preguntas', ruta => ruta.fulfill({ json: { preguntas: ['¿Para qué sirve este asistente?'] } }))
  await page.route('**/api/ia/asistente/conversaciones', ruta => ruta.fulfill({ json: { items: [] } }))
  await page.route('**/api/ia/asistente', ruta => ruta.fulfill({ json: { conversacion_id: 'ayuda', texto: 'Te ayudo a entender los datos de la mesa de ayuda. Solo consulto información permitida para tu cuenta.', fuentes: ['guia_analisis'], periodo: null } }))
  await page.goto('/panel/analisis?tab=asistente')
  await page.getByRole('button', { name: '¿Para qué sirve este asistente?' }).click()
  await expect(page.getByRole('log')).toContainText('Te ayudo a entender los datos')
  await expect(page.getByRole('log').getByText('Asistente interno', { exact: true })).toBeVisible()
  await expect(page.getByRole('log').getByText('Ayuda del sistema', { exact: true })).toBeVisible()
  await expect(page.getByRole('figure', { name: 'Comparación de resultados' })).toHaveCount(0)
})

test('centro de análisis explica cifras, conserva filtros y permite continuar una consulta', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const pregunta = '¿Hay más tickets que en el periodo anterior?'
  let mensajes: Record<string, unknown>[] = []
  const enviadas: string[] = []
  const datos = {
    kpis: { tickets_analizados: 30, tickets_periodo_anterior: 20, cerrados: 12, tiempo_medio_resolucion_min: null, cumplimiento_sla: 50, cerrados_a_tiempo: 6, satisfaccion_promedio: null, precision_clasificacion: null, muestras_satisfaccion: 0, muestras_tiempo: 0, suficiente_datos: true, periodo: { desde: '2026-10-01', hasta: '2026-10-30' } },
    ranking_oficinas: { items: [{ id: 'oficina', oficina: 'Soporte TI', total: 30, criticas: 2 }] }, ranking_zonas: { items: [] }, ranking_conjuntos: { items: [] },
    riesgo_sla_oficina: { items: [{ nombre: 'Soporte TI', vencidos: 2, sin_plazo: 1 }] }, causas: { items: [] },
    tendencia: { serie: [{ fecha: '2026-10-01', valor: 10 }, { fecha: '2026-10-02', valor: 20 }] }, actualizado_en: '2026-10-30T17:00:00Z',
  }
  await page.route('**/api/analitica/panel?**', ruta => ruta.fulfill({ json: datos }))
  await page.route('**/api/analitica/equipos-prediccion', ruta => ruta.fulfill({ json: { familias: [] } }))
  await page.route('**/api/ia/asistente/preguntas', ruta => ruta.fulfill({ json: { preguntas: [pregunta, '¿Puedes darme un resumen del servicio?', '¿Cuántos equipos tenemos registrados?', '¿Qué técnico está disponible ahora?', '¿Para qué sirve este asistente?', '¿Qué tickets tienen el plazo vencido?', '¿Cuántos tickets están abiertos y cerrados?', '¿Cómo evolucionan los tickets por día?'] } }))
  await page.route('**/api/ia/asistente/conversaciones', ruta => ruta.fulfill({ json: { items: mensajes.length ? [{ id: 'lectura', titulo: pregunta }] : [] } }))
  await page.route('**/api/ia/asistente/conversaciones/lectura', ruta => ruta.fulfill({ json: { id: 'lectura', titulo: pregunta, mensajes } }))
  await page.route('**/api/ia/asistente', ruta => {
    const solicitud = ruta.request().postDataJSON()
    expect(solicitud.filtros.periodo).toBe('30d')
    if (enviadas.length) expect(solicitud.conversacion_id).toBe('lectura')
    enviadas.push(solicitud.pregunta)
    const respuesta = { texto: 'Hay 30 tickets frente a 20 del intervalo anterior.', fuentes: ['comparacion_periodos'], periodo: '30d', alcance_consulta: 'Todas las oficinas', analisis: { significado: 'Comparamos dos intervalos de igual duración.', revision: 'Revisa las oficinas con más reportes.', limite: 'Más tickets no demuestra peor atención.' }, seguimientos: ['¿Y ayer?'], tabla: { columnas: [{ clave: 'intervalo', titulo: 'Intervalo' }, { clave: 'total', titulo: 'Tickets' }], filas: [{ intervalo: 'Actual', total: 30 }, { intervalo: 'Anterior', total: 20 }] } }
    mensajes = [...mensajes, { rol: 'user', texto: solicitud.pregunta }, { rol: 'assistant', ...respuesta }]
    return ruta.fulfill({ json: { conversacion_id: 'lectura', ...respuesta } })
  })
  await page.goto('/panel/analisis')
  await expect(page.getByRole('heading', { name: 'Primero entiende. Después decide.' })).toBeVisible()
  await expect(page.locator('.analisis-indicator')).toHaveCount(6)
  await expect(page.locator('.analisis-indicator').filter({ hasText: 'Satisfacción' })).toContainText('Sin datos')
  await expect(page.locator('.analisis-indicator').filter({ hasText: 'Precisión de la clasificación' })).toContainText('Sin datos')
  await expect(page.locator('.analisis-overview')).toContainText('2 tickets vencidos')
  await page.locator('.analisis-indicator summary').first().click()
  await expect(page.locator('.analisis-indicator').first()).toContainText('Cómo se obtiene')
  await expect(page.getByTestId('mosaico-graficos').locator(':scope > div')).toHaveCount(7)
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(t => document.documentElement.setAttribute('data-tema', t), tema)
    for (const ancho of [320, 1440]) {
      await page.setViewportSize({ width: ancho, height: 1000 })
      await page.screenshot({ path: `../.codex-pdf-tools/centro-analisis-${tema}-${ancho}.png`, fullPage: true })
      const desbordados = await page.locator('.analisis-centro *').evaluateAll(es => es.filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => ({ tag: e.tagName, clase: e.className, ancho: e.getBoundingClientRect().width, texto: e.textContent?.slice(0, 60) })).slice(0, 12))
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), { message: JSON.stringify(desbordados) }).toBe(true)
    }
    expect((await new AxeBuilder({ page }).include('.analisis-centro').analyze()).violations).toEqual([])
  }
  await page.getByRole('button', { name: 'Entender la comparación' }).click()
  await expect(page.getByLabel('Tu pregunta', { exact: true })).toHaveValue(pregunta)
  expect(enviadas).toEqual([])
  await expect(page.getByRole('group', { name: 'Tipo de consulta' })).toBeVisible()
  await expect(page.getByLabel('Periodo', { exact: true })).toHaveValue('30d')
  await expect(page.getByLabel('Buscar conversaciones')).toBeVisible()
  await page.getByRole('group', { name: 'Tipo de consulta' }).getByRole('button', { name: 'Equipos', exact: true }).click()
  await expect(page.getByRole('button', { name: '¿Cuántos equipos tenemos registrados?' })).toBeVisible()
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  await expect(page.getByRole('log')).toContainText('Comparamos dos intervalos de igual duración.')
  await expect(page.getByRole('log')).toContainText('Todas las oficinas')
  await page.getByRole('group', { name: 'Seguir consultando' }).getByRole('button', { name: '¿Y ayer?' }).click()
  expect(enviadas).toEqual([pregunta, '¿Y ayer?'])
  await page.reload()
  await expect(page.getByRole('log')).toContainText('Comparamos dos intervalos de igual duración.')
  await page.getByRole('button', { name: 'Explícame este resultado' }).click()
  expect(enviadas).toEqual([pregunta, '¿Y ayer?', 'Explícame eso'])
  await page.getByRole('tab', { name: 'Paneles', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Análisis IA', exact: true })).toBeVisible()
})

test('chatbot guarda y recupera conversaciones tras recargar y permite eliminarlas', async ({ page }) => {
  await portal(page, false, 'tecnico')
  let guardado: { id: string; titulo: string; mensajes: { rol: string; texto: string }[]; consumo: { consultas: number; tokens: number; conTokens: number }; limite: number } | null = null
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true, proveedor: 'Groq', limite_consultas: 15 } }))
  await page.route('**/api/ia/chatbot/conversaciones', ruta => ruta.fulfill({ json: { items: guardado ? [guardado] : [] } }))
  await page.route('**/api/ia/chatbot/conversaciones/chat-propio', ruta => {
    if (ruta.request().method() === 'DELETE') { guardado = null; return ruta.fulfill({ json: { eliminada: true } }) }
    return ruta.fulfill({ json: guardado })
  })
  await page.route('**/api/ia/chatbot', ruta => {
    guardado = { id: 'chat-propio', titulo: 'Consulta de inventario', mensajes: [{ rol: 'user', texto: 'Consulta de inventario' }, { rol: 'assistant', texto: 'Respuesta guardada de inventario.' }], consumo: { consultas: 1, tokens: 40, conTokens: 1 }, limite: 15 }
    return ruta.fulfill({ json: { disponible: true, texto: 'Respuesta guardada de inventario.', fuentes: [], conversacion_id: 'chat-propio', consumo: guardado.consumo, limite: 15 } })
  })
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await page.getByLabel('Tu consulta al asistente TI').fill('Consulta de inventario')
  await page.getByRole('dialog').getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('log').getByText('Respuesta guardada de inventario.')).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await expect(page.getByRole('log').getByText('Respuesta guardada de inventario.')).toBeVisible()
  await expect(page.getByLabel('Tus conversaciones')).toHaveValue('chat-propio')
  await page.getByRole('button', { name: 'Eliminar conversación' }).click()
  await expect(page.getByRole('log').getByText('Respuesta guardada de inventario.')).toHaveCount(0)
  await page.reload()
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await expect(page.getByRole('log').getByText('Respuesta guardada de inventario.')).toHaveCount(0)
})

test('chatbot conserva el detalle mas reciente sin releerlo por un historial atrasado', async ({ page }) => {
  await portal(page, false, 'tecnico')
  const consumo = { consultas: 1, tokens: 40, conTokens: 1 }
  let lecturas = 0
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true, limite_consultas: 15 } }))
  await page.route('**/api/ia/chatbot/conversaciones', ruta => ruta.fulfill({ json: { items: [{ id: 'chat-actualizado', titulo: 'Inventario', consumo, limite: 15 }] } }))
  await page.route('**/api/ia/chatbot/conversaciones/chat-actualizado', ruta => {
    lecturas++
    return ruta.fulfill({ json: { id: 'chat-actualizado', mensajes: [{ rol: 'assistant', texto: 'Respuesta mas reciente del servidor.' }], consumo: { consultas: 2, tokens: 80, conTokens: 2 }, limite: 15 } })
  })
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await expect(page.getByRole('log').getByText('Respuesta mas reciente del servidor.')).toBeVisible()
  await expect(page.getByText(/2\/15 consultas/)).toBeVisible()
  await page.waitForTimeout(600)
  expect(lecturas).toBe(1)
  await expect(page.getByLabel('Tu consulta al asistente TI')).toBeEnabled()
})

test('un fallo al refrescar el historial no borra el chat recien creado', async ({ page }) => {
  await portal(page, false, 'tecnico')
  let consultas = 0
  const conversaciones: (string | undefined)[] = []
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true, limite_consultas: 15 } }))
  await page.route('**/api/ia/chatbot/conversaciones', ruta => consultas
    ? ruta.fulfill({ status: 503, json: { mensaje: 'Historial temporalmente no disponible' } })
    : ruta.fulfill({ json: { items: [] } }))
  await page.route('**/api/ia/chatbot', ruta => {
    consultas++
    conversaciones.push(ruta.request().postDataJSON().conversacion_id)
    return ruta.fulfill({ json: { disponible: true, texto: `Respuesta conservada ${consultas}.`, fuentes: [], conversacion_id: 'chat-persistente', consumo: { consultas, tokens: consultas * 40, conTokens: consultas }, limite: 15 } })
  })
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await page.getByLabel('Tu consulta al asistente TI').fill('Consulta inicial')
  await page.getByRole('dialog').getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('log').getByText('Respuesta conservada 1.')).toBeVisible()
  await page.waitForTimeout(600)
  await page.getByLabel('Tu consulta al asistente TI').fill('Continua con la misma consulta')
  await page.getByRole('dialog').getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('log').getByText('Respuesta conservada 2.')).toBeVisible()
  await expect(page.getByRole('log').getByText('Respuesta conservada 1.')).toBeVisible()
  expect(conversaciones).toEqual([undefined, 'chat-persistente'])
})

test('chatbot bloquea al tecnico en quince consultas y permite iniciar otro chat', async ({ page }) => {
  await portal(page, false, 'tecnico')
  const chat = { id: 'chat-lleno', titulo: 'Conversación terminada', mensajes: [{ rol: 'assistant', texto: 'Última respuesta guardada.' }], consumo: { consultas: 15, tokens: 900, conTokens: 15 }, limite: 15 }
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true, limite_consultas: 15 } }))
  await page.route('**/api/ia/chatbot/conversaciones', ruta => ruta.fulfill({ json: { items: [chat] } }))
  await page.route('**/api/ia/chatbot/conversaciones/chat-lleno', ruta => ruta.fulfill({ json: chat }))
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await expect(page.getByRole('log').getByText('Última respuesta guardada.')).toBeVisible()
  await expect(page.getByLabel('Tu consulta al asistente TI')).toBeDisabled()
  await expect(page.getByText(/15\/15 consultas/)).toBeVisible()
  await page.getByRole('button', { name: 'Nueva consulta', exact: true }).click()
  await expect(page.getByLabel('Tu consulta al asistente TI')).toBeEnabled()
  await expect(page.getByText(/0\/15 consultas/)).toBeVisible()
})

test('chatbot exclusivo de TI muestra configuracion pendiente y no aparece al usuario', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: false, proveedor: 'Gemini', solo_lectura: true } }))
  await page.goto('/panel/tickets')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await expect(page.getByRole('dialog').getByText(/Falta configurar la clave/)).toBeVisible()
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Enviar', exact: true })).toBeDisabled()
  await expect(page.getByRole('dialog').getByLabel('Tu consulta al asistente TI')).toBeDisabled()
})

test('chatbot responde consultas sin modificar registros y permite limpiar la conversacion', async ({ page }) => {
  await portal(page, false, 'tecnico')
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true } }))
  const consultas: Record<string, unknown>[] = []
  await page.route('**/api/ia/chatbot', ruta => { consultas.push(ruta.request().postDataJSON()); return ruta.fulfill({ json: { disponible: true, texto: 'Abre el historial del conjunto desde el ticket.', fuentes: [] } }) })
  await page.goto('/panel?periodo=7d&token=no_enviar')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  await page.getByLabel('Tu consulta al asistente TI').fill('Como veo el historial')
  await page.getByRole('dialog').getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('log').getByText('Abre el historial del conjunto desde el ticket.')).toBeVisible()
  expect(consultas).toHaveLength(1)
  expect(consultas[0]).toEqual({ pregunta: 'Como veo el historial', historial: [], pagina: '/panel', filtros: { periodo: '7d' } })
  await page.getByRole('button', { name: 'Nueva consulta', exact: true }).click()
  await expect(page.getByRole('log').getByText('Abre el historial del conjunto desde el ticket.')).toHaveCount(0)
})

test('el portal de usuario conserva su asistente actual y no recibe el chatbot TI', async ({ page }) => {
  await portal(page)
  await page.goto('/portal')
  await expect(page.getByRole('button', { name: 'Abrir asistente TI' })).toHaveCount(0)
})

test('asistente TI adapta el diseño a celular y escritorio sin desbordes ni scroll doble', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/ia/chatbot/estado', ruta => ruta.fulfill({ json: { configurado: true } }))
  await page.route('**/api/ia/chatbot', ruta => ruta.fulfill({ json: { disponible: true, texto: '**Inventario:** consulta el conjunto.\n\nUsa `ipconfig` para revisar la red.', fuentes: [] } }))
  await page.goto('/panel')
  await page.getByRole('button', { name: 'Abrir asistente TI' }).click()
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(valor => { document.documentElement.dataset.tema = valor }, tema)
    for (const ancho of [320, 1440]) {
      await page.setViewportSize({ width: ancho, height: 850 })
      const dialogo = page.getByRole('dialog')
      await expect(dialogo).toBeVisible()
      expect(await dialogo.evaluate(e => e.scrollWidth <= e.clientWidth + 1)).toBe(true)
      expect(await dialogo.evaluate(e => e.scrollHeight <= e.clientHeight + 1)).toBe(true)
      await expect(dialogo.getByRole('button', { name: 'Enviar', exact: true })).toBeInViewport()
      await page.screenshot({ path: `../.codex-pdf-tools/chatbot-${tema}-${ancho}.png` })
    }
  }
  await page.getByLabel('Tu consulta al asistente TI').fill('Como reviso mi red')
  await page.getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(page.getByRole('log').locator('strong')).toHaveText('Inventario:')
  await expect(page.getByRole('log').locator('code')).toHaveText('ipconfig')
  await expect(page.getByRole('log')).not.toContainText('**')
})

// Toda la API se intercepta: estas pruebas no crean cuentas, tickets ni archivos reales.
async function portal(page: Page, fallarPrimerEnvio = false, rol = 'usuario', recomendaciones = false) {
  const solicitudes: Record<string, unknown>[] = []
  const mensajes: Record<string, unknown>[] = []
  const usuario = { id: 'persona', nombre: 'Ana Prueba', email: 'ana@example.invalid', rol, permisos: [], institucion: 'Municipalidad Provincial de Casma', csrf_token: 'csrf-simulado', recomendaciones_ia: recomendaciones }
  let asuntoActual = 'La impresora no imprime desde esta mañana'
  let categoriaActual = 'Impresora'
  let vinculo: Record<string, unknown> = {}
  let intentos = 0
  let creado = false
  let estadoActual = 'nuevo'
  let socketTicket: WebSocketRoute | null = null
  let socketAvisos: WebSocketRoute | null = null
  let iaGlobal = true
  const preferencia = () => ({ recomendaciones_ia: usuario.recomendaciones_ia, recomendaciones_personales: usuario.recomendaciones_ia, ia_global_activa: iaGlobal, recomendaciones_globales: iaGlobal, recomendaciones_visibles: iaGlobal && usuario.recomendaciones_ia, aprendizaje_activo: true, proveedor_disponible: false, modelo: null })
  const ticket = () => ({ id: 'caso', codigo: 'TKT-2026-000001', asunto: asuntoActual, categoria: categoriaActual, tipo_problema: 'Sistema/programa', descripcion: 'La impresora no imprime desde esta mañana', estado: estadoActual, prioridad: 'media', origen: 'usuario', creado_en: '2026-10-17T14:00:00Z', tiene_chat: true, tecnico_nombre: null, oficina_id: 'oficina', oficina_nombre: 'SOPORTE', activo_nombre: null, adjuntos: [], ...vinculo })
  await page.routeWebSocket('**/api/ws/**', socket => { if (socket.url().includes('/ticket/caso')) socketTicket = socket; else if (socket.url().includes('/notificaciones')) socketAvisos = socket })
  await page.addInitScript(() => sessionStorage.setItem('ma.acceso', 'sesion-simulada'))
  await page.route('**/api/**', async ruta => {
    const url = new URL(ruta.request().url())
    if (!url.pathname.startsWith('/api/')) { await ruta.continue(); return }
    const camino = url.pathname.replace('/api', '')
    let cuerpo: unknown = {}
    let status = 200
    if (camino === '/auth/sesion') cuerpo = usuario
    else if (camino === '/mi-perfil') cuerpo = { ...usuario, tiene_foto: false, equipos_responsable: [], oficina_nombre: 'SOPORTE', zona_nombre: 'PALACIO' }
    else if (camino === '/notificaciones') cuerpo = { items: [], no_leidas: 0 }
    else if (camino === '/auth/preferencia-ia') { if (ruta.request().method() === 'POST') usuario.recomendaciones_ia = Boolean(ruta.request().postDataJSON().recomendaciones_ia); cuerpo = preferencia() }
    else if (camino === '/auth/dispositivos') cuerpo = { items: [], total: 0, limite: 3 }
    else if (camino === '/auth/password') cuerpo = {}
    else if (camino === '/publico/configuracion') cuerpo = { institucion: usuario.institucion }
    else if (camino === '/equipos/mis') cuerpo = { por_conjunto: [{ conjunto: 'Computadora N°1', equipos: [{ id: 'propio', nombre_equipo: 'Mi computadora', tipo: 'CPU', estado: 'OPERATIVO' }] }], uso_comun_oficina: [{ id: 'comun', nombre_equipo: 'Impresora compartida', tipo: 'Impresora', estado: 'OPERATIVO' }] }
    else if (camino === '/usuarios/companeros') cuerpo = { items: [{ id: 'companero', nombre: 'Luis Prueba' }] }
    else if (camino === '/tickets/ajustes-crear') cuerpo = { tipos_problema: [
      { clave: 'Sistema/programa', titulo: 'Office, programas o formateo', descripcion: 'Quiero instalar o quitar programas, o formatear mi PC.', icono: 'disc' },
      { clave: 'SIGA/Casita/Servidor', titulo: 'SIGA, Casita o servidor', descripcion: 'No puedo entrar, se queda colgado o muestra un error.', icono: 'server' },
      { clave: 'Carpeta compartida', titulo: 'La compartida', descripcion: 'No abre o no conecta la carpeta compartida de la oficina.', icono: 'folder-network' },
      { clave: 'Impresora', titulo: 'Impresora', descripcion: 'No imprime, se atascó la hoja o no puedo escanear.', icono: 'printer' },
      { clave: 'Huella dactilar', titulo: 'Huella dactilar', descripcion: 'El lector no reconoce mi huella o no enciende.', icono: 'fingerprint' },
      { clave: 'Internet/red', titulo: 'Internet', descripcion: 'Mi PC no tiene internet o está muy lento.', icono: 'wifi' },
      { clave: 'No enciende', titulo: 'No enciende o falla el equipo', descripcion: 'Mi PC no prende, o falla la pantalla, el teclado o el mouse.', icono: 'power' },
      { clave: 'Otro', titulo: 'Otro problema', descripcion: 'Correo, cuentas o algo que no encuentres en esta lista.', icono: 'message-circle' },
    ], urgencias: [], categorias: ['Hardware', 'Impresora', 'Sistema / Programa', 'Software instalado', 'Correo / Cuenta', 'Formateo'] }
    else if (camino === '/tickets/caso' && ruta.request().method() === 'PATCH') { const datos = ruta.request().postDataJSON(); asuntoActual = datos.asunto; categoriaActual = datos.categoria; creado = true; vinculo = { ...datos, activo_nombre: datos.activo_id ? 'PC Soporte' : null, conjunto_id: datos.activo_id ? 'conjunto' : datos.conjunto_id, conjunto_nombre: datos.activo_id || datos.conjunto_id ? 'Computadora N°1' : null }; cuerpo = ticket() }
    else if (camino === '/activos') cuerpo = { items: [{ id: 'pc', nombre_equipo: 'PC Soporte', tipo: 'CPU' }], total: 1 }
    else if (camino === '/tickets/caso/vinculos') cuerpo = { equipos: [{ id: 'pc', nombre: 'PC Soporte', tipo: 'CPU', conjunto_id: 'conjunto', grupo: 'propios' }, ...((url.searchParams.get('corregir_origen') === 'true' || !vinculo.activo_id && !vinculo.conjunto_id) ? [{ id: 'comun', nombre: 'Impresora oficina', grupo: 'oficina' }] : [])], conjuntos: [{ id: 'conjunto', nombre: 'Computadora N°1', grupo: 'propios' }], grupo_bloqueado: url.searchParams.get('corregir_origen') === 'true' ? null : vinculo.activo_id || vinculo.conjunto_id ? 'propios' : null }
    else if (/^\/usuarios\/[^/]+\/destinos-ticket$/.test(camino)) cuerpo = { equipos: [{ id: camino.includes('/companero/') ? 'de-luis' : 'propio', nombre: 'Mi computadora', tipo: 'CPU', grupo: 'propios', conjunto_id: 'conjunto' }, { id: 'comun', nombre: 'Impresora compartida', tipo: 'Impresora', grupo: 'oficina' }], conjuntos: [{ id: 'conjunto', nombre: 'Computadora N°1', grupo: 'propios' }] }
    else if (camino === '/usuarios/buscar') cuerpo = { items: [{ id: 'persona', nombre: 'Ana Prueba', oficina_nombre: 'SOPORTE' }] }
    else if (camino === '/tickets/manual' && ruta.request().method() === 'POST') { solicitudes.push(ruta.request().postDataJSON()); creado = true; cuerpo = { ticket: ticket() } }

    else if (camino === '/conjuntos') cuerpo = { items: [{ id: 'conjunto', nombre: 'Computadora N°1' }] }
    else if (['/tickets/caso/notas', '/equipo-ti/tecnicos', '/kb/respuestas-rapidas'].includes(camino)) cuerpo = { items: [] }
    else if (camino === '/tickets' && ruta.request().method() === 'POST') {
      solicitudes.push(ruta.request().postDataJSON())
      intentos++
      await new Promise(resolve => setTimeout(resolve, 200))
      if (fallarPrimerEnvio && intentos === 1) { status = 503; cuerpo = { mensaje: 'No se pudo enviar. Intenta de nuevo.', codigo: 'prueba' } }
      else { creado = true; cuerpo = { ticket: ticket() } }
    } else if (camino === '/tickets') cuerpo = { items: creado ? [ticket()] : [], total: creado ? 1 : 0, pagina: 1, por_pagina: 20, total_paginas: 1 }
    else if (camino === '/tickets/caso' || camino === '/tickets/otro') cuerpo = { ...ticket(), id: camino.split('/').at(-1) }
    else if (camino === '/tickets/otro/mensajes') cuerpo = { items: [] }
    else if (camino === '/tickets/caso/mensajes') {
      if (ruta.request().method() === 'POST') mensajes.push({ ...ruta.request().postDataJSON(), id: `mensaje-${mensajes.length}`, autor_id: usuario.id, autor_nombre: usuario.nombre, creado_en: '2026-10-17T14:01:00Z' })
      cuerpo = { items: mensajes }
    }
    else if (camino === '/auth/logout') cuerpo = {}
    else if (camino === '/kb/articulos') cuerpo = { items: [], total: 0 }
    else if (camino === '/kb/categorias') cuerpo = { items: [] }
    else { status = 404; cuerpo = { mensaje: `Ruta no simulada: ${camino}` } }
    await ruta.fulfill({ status, contentType: 'application/json', body: JSON.stringify(cuerpo) })
  })
  return { avisosConectados: () => Boolean(socketAvisos), publicarCambio: (dominios: string[], fotos: string[] = []) => socketAvisos?.send(JSON.stringify({ tipo: 'datos_actualizados', dominios, fotos })), reconectarAvisos: () => socketAvisos?.close({ code: 1012, reason: 'prueba' }), publicarIa: (activa: boolean) => { iaGlobal = activa; socketAvisos?.send(JSON.stringify({ tipo: 'ia_actualizada', global_activa: activa, recomendaciones_activas: true })) }, preferenciaRemota: (activa: boolean) => { usuario.recomendaciones_ia = activa; socketAvisos?.send(JSON.stringify({ tipo: 'ia_preferencia', recomendaciones_ia: activa })) }, solicitudes, mensajes, conectado: () => Boolean(socketTicket), cambiarEstado: (estado: string) => { estadoActual = estado; socketTicket?.send(JSON.stringify({ tipo: 'ticket_estado' })) }, mensajeSoporte: () => { mensajes.push({ id: 'respuesta-ti', cuerpo: 'Voy a revisar tu impresora ahora', autor_id: 'soporte', autor_nombre: 'Soporte TI', creado_en: '2026-10-17T14:02:00Z', adjuntos: [] }); socketTicket?.send(JSON.stringify({ tipo: 'mensaje' })) } }
}

test('me gusta se conserva, se puede retirar y muestra personas sin volver a consultar la lectura', async ({ page }) => {
  await portal(page)
  let gusta = false
  let consultas = 0
  let votos = 0
  await page.route('**/api/kb/articulos/guia**', async ruta => {
    const camino = new URL(ruta.request().url()).pathname
    const estadisticas = () => ({ me_gusta: gusta ? 2 : 1, mi_valoracion: gusta ? true : null, valoraciones: gusta ? 2 : 1, valoracion_promedio: 100 })
    let cuerpo: unknown
    if (camino.endsWith('/valorar')) { votos++; gusta = ruta.request().method() !== 'DELETE'; cuerpo = estadisticas() }
    else if (camino.endsWith('/me-gusta')) cuerpo = { items: [{ usuario_id: 'soporte', nombre: 'Soporte municipal' }], total: 1, total_paginas: 1 }
    else { consultas++; cuerpo = { id: 'guia', titulo: 'Problemas con la impresora', categoria: 'Impresora', cuerpo: 'Revisa el papel de la impresora.', pasos: [], etiquetas: [], relacionados: [], actualizado_en: '2026-10-18T14:00:00Z', visualizaciones: 1, ...estadisticas() } }
    await ruta.fulfill({ contentType: 'application/json', body: JSON.stringify(cuerpo) })
  })
  await page.goto('/ayuda/guia')
  await page.getByRole('button', { name: 'Me gusta', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Quitar me gusta' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: /Ver a qui/ }).click()
  await expect(page.getByText('Soporte municipal', { exact: true })).toBeVisible()
  expect(consultas).toBe(1)
  await page.reload()
  await page.getByRole('button', { name: 'Quitar me gusta' }).click()
  await expect(page.getByRole('button', { name: 'Me gusta', exact: true })).toHaveAttribute('aria-pressed', 'false')
  expect(votos).toBe(2)
})

test('pedir ayuda en dos pantallas, enviar una sola vez y conversar con soporte', async ({ page }) => {
  const api = await portal(page)
  await page.goto('/')
  await page.getByRole('link', { name: 'Necesito ayuda' }).click()
  await expect(page.getByRole('heading', { name: '¿Con qué necesitas ayuda?' })).toBeVisible()
  await page.getByRole('button', { name: /Impresora No imprime/ }).click()
  const enviar = page.getByRole('button', { name: 'Enviar a soporte', exact: true })
  await expect(enviar).toBeDisabled()
  await page.getByLabel('¿Qué está pasando?').fill('La impresora no imprime desde esta mañana')
  await page.getByRole('radio', { name: /Con dificultad/ }).check()
  await enviar.dblclick()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  await expect(page.getByText('Tu reporte fue enviado')).toBeVisible()
  expect(api.solicitudes).toHaveLength(1)
  expect(api.solicitudes[0]).toMatchObject({ tipo_problema: 'Impresora', urgencia: 'me_frena', persona: { es_para_mi: true } })
  await expect(page.getByRole('heading', { name: 'Habla con soporte' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Escribe un mensaje' }).fill('También aparece una luz roja')
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page.getByText('También aparece una luz roja', { exact: true })).toBeVisible()
  expect(api.mensajes).toHaveLength(1)
  await expect(page.getByRole('button', { name: 'Grabar audio', exact: true })).toBeVisible()
  await expect(page.locator('button[aria-label="Adjuntar fotos o audios"]')).toBeVisible()
})

test('conserva la descripción al cambiar el problema y al fallar el envío', async ({ page }) => {
  const api = await portal(page, true)
  await page.goto('/reportar?tipo=Impresora')
  await page.getByLabel('¿Qué está pasando?').fill('La impresora no imprime desde esta mañana')
  await page.getByRole('radio', { name: /Sí, puedo continuar/ }).check()
  await page.getByRole('button', { name: 'Cambiar', exact: true }).click()
  await page.getByRole('button', { name: /Otro problema/ }).click()
  await expect(page.getByLabel('¿Qué está pasando?')).toHaveValue('La impresora no imprime desde esta mañana')
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Intenta de nuevo')
  await expect(page.getByLabel('¿Qué está pasando?')).toHaveValue('La impresora no imprime desde esta mañana')
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  expect(api.solicitudes).toHaveLength(2)
})

test('separa mis equipos de los compartidos y no asigna mi equipo a un compañero', async ({ page }) => {
  const api = await portal(page)
  await page.goto('/reportar?tipo=Impresora')
  await page.getByRole('button', { name: 'Para un compañero', exact: true }).click()
  await expect(page.getByLabel('Equipo o computadora afectada')).toHaveCount(0)
  await expect(page.getByLabel('¿En qué equipo te pasa?')).toHaveCount(0)
  await page.getByLabel('Persona que necesita ayuda').selectOption('companero')
  await page.getByLabel('¿Qué está pasando?').fill('La impresora no imprime desde esta mañana')
  await page.getByRole('radio', { name: /No puedo trabajar/ }).check()
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  expect(api.solicitudes[0]).toMatchObject({ persona: { es_para_mi: false, afectado_id: 'companero' } })
  expect(api.solicitudes[0]).not.toHaveProperty('activo_id')
})

for (const ancho of [320, 390, 1440]) test(`portal claro y sin desborde a ${ancho}px, en ambos temas`, async ({ page }) => {
  await portal(page)
  await page.setViewportSize({ width: ancho, height: 900 })
  for (const ruta of ['/', '/reportar', '/reportar?tipo=Impresora', '/mis-tickets', '/mis-equipos', '/perfil']) {
    await page.goto(ruta)
    await expect(page.locator('main h1').first()).toBeVisible()
    if (ruta.includes('?tipo=')) {
      for (const radio of await page.getByRole('radio').all()) {
        await radio.evaluate(elemento => elemento.scrollIntoView({ block: 'center' }))
        await radio.check({ trial: true })
      }
    }
    for (const tema of ['claro', 'oscuro']) {
      await page.evaluate(tema => document.documentElement.dataset.tema = tema, tema)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${ruta} ${tema}`).toBe(true)
    }
  }
  await page.goto('/')
  const principal = page.getByRole('link', { name: 'Necesito ayuda' })
  await expect(principal).toBeInViewport()
  expect((await principal.boundingBox())!.height).toBeGreaterThanOrEqual(48)
})

test('el usuario solicita el cambio de contraseña al equipo TI sin cambiarla directamente', async ({ page }) => {
  await portal(page)
  await page.goto('/perfil')
  await expect(page.getByRole('heading', { name: 'Mi cuenta', exact: true })).toBeVisible()
  await page.getByText('Dispositivos conectados a mi cuenta', { exact: true }).click()
  await expect(page.getByRole('heading', { name: /Dispositivos conectados/ })).toBeVisible()
  await expect(page.getByLabel('Contraseña actual', { exact: true })).toHaveCount(0)
  await page.getByRole('link', { name: 'Solicitar cambio de contraseña' }).click()
  await expect(page).toHaveURL(/solicitud=password/)
  await expect(page.getByLabel('¿Qué está pasando?')).toHaveValue(/administrador restablezca/)
})

test('inicio y reporte mantienen accesibilidad y contraste en ambos temas', async ({ page }) => {
  await portal(page)
  for (const ruta of ['/', '/reportar', '/reportar?tipo=Impresora']) {
    await page.goto(ruta)
    await expect(page.locator('main h1').first()).toBeVisible()
    for (const tema of ['claro', 'oscuro']) {
      await page.evaluate(tema => document.documentElement.dataset.tema = tema, tema)
      // Esperar la transición de colores antes de medir el tema final.
      await page.waitForTimeout(250)
      const resultado = await new AxeBuilder({ page }).analyze()
      expect(resultado.violations.filter(v => v.impact === 'serious' || v.impact === 'critical'), `${ruta} ${tema}`).toEqual([])
    }
  }
})

test('no mezcla mensajes sin enviar al abrir otro reporte', async ({ page }) => {
  await portal(page)
  await page.goto('/mis-tickets/caso')
  await page.getByRole('textbox', { name: 'Escribe un mensaje' }).fill('Este texto es solo para el primer reporte')
  await page.evaluate(() => { history.pushState({}, '', '/mis-tickets/otro'); window.dispatchEvent(new PopStateEvent('popstate')) })
  await expect(page).toHaveURL(/mis-tickets\/otro$/)
  await expect(page.getByRole('textbox', { name: 'Escribe un mensaje' })).toHaveValue('')
})

test('el acceso a ayuda conserva fondo y texto visibles en los dos temas', async ({ page }) => {
  await portal(page)
  await page.goto('/')
  const boton = page.getByRole('link', { name: 'Necesito ayuda', exact: true })
  for (const tema of ['claro', 'oscuro']) {
    await page.evaluate(tema => document.documentElement.dataset.tema = tema, tema)
    await page.mouse.move(0, 0)
    await expect(boton).toHaveCSS('background-image', /linear-gradient/)
    const fondoAzul = await boton.evaluate(e => getComputedStyle(e).backgroundImage)
    await expect(boton).toHaveCSS('color', 'rgb(255, 255, 255)')
    await boton.hover()
    await expect.poll(() => boton.evaluate(e => getComputedStyle(e).backgroundImage)).not.toBe(fondoAzul)
    await expect(boton).toHaveCSS('color', 'rgb(255, 255, 255)')
  }
})

test('las ocho situaciones tienen texto familiar e iconos propios y se pueden reportar', async ({ page }) => {
  const api = await portal(page)
  await page.goto('/reportar')
  const opciones = page.getByRole('group', { name: 'Tipo de problema' })
  await expect(opciones.getByRole('button')).toHaveCount(8)
  await expect(opciones.locator('svg.lucide-fingerprint')).toBeVisible()
  await expect(opciones.locator('svg.lucide-server')).toBeVisible()
  await expect(opciones.locator('svg.lucide-folder-tree')).toBeVisible()
  for (const nombre of ['Office, programas o formateo', 'SIGA, Casita o servidor', 'La compartida', 'Huella dactilar', 'Internet', 'No enciende o falla el equipo']) {
    await opciones.getByRole('button', { name: new RegExp(nombre.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click()
    await expect(page.getByRole('heading', { name: 'Cuéntanos qué ocurre' })).toBeVisible()
    await page.getByRole('button', { name: 'Cambiar', exact: true }).click()
  }
  await opciones.getByRole('button', { name: /Huella dactilar/ }).click()
  await page.getByLabel('¿Qué está pasando?').fill('El lector no reconoce mi huella desde esta mañana')
  await page.getByRole('radio', { name: /Con dificultad/ }).check()
  await page.getByRole('button', { name: 'Enviar a soporte', exact: true }).click()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  expect(api.solicitudes[0]).toMatchObject({ tipo_problema: 'Huella dactilar' })
})

test('los estados y mensajes nuevos aparecen por el canal en vivo', async ({ page }) => {
  const api = await portal(page)
  await page.goto('/mis-tickets/caso')
  await expect.poll(api.conectado).toBe(true)
  api.cambiarEstado('en_progreso')
  await expect(page.getByRole('heading', { name: 'En atención', exact: true })).toBeVisible({ timeout: 3000 })
  api.mensajeSoporte()
  await expect(page.getByText('Voy a revisar tu impresora ahora', { exact: true })).toBeVisible({ timeout: 3000 })
})

test('TI edita el título y la categoría sin dejar el formulario abierto', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.goto('/panel/tickets/caso')
  const ficha = page.getByLabel('Incidencia reportada', { exact: true })
  await expect(ficha.getByRole('heading', { name: 'La impresora no imprime desde esta mañana' })).toBeVisible()
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await ficha.getByLabel('Título de la incidencia').fill('Instalación de Office')
  await ficha.getByLabel('Categoría', { exact: true }).selectOption('Software instalado')
  await ficha.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(ficha.getByLabel('Título de la incidencia')).toHaveCount(0)
  await expect(ficha.getByRole('heading', { name: 'Instalación de Office', exact: true })).toBeVisible()
  await expect(ficha.getByText('Software instalado', { exact: true })).toBeVisible()
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await ficha.getByLabel('Título de la incidencia').fill('Cambio sin guardar')
  await ficha.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await expect(ficha.getByRole('heading', { name: 'Instalación de Office', exact: true })).toBeVisible()
})

test('los títulos largos se limitan a dos líneas y el envío tiene fondo azul', async ({ page }) => {
  await portal(page)
  const asunto = 'Necesito que revisen este problema en la oficina porque no puedo trabajar normalmente '.repeat(12)
  await page.route('**/api/tickets?**', ruta => ruta.fulfill({ json: { items: [{ id: 'caso', codigo: 'TKT-2026-000001', asunto, estado: 'nuevo', prioridad: 'media', creado_en: '2026-10-17T14:00:00Z' }], total: 1 } }))
  for (const ancho of [320, 1440]) {
    await page.setViewportSize({ width: ancho, height: 900 })
    await page.goto('/')
    const titulo = page.getByRole('heading', { name: asunto, exact: true })
    await expect(titulo).toBeVisible()
    expect(await titulo.evaluate(e => e.clientHeight <= parseFloat(getComputedStyle(e).lineHeight) * 2 + 1)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  await page.goto('/reportar?tipo=Sistema%2Fprograma')
  await page.getByLabel('¿Qué está pasando?').fill('Necesito instalar Office en mi computadora')
  await page.getByRole('radio', { name: /Con dificultad/ }).check()
  const enviar = page.getByRole('button', { name: 'Enviar a soporte', exact: true })
  await expect(enviar).toBeEnabled()
  const fondo = await enviar.evaluate(e => getComputedStyle(e).backgroundColor)
  expect(fondo).not.toBe('rgb(255, 255, 255)')
  expect(fondo).not.toBe('rgba(0, 0, 0, 0)')
})

for (const rol of ['usuario', 'tecnico', 'administrador']) test(`eliminar avisos propios y vaciar la bandeja como ${rol}`, async ({ page }) => {
  await portal(page, false, rol)
  let avisos = [{ id: 'aviso-1', titulo: 'Primer aviso', mensaje: 'Soporte está revisando el caso', leida: false, creado_en: '2026-10-18T14:00:00Z', tipo: 'mensaje' }, { id: 'aviso-2', titulo: 'Segundo aviso', mensaje: 'Se actualizó tu reporte', leida: true, creado_en: '2026-10-18T14:00:00Z', tipo: 'mensaje_cerrado' }]
  await page.route('**/api/notificaciones**', async ruta => {
    const url = new URL(ruta.request().url())
    if (ruta.request().method() === 'DELETE') { avisos = url.pathname === '/api/notificaciones' ? [] : avisos.filter(aviso => !url.pathname.endsWith(aviso.id)); await ruta.fulfill({ json: { eliminadas: 1 } }); return }
    await ruta.fulfill({ json: { items: avisos, no_leidas: avisos.filter(a => !a.leida).length } })
  })
  await page.goto(rol === 'usuario' ? '/' : '/panel/tickets/caso')
  await page.getByRole('button', { name: /^Notificaciones/ }).click()
  await expect(page.getByText('Mensaje en ticket finalizado', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Eliminar notificación: Primer aviso', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Eliminar notificación: Primer aviso', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Eliminar notificación: Segundo aviso', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Eliminar todas las notificaciones', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Eliminar todas', exact: true }).click()
  expect(avisos).toHaveLength(0)
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('las recomendaciones ofrecen una guía y el chat sigue siendo con soporte', async ({ page }) => {
  await portal(page, false, 'usuario', true)
  await page.route('**/api/ia/sugerencias-reporte?**', ruta => ruta.fulfill({ json: { disponible: true, articulos: [{ id: 'guia', titulo: 'Qué revisar si la impresora no imprime' }] } }))
  await page.goto('/mis-tickets/caso')
  const ayuda = page.getByLabel('Guías recomendadas', { exact: true })
  await expect(ayuda.getByRole('link', { name: 'Qué revisar si la impresora no imprime' })).toHaveAttribute('href', '/ayuda/guia')
  await expect(page.getByRole('heading', { name: 'Habla con soporte', exact: true })).toBeVisible()
})

test('Mis reportes pagina de 25 en 25 y los filtros vuelven a la primera página', async ({ page }) => {
  await portal(page)
  const consultas: URL[] = []
  await page.route('**/api/tickets?**', async ruta => {
    const url = new URL(ruta.request().url())
    consultas.push(url)
    const pagina = Number(url.searchParams.get('pagina') ?? 1)
    const cantidad = Number(url.searchParams.get('por_pagina'))
    const items = Array.from({ length: 52 }, (_, i) => ({ id: `caso-${i + 1}`, codigo: `TKT-${i + 1}`, asunto: `Incidencia de prueba ${i + 1}`, estado: 'nuevo', prioridad: 'media', creado_en: '2026-10-18T14:00:00Z' }))
    await ruta.fulfill({ json: { items: items.slice((pagina - 1) * cantidad, pagina * cantidad), total: 52, pagina, por_pagina: cantidad, total_paginas: Math.ceil(52 / cantidad) } })
  })
  for (const ancho of [390, 1440]) {
    await page.setViewportSize({ width: ancho, height: 900 })
    await page.goto('/mis-tickets')
    const tarjetas = page.locator('a[href^="/mis-tickets/caso-"]')
    await expect(tarjetas).toHaveCount(25)
    await expect(tarjetas.first()).toContainText('TKT-1')
    await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(tarjetas.first()).toContainText('TKT-26')
    await expect(tarjetas).toHaveCount(25)
    await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(tarjetas).toHaveCount(2)
    await expect(tarjetas.first()).toContainText('TKT-51')
    await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
    await page.getByLabel('Estado', { exact: true }).selectOption('en_progreso')
    await expect(tarjetas).toHaveCount(25)
    await expect(tarjetas.first()).toContainText('TKT-1')
  }
  expect(consultas.every(url => url.searchParams.get('por_pagina') === '25')).toBe(true)
})

test('TI edita programas con el selector habitual sin opciones adicionales de servicio', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.goto('/panel/tickets/caso')
  const ficha = page.getByLabel('Incidencia reportada', { exact: true })
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await ficha.getByLabel('Categoría', { exact: true }).selectOption('Sistema / Programa')
  await expect(ficha.getByRole('button', { name: 'Servicio de la oficina', exact: true })).toHaveCount(0)
  await expect(ficha.getByRole('button', { name: 'En una computadora', exact: true })).toHaveCount(0)
  await expect(ficha.getByLabel('Computadora afectada')).toHaveValue('pc:conjunto')
  await ficha.getByLabel('Programa, sistema o correo').fill('Office')
  const solicitud = page.waitForRequest(peticion => new URL(peticion.url()).pathname === '/api/tickets/caso' && peticion.method() === 'PATCH')
  await ficha.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  expect((await solicitud).postDataJSON()).toMatchObject({ alcance_incidencia: 'programa', conjunto_id: 'conjunto', activo_id: null, sistema_afectado: 'Office' })
  await expect(ficha.getByRole('button', { name: 'Editar', exact: true })).toBeVisible()
})

test('TI separa equipos personales y compartidos con tarjetas y listas filtradas', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.goto('/panel/tickets/caso')
  const ficha = page.getByLabel('Incidencia reportada', { exact: true })
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await expect(ficha.getByRole('button', { name: 'Equipo de la persona', exact: true })).toHaveAttribute('aria-pressed', 'true')
  const lista = ficha.getByLabel('Equipo o computadora afectada')
  await expect(lista.getByRole('option', { name: 'PC Soporte', exact: true })).toHaveCount(1)
  await expect(lista.getByRole('option', { name: 'Impresora oficina', exact: true })).toHaveCount(0)
  await lista.selectOption('equipo:pc')
  await ficha.getByRole('button', { name: 'Equipo compartido de la oficina', exact: true }).click()
  await expect(lista).toHaveValue('')
  await expect(lista.getByRole('option', { name: 'PC Soporte', exact: true })).toHaveCount(0)
  await expect(lista.getByRole('option', { name: 'Impresora oficina', exact: true })).toHaveCount(1)
  await lista.selectOption('equipo:comun')
  await expect(lista).toHaveValue('equipo:comun')
  const guardado = page.waitForRequest(peticion => new URL(peticion.url()).pathname === '/api/tickets/caso' && peticion.method() === 'PATCH')
  await ficha.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  expect((await guardado).postDataJSON()).toMatchObject({ activo_id: 'comun', corregir_origen: true })
  await expect(ficha.getByRole('button', { name: 'Editar', exact: true })).toBeVisible()
})

test('inventario filtra equipos compartidos y permite volver a todos', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/activos?*', ruta => ruta.fulfill({ json: { items: [], total: 0, pagina: 1, por_pagina: 25, total_paginas: 1 } }))
  await page.goto('/panel/equipos')
  const consulta = page.waitForRequest(peticion => new URL(peticion.url()).pathname === '/api/activos' && new URL(peticion.url()).searchParams.get('solo_uso_comun') === 'true')
  await page.getByLabel('Asignación', { exact: true }).selectOption('comun')
  await consulta
  await expect(page).toHaveURL(/solo_uso_comun=1/)
  await page.getByLabel('Asignación', { exact: true }).selectOption('todos')
  await expect(page.getByLabel('Asignación', { exact: true })).toHaveValue('todos')
  await expect(page).not.toHaveURL(/solo_uso_comun/)
})

test('TI conserva el equipo elegido y programas se vinculan a la PC sin preguntas redundantes', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.goto('/panel/tickets/caso')
  const ficha = page.getByLabel('Incidencia reportada', { exact: true })
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await expect(ficha.getByLabel('Buscar equipo', { exact: true })).toHaveCount(0)
  await expect(ficha.getByLabel('Qué afecta', { exact: true })).toHaveCount(0)
  await ficha.getByLabel('Equipo o computadora afectada').selectOption('equipo:pc')
  await ficha.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  await expect(ficha.getByRole('link', { name: 'PC Soporte', exact: true })).toBeVisible()
  await ficha.getByRole('button', { name: 'Editar', exact: true }).click()
  await expect(ficha.getByLabel('Equipo o computadora afectada')).toHaveValue('equipo:pc')
  await page.screenshot({ path: '../.codex-pdf-tools/editar-destino-propio.png', fullPage: true })
  await expect(ficha.getByRole('button', { name: 'De la oficina', exact: true })).toHaveCount(0)
  await ficha.getByLabel('Categoría', { exact: true }).selectOption('Sistema / Programa')
  await expect(ficha.getByLabel('Computadora afectada')).toHaveValue('pc:conjunto')
  await ficha.getByLabel('Programa, sistema o correo').fill('Office')
  await ficha.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  await expect(ficha.getByText('Office', { exact: true })).toBeVisible()
  await expect(ficha.getByRole('link', { name: 'PC Soporte', exact: true })).toHaveCount(0)
  await ficha.getByRole('button', { name: 'Historial del conjunto', exact: true }).click()
  await page.getByRole('dialog').getByRole('link', { name: /TKT-2026-000001/ }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page).toHaveURL(/\/panel\/tickets\/caso$/)
})

test('registro manual comparte categorías y ofrece la PC real para programas', async ({ page }) => {
  const api = await portal(page, false, 'administrador')
  await page.goto('/panel/tickets/nuevo')
  await page.getByRole('combobox', { name: 'Persona afectada' }).fill('Ana')
  await page.getByRole('button', { name: /Ana Prueba.*SOPORTE/ }).click()
  await page.getByLabel('Asunto').fill('Instalar Office')
  await page.getByLabel('Categoría', { exact: true }).selectOption('Sistema / Programa')
  await expect(page.getByLabel('Computadora afectada')).toHaveValue('pc:conjunto')
  await expect(page.getByLabel('Tipo de equipo', { exact: true })).toHaveCount(0)
  await page.getByLabel('Programa, sistema o correo').fill('Office')
  await page.screenshot({ path: '../.codex-pdf-tools/manual-destino-pc.png', fullPage: true })
  await page.getByRole('button', { name: 'Registrar ticket', exact: true }).click()
  await expect(page).toHaveURL(/panel\/tickets\/caso$/)
  expect(api.solicitudes[0]).toMatchObject({ categoria: 'Sistema / Programa', conjunto_id: 'conjunto', sistema_afectado: 'Office' })
  expect(api.solicitudes[0]).not.toHaveProperty('activo_tipo')
  expect(api.solicitudes[0]).not.toHaveProperty('activo_id')
})

test('la bandeja principal conserva la presentación original del SLA y permite abrir el caso', async ({ page }) => {
  await portal(page, false, 'administrador')
  await page.route('**/api/tickets?**', r => r.fulfill({ json: { items: [{ id: 'caso', codigo: 'TKT-2026-000001', asunto: 'La impresora no imprime', afectado_nombre: 'Ana Prueba', oficina_nombre: 'SOPORTE', estado: 'en_progreso', prioridad: 'media', tecnico_nombre: 'Soporte TI', creado_en: '2026-10-18T14:00:00Z', actualizado_en: '2026-10-18T14:00:00Z', sla: { estado: 'seguro', minutos_restantes: 480, minutos_transcurridos: 0, activo: true, modo: 'resolver', progreso: 0 } }], total: 1, pagina: 1, por_pagina: 20, total_paginas: 1 } }))
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/panel/tickets')
  await expect(page.getByRole('columnheader', { name: 'SLA', exact: true })).toBeVisible()
  const fila = page.getByRole('row').filter({ hasText: 'TKT-2026-000001' })
  const sla = fila.getByRole('cell').nth(3)
  await expect(sla).toContainText('En tiempo')
  await expect(sla).toContainText('Quedan 8 horas')
  await expect(sla.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  const bloque = sla.locator('span.block.min-w-32')
  await expect(bloque).not.toHaveClass(/text-center|mx-auto/)
  await page.screenshot({ path: '../.codex-pdf-tools/bandeja-sla-restaurado.png', fullPage: true })
  await fila.click()
  await expect(page).toHaveURL(/panel\/tickets\/caso$/)
})

test('el perfil filtra antecedentes por computadora y componente con paginación', async ({ page }) => {
  await portal(page, false, 'administrador')
  const peticiones: URLSearchParams[] = []
  await page.route('**/api/zonas**', r => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) }))
  await page.route('**/api/usuarios/persona**', async r => {
    const url = new URL(r.request().url())
    let datos: unknown
    if (url.pathname.endsWith('/inventario-historial')) datos = { conjuntos: [{ id: 'pc1', nombre: 'Computadora 1', tickets: 17 }], equipos: [{ id: 'cpu', nombre: 'CPU principal', conjunto_id: 'pc1' }] }
    else if (url.pathname.endsWith('/tickets')) {
      peticiones.push(url.searchParams)
      const pagina = Number(url.searchParams.get('pagina') || 1)
      datos = { items: Array.from({ length: pagina === 1 ? 15 : 2 }, (_, i) => ({ id: `${pagina}-${i}`, codigo: `TKT-${pagina}-${i}`, asunto: 'Office no abre', afectado_nombre: 'Ana Prueba', estado: 'cerrado', prioridad: 'media' })), total: 17, pagina, total_paginas: 2 }
    } else if (url.pathname.endsWith('/dispositivos')) datos = { items: [], total: 0, limite: 3 }
    else datos = { id: 'persona', nombre: 'Ana Prueba', rol: 'usuario', activo: true, equipos_responsable: [], tiene_foto: false, creado_en: '2026-10-18T14:00:00Z' }
    await r.fulfill({ contentType: 'application/json', body: JSON.stringify(datos) })
  })
  await page.goto('/panel/usuarios/persona?tab=tickets&activo_id=cpu&estado=cerrado')
  await expect(page.getByRole('tab', { name: 'Tickets', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByLabel('Equipo espec\u00edfico')).toHaveValue('cpu')
  await expect(page.getByLabel('Estado', { exact: true })).toHaveValue('cerrado')
  await page.getByRole('tab', { name: 'Tickets', exact: true }).click()
  await expect(page.getByRole('columnheader', { name: 'Estado y prioridad' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Equipo', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'SLA', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Estado', { exact: true }).locator('option')).not.toContainText(['Resuelto'])
  await expect(page.getByLabel('Computadora / conjunto').locator('option')).toContainText(['Computadora 1 · 17'])
  await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect.poll(() => peticiones.at(-1)?.get('pagina')).toBe('2')
  await page.getByLabel('Computadora / conjunto').selectOption('pc1')
  await expect.poll(() => peticiones.at(-1)?.get('conjunto_id')).toBe('pc1')
  expect(peticiones.at(-1)?.get('pagina')).toBe('1')
  await page.getByLabel('Equipo específico').selectOption('cpu')
  await expect.poll(() => peticiones.at(-1)?.get('activo_id')).toBe('cpu')
  expect(peticiones.at(-1)?.get('por_pagina')).toBe('15')
})

test('la oficina pagina 25 tickets y coloca los indicadores al lado sin desbordar', async ({ page }) => {
  await portal(page, false, 'administrador')
  let limite = ''
  await page.route('**/api/oficinas/oficina', r => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: 'oficina', nombre: 'Soporte', zona_id: 'zona', zona_nombre: 'Palacio', zona_color_indice: 1, total_equipos: 0, total_usuarios: 0, tickets_abiertos: 26, completitud_inventario: 100, usuarios: [], equipos_por_usuario: [], equipos_uso_comun: [], tendencia: [{ mes: '2026-10-18', total: 26 }], incidencias_recurrentes: [{ categoria: 'Software', total: 26 }] }) }))
  await page.route('**/api/tickets?**', async r => {
    limite = new URL(r.request().url()).searchParams.get('por_pagina') || ''
    await r.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [{ id: 'caso', codigo: 'TKT-001', asunto: 'Problema de Office', afectado_nombre: 'Ana Prueba', estado: 'nuevo', prioridad: 'media' }], total: 26, pagina: 1, total_paginas: 2 }) })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/panel/oficinas/oficina')
  await expect(page.getByRole('columnheader', { name: 'Estado y prioridad' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Equipo', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'SLA', exact: true })).toHaveCount(0)
  expect(limite).toBe('25')
  const tabla = await page.getByRole('table').boundingBox()
  const lateral = await page.getByRole('heading', { name: 'Incidencias recurrentes' }).boundingBox()
  expect(lateral!.x).toBeGreaterThan(tabla!.x)
  await page.screenshot({ path: '../.codex-pdf-tools/oficina-escritorio.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../.codex-pdf-tools/oficina-movil.png', fullPage: true })
})

test('el resultado resalta y los estados terminados tienen un único filtro', async ({ page }) => {
  await portal(page)
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: { id: 'caso', codigo: 'TKT-2026-000001', asunto: 'Instalación de Office', descripcion: 'Necesito instalar Office', estado: 'resuelto', prioridad: 'media', tiene_chat: true, creado_en: '2026-10-18T14:00:00Z', nota_resolucion: 'Se instaló Office y se verificó su funcionamiento.' } }))
  for (const tema of ['claro', 'oscuro']) {
    await page.goto('/mis-tickets/caso')
    await page.evaluate(t => document.documentElement.setAttribute('data-tema', t), tema)
    await expect(page.getByRole('heading', { name: 'Finalizado', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Resultado de la atención', exact: true })).toBeVisible()
    await expect(page.getByText('Se instaló Office y se verificó su funcionamiento.', { exact: true })).toBeVisible()
    const resultado = page.locator('.portal-resultado')
    expect(await resultado.evaluate(e => parseFloat(getComputedStyle(e).borderLeftWidth))).toBeGreaterThanOrEqual(4)
  }
  await page.goto('/mis-tickets')
  await expect(page.getByLabel('Estado', { exact: true }).locator('option')).toHaveText(['Todos', 'Recibidos', 'En atención', 'En espera', 'Finalizados'])
})

test('las estrellas envían la puntuación correcta una sola vez y persisten al volver', async ({ page }) => {
  await portal(page)
  let puntuacion: number | null = null
  const envios: unknown[] = []
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: { id: 'caso', codigo: 'TKT-2026-000001', asunto: 'Impresora reparada', descripcion: 'La impresora no imprime', estado: 'cerrado', prioridad: 'media', tiene_chat: true, satisfaccion: puntuacion, creado_en: '2026-10-18T14:00:00Z' } }))
  await page.route('**/api/tickets/caso/valorar', async ruta => {
    const datos = ruta.request().postDataJSON()
    envios.push(datos)
    await new Promise(resolve => setTimeout(resolve, 200))
    puntuacion = datos.puntuacion
    await ruta.fulfill({ json: { satisfaccion: puntuacion } })
  })
  await page.goto('/mis-tickets/caso')
  const cuatro = page.getByRole('button', { name: 'Valorar con 4 estrellas', exact: true })
  await cuatro.evaluate((boton: HTMLButtonElement) => { boton.click(); boton.click() })
  await expect(page.getByText('Calificación guardada: 4/5', { exact: true })).toBeVisible()
  expect(envios).toEqual([{ puntuacion: 4 }])
  await expect(cuatro).toHaveAttribute('aria-pressed', 'true')
  await expect(cuatro).toBeDisabled()
  await page.reload()
  await expect(page.getByText('Calificación guardada: 4/5', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Valorar con 4 estrellas', exact: true })).toHaveAttribute('aria-pressed', 'true')
})

test('una calificación fallida no se muestra como guardada y permite reintentar', async ({ page }) => {
  await portal(page)
  let envios = 0
  await page.route('**/api/tickets/caso', ruta => ruta.fulfill({ json: { id: 'caso', codigo: 'TKT-2026-000001', asunto: 'Impresora reparada', estado: 'cerrado', prioridad: 'media', tiene_chat: true, satisfaccion: null, creado_en: '2026-10-18T14:00:00Z' } }))
  await page.route('**/api/tickets/caso/valorar', async ruta => { envios++; await ruta.fulfill(envios === 1 ? { status: 503, json: { mensaje: 'No se pudo guardar la calificación.' } } : { json: { satisfaccion: 3 } }) })
  await page.goto('/mis-tickets/caso')
  const tres = page.getByRole('button', { name: 'Valorar con 3 estrellas', exact: true })
  await tres.click()
  await expect(tres).toBeEnabled()
  await expect(page.getByText(/Calificación guardada:/)).toHaveCount(0)
  await tres.click()
  await expect(page.getByText('Calificación guardada: 3/5', { exact: true })).toBeVisible()
  expect(envios).toBe(2)
})

test('la ayuda de IA cambia sin recargar por ajustes globales y preferencias personales', async ({ page }) => {
  const api = await portal(page, false, 'usuario', true)
  await page.route('**/api/ia/sugerencias-reporte?**', ruta => ruta.fulfill({ json: { disponible: true, articulos: [{ id: 'guia', titulo: 'Guía de impresora' }] } }))
  await page.goto('/mis-tickets/caso')
  const guias = page.getByLabel('Guías recomendadas', { exact: true })
  await expect(guias).toBeVisible()
  api.publicarIa(false)
  await expect(guias).toHaveCount(0, { timeout: 2500 })
  api.publicarIa(true)
  await expect(guias).toBeVisible({ timeout: 2500 })
  api.preferenciaRemota(false)
  await expect(guias).toHaveCount(0, { timeout: 2500 })
  api.preferenciaRemota(true)
  await expect(guias).toBeVisible({ timeout: 2500 })
  await page.getByRole('link', { name: 'Mi cuenta', exact: true }).click()
  await page.getByText('Preferencias de ayuda automática', { exact: true }).click()
  const interruptor = page.getByRole('switch', { name: 'Mostrar guías recomendadas', exact: true })
  await expect(interruptor).toBeChecked()
  await interruptor.click()
  await expect(interruptor).not.toBeChecked()
  await page.goBack()
  await expect(page).toHaveURL(/mis-tickets\/caso$/)
  await expect(guias).toHaveCount(0)
})
