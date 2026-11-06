import { puedeEditarCuenta, puedeRestablecerCuenta, puedeCambiarEstadoCuenta } from '../../dominio/cuentas'
import { ListaEquiposPerfil } from '../../componentes/dominio/ListaEquiposPerfil'
/** Perfil navegable de una persona del directorio y de los tickets. */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bot, BriefcaseBusiness, Building2, CalendarDays, Clock3, ContactRound, Mail, MapPin, Pencil, Phone, ShieldCheck, Ticket, UserRound, type LucideIcon } from 'lucide-react'
import { useEffect, useState, type CSSProperties } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { api, ErrorPeticion, erroresDeValidacion } from '../../api/cliente'
import { claves } from '../../api/consultas'
import { useFotoUsuario } from '../../api/fotos'
import { useOficinas, useZonas } from '../../api/hooks'
import type { HorarioSemanal, UsuarioDetalle } from '../../api/tipos'
import { Button } from '../../componentes/base/Button'
import { Input, Select } from '../../componentes/base/Campo'
import { Avatar, ContenidoTab, ErrorState, InsigniaRol, ListaTabs, NoPermission, Nota, PageHeader, Panel, SkeletonPanel, Tab, TabsPanel } from '../../componentes/base/Estructura'
import { ControlFoto } from '../../componentes/dominio/ControlFoto'
import { EtiquetaEstadoActivo } from '../../componentes/dominio/EtiquetaActivo'
import { etiquetaRol, fechaHora, ROLES } from '../../dominio/formato'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'
import { ZonaBadge } from '../../componentes/dominio/ZonaBadge'
import { TarjetaPerfil } from '../../componentes/dominio/TarjetaPerfil'
import { TicketsUsuario } from '../../componentes/dominio/TicketsUsuario'
import { DispositivosCuenta } from '../../componentes/dominio/DispositivosCuenta'
import { RestablecerPassword } from '../../componentes/dominio/RestablecerPassword'
import { EstadoCuentaUsuario } from '../../componentes/dominio/EstadoCuentaUsuario'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { DatoPerfil } from '../../componentes/dominio/DatoPerfil'

type EquipoResponsable = {
  id: string
  nombre: string
  tipo: string
  codigo_patrimonial: string | null
  oficina_nombre?: string | null
  estado?: string | null
}

type PerfilPersona = Omit<UsuarioDetalle, 'equipos_responsable'> & {
  equipos_responsable: EquipoResponsable[]
  horario?: HorarioSemanal
  especiales?: string[]
  carga_actual?: number
}

export function PerfilUsuario() {
  const { id } = useParams<{ id: string }>()
  return <ContenidoPerfilUsuario key={id} id={id} />
}

function ContenidoPerfilUsuario({ id }: { id?: string }) {
  const [parametros] = useSearchParams()
  const sesion = useSesion()
  const avisos = useAvisos()
  const invalidar = useQueryClient()
  const perfil = useQuery({
    queryKey: claves.usuario(id ?? ''),
    queryFn: () => api.obtener<PerfilPersona>(`/usuarios/${id}`),
    enabled: Boolean(id),
    placeholderData: undefined,
    retry: false,
  })
  const [editando, setEditando] = useState(false)
  const [pestana, setPestana] = useState(parametros.get('tab') === 'tickets' ? 'tickets' : 'resumen')
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [cargo, setCargo] = useState('')
  const [telefono, setTelefono] = useState('')
  const [anexo, setAnexo] = useState('')
  const [zonaId, setZonaId] = useState('')
  const [oficinaId, setOficinaId] = useState('')
  const [rolNuevo, setRolNuevo] = useState('usuario')
  const [ayudaIa, setAyudaIa] = useState(true)
  const [paginaEquipos, setPaginaEquipos] = useState(1)
  const puedeEditarUbicacion = sesion.esAdmin || id !== sesion.usuario?.id && sesion.puede('usuarios.editar')
  const zonas = useZonas()
  const oficinas = useOficinas(zonaId ? { zona_id: zonaId } : {})

  useEffect(() => {
    document.title = `${perfil.data?.nombre ?? 'Perfil de usuario'} · Mesa de Ayuda TI`
  }, [perfil.data?.nombre])

  const abrirEdicion = () => {
    const datos = perfil.data
    if (!datos) return
    setNombre(datos.nombre)
    setEmail(datos.email ?? '')
    setCargo(datos.cargo ?? '')
    setTelefono(datos.telefono ?? '')
    setAnexo(datos.anexo ?? '')
    setZonaId(datos.zona_id ?? '')
    setOficinaId(datos.oficina_id ?? '')
    setRolNuevo(datos.rol)
    setAyudaIa(datos.recomendaciones_ia)
    setErrores({})
    setErrorGeneral(null)
    setPestana('cuenta')
    setEditando(true)
  }

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (!id || !perfil.data || !puedeEditarCuenta(sesion, perfil.data) || nombre.trim().length < 3 || guardando) return
    setGuardando(true)
    setErrores({})
    setErrorGeneral(null)
    try {
      await api.editar(`/usuarios/${id}`, {
        nombre: nombre.trim(),
        email: email.trim() || null,
        cargo: cargo.trim() || null,
        telefono: telefono.trim() || null,
        anexo: anexo.trim() || null,
        ...(puedeEditarUbicacion ? { zona_id: zonaId || null, oficina_id: oficinaId || null } : {}),
        recomendaciones_ia: ayudaIa,
        ...(sesion.esAdmin && id !== sesion.usuario?.id ? { rol: rolNuevo } : {}),
      })
      await Promise.all([
        invalidar.invalidateQueries({ queryKey: claves.usuario(id) }),
        invalidar.invalidateQueries({ queryKey: ['usuarios'] }),
        invalidar.invalidateQueries({ queryKey: claves.miPerfil }),
        invalidar.invalidateQueries({ queryKey: claves.sesion }),
        invalidar.invalidateQueries({ queryKey: ['equipo-ti'] }),
        invalidar.invalidateQueries({ queryKey: ['oficina'] }),
        invalidar.invalidateQueries({ queryKey: ['zona'] }),
      ])
      setEditando(false)
      avisos.exito('Perfil actualizado')
    } catch (fallo) {
      const campos = erroresDeValidacion(fallo)
      if (fallo instanceof ErrorPeticion && fallo.estado === 409) campos.email = fallo.message
      setErrores(campos)
      setErrorGeneral(fallo instanceof Error ? fallo.message : 'No se pudieron guardar los datos.')
    } finally {
      setGuardando(false)
    }
  }

  /*
    La foto se pide **antes** de los retornos tempranos, aunque todavía no haya
    datos. Un gancho que se declara después de un `return` hace que el número de
    ganchos cambie entre renderizados —primero carga, después ya no— y React lo
    rechaza. Con `undefined` y `false` no se pide nada.
  */
  const foto = useFotoUsuario(perfil.data?.id, perfil.data?.tiene_foto)

  if (perfil.isLoading) return <SkeletonPanel filas={5} />
  if (perfil.isError || !perfil.data) {
    if (perfil.error instanceof ErrorPeticion && perfil.error.esPermiso) {
      return <NoPermission queIntentas="el perfil de esta persona" />
    }
    return (
      <ErrorState
        mensaje={perfil.error instanceof ErrorPeticion && perfil.error.estado === 404 ? 'Este usuario no existe.' : 'No pudimos cargar el perfil.'}
        detalle={perfil.error instanceof Error ? perfil.error.message : undefined}
        alReintentar={() => void perfil.refetch()}
      />
    )
  }

  const datos = perfil.data
  const puedeAdministrar = puedeEditarCuenta(sesion, datos)
  const equipos = datos.equipos_responsable ?? []
  const indiceZona = zonas.data?.items.find((zona) => zona.id === datos.zona_id)?.color_indice
  const colorZona = indiceZona && indiceZona >= 1 && indiceZona <= 8 ? `var(--zona-${indiceZona})` : 'var(--color-muted-foreground)'
  const colorSuave = `color-mix(in srgb, ${colorZona} 10%, var(--color-surface))`
  const colorFuerte = `color-mix(in srgb, ${colorZona} 75%, var(--color-foreground))`
  const colorBorde = `color-mix(in srgb, ${colorZona} 28%, var(--color-border))`
  const coloresPerfil = {
    '--perfil-acento': colorZona, '--color-primary': colorZona,
    '--color-primary-strong': colorFuerte, '--color-primary-soft': colorSuave, '--color-primary-borde': colorBorde,
    '--rol-relleno': colorZona, '--rol-fuerte': colorFuerte, '--rol-suave': colorSuave, '--rol-borde': colorBorde,
  } as CSSProperties
  const rolPerfil = datos.administrador_principal ? 'Administrador principal' : etiquetaRol(datos.rol)

  return (
    <div className="flex min-w-0 flex-col gap-4" style={coloresPerfil}>
      <PageHeader
        titulo="Perfil de usuario"
        descripcion="Datos de contacto, equipos a su cargo y tickets de esta persona."
        migas={[
          { texto: 'Panel', enlace: '/panel' },
          { texto: 'Usuarios', enlace: '/panel/usuarios' },
          { texto: 'Perfil' },
        ]}
        acciones={
          <>
            <Button asChild variante="secundario">
              <Link to="/panel/usuarios">
                <ArrowLeft size={16} aria-hidden="true" />
                Volver al directorio
              </Link>
            </Button>
            {puedeAdministrar ? (
              <Button variante="primario" icono={<Pencil size={16} aria-hidden="true" />} onClick={abrirEdicion}>
                Editar datos
              </Button>
            ) : null}
          </>
        }
      />

      <TarjetaPerfil
        titulo={datos.nombre}
        subtitulo={[datos.nombre.toLocaleLowerCase('es') !== rolPerfil.toLocaleLowerCase('es') ? rolPerfil : null, datos.oficina_nombre].filter(Boolean).join(' · ')}
        icono={<Avatar nombre={datos.nombre} foto={foto} tamano="lg" />}
        colorIndice={indiceZona}
        metricas={[
          { etiqueta: 'Equipos a cargo', valor: equipos.length },
          { etiqueta: 'Tickets creados', valor: datos.tickets_creados ?? 0 },
          { etiqueta: datos.rol === 'usuario' ? 'Tickets abiertos' : 'Asignados abiertos', valor: datos.rol === 'usuario' ? datos.tickets_activos ?? 0 : datos.carga_actual ?? 0 },
          { etiqueta: 'Cuenta', valor: datos.archivado ? 'Archivada' : datos.activo ? 'Activa' : 'Desactivada' },
        ]}
      />

      <TabsPanel valor={pestana} alCambiar={setPestana} className="flex flex-col gap-5">
        <ListaTabs>
          <Tab valor="resumen">Resumen</Tab>
          {sesion.puede('tickets.operar') ? <Tab valor="tickets">Tickets</Tab> : null}
          <Tab valor="equipos">Equipos ({equipos.length})</Tab>
          {puedeAdministrar ? <Tab valor="cuenta">Cuenta y edición</Tab> : null}
        </ListaTabs>
        <ContenidoTab valor="resumen" className="flex flex-col gap-5">
      <Panel titulo="Datos de la persona">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex min-w-0 items-center gap-2 break-all text-sm"><Mail size={16} className="shrink-0 text-muted-foreground" aria-hidden="true" />{datos.email ?? 'Sin correo registrado'}</p>
          <div className="flex items-center gap-2">
            <InsigniaRol rol={datos.rol} principal={datos.administrador_principal} />
            <EtiquetaEstadoActivo activo={datos.activo} archivado={datos.archivado} cuenta />
          </div>
        </div>
        <dl className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <DatoPerfil etiqueta="Zona" icono={MapPin}><ZonaBadge id={datos.zona_id} nombre={datos.zona_nombre} /></DatoPerfil>
          <Dato etiqueta="Oficina" valor={datos.oficina_nombre ?? 'Sin oficina'} enlace={sesion.puede('org.ver') && datos.oficina_id ? `/panel/oficinas/${datos.oficina_id}` : undefined} />
          <Dato etiqueta="Cargo" valor={datos.cargo ?? 'No indicado'} />
          <Dato etiqueta="Teléfono" valor={datos.telefono ?? 'No indicado'} />
          <Dato etiqueta="Anexo" valor={datos.anexo ?? 'No indicado'} />
          <Dato etiqueta="Creación de la cuenta" valor={fechaHora(datos.creado_en)} />
          {datos.desactivado_en ? <Dato etiqueta="Fecha de baja" valor={fechaHora(datos.desactivado_en)} /> : null}
          {datos.archivado_en ? <Dato etiqueta="Fecha de archivo" valor={fechaHora(datos.archivado_en)} /> : null}
          <Dato etiqueta="Último acceso" valor={datos.ultimo_acceso ? fechaHora(datos.ultimo_acceso) : 'Nunca'} />
          <Dato etiqueta="Ayuda IA" valor={datos.recomendaciones_ia ? 'Activada' : 'Desactivada'} />
        </dl>

      </Panel>

      <Panel titulo="Actividad de tickets">
        <dl className="grid grid-cols-3 gap-3 text-sm">
          <Dato etiqueta="Creados" valor={String(datos.tickets_creados ?? 0)} />
          <Dato etiqueta="Como afectado" valor={String(datos.tickets_afectado ?? 0)} />
          <Dato etiqueta="Activos" valor={String(datos.tickets_activos ?? 0)} />
        </dl>
      </Panel>

      {(datos.rol === 'tecnico' || datos.rol === 'administrador') && sesion.puede('horarios.ver') ? (
        <Panel titulo="Horario y perfil TI" acciones={<Button asChild tamano="sm"><Link to={`/panel/equipo-ti?tab=horarios&tecnico_id=${datos.id}`}>Ver horario completo</Link></Button>}>
          <p className="text-sm">Especialidades: {datos.especiales?.join(', ') || 'Sin especialidades registradas'}</p>
          <p className="mt-1 text-sm">Tickets asignados activos: {datos.carga_actual ?? 0}</p>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'].map((dia, indice) => {
              const configuracion = datos.horario?.dias?.[indice]
              return <div key={dia}><dt className="text-sm font-semibold">{dia}</dt><dd className="text-sm text-muted-foreground">{configuracion && !configuracion.libre && configuracion.tramos?.length ? configuracion.tramos.map((tramo) => `${tramo.entrada}–${tramo.salida}`).join(', ') : 'Día libre / sin horario'}</dd></div>
            })}
          </dl>
        </Panel>
      ) : null}

        </ContenidoTab>
        <ContenidoTab valor="equipos">
      <Panel titulo="Equipos a su cargo" descripcion={`${equipos.length} equipos con esta persona como responsable.`}>
        <ListaEquiposPerfil equipos={equipos.slice((paginaEquipos - 1) * 10, paginaEquipos * 10)} etiqueta="Equipos de esta persona" enlazar={sesion.puede('equipos.ver')} />
        {equipos.length > 10 ? <div className="mt-4"><Paginacion pagina={paginaEquipos} totalPaginas={Math.ceil(equipos.length / 10)} total={equipos.length} porPagina={10} alCambiar={setPaginaEquipos} /></div> : null}
      </Panel>

        </ContenidoTab>
        {sesion.puede('tickets.operar') ? (
          <ContenidoTab valor="tickets"><TicketsUsuario key={datos.id} usuarioId={datos.id} esPersonalTI={datos.rol !== 'usuario'} /></ContenidoTab>
        ) : null}
        {puedeAdministrar ? (
          <ContenidoTab valor="cuenta" className="flex flex-col gap-4">
            {sesion.esAdmin || sesion.usuario?.id === datos.id ? <DispositivosCuenta usuarioId={datos.id} /> : null}
            <Panel titulo={<span className="flex items-center gap-2"><ContactRound size={20} className="text-primary-strong" aria-hidden="true" />Datos y acceso</span>} descripcion="Identidad, contacto y ubicación de esta persona.">
              {!editando ? (
                <div className="flex flex-col gap-4">
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <Dato etiqueta="Nombre" valor={datos.nombre} />
                    <Dato etiqueta="Correo de acceso" valor={datos.email || 'Sin correo registrado'} />
                    <Dato etiqueta="Oficina" valor={datos.oficina_nombre || 'Sin oficina'} />
                    <Dato etiqueta="Cargo" valor={datos.cargo || 'No indicado'} />
                    <Dato etiqueta="Teléfono" valor={datos.telefono || 'No indicado'} />
                    <Dato etiqueta="Anexo" valor={datos.anexo || 'No indicado'} />
                  </dl>
                  <Button variante="secundario" className="self-start" onClick={abrirEdicion}>Modificar información</Button>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  {errorGeneral ? <Nota tono="peligro" titulo="No se pudieron guardar los cambios">{errorGeneral}</Nota> : null}
                  <div className="flex items-start gap-2 rounded-lg border border-primary-borde bg-primary-soft p-3 text-sm"><ShieldCheck size={18} className="mt-0.5 shrink-0 text-primary-strong" aria-hidden="true" /><p>Al cambiar el correo, la persona deberá usar la nueva dirección para iniciar sesión.</p></div>
        <form id="editar-perfil-usuario" autoComplete="off" onSubmit={guardar} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <p className="text-sm font-semibold sm:col-span-2">Identidad y contacto</p>
          <Input error={errores.nombre} disabled={guardando} etiqueta="Nombre completo" requerido minLength={3} maxLength={160} value={nombre} onChange={(evento) => setNombre(evento.target.value)} />
          <Input error={errores.email} disabled={guardando} etiqueta="Correo" name="usuario-editar-correo" autoComplete="off" type="email" ayuda="Opcional. Sin correo, esta persona no podrá iniciar sesión con una dirección de email." maxLength={160} value={email} onChange={(evento) => setEmail(evento.target.value)} />
          <Input error={errores.cargo} disabled={guardando} etiqueta="Cargo" maxLength={120} value={cargo} onChange={(evento) => setCargo(evento.target.value)} />
          <Input error={errores.telefono} disabled={guardando} etiqueta="Teléfono" maxLength={40} value={telefono} onChange={(evento) => setTelefono(evento.target.value)} />
          <Input error={errores.anexo} disabled={guardando} etiqueta="Anexo" maxLength={40} value={anexo} onChange={(evento) => setAnexo(evento.target.value)} />
          <p className="border-t border-border pt-4 text-sm font-semibold sm:col-span-2">Acceso, preferencias y ubicación</p>
          {sesion.esAdmin && datos.id !== sesion.usuario?.id ? (
            <Select etiqueta="Rol de la cuenta" disabled={guardando} value={rolNuevo} opciones={ROLES.filter(opcion => opcion.valor !== 'administrador' || sesion.usuario?.administrador_principal || datos.rol === 'administrador')}
              ayuda="El rol determina a qué funciones puede acceder la persona."
              onChange={(evento) => setRolNuevo(evento.target.value)} />
          ) : null}
          <Select etiqueta="Ayuda IA" disabled={guardando} value={ayudaIa ? 'si' : 'no'}
            opciones={[{ valor: 'si', etiqueta: 'Activada' }, { valor: 'no', etiqueta: 'Desactivada' }]}
            onChange={(evento) => setAyudaIa(evento.target.value === 'si')} />
          <Select
            disabled={guardando || !puedeEditarUbicacion}
            etiqueta="Zona"
            placeholder="Sin zona"
            value={zonaId}
            onChange={(evento) => { setZonaId(evento.target.value); setOficinaId('') }}
            opciones={(zonas.data?.items ?? []).map((zona) => ({ valor: zona.id, etiqueta: zona.nombre }))}
          />
          <Select
            disabled={guardando || !puedeEditarUbicacion}
            etiqueta="Oficina"
            placeholder="Sin oficina"
            value={oficinaId}
            onChange={(evento) => {
              const nuevaOficina = oficinas.data?.items.find((oficina) => oficina.id === evento.target.value)
              setOficinaId(evento.target.value)
              if (nuevaOficina?.zona_id) setZonaId(nuevaOficina.zona_id)
            }}
            opciones={(oficinas.data?.items ?? []).map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
          />
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button type="submit" variante="primario" cargando={guardando} disabled={nombre.trim().length < 3}>Guardar datos</Button>
            <Button disabled={guardando} onClick={() => setEditando(false)}>Cancelar edición</Button>
          </div>
        </form>
                </div>
              )}
              <div className="mt-5 rounded-xl border border-dashed border-border bg-surface-2/50 p-4">
                <p className="mb-3 text-sm font-semibold">Foto del perfil</p>
                <ControlFoto usuarioId={datos.id} nombre={datos.nombre} puedeEditar={puedeAdministrar}
                  alCambiar={() => { void perfil.refetch(); void invalidar.invalidateQueries({ queryKey: ['usuarios'] }); void invalidar.invalidateQueries({ queryKey: ['equipo-ti'] }) }} />
              </div>
            </Panel>
            {puedeRestablecerCuenta(sesion, datos) ? <Panel titulo="Restablecer contraseña" descripcion="Crea una clave nueva y revisa sus caracteres antes de guardarla.">
              <RestablecerPassword key={datos.id} usuarioId={datos.id} nombre={datos.nombre} permitido={puedeRestablecerCuenta(sesion, datos)} />
            </Panel> : null}
            {puedeCambiarEstadoCuenta(sesion, datos) ? (
              <Panel titulo="Estado de la cuenta">
                <EstadoCuentaUsuario key={datos.id} usuarioId={datos.id} nombre={datos.nombre} activo={datos.activo} archivado={datos.archivado} propia={datos.id === sesion.usuario?.id} />
              </Panel>
            ) : null}
          </ContenidoTab>
        ) : null}
      </TabsPanel>
    </div>
  )
}

function Dato({ etiqueta, valor, enlace }: { etiqueta: string; valor: string; enlace?: string }) {
  const iconos: Record<string, LucideIcon> = {
    Nombre: UserRound, 'Correo de acceso': Mail, Oficina: Building2, Cargo: BriefcaseBusiness,
    Teléfono: Phone, Anexo: ContactRound, 'Creación de la cuenta': CalendarDays,
    'Último acceso': Clock3, 'Ayuda IA': Bot, Creados: Ticket, 'Como afectado': UserRound, Activos: Clock3,
  }
  return (
    <DatoPerfil etiqueta={etiqueta} icono={iconos[etiqueta] ?? UserRound}
      color={etiqueta === 'Ayuda IA' ? 'var(--color-ai-strong)' : etiqueta === 'Último acceso' ? 'var(--color-success-strong)' : undefined}>
      {enlace ? <Link className="text-primary-strong hover:underline" to={enlace}>{valor}</Link> : valor}
    </DatoPerfil>
  )
}
