import { defineConfig } from '@playwright/test'
import configuracion from './playwright.config'

/** Comprueba la compilación servida por Nginx, incluido el límite de las subidas. */
export default defineConfig({
  ...configuracion,
  webServer: undefined,
  testMatch: ['usuarios-flujos.spec.ts', 'equipo-ti-flujos.spec.ts', 'analisis-flujos.spec.ts', 'reportes-flujos.spec.ts', 'mas-flujos.spec.ts', 'contraste-shell.spec.ts', 'inventario-anual-flujos.spec.ts', 'redisenio-general.spec.ts', 'correcciones-pdf.spec.ts'],
  use: { ...configuracion.use, baseURL: process.env.PRUEBA_BASE_URL ?? 'http://127.0.0.1:4317' },
})
