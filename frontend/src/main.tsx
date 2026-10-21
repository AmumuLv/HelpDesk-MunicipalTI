/** Punto de entrada de la interfaz. */

import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { clienteConsulta } from './api/consultas'
import { ProveedorAvisos } from './estado/Avisos'
import { ProveedorSesion } from './estado/Sesion'
import { Rutas } from './Rutas'
import './estilos/tokens.css'
import './estilos/futurista.css'

const contenedor = document.getElementById('root')
if (!contenedor) throw new Error('No se encontró el elemento #root')

createRoot(contenedor).render(
  <StrictMode>
    <BrowserRouter>
      <ProveedorAvisos>
        <QueryClientProvider client={clienteConsulta}>
          <ProveedorSesion>
            <Rutas />
          </ProveedorSesion>
        </QueryClientProvider>
      </ProveedorAvisos>
    </BrowserRouter>
  </StrictMode>,
)