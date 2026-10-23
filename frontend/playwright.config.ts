import { defineConfig, devices } from '@playwright/test'

/**
 * Verificación visual sin generar archivos de captura.
 *
 * Recorre las rutas de cada rol en tres tamaños y comprueba, en cada una:
 * - que no haya desbordamiento horizontal,
 * - que no haya errores en la consola,
 * - que el foco sea visible,
 * - que axe-core no encuentre violaciones serias ni criticas.
 *
 * El servidor de desarrollo se levanta solo. El puerto importa: con
 * `reuseExistingServer: true`, si otro despliegue ya ocupa el puerto las pruebas
 * se ejecutan contra ese y no contra el código del proyecto. Pasó con el 4317,
 * que ocupaba un despliegue de pruebas con su propia base de datos; por eso las
 * cuentas de demostración y el número de activos no correspondían. Ahora el puerto
 * es 4321, que no publica ningún `docker compose` del proyecto.
 *
 * Las pruebas hablan con la API real por el proxy de Vite
 * (`PRUEBA_API_URL`, `127.0.0.1:8100` por defecto, instalación de pruebas separada).
 */
const PUERTO = 4321
const BASE = `http://127.0.0.1:${PUERTO}`

export default defineConfig({
  testDir: './pruebas',
  // Cada prueba recorre todas las pantallas de un rol en un tamaño, y cada
  // pantalla pasa cuatro comprobaciones: 90 s se quedaban cortos.
  timeout: 420_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: BASE,
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
    locale: 'es-PE',
    timezoneId: 'America/Lima',
    trace: 'off',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --port ${PUERTO} --strictPort`,
    env: { VITE_API_TARGET: process.env.PRUEBA_API_URL ?? 'http://127.0.0.1:8100' },
    url: BASE,
    // Solo se reutiliza si lo que escucha es el servidor de Vite de este proyecto,
    // no cualquier otra cosa que ya tenga el puerto.
    reuseExistingServer: false,
    timeout: 180_000,
  },
})
