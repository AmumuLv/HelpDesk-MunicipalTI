/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base de la API. Por defecto es la misma del origen: /api. */
  readonly VITE_API_BASE?: string
  /** Servidor de la API usado por el proxy en desarrollo. */
  readonly VITE_API_TARGET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}