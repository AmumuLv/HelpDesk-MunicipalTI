/* Navegador con certificado local fijado y sesión ficticia recibida por stdin. */
const { chromium } = require('../frontend/node_modules/playwright')
const { X509Certificate, createHash } = require('node:crypto')
let entrada = ''
process.stdin.on('data', b => { entrada += b })
process.stdin.on('end', async () => {
  let navegador
  try {
    const datos = JSON.parse(entrada)
    const spki = new X509Certificate(Buffer.from(datos.certificado, 'base64')).publicKey.export({ type: 'spki', format: 'der' })
    const huella = createHash('sha256').update(spki).digest('base64')
    navegador = await chromium.launch({ args: [`--ignore-certificate-errors-spki-list=${huella}`] })
    const contexto = await navegador.newContext({ baseURL: 'https://localhost:18111' })
    await contexto.addCookies(datos.cookies)
    await contexto.addInitScript(token => { sessionStorage.setItem('ma.acceso', token) }, datos.token)
    const pagina = await contexto.newPage()
    const violaciones = []
    const errores = []
    await pagina.exposeFunction('violacionCsp', directiva => { violaciones.push(directiva) })
    await pagina.addInitScript(() => document.addEventListener('securitypolicyviolation', e => window.violacionCsp(e.effectiveDirective)))
    pagina.on('pageerror', error => errores.push(error.name))
    for (const [ruta, titulo] of [['/panel', 'Resumen'], ['/panel/tickets', 'Abiertos'], ['/panel/equipos', 'Equipos']]) {
      await pagina.goto(ruta)
      await pagina.getByRole('heading', { name: titulo, exact: true }).first().waitFor({ state: 'visible', timeout: 20000 })
    }
    await pagina.evaluate(() => localStorage.setItem('ma.tema', 'oscuro'))
    await pagina.reload()
    if (await pagina.locator('html').getAttribute('data-tema') !== 'oscuro') throw new Error('No se conservó el tema')
    if (violaciones.length || errores.length) throw new Error(JSON.stringify({ violaciones, errores }))
    console.log(JSON.stringify({ navegador_https: 'aprobado', pantallas: 3, csp_violaciones: 0, tema: 'conservado', validacion_certificado: 'clave pública fijada tras validación de CA por Python' }))
  } catch (error) {
    console.error(error.message)
    process.exitCode = 1
  } finally {
    if (navegador) await navegador.close()
  }
})
