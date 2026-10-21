import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// La API cuelga del mismo origen bajo /api (ver deploy/nginx.conf y Caddyfile).
// En desarrollo se puede apuntar a otro servidor con VITE_API_BASE.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      // El navegador sigue hablando con /api: nada de CORS ni URLs absolutas.
      // 127.0.0.1 y no localhost: en Windows `localhost` resuelve primero a ::1
      // y la API solo escucha en IPv4.
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
})