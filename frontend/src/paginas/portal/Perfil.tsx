import { useFotoUsuario } from '../../api/fotos'
/**
 * Mi perfil: datos de la persona y sus preferencias.
 *
 * El interruptor de recomendaciones de IA es el punto central: explica qué pasa
 * al activarlo y lo que la API responde, sin vender la función ni prometer nada
 * que el sistema no haga.
 */

import { BookOpen, CircleAlert, KeyRound, LogOut, Monitor, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useGuardarPreferenciaIa } from '../../api/hooks'
import { useMiPerfil, usePreferenciaIa } from '../../api/hooks'
import { useAvisos } from '../../estado/Avisos'
import { useSesion } from '../../estado/Sesion'
import { TEXTOS_IA } from '../../dominio/textos-ia'
import { Button } from '../../componentes/base/Button'
import { Input, Switch } from '../../componentes/base/Campo'
import { ErrorState, Nota, PageHeader, Panel, PantallaFormulario, SkeletonPanel } from '../../componentes/base/Estructura'
import { EtiquetaIA } from '../../componentes/dominio/Badge'
import { PersonaFila } from '../../componentes/base/Estructura'
import { DispositivosCuenta } from '../../componentes/dominio/DispositivosCuenta'
import { ControlFoto } from '../../componentes/dominio/ControlFoto'

export function Perfil() {
  const sesion = useSesion()
  const avisos = useAvisos()
  const navegar = useNavigate()

  const perfil = useMiPerfil()
  const foto = useFotoUsuario(sesion.usuario?.id, Boolean(perfil.data?.tiene_foto))
  const preferencia = usePreferenciaIa()
  const guardarPreferencia = useGuardarPreferenciaIa()

  const [passwordActual, setPasswordActual] = useState('')
  const [passwordNuevo, setPasswordNuevo] = useState('')
  const [repetir, setRepetir] = useState('')
  const [cambiando, setCambiando] = useState(false)

  useEffect(() => {
    document.title = 'Mi perfil · Mesa de Ayuda'
  }, [])

  const cambiarPassword = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (passwordNuevo !== repetir) {
      avisos.aviso('La nueva contraseña y su repetición no coinciden.')
      return
    }
    setCambiando(true)
    try {
      await api.crear('/auth/password', {
        password_actual: passwordActual,
        password_nuevo: passwordNuevo,
      })
      avisos.exito('Contraseña actualizada', 'Vuelve a ingresar con la nueva contraseña.')
      await sesion.salir()
      navegar('/acceder', { replace: true })
      setPasswordActual('')
      setPasswordNuevo('')
      setRepetir('')
    } catch (fallo) {
      avisos.desdeError(fallo, 'No pudimos cambiar la contraseña')
    } finally {
      setCambiando(false)
    }
  }

  const salir = async () => {
    await sesion.salir()
    navegar('/acceder')
  }

  if (perfil.isLoading) return <SkeletonPanel filas={4} />

  if (perfil.isError || !perfil.data) {
    return (
      <ErrorState
        mensaje="No pudimos cargar tu perfil."
        detalle={perfil.error instanceof Error ? perfil.error.message : undefined}
        alReintentar={() => void perfil.refetch()}
      />
    )
  }

  const datos = perfil.data
  const datosIa = preferencia.data
  // La IA global la decide el administrador; la persona solo puede apagarla
  const globalActiva = datosIa?.ia_global_activa ?? false

  return (
    <PantallaFormulario>
      <PageHeader titulo="Mi cuenta" descripcion="Tus datos, tus equipos y la seguridad de tu cuenta." />
      <div className="grid gap-3 sm:grid-cols-2">
        <Link to={sesion.esTecnico ? "/panel/mis-equipos" : "/mis-equipos"} className="flex min-h-20 items-center gap-3 rounded-2xl border border-border bg-surface p-4 font-semibold hover:border-warning"><span className="rounded-xl bg-primary-soft p-3 text-primary-strong"><Monitor size={23} /></span>Mis equipos</Link>
        <Link to={sesion.esTecnico ? "/panel/ayuda" : "/ayuda"} className="flex min-h-20 items-center gap-3 rounded-2xl border border-border bg-surface p-4 font-semibold hover:border-warning"><span className="rounded-xl bg-success-soft p-3 text-success-strong"><BookOpen size={23} /></span>Guías de ayuda</Link>
      </div>

      <Panel titulo="Mis datos" descripcion="Los datos los mantiene el administrador de la institución">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col items-start gap-2">
            <PersonaFila foto={foto} nombre={datos.nombre} detalle={datos.email ?? undefined} tamano="lg" rol={sesion.rol} />
            {sesion.esTecnico ? <div className="sm:pl-16">
              <ControlFoto usuarioId={datos.id} nombre={datos.nombre} puedeEditar discreto
                alCambiar={() => { void perfil.refetch() }} />
            </div> : null}
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Campo etiqueta="Oficina" valor={datos.oficina_nombre ?? 'Sin oficina'} />
            <Campo etiqueta="Zona" valor={datos.zona_nombre ?? 'Sin zona'} />
            <Campo etiqueta="Cargo" valor={datos.cargo ?? 'No indicado'} />
            <Campo etiqueta="Anexo" valor={datos.anexo ?? datos.telefono ?? 'No indicado'} />
          </dl>
          <Nota tono="info">
            <p>
              Para cambiar tu oficina o tu cargo,{' '}
              <strong>pídele al administrador</strong> que lo actualice: esos datos vienen del padrón de la institución.
            </p>
          </Nota>
        </div>
      </Panel>

      {/* ── IA ─────────────────────────────────────────────────────── */}
      <details className="rounded-2xl border border-border bg-surface p-4"><summary className="min-h-8 cursor-pointer font-semibold">Preferencias de ayuda automática</summary><div className="mt-3"><Panel
        titulo={
          <span className="flex items-center gap-2">
            Ayudas automáticas <EtiquetaIA />
          </span>
        }
        descripcion="Guías relacionadas con tus reportes. La conversación del ticket es con soporte TI."
      >
        {!datosIa ? (
          <p className="text-sm text-muted-foreground">Cargando el estado de las ayudas automáticas…</p>
        ) : !globalActiva ? (
          <Nota tono="info" titulo="Las ayudas automáticas están desactivadas" icono={<CircleAlert size={16} aria-hidden="true" />}>
            <p>{TEXTOS_IA.desactivada}</p>
          </Nota>
        ) : (
          <div className="flex flex-col gap-3">
            <Switch
              etiqueta="Mostrar guías recomendadas"
              descripcion="Ver artículos de ayuda relacionados al consultar mis reportes."
              valor={datosIa.recomendaciones_ia}
              cargando={guardarPreferencia.isPending}
              alCambiar={(valor) => {
                guardarPreferencia.mutate(valor, {
                  onSuccess: () => avisos.info(valor ? 'Sugerencias activadas' : 'Sugerencias desactivadas'),
                  onError: (fallo: unknown) => avisos.desdeError(fallo),
                })
              }}
            />
            <p className="flex items-start gap-2 text-sm text-muted-foreground">
              <Sparkles size={16} className="mt-0.5 shrink-0 text-ai-strong" aria-hidden="true" />
              <span>{datosIa.proveedor_disponible ? TEXTOS_IA.disponible : TEXTOS_IA.basica}</span>
            </p>
          </div>
        )}
      </Panel>

      {/* ── Contraseña ─────────────────────────────────────────────── */}
      </div></details>
      <details className="rounded-2xl border border-border bg-surface p-4"><summary className="min-h-8 cursor-pointer font-semibold">Dispositivos conectados a mi cuenta</summary><div className="mt-3"><DispositivosCuenta /></div></details>
      {sesion.rol === 'usuario' ? <Panel titulo="¿Necesitas cambiar tu contraseña?" descripcion="El administrador realiza el cambio. Envía una solicitud al equipo TI para que la revise."><Button asChild icono={<KeyRound size={18} />}><Link to="/reportar?tipo=Otro&solicitud=password">Solicitar cambio de contraseña</Link></Button><p className="mt-3 text-sm text-muted-foreground">No escribas tu contraseña actual en el reporte ni en el chat.</p></Panel> : <details className="rounded-2xl border border-border bg-surface p-4"><summary className="flex min-h-8 cursor-pointer items-center gap-2 font-semibold"><KeyRound size={18} />Cambiar mi contraseña</summary><div className="mt-3">
        <Panel titulo="Contraseña" descripcion="Cámbiala si crees que alguien más la conoce">
          <form onSubmit={cambiarPassword} className="flex flex-col gap-4" noValidate>
            <Input
              etiqueta="Contraseña actual"
              type="password"
              autoComplete="current-password"
              required
              tamano="tactil"
              value={passwordActual}
              onChange={(evento) => setPasswordActual(evento.target.value)}
            />
            <Input
              etiqueta="Nueva contraseña"
              type="password"
              autoComplete="new-password"
              required
              tamano="tactil"
              value={passwordNuevo}
              onChange={(evento) => setPasswordNuevo(evento.target.value)}
              ayuda="Mínimo 8 caracteres."
            />
            <Input
              etiqueta="Repite la nueva contraseña"
              type="password"
              autoComplete="new-password"
              required
              tamano="tactil"
              value={repetir}
              onChange={(evento) => setRepetir(evento.target.value)}
              error={repetir && repetir !== passwordNuevo ? 'No coinciden' : undefined}
            />
            <div>
              <Button type="submit" variante="primario" tamano="tactil" cargando={cambiando} icono={<KeyRound size={16} aria-hidden="true" />}>
                Cambiar contraseña
              </Button>
            </div>
          </form>
        </Panel>
      </div></details>}

      <div>
        <Button variante="secundario" icono={<LogOut size={16} aria-hidden="true" />} onClick={() => void salir()}>
          Cerrar sesión
        </Button>
      </div>
    </PantallaFormulario>
  )
}

function Campo({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="truncate font-medium">{valor}</dd>
    </div>
  )
}
