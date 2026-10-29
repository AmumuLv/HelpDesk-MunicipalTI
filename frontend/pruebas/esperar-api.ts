import { expect, request } from '@playwright/test'

/** Wait for the isolated backend to finish seeding and its startup checks. */
export default async function esperarApi() {
  const destino = process.env.PRUEBA_API_URL
  if (!destino) return
  const cliente = await request.newContext({ baseURL: destino, timeout: 5000 })
  try {
    await expect.poll(async () => {
      try { return (await cliente.get('/api/health')).status() }
      catch { return 0 }
    }, { timeout: 180_000, intervals: [500, 1000, 2000], message: `Esperando la API de pruebas: ${destino}` }).toBe(200)
  } finally {
    await cliente.dispose()
  }
}
