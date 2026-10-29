/**
 * Tablero de rutas.
 *
 * Cada módulo se carga aparte: quien entra al portal no descarga el módulo de
 * campañas anuales ni el de auditoría. Las guardas de rol y de permiso son
 * explícitas: sin permiso se ve una pantalla que lo explica, no un error.
 */

import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { ProveedorAvisos } from './estado/Avisos'
import { useSesion } from './estado/useSesion'
import { ShellPanel } from './componentes/shell/ShellPanel'
import { ShellPortal } from './componentes/shell/ShellPortal'
import { ErrorState, NoPermission, SkeletonPanel } from './componentes/base/Estructura'
import { Acceso } from './paginas/Acceso'
import { Instalacion } from './paginas/Instalacion'
import { Inicio } from './paginas/portal/Inicio'

const Resumen = lazy(() => import('./paginas/panel/Resumen').then((m) => ({ default: m.Resumen })))
const Bandeja = lazy(() => import('./paginas/panel/Bandeja').then((m) => ({ default: m.Bandeja })))
const MisAsignaciones = lazy(() => import('./paginas/panel/MisAsignaciones').then((m) => ({ default: m.MisAsignaciones })))
const Cerrados = lazy(() => import('./paginas/panel/Cerrados').then((m) => ({ default: m.Cerrados })))
const RegistrarTicketManual = lazy(() =>
  import('./paginas/panel/RegistrarTicketManual').then((m) => ({ default: m.RegistrarTicketManual })),
)
const TicketDetalle = lazy(() => import('./paginas/panel/TicketDetalle').then((m) => ({ default: m.TicketDetalle })))
const Equipos = lazy(() => import('./paginas/panel/Equipos').then((m) => ({ default: m.Equipos })))
const FichaEquipo = lazy(() => import('./paginas/panel/FichaEquipo').then((m) => ({ default: m.FichaEquipo })))
const CalidadInventario = lazy(() => import('./paginas/panel/CalidadInventario').then((m) => ({ default: m.CalidadInventario })))
const ImportarInventario = lazy(() => import('./paginas/panel/ImportarInventario').then((m) => ({ default: m.ImportarInventario })))
const InventarioAnual = lazy(() => import('./paginas/panel/InventarioAnual').then((m) => ({ default: m.InventarioAnual })))
const Organizacion = lazy(() => import('./paginas/panel/Organizacion').then((m) => ({ default: m.Organizacion })))
const PerfilZona = lazy(() => import('./paginas/panel/PerfilOrganizacion').then((m) => ({ default: m.PerfilZona })))
const PerfilOficina = lazy(() => import('./paginas/panel/PerfilOrganizacion').then((m) => ({ default: m.PerfilOficina })))
const Usuarios = lazy(() => import('./paginas/panel/Usuarios').then((m) => ({ default: m.Usuarios })))
const PerfilUsuario = lazy(() => import('./paginas/panel/PerfilUsuario').then((m) => ({ default: m.PerfilUsuario })))
const EquipoTi = lazy(() => import('./paginas/panel/EquipoTi').then((m) => ({ default: m.EquipoTi })))
const PerfilTecnico = lazy(() => import('./paginas/panel/PerfilTecnico').then((m) => ({ default: m.PerfilTecnico })))
const Analisis = lazy(() => import('./paginas/panel/Analisis').then((m) => ({ default: m.Analisis })))
const Reportes = lazy(() => import('./paginas/panel/Reportes').then((m) => ({ default: m.Reportes })))
const Conocimiento = lazy(() => import('./paginas/panel/Conocimiento').then((m) => ({ default: m.Conocimiento })))
const Auditoria = lazy(() => import('./paginas/panel/Auditoria').then((m) => ({ default: m.Auditoria })))
const Configuracion = lazy(() => import('./paginas/panel/Configuracion').then((m) => ({ default: m.Configuracion })))

const Reportar = lazy(() => import('./paginas/portal/Reportar').then((m) => ({ default: m.Reportar })))
const MisTickets = lazy(() => import('./paginas/portal/MisTickets').then((m) => ({ default: m.MisTickets })))
const TicketUsuario = lazy(() => import('./paginas/portal/TicketUsuario').then((m) => ({ default: m.TicketUsuario })))
const MisEquipos = lazy(() => import('./paginas/portal/MisEquipos').then((m) => ({ default: m.MisEquipos })))
const Ayuda = lazy(() => import('./paginas/portal/Ayuda').then((m) => ({ default: m.Ayuda })))
const Articulo = lazy(() => import('./paginas/portal/Articulo').then((m) => ({ default: m.Articulo })))
const Perfil = lazy(() => import('./paginas/portal/Perfil').then((m) => ({ default: m.Perfil })))
const Galeria = lazy(() => import('./paginas/Galeria').then((m) => ({ default: m.Galeria })))

/** Carga diferida con la silueta del contenido, para que no salte el layout. */
function Cargando() {
  return (
    <div className="flex flex-col gap-4">
      <div className="h-8 w-64 animate-pulse rounded bg-muted" />
      <SkeletonPanel filas={5} />
    </div>
  )
}

/**
 * Si un módulo no carga, la pantalla lo dice y ofrece recargar. Se declara una
 * clase de error propia porque React no expone un errorElement en Suspense.
 */
class ErrorDeCarga extends Error {}

function RutaDeError({ children }: { children: React.ReactNode }) {
  return (
    <LimiteDeError>
      <Suspense fallback={<Cargando />}>{children}</Suspense>
    </LimiteDeError>
  )
}

/** Captura el fallo de un módulo lazy y muestra la pantalla de reintento. */
function LimiteDeError({ children }: { children: React.ReactNode }) {
  const [fallo, setFallo] = useState(false)
  useEffect(() => {
    const alFallar = (evento: PromiseRejectionEvent) => {
      if (evento.reason instanceof ErrorDeCarga || String(evento.reason).includes('ChunkLoad')) {
        setFallo(true)
        evento.preventDefault()
      }
    }
    window.addEventListener('unhandledrejection', alFallar)
    return () => window.removeEventListener('unhandledrejection', alFallar)
  }, [])

  if (fallo) {
    return <ErrorState mensaje="No pudimos cargar esta sección." alReintentar={() => window.location.reload()} />
  }
  return <>{children}</>
}

/** Exige sesión iniciada; si no, al acceso. */
function ExigeSesion({ children }: { children: React.ReactNode }) {
  const sesion = useSesion()
  const ubicacion = useLocation()
  if (sesion.cargando) return <Cargando />
  if (!sesion.usuario) return <Navigate to={ubicacion.pathname.startsWith('/panel') ? '/acceder/ti' : '/acceder'} state={{ desde: ubicacion.pathname + ubicacion.search }} replace />
  return <>{children}</>
}

/** Exige el panel TI: un usuario normal no entra, aunque escriba la URL. */
function ExigePanel({ children }: { children: React.ReactNode }) {
  const sesion = useSesion()
  if (!sesion.esTecnico) {
    return (
      <ShellPortal>
        <NoPermission queIntentas="el panel del equipo TI" />
      </ShellPortal>
    )
  }
  return <ShellPanel>{children}</ShellPanel>
}

/** Conserva el entorno de trabajo al abrir paginas compartidas de la cuenta. */
function ShellCuenta({ children }: { children: React.ReactNode }) {
  const sesion = useSesion()
  return sesion.esTecnico ? <ShellPanel>{children}</ShellPanel> : <ShellPortal>{children}</ShellPortal>
}

/** Exige un permiso concreto: el enlace ya no está, pero la URL puede escribirse. */
function ExigePermiso({ permiso, children }: { permiso: string; children: React.ReactNode }) {
  const sesion = useSesion()
  if (!sesion.puede(permiso)) {
    return <NoPermission queIntentas="esta sección" permiso={permiso} />
  }
  return <>{children}</>
}

/**
 * Raíz del sistema: cada rol entra por donde le toca trabajar.
 *
 * El equipo TI (administrador o técnico) va a su panel; cualquier otra persona
 * va al portal. Se decide con el rol de la sesión, no con la URL.
 */
function RaizPorRol() {
  const sesion = useSesion()
  if (sesion.cargando) return <Cargando />
  if (sesion.esTecnico) {
    return (
      <ShellPanel>
        <RutaDeError>
          <Resumen />
        </RutaDeError>
      </ShellPanel>
    )
  }
  return (
    <ShellPortal>
      <RutaDeError>
        <Inicio />
      </RutaDeError>
    </ShellPortal>
  )
}

export function Rutas() {
  const sesion = useSesion()

  if (sesion.cargando) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <div className="w-full max-w-md">
          <SkeletonPanel filas={3} />
        </div>
      </div>
    )
  }

  return (
    <Routes>
      {/* Público */}
      <Route path="/acceder" element={sesion.usuario ? <Navigate to="/" replace /> : <Acceso />} />
      <Route path="/acceder/usuarios" element={sesion.usuario ? <Navigate to="/" replace /> : <Acceso acceso="usuario" />} />
      <Route path="/acceder/ti" element={sesion.usuario ? <Navigate to="/panel" replace /> : <Acceso acceso="ti" />} />
      <Route path="/instalacion" element={<Instalacion />} />

      {/* El inicio depende del rol: quien es del equipo TI entra a su panel,
          no al portal de usuario. Sin esto el administrador abre el portal. */}
      <Route
        path="/"
        element={
          <ExigeSesion>
            <RaizPorRol />
          </ExigeSesion>
        }
      />
      <Route
        path="/reportar"
        element={
          <ExigeSesion>
            <ShellPortal>
              <RutaDeError>
                <Reportar />
              </RutaDeError>
            </ShellPortal>
          </ExigeSesion>
        }
      />
      <Route
        path="/mis-tickets"
        element={
          <ExigeSesion>
            <ShellPortal>
              <RutaDeError>
                <MisTickets />
              </RutaDeError>
            </ShellPortal>
          </ExigeSesion>
        }
      />
      <Route
        path="/mis-tickets/:id"
        element={
          <ExigeSesion>
            <ShellPortal>
              <RutaDeError>
                <TicketUsuario />
              </RutaDeError>
            </ShellPortal>
          </ExigeSesion>
        }
      />
      <Route
        path="/mis-equipos"
        element={
          <ExigeSesion>
            <ShellCuenta>
              <RutaDeError>
                <MisEquipos />
              </RutaDeError>
            </ShellCuenta>
          </ExigeSesion>
        }
      />
      <Route
        path="/ayuda"
        element={
          <ExigeSesion>
            <ShellCuenta>
              <RutaDeError>
                <Ayuda />
              </RutaDeError>
            </ShellCuenta>
          </ExigeSesion>
        }
      />
      <Route
        path="/ayuda/:id"
        element={
          <ExigeSesion>
            <ShellCuenta>
              <RutaDeError>
                <Articulo />
              </RutaDeError>
            </ShellCuenta>
          </ExigeSesion>
        }
      />
      <Route
        path="/perfil"
        element={
          <ExigeSesion>
            <ShellCuenta>
              <RutaDeError>
                <Perfil />
              </RutaDeError>
            </ShellCuenta>
          </ExigeSesion>
        }
      />

      {[{ ruta: '/panel/mis-equipos', pagina: <MisEquipos /> }, { ruta: '/panel/ayuda', pagina: <Ayuda /> }, { ruta: '/panel/ayuda/:id', pagina: <Articulo /> }].map(({ ruta, pagina }) => (
        <Route key={ruta} path={ruta} element={<ExigeSesion><ExigePanel><RutaDeError>{pagina}</RutaDeError></ExigePanel></ExigeSesion>} />
      ))}

      {/* Panel del equipo TI */}
      <Route
        path="/panel"
        element={
          <ExigeSesion>
            <ExigePanel>
              <RutaDeError>
                <Resumen />
              </RutaDeError>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/tickets"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="tickets.operar">
                <RutaDeError>
                  <Bandeja />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/mis-asignaciones"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="tickets.operar">
                <RutaDeError>
                  <MisAsignaciones />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/cerrados"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="tickets.operar">
                <RutaDeError>
                  <Cerrados />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/tickets/nuevo"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="tickets.crear">
                <RutaDeError>
                  <RegistrarTicketManual />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/tickets/:id"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="tickets.operar">
                <RutaDeError>
                  <TicketDetalle />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipos"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="equipos.ver">
                <RutaDeError>
                  <Equipos />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipos/nuevo"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="equipos.crear">
                <RutaDeError>
                  <Equipos />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipos/:id"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="equipos.ver">
                <RutaDeError>
                  <FichaEquipo />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipos/calidad"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="equipos.ver">
                <RutaDeError>
                  <CalidadInventario />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipos/importar"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="equipos.importar">
                <RutaDeError>
                  <ImportarInventario />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/inventario-anual"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="equipos.campanas">
                <RutaDeError>
                  <InventarioAnual />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/organizacion"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="org.ver">
                <RutaDeError>
                  <Organizacion />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/zonas/:id"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="org.ver">
                <RutaDeError>
                  <PerfilZona />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/oficinas/:id"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="org.ver">
                <RutaDeError>
                  <PerfilOficina />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/usuarios"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="usuarios.ver">
                <RutaDeError>
                  <Usuarios />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/usuarios/:id"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="usuarios.ver">
                <RutaDeError>
                  <PerfilUsuario />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipo-ti"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="horarios.ver">
                <RutaDeError>
                  <EquipoTi />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/equipo-ti/:id"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="horarios.ver">
                <RutaDeError>
                  <PerfilTecnico />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/analisis"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="analitica.ver">
                <RutaDeError>
                  <Analisis />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/reportes"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="reportes.ver">
                <RutaDeError>
                  <Reportes />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/conocimiento"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="kb.ver">
                <RutaDeError>
                  <Conocimiento />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/auditoria"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="auditoria.ver">
                <RutaDeError>
                  <Auditoria />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />
      <Route
        path="/panel/configuracion"
        element={
          <ExigeSesion>
            <ExigePanel>
              <ExigePermiso permiso="configuracion.ver">
                <RutaDeError>
                  <Configuracion />
                </RutaDeError>
              </ExigePermiso>
            </ExigePanel>
          </ExigeSesion>
        }
      />

      {/* El perfil dentro del panel. `/perfil` usa el cascarón del portal, así
          que desde aquí «Mi perfil» sacaba a la persona del panel y le dejaba
          sin barra lateral: parecía que el menú no hacía nada. */}
      <Route
        path="/panel/perfil"
        element={
          <ExigeSesion>
            <ExigePanel>
              <RutaDeError>
                <Perfil />
              </RutaDeError>
            </ExigePanel>
          </ExigeSesion>
        }
      />

      {/* Galería de componentes: solo en desarrollo. No lleva shell porque es
          una pantalla de trabajo, pero sí los proveedores que usa. */}
      {import.meta.env.DEV ? (
        <Route
          path="/dev/componentes"
          element={
            <ExigeSesion>
              <ProveedorAvisos>
                <RutaDeError>
                  <Galeria />
                </RutaDeError>
              </ProveedorAvisos>
            </ExigeSesion>
          }
        />
      ) : null}

      {/* Cualquier ruta desconocida vuelve al inicio del rol */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
