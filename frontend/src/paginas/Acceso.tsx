/**
 * Acceso: la primera pantalla de todo el sistema.
 *
 * El formulario es corto a propósito: correo y contraseña, con el mensaje de
 * error del backend tal como lo escribió. Si el sistema aún no está instalado,
 * se ofrece el enlace al asistente de instalación en lugar de un 404.
 */

import { CircleAlert, LogIn, Headset, Users, ShieldCheck, Eye, EyeOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useConfiguracionPublica, useEstadoInstalacion } from '../api/hooks'
import { useSesion } from '../estado/Sesion'
import { cn } from '../lib/cn'
import { Button } from '../componentes/base/Button'
import { BotonTema } from '../componentes/base/BotonTema'
import { LogoMesa } from '../componentes/base/LogoMesa'
import { Input } from '../componentes/base/Campo'
import { Nota } from '../componentes/base/Estructura'
import { useAvisos } from '../estado/Avisos'

type UbicacionConEstado = { state?: { desde?: string } }

export function Acceso({ acceso }: { acceso?: 'usuario' | 'ti' }) {
  const sesion = useSesion()
  const avisos = useAvisos()
  const navegar = useNavigate()
  const ubicacion = useLocation()

  const instalacion = useEstadoInstalacion()
  const publica = useConfiguracionPublica()

  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [verPassword, setVerPassword] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const institution = (publica.data?.institucion ?? 'Municipalidad Provincial de Casma').replace(/^Municipalidad de Casma$/i, 'Municipalidad Provincial de Casma')
  const tituloAcceso = acceso === 'ti' ? 'Acceso del equipo TI' : acceso === 'usuario' ? 'Acceso de trabajadores' : 'Iniciar sesión'

  useEffect(() => {
    document.title = `Acceder · ${institution}`
  }, [institution])

  const entrar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await sesion.entrar(correo.trim(), password, acceso)
      const destino = (ubicacion as UbicacionConEstado).state?.desde ?? (acceso === 'ti' ? '/panel' : '/')
      navegar(destino, { replace: true })
      avisos.exito('Sesión iniciada', institution)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No pudimos iniciar sesión.')
    } finally {
      setEnviando(false)
    }
  }

  const sinInstalar = instalacion.data && !instalacion.data.hay_admin

  return (
    <main className="acceso-futurista relative isolate flex min-h-dvh flex-col bg-background">
      <div className="absolute right-4 top-4 z-10 rounded-xl border border-white/20 bg-slate-950/60 p-1"><BotonTema compacto /></div>
      <img src="/identidad/casma-dia.jpg" alt="" aria-hidden="true" className="absolute inset-0 -z-20 h-full w-full object-cover" />
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-gradient-to-r from-slate-950/90 via-slate-950/60 to-slate-950/35" />
      <div className="mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 p-4 sm:p-8 lg:grid-cols-2 lg:gap-20 lg:py-12">
        <section className="hidden text-white lg:block" aria-label="Mesa de ayuda institucional">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-4 py-2 text-sm"><Headset size={18} /> Mesa de Ayuda TI</span>
          <h2 className="mt-6 text-5xl font-bold leading-tight">Tu soporte, en un solo lugar.</h2>
          <p className="mt-5 max-w-md text-lg leading-relaxed text-slate-200">Reporta una incidencia, conversa con soporte y consulta el avance de tu solicitud.</p>
          <div className="mt-10 flex items-center gap-3 border-t border-white/20 pt-6 text-sm text-slate-200"><ShieldCheck size={22} className="text-sky-300" /> Acceso institucional y seguimiento de tus tickets</div>
        </section>
        <div className="acceso-tarjeta mx-auto w-full max-w-md overflow-hidden rounded-2xl border border-border bg-background p-5 shadow-2xl ring-1 ring-white/10 sm:p-8 lg:justify-self-end">
          <div className="mb-6 flex items-center gap-3 border-b border-border pb-5">
            <span className="shrink-0 [&>span]:size-14 sm:[&>span]:size-16"><LogoMesa grande /></span>
            <div className="min-w-0">
              <h1 aria-label={institution} className="text-[clamp(0.875rem,4vw,1.25rem)] font-bold leading-snug break-words">{institution === 'Municipalidad Provincial de Casma' ? <><span className="block whitespace-nowrap">Municipalidad Provincial</span><span className="block">de Casma</span></> : institution}</h1>
              <p className="mt-1 text-xs font-medium text-muted-foreground">{tituloAcceso}</p>
            </div>
          </div>

          <nav aria-label="Tipo de acceso" className="mb-6 grid grid-cols-2 gap-2">
            <Link to="/acceder/usuarios" state={ubicacion.state} aria-current={acceso === 'usuario' ? 'page' : undefined} className={cn('flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary', acceso === 'usuario' ? 'border-primary bg-primary-soft text-primary-strong shadow-sm' : 'border-border bg-surface-2/40 text-muted-foreground hover:bg-muted hover:text-foreground')}><Users size={20} aria-hidden="true" />Trabajadores<span className="font-normal text-2xs">Reportar y seguir tickets</span></Link>
            <Link to="/acceder/ti" state={ubicacion.state} aria-current={acceso === 'ti' ? 'page' : undefined} className={cn('flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary', acceso === 'ti' ? 'border-primary bg-primary-soft text-primary-strong shadow-sm' : 'border-border bg-surface-2/40 text-muted-foreground hover:bg-muted hover:text-foreground')}><Headset size={20} aria-hidden="true" />Equipo TI<span className="font-normal text-2xs">Técnicos y administrador</span></Link>
          </nav>

          {sinInstalar ? (
            <Nota tono="aviso" titulo="El sistema todavía no está configurado" icono={<CircleAlert size={16} aria-hidden="true" />}>
              <p>Antes del primer acceso hay que crear la institución y el administrador inicial.</p>
              <Link to="/instalacion" className="mt-2 inline-block font-semibold underline">
                Ir al asistente de instalación
              </Link>
            </Nota>
          ) : null}

          <form onSubmit={entrar} className="mt-4 flex flex-col gap-5" noValidate>
            <Input
              etiqueta="Correo institucional"
              type="email"
              autoComplete="username"
              required
              tamano="tactil"
              value={correo}
              onChange={(evento) => setCorreo(evento.target.value)}
              placeholder="nombre@municipalidad.gob.pe"
              autoFocus
            />
            <div className="relative">
            <Input
              etiqueta="Contraseña"
              type={verPassword ? 'text' : 'password'}
              className="[&_input]:pr-12"
              autoComplete="current-password"
              required
              tamano="tactil"
              value={password}
              onChange={(evento) => setPassword(evento.target.value)}
            />
            <button type="button" aria-label={verPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={verPassword} onClick={() => setVerPassword(!verPassword)} className="absolute bottom-0 right-1 flex size-12 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground">{verPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button>
            </div>

            {error ? (
              <p role="alert" className={cn('rounded-[var(--radius-panel)] border border-destructive/40 bg-destructive-soft p-3 text-sm font-semibold text-destructive-strong')}>
                {error}
              </p>
            ) : null}

            <Button
              type="submit"
              variante="primario"
              tamano="tactil"
              anchoCompleto
              cargando={enviando}
              icono={<LogIn size={18} aria-hidden="true" />}
            >
              Entrar
            </Button>
          </form>

          <p className="mt-5 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
            ¿No recuerdas tu contraseña? Pídele al administrador de la institución que te la restablezca.
          </p>
        </div>
      </div>

      <footer className="border-t border-white/20 bg-slate-950/75 px-4 py-3 text-center text-2xs text-white">
        Sistema de Mesa de Ayuda TI · datos del navegador: la sesión termina al cerrar la pestaña
      </footer>
    </main>
  )
}

