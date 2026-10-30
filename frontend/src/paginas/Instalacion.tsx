/**
 * Instalación: el recorrido guiado de puesta en marcha.
 *
 * Solo aparece cuando el sistema aún no está configurado. Muestra el estado
 * real de cada paso (lo devuelve `GET /instalacion`) y ofrece la acción que
 * falta: crear el administrador, cargar zonas, importar el inventario o
 * completar los horarios. Nunca dice «pendiente» sin decir qué hacer.
 */

import { Check, CircleDashed, FileSpreadsheet, Network, Users, UserCog, Wrench } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/cliente'
import { useEstadoInstalacion } from '../api/hooks'
import type { CuerpoAdministradorInicial } from '../api/tipos'
import { useAvisos } from '../estado/useAvisos'
import { useSesion } from '../estado/useSesion'
import { cn } from '../lib/cn'
import { Button } from '../componentes/base/Button'
import { Input } from '../componentes/base/Campo'
import { ErrorState, Panel, SkeletonPanel } from '../componentes/base/Estructura'

const ICONO_PASO: Record<string, LucideIcon> = {
  crear_admin: UserCog,
  importar_inventario: FileSpreadsheet,
  crear_usuarios: Users,
  crear_tecnicos: UserCog,
  asignar_responsables: Network,
  definir_horarios: Wrench,
}

export function Instalacion() {
  const estado = useEstadoInstalacion()
  const avisos = useAvisos()
  const navegar = useNavigate()
  const sesion = useSesion()

  const [correo, setCorreo] = useState('')
  const [nombre, setNombre] = useState('')
  const [password, setPassword] = useState('')
  const [telefono, setTelefono] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const crearAdmin = async (evento: React.FormEvent) => {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const cuerpo: CuerpoAdministradorInicial = {
        nombre: nombre.trim(),
        email: correo.trim(),
        password,
        ...(telefono.trim() ? { telefono: telefono.trim() } : {}),
      }
      await api.crear('/instalacion/administrador', cuerpo)
      avisos.exito('Administrador creado', 'Ya puedes entrar con ese correo.')
      await estado.refetch()
      navegar('/acceder/ti')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No pudimos crear el administrador.')
    } finally {
      setEnviando(false)
    }
  }

  if (estado.isLoading) {
    return (
      <main className="mx-auto w-full max-w-3xl p-4">
        <SkeletonPanel filas={5} />
      </main>
    )
  }

  const datos = estado.data
  if (estado.isError) return <main className="mx-auto max-w-3xl p-6"><ErrorState mensaje="No pudimos comprobar la puesta en marcha." alReintentar={() => void estado.refetch()} /></main>

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4 sm:p-6">
      <header>
        <h1 className="titulo-pagina">Puesta en marcha</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {datos?.configurado
            ? `${datos.institucion} ya está configurada. Entra con tu cuenta.`
            : datos?.hay_admin ? 'Ya puedes iniciar sesión. Completa los datos reales indicados en cada paso.' : 'Crea el administrador para comenzar la configuración.'}
        </p>
      </header>

      <Panel titulo="Estado" descripcion={`${datos?.pasos.filter(paso => paso.hecho).length ?? 0} de ${datos?.pasos.length ?? 6} pasos completados`} acciones={<Button tamano="sm" cargando={estado.isFetching} onClick={() => void estado.refetch()}>Actualizar estado</Button>}>
        <ul className="flex flex-col gap-2">
          {(datos?.pasos ?? []).map((paso) => {
            const Icono = ICONO_PASO[paso.clave] ?? CircleDashed
            const hecho = paso.hecho
            return (
              <li
                key={paso.clave}
                className={cn(
                  'flex items-start gap-3 rounded-[var(--radius-panel)] border p-3',
                  hecho ? 'border-success/25 bg-success-soft' : 'border-border bg-surface',
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full',
                    hecho ? 'bg-success text-primary-foreground' : 'bg-muted text-muted-foreground',
                  )}
                >
                  {hecho ? <Check size={16} /> : <Icono size={16} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 font-semibold">
                    {paso.titulo}
                    <span className="text-2xs font-normal text-muted-foreground">{hecho ? 'hecho' : 'pendiente'}</span>
                  </p>
                  {paso.descripcion ? <p className="mt-1 text-sm text-muted-foreground">{paso.descripcion}</p> : null}
                  {paso.alternativa ? (
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      Alternativa: {paso.alternativa}
                      {paso.alternativa_hecha ? ' (hecha)' : ''}
                    </p>
                  ) : null}
                  {paso.ruta && paso.clave !== 'crear_admin' && (sesion.esAdmin || !sesion.usuario) ? (
                    <Button asChild tamano="sm" variante={hecho ? 'secundario' : 'primario'} className="mt-2">
                      <Link to={sesion.esAdmin ? paso.ruta : '/acceder/ti'} state={sesion.esAdmin ? undefined : { desde: paso.ruta }}>{paso.accion || 'Completar paso'}</Link>
                    </Button>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>
      </Panel>

      {!datos?.hay_admin ? (
        <Panel titulo="Crear el administrador principal" descripcion="Primera cuenta protegida; autoriza nuevos administradores">
          <form onSubmit={crearAdmin} className="flex flex-col gap-4" noValidate>
            <Input
              etiqueta="Nombre completo"
              required
              tamano="tactil"
              value={nombre}
              onChange={(evento) => setNombre(evento.target.value)}
              placeholder="Nombre del administrador"
            />
            <Input
              etiqueta="Correo"
              type="email"
              required
              tamano="tactil"
              value={correo}
              onChange={(evento) => setCorreo(evento.target.value)}
              placeholder="admin@municipalidad.gob.pe"
            />
            <Input
              etiqueta="Contraseña"
              type="password"
              required
              tamano="tactil"
              value={password}
              onChange={(evento) => setPassword(evento.target.value)}
              ayuda="Mínimo 8 caracteres."
            />
            <Input
              etiqueta="Teléfono o anexo"
              tamano="tactil"
              value={telefono}
              onChange={(evento) => setTelefono(evento.target.value)}
              placeholder="Opcional"
            />

            {error ? (
              <p role="alert" className="rounded-[var(--radius-panel)] border border-destructive/40 bg-destructive-soft p-3 text-sm font-semibold text-destructive-strong">
                {error}
              </p>
            ) : null}

            <Button type="submit" variante="primario" tamano="tactil" cargando={enviando} anchoCompleto>
              Crear administrador
            </Button>
          </form>
        </Panel>
      ) : (
        <Panel>
          <div className="flex flex-wrap gap-2">
            <Button asChild variante="primario"><Link to="/acceder/ti">Acceso del equipo TI</Link></Button>
            <Button asChild variante="secundario"><Link to="/acceder/usuarios">Acceso de trabajadores</Link></Button>
            <Button asChild variante="secundario">
              <Link to="/panel/equipos/importar">Importar inventario</Link>
            </Button>
            <Button asChild variante="secundario">
              <Link to="/panel/organizacion">Crear zonas y oficinas</Link>
            </Button>
            <Button asChild variante="secundario">
              <Link to="/panel/equipo-ti?tab=horarios">Completar horarios</Link>
            </Button>
          </div>
        </Panel>
      )}
    </main>
  )
}
