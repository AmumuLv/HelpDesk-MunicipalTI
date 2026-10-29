/**
 * Directorio de usuarios.
 *
 * Búsqueda, filtro por rol, zona y oficina. Cada fila dice su rol, su oficina, si
 * tiene activa la ayuda automática —que es lo que hace falta entender por qué a
 * alguien no le aparecen sugerencias— y si su cuenta sigue activa.
 *
 * Cuatro cosas que se corrigieron al recorrerla (decisiones 221 a 224):
 *
 * **El filtro de oficina no se acotaba a la zona elegida.** Se podía marcar zona
 * COMPLEJO y oficina de PISCINA y salir «0 resultados» sin explicación. Ahora las
 * oficinas son las de la zona, y si chegaram a quedar incompatibles se dice por qué.
 *
 * **No había forma de desactivar ni de reactivar a nadie.** El backend lo tenía y la
 * pantalla no lo llamaba; además la lista pedía solo las cuentas activas, así que
 * una cuenta desactivada desaparecía sin dejar rastro y sin vuelta atrás. Es el
 * mismo callejón sin salida que se corrigió en Zonas y oficinas.
 *
 * **El error del servidor solo salía como aviso en la esquina.** Si el correo ya
 * estaba en uso, el formulario se quedaba igual de limpio y el campooffensivo no se
 * marcaba. Ahora el motivo se escribe dentro del diálogo.
 *
 * **El rol se escribía de dos maneras.** El filtro decía «Técnico TI» y la tabla
 * aplicaba `capitalize` sobre el valor crudo, así que un técnico salía «Tecnico»:
 * sin tilde y con otro nombre. `capitalize` pone mayúscula, no tilde.
 */

import { ArrowUpRight, Building2, ChevronDown, KeyRound, Plus, Users } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { api, ErrorPeticion, erroresDeValidacion } from '../../api/cliente'
import { useFotoUsuario } from '../../api/fotos'
import { useOficinas, useUsuarios, useZonas } from '../../api/hooks'
import type { FiltrosUsuarios } from '../../api/tipos'
import { DataTable, Paginacion, type ColumnaTabla } from '../../componentes/dominio/DataTable'
import { Button } from '../../componentes/base/Button'
import { Input, SearchInput, Select } from '../../componentes/base/Campo'
import { CampoPassword } from '../../componentes/base/CampoPassword'
import { RestablecerPassword } from '../../componentes/dominio/RestablecerPassword'
import { ConfirmDialog, DialogModal } from '../../componentes/base/Sobreposiciones'
import { Avatar, EmptyState, ErrorState, Nota, PageHeader } from '../../componentes/base/Estructura'
import { ControlFoto } from '../../componentes/dominio/ControlFoto'
import { CuerpoPerfilUsuario } from '../../componentes/dominio/CuerpoPerfilUsuario'
import { EtiquetaEstadoActivo } from '../../componentes/dominio/EtiquetaActivo'
import { ROLES, etiquetaRol, numero } from '../../dominio/formato'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'
import { Ubicacion } from '../../componentes/dominio/Ubicacion'
import type { MiPerfil, UsuarioResumen } from '../../api/tipos'

/**
 * Si mostrar las cuentas desactivadas está marcado.
 *
 * Se guarda porque es una decisión de quien mira. Antes solo vivía mientras la
 * pantalla estuviera abierta, igual que en Zonas y oficinas.
 */
const CLAVE_PREFERENCIA = 'usuarios.ver-desactivados'
const mostrarDesactivadosGuardado = (() => {
  try {
    return window.localStorage.getItem(CLAVE_PREFERENCIA) !== 'false'
  } catch {
    return true
  }
})()

export function Usuarios() {
  const sesion = useSesion()
  const avisos = useAvisos()
  const invalidar = useQueryClient()
  const [parametros] = useSearchParams()
  const rolInicial = parametros.get('crear') === 'tecnico' ? 'tecnico' : 'usuario'
  const zonas = useZonas()
  const oficinas = useOficinas()

  const [texto, setTexto] = useState('')
  const [rol, setRol] = useState('')
  const [zonaId, setZonaId] = useState('')
  const [oficinaId, setOficinaId] = useState('')
  const [pagina, setPagina] = useState(1)
  const [verInactivas, setVerInactivas] = useState(mostrarDesactivadosGuardado)
  const [creando, setCreando] = useState(Boolean(parametros.get('crear')))
  const [seleccionado, setSeleccionado] = useState<string | null>(null)
  const [mostrarPassword, setMostrarPassword] = useState(false)
  const passwordRef = useRef<HTMLDetailsElement>(null)
  const detalle = useQuery({
    queryKey: ['usuario', seleccionado],
    queryFn: () => api.obtener<MiPerfil>(`/usuarios/${seleccionado}`),
    enabled: Boolean(seleccionado),
    placeholderData: undefined,
  })
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [telefono, setTelefono] = useState('')
  const [anexo, setAnexo] = useState('')
  const [cargo, setCargo] = useState('')
  const [zonaNueva, setZonaNueva] = useState('')
  const [password, setPassword] = useState('')
  const [confirmacionPassword, setConfirmacionPassword] = useState('')
  const [rolNuevo, setRolNuevo] = useState(rolInicial)
  const [oficinaNueva, setOficinaNueva] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [errores, setErrores] = useState<Record<string, string>>({})
  /* El motivo del rechazo del servidor, para escribirlo **dentro** del diálogo y no
     solo como aviso en la esquina. `null` = todavía no ha fallado nada. */
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)
  const [cambiandoActivo, setCambiandoActivo] = useState<{ usuario: UsuarioResumen; activar: boolean } | null>(null)

  useEffect(() => {
    document.title = 'Usuarios · Mesa de Ayuda TI'
  }, [])

  /** Cada cambio se guarda en el momento. */
  const cambiarVisibilidadInactivas = (valor: boolean) => {
    setVerInactivas(valor)
    try {
      window.localStorage.setItem(CLAVE_PREFERENCIA, valor ? 'true' : 'false')
    } catch {
      // Si no se puede guardar, el cambio se aplica igual en esta sesión.
    }
  }

  const filtros: FiltrosUsuarios = {
    ...(texto.trim() ? { texto: texto.trim() } : {}),
    ...(rol ? { rol } : {}),
    ...(zonaId ? { zona_id: zonaId } : {}),
    ...(oficinaId ? { oficina_id: oficinaId } : {}),
    solo_activos: !verInactivas,
    pagina,
    por_pagina: 25,
  }
  const usuarios = useUsuarios(filtros)

  /*
    Las oficinas del filtro se acotan a la zona elegida.

    Antes salían las 59 con cualquier zona marcada, y marcar zona COMPLEJO + oficina
    de PISCINA daba «0 resultados» sin decir que esa combinación no existe. Además,
    al cambiar de zona la oficina anterior se quedaba puesta —y ahora es de otra
    zona—, que es como se llegaba a esa combinación imposible sin querer.
  */
  const oficinasDeLaZona = (oficinas.data?.items ?? []).filter((oficina) => !zonaId || oficina.zona_id === zonaId)
  const zonaElegida = zonas.data?.items.find((zona) => zona.id === zonaId)
  const oficinaElegida = oficinas.data?.items.find((oficina) => oficina.id === oficinaId)
  const combinacionImposible = Boolean(
    zonaElegida && oficinaElegida && oficinaElegida.zona_id !== zonaElegida.id,
  )

  /*
    Anchos declarados. Sin ellos la tabla reparte el espacio a partes iguales y la
    ubicación —que lleva la oficina **y** la pastilla de zona debajo— se queda
    mirando la mitad del nombre: «GERENCIA DE ADMINISTRACI…», «SUB GERENCIA DE
    DESARROL…». En una pantalla de la que lo que interesa es saber dónde está cada
    persona, esa es la columna que no puede recortarse.

    Suman 100, y todas lo declaran porque la tabla solo usa `<colgroup>` cuando lo
    hacen todas: una columna sin ancho y la declaración se ignoran.
  */
  const columnas: ColumnaTabla<UsuarioResumen>[] = [
    {
      accessorKey: 'nombre',
      header: 'Persona',
      meta: { ancho: '30%' },
      cell: ({ row }) => (
        <span className="flex min-w-0 items-center gap-2">
          <AvatarConFoto usuario={row.original} />
          <span className="min-w-0">
            <span className="block truncate font-medium">{row.original.nombre}</span>
            <span className="block truncate text-2xs text-muted-foreground">{row.original.email}</span>
          </span>
        </span>
      ),
    },
    {
      accessorKey: 'rol',
      header: 'Rol',
      meta: { ancho: '11%' },
      cell: ({ row }) => <span>{etiquetaRol(row.original.rol)}</span>,
    },
    {
      id: 'ubicacion',
      header: 'Ubicación',
      // Sin recorte: lleva la insignia de zona, que con el recorte automático de la
      // tabla quedaba partida por la mitad.
      meta: { celdaLibre: true, ancho: '30%' },
      cell: ({ row }) => (
        <Ubicacion
          zonaId={row.original.zona_id}
          zonaNombre={row.original.zona_nombre}
          oficinaId={row.original.oficina_id}
          oficinaNombre={row.original.oficina_nombre}
        />
      ),
    },
    {
      accessorKey: 'recomendaciones_ia',
      header: 'Ayuda IA',
      enableSorting: false,
      meta: { ancho: '13%' },
      // El encabezado de esta página promete que cada fila dice si tiene activa la
      // ayuda automática, y solo lo decía la tarjeta del móvil. Es la columna que
      // explica por qué a alguien no le salen sugerencias.
      cell: ({ row }) =>
        row.original.recomendaciones_ia ? (
          <span className="text-sm text-muted-foreground">Activada</span>
        ) : (
          <span className="text-sm text-muted-foreground">Desactivada</span>
        ),
    },
    {
      accessorKey: 'activo',
      header: 'Estado',
      meta: { celdaLibre: true, ancho: '16%' },
      cell: ({ row }) => <EtiquetaEstadoActivo activo={row.original.activo} />,
    },
  ]

  const crear = async () => {
    if (guardando || nombre.trim().length < 3 || !email.trim() || password.length < 8 || password !== confirmacionPassword) return
    setErrores({})
    setErrorGeneral(null)
    setGuardando(true)
    try {
      await api.crear('/usuarios', {
        nombre: nombre.trim(),
        email: email.trim(),
        telefono: telefono.trim() || undefined,
        anexo: anexo.trim() || undefined,
        cargo: cargo.trim() || undefined,
        password,
        rol: rolNuevo,
        ...(zonaNueva ? { zona_id: zonaNueva } : {}),
        ...(oficinaNueva ? { oficina_id: oficinaNueva } : {}),
      })
      avisos.exito('Usuario creado', email.trim())
      await invalidar.invalidateQueries({ queryKey: ['instalacion'] })
      await invalidar.invalidateQueries({ queryKey: ['equipo-ti'] })
      setCreando(false)
      setNombre('')
      setEmail('')
      setTelefono('')
      setAnexo('')
      setCargo('')
      setZonaNueva('')
      setPassword('')
      setConfirmacionPassword('')
      setRolNuevo(rolInicial)
      setOficinaNueva('')
      setErrores({})
      await usuarios.refetch()
    } catch (fallo) {
      const validacion = erroresDeValidacion(fallo)
      if (fallo instanceof ErrorPeticion && fallo.estado === 409) validacion.email = fallo.message
      setErrores(validacion)
      if (Object.keys(validacion).length === 0) {
        /*
          Sin errores por campo —un correo repetido, un nombre que ya existe— no hay
          dónde pegarlos. Antes solo se llamaba a `avisos.desdeError`, que pinta una
          pastilla en la esquina: se quedaba abierta mientras el formulario, a dos
          pasos de donde está la pastilla, seguía impávido. Ahora el motivo se escribe
          arriba del formulario, dentro del diálogo, que es donde se está mirando.
        */
        const mensaje = fallo instanceof Error ? fallo.message : 'No se pudo crear la cuenta.'
        setErrorGeneral(mensaje)
        avisos.desdeError(fallo)
      }
    } finally {
      setGuardando(false)
    }
  }

  const cambiarActivo = async () => {
    if (!cambiandoActivo) return
    setGuardando(true)
    try {
      if (cambiandoActivo.activar) {
        // Reactivar es un `PATCH` con `activo`. No hay endpoint aparte: el de
        // desactivar es un `POST` que solo sabe apagar, y usar el `PATCH` para
        // ambos deja un solo camino y una sola comprobación de permisos.
        await api.editar(`/usuarios/${cambiandoActivo.usuario.id}`, { activo: true })
      } else {
        await api.crear(`/usuarios/${cambiandoActivo.usuario.id}/desactivar`)
      }
      avisos.exito(
        cambiandoActivo.activar ? 'Cuenta reactivada' : 'Cuenta desactivada',
        cambiandoActivo.activar
          ? `${cambiandoActivo.usuario.nombre} vuelve a poder entrar.`
          : `${cambiandoActivo.usuario.nombre} no podrá entrar. Su historial y sus equipos no se tocan.`,
      )
      setCambiandoActivo(null)
      setSeleccionado(null)
      await usuarios.refetch()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  /* Hay filtros puesta: se puede volver atrás con un clic. */
  const hayFiltros = Boolean(texto.trim() || rol || zonaId || oficinaId)
  const quitarFiltros = () => {
    setTexto('')
    setRol('')
    setZonaId('')
    setOficinaId('')
    setPagina(1)
  }

  return (
    <>
      <PageHeader
        titulo="Usuarios"
        descripcion="Quiénes tienen cuenta en el sistema y a qué rol pertenecen."
        acciones={
          sesion.puede('usuarios.editar') ? (
            <Button variante="destacado" icono={<Plus size={16} aria-hidden="true" />} onClick={() => {
            setCreando(true)
            setErrores({})
            setErrorGeneral(null)
          }}>
              Nuevo usuario
            </Button>
          ) : null
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={verInactivas}
            onChange={(evento) => cambiarVisibilidadInactivas(evento.target.checked)}
          />
          Mostrar cuentas desactivadas
        </label>
        <span className="text-sm text-muted-foreground">
          {numero(usuarios.data?.total ?? 0)} {usuarios.data?.total === 1 ? 'cuenta' : 'cuentas'}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SearchInput
          etiqueta="Buscar personas"
          bloqueado={Boolean(seleccionado) || creando}
          valor={texto}
          alCambiar={(valor) => {
            setTexto(valor)
            setPagina(1)
          }}
          placeholder="Escribe para filtrar…"
        />
        <Select
          etiqueta="Rol"
          value={rol}
          onChange={(evento) => {
            setRol(evento.target.value)
            setPagina(1)
          }}
          placeholder="Todos"
          opciones={ROLES}
        />
        <Select
          etiqueta="Zona"
          value={zonaId}
          onChange={(evento) => {
            setZonaId(evento.target.value)
            // La oficina se suelta al cambiar de zona: si no, se queda la anterior y
            // el filtro acaba pidiendo dos zonas a la vez.
            setOficinaId('')
            setPagina(1)
          }}
          placeholder="Todas"
          opciones={(zonas.data?.items ?? []).map((zona) => ({ valor: zona.id, etiqueta: zona.nombre }))}
        />
        <Select
          etiqueta="Oficina"
          value={oficinaId}
          onChange={(evento) => {
            setOficinaId(evento.target.value)
            setPagina(1)
          }}
          placeholder={zonaElegida ? `Todas de ${zonaElegida.nombre}` : 'Todas'}
          opciones={oficinasDeLaZona.map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
        />
      </div>

      {/* La combinación imposible ya no se puede marcar, pero si llegara por la URL
          o por un «atrás» del navegador, se explica en vez de salir en blanco. */}
      {combinacionImposible ? (
        <Nota tono="aviso" titulo="Esa oficina no pertenece a la zona elegida">
          <p>
            {zonaElegida?.nombre} y {oficinaElegida?.nombre} no van juntas. Cambia una de las dos
            para ver gente.
          </p>
        </Nota>
      ) : null}

      {usuarios.isError ? (
        <ErrorState
          mensaje="No pudimos cargar el directorio."
          detalle={usuarios.error instanceof Error ? usuarios.error.message : undefined}
          alReintentar={() => void usuarios.refetch()}
        />
      ) : (usuarios.data?.items.length ?? 0) === 0 && !usuarios.isLoading ? (
        <EmptyState
          icono={<Users size={20} aria-hidden="true" />}
          titulo={
            combinacionImposible
              ? 'Esa combinación de zona y oficina no tiene cuentas'
              : texto.trim() || rol || zonaId || oficinaId
                ? 'No hay personas con estos filtros'
                : 'Todavía no hay ninguna cuenta'
          }
          descripcion={
            hayFiltros
              ? 'Prueba con otra palabra o quita los filtros.'
              : 'Crea la primera con «Nuevo usuario».'
          }
          accion={
            /*
              Con filtros puestos y cero resultados no había forma de volver: había que
              vaciar los cuatro a mano. Es el caso de buscar el correo de alguien que
              todavía no tiene cuenta —la razón más normal para buscar y no encontrar.
            */
            hayFiltros ? (
              <Button variante="secundario" onClick={quitarFiltros}>
                Quitar los filtros
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <DataTable
            columnas={columnas}
            datos={usuarios.data?.items ?? []}
            claveFila={(fila) => fila.id}
            cargando={usuarios.isLoading}
            columnasConfigurables
            alPulsarFila={(fila) => { setMostrarPassword(false); setSeleccionado(fila.id) }}
            etiquetaVacia="No hay personas con estos filtros."
            tarjeta={(usuario) => (
              <>
                <div className="flex items-center gap-2">
                  <Avatar nombre={usuario.nombre} tamano="sm" />
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{usuario.nombre}</p>
                    <p className="truncate text-sm text-muted-foreground">{usuario.email}</p>
                  </div>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  {etiquetaRol(usuario.rol)} · {usuario.oficina_nombre ?? 'Sin oficina'}
                </p>
                <div className="mt-2 flex items-center gap-1.5">
                  <EtiquetaEstadoActivo activo={usuario.activo} />
                  <span className="text-2xs text-muted-foreground">
                    Ayuda IA: {usuario.recomendaciones_ia ? 'activada' : 'desactivada'}
                  </span>
                </div>
              </>
            )}
          />
          <Paginacion
            pagina={usuarios.data?.pagina ?? 1}
            totalPaginas={usuarios.data?.total_paginas ?? 1}
            total={usuarios.data?.total ?? 0}
            porPagina={25}
            alCambiar={setPagina}
          />
        </>
      )}

      <DialogModal abierto={Boolean(seleccionado)} alCerrar={() => setSeleccionado(null)} titulo="Perfil del usuario" tamano="md"
        pie={detalle.data ? (
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {sesion.puede('usuarios.editar') && (detalle.data.rol !== 'administrador' || sesion.esAdmin) ? (
                <Button variante="secundario" icono={<KeyRound size={16} />} onClick={() => {
                  setMostrarPassword(!mostrarPassword)
                  requestAnimationFrame(() => passwordRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
                }}>Restablecer contraseña</Button>
              ) : null}
              {sesion.esAdmin && detalle.data.id !== sesion.usuario?.id ? (
                <Button variante="destructivo" onClick={() => setCambiandoActivo({
                  usuario: { id: detalle.data!.id, nombre: detalle.data!.nombre } as UsuarioResumen,
                  activar: detalle.data!.activo === false,
                })}>{detalle.data.activo === false ? 'Reactivar cuenta' : 'Desactivar cuenta'}</Button>
              ) : null}
            </div>
            <Button asChild variante="primario" icono={<ArrowUpRight size={16} />}>
              <Link to={`/panel/usuarios/${detalle.data.id}`}><ArrowUpRight size={16} aria-hidden="true" />Abrir perfil completo</Link>
            </Button>
          </div>
        ) : undefined}>
        {detalle.isPending ? (
          <p className="text-sm text-muted-foreground">Cargando perfil…</p>
        ) : detalle.isError ? (
          <ErrorState mensaje="No pudimos cargar el perfil." detalle={detalle.error.message} alReintentar={() => void detalle.refetch()} />
        ) : detalle.data ? (
          <CuerpoPerfilUsuario
            usuario={detalle.data}
            acciones={
              <section
                aria-label="Acciones de la cuenta"
                className="flex flex-col gap-3 rounded-[var(--radius-panel)] border border-border bg-surface-2/70 p-3"
              >
                <p className="text-2xs font-semibold uppercase tracking-wide text-muted-foreground">Cuenta</p>
                <ControlFoto
                  usuarioId={detalle.data.id}
                  nombre={detalle.data.nombre}
                  puedeEditar={sesion.puede('usuarios.editar') && (detalle.data.rol !== 'administrador' || sesion.esAdmin)}
                  alCambiar={(tiene) => {
                    /*
                      La foto vive en un caché de módulo aparte del de React Query,
                      así que hay que olvidarla a mano o seguiría viendo la anterior.
                      Se recarga el perfil para que `tiene_foto` vuelva a salir del
                      backend, y la lista para que la columna de la persona se entere.
                    */
                    void detalle.refetch()
                    void usuarios.refetch()
                    void invalidar.invalidateQueries({ queryKey: ['equipo-ti'] })
                    if (tiene) avisos.exito('Foto actualizada', 'Ya se ve en su avatar.')
                  }}
                />
                {sesion.puede('usuarios.editar') && (detalle.data.rol !== 'administrador' || sesion.esAdmin) ? (
                  <>
                    <details ref={passwordRef} open={mostrarPassword} onToggle={(evento) => setMostrarPassword(evento.currentTarget.open)} className="group rounded-xl border border-border bg-surface p-3">
                      <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-primary-strong focus-visible:outline-2 focus-visible:outline-ring">
                        <KeyRound size={17} aria-hidden="true" />Restablecer contraseña
                        <ChevronDown size={16} aria-hidden="true" className="ml-auto transition-transform group-open:rotate-180" />
                      </summary>
                      <div className="mt-4"><RestablecerPassword key={detalle.data.id} usuarioId={detalle.data.id} nombre={detalle.data.nombre} /></div>
                    </details>
                  </>
                ) : null}
              </section>
            }
          />
        ) : null}
      </DialogModal>

      <ConfirmDialog
        abierto={Boolean(cambiandoActivo)}
        alCerrar={() => setCambiandoActivo(null)}
        alConfirmar={() => void cambiarActivo()}
        titulo={cambiandoActivo?.activar ? 'Reactivar cuenta' : 'Desactivar cuenta'}
        mensaje={
          cambiandoActivo
            ? `«${cambiandoActivo.usuario.nombre}» ${
                cambiandoActivo.activar
                  ? 'volverá a poder entrar al sistema.'
                  : 'no podrá entrar al sistema. Su historial, sus tickets y los equipos que tiene asignados no se tocan, y aquí seguirá apareciendo marcada como desactivada.'
              }`
            : ''
        }
        textoConfirmar={cambiandoActivo?.activar ? 'Reactivar' : 'Desactivar'}
        cargando={guardando}
        peligro={!cambiandoActivo?.activar}
      />

      <DialogModal
        abierto={creando}
        alCerrar={() => { if (!guardando) { setCreando(false); setPassword(''); setConfirmacionPassword('') } }}
        titulo="Nuevo usuario"
        descripcion="La cuenta queda activa desde el momento de crearla."
        tamano="lg"
        pie={
          <>
            <Button disabled={guardando} onClick={() => { setCreando(false); setPassword(''); setConfirmacionPassword('') }}>Cancelar</Button>
            <Button
              type="submit"
              form="crear-usuario"
              variante="primario"
              cargando={guardando}
              disabled={nombre.trim().length < 3 || !email.trim() || password.length < 8 || password !== confirmacionPassword}
            >
              Crear usuario
            </Button>
          </>
        }
      >
        {/*
          Dos columnas. Con ocho campos en una sola el cuerpo se desplazaba y el
          último —la oficina— quedaba cortado detrás del pie de botones; al poner
          una explicación debajo de cada campo, todavía peor. En dos columnas entra
          entero y además se lee por parejas: lo que identifica arriba, lo que sitúa
          abajo.

          El motivo del rechazo va aquí dentro y no solo como aviso en la esquina: con
          el formulario abierto e impávido delante, la única pista a dos pasos no
          guiaba.
        */}
        <form id="crear-usuario" className="flex flex-col gap-4" autoComplete="off" onSubmit={(evento) => { evento.preventDefault(); void crear() }}>
          <fieldset disabled={guardando} className="flex min-w-0 flex-col gap-4">
          {errorGeneral ? <Nota tono="peligro" titulo="No se pudo crear la cuenta">{errorGeneral}</Nota> : null}
          <div className="flex min-w-0 items-center gap-3 rounded-xl border border-info-borde bg-info-soft/40 p-4">
            <Avatar nombre={nombre.trim() || 'Nueva cuenta'} tamano="md" />
            <div className="min-w-0 flex-1"><p className="truncate font-bold">{nombre.trim() || 'Nueva cuenta'}</p><p className="truncate text-sm text-muted-foreground">{email.trim() || 'Completa los datos de acceso'}</p></div>
            <span className="rounded-full border border-info-borde bg-surface px-2 py-1 text-2xs font-semibold text-info-strong">{etiquetaRol(rolNuevo)}</span>
          </div>
          <section className="rounded-xl border border-border p-4">
          <h3 className="mb-4 flex items-center gap-2 font-semibold"><Users size={18} className="text-info-strong" />Datos personales</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              etiqueta="Nombre completo"
              requerido
              minLength={3}
              maxLength={160}
              value={nombre}
              error={errores.nombre}
              onChange={(evento) => setNombre(evento.target.value)}
              ayuda="Así aparecerá en la lista y en los tickets que reporte."
            />
            <Input
              etiqueta="Correo institucional"
              type="email"
              requerido
              name="usuario-nuevo-correo"
              autoComplete="off"
              value={email}
              error={errores.email}
              onChange={(evento) => setEmail(evento.target.value)}
              ayuda="Correo que usará para iniciar sesión."
            />
            <Input
              etiqueta="Teléfono"
              type="tel"
              value={telefono}
              error={errores.telefono}
              onChange={(evento) => setTelefono(evento.target.value)}
              ayuda="Opcional."
            />
            <Input etiqueta="Anexo" value={anexo} maxLength={40} error={errores.anexo}
              onChange={(evento) => setAnexo(evento.target.value)} ayuda="Número interno de la oficina, si tiene uno." />
            <Input
              etiqueta="Cargo o puesto"
              value={cargo}
              error={errores.cargo}
              onChange={(evento) => setCargo(evento.target.value)}
              ayuda="Por ejemplo: Secretaria o Jefe de soporte."
            />
          </div>
          </section>
          <section className="rounded-xl border border-border bg-surface-2/30 p-4">
          <h3 className="mb-4 flex items-center gap-2 font-semibold"><KeyRound size={18} className="text-success-strong" />Acceso a la cuenta</h3>
          <div className="grid gap-4 sm:grid-cols-2">
          <CampoPassword
            etiqueta="Contraseña"
            requerido
            minLength={8}
            name="usuario-nuevo-password"
            autoComplete="new-password"
            value={password}
            error={errores.password}
            onChange={(evento) => setPassword(evento.target.value)}
            ayuda="Mínimo 8 caracteres."
          />
          <CampoPassword etiqueta="Confirmar contraseña" name="usuario-nuevo-confirmacion" requerido minLength={8}
            value={confirmacionPassword} onChange={(evento) => setConfirmacionPassword(evento.target.value)}
            error={confirmacionPassword && password !== confirmacionPassword ? 'Las contraseñas no coinciden.' : undefined} />
          </div></section>
          <section className="rounded-xl border border-border p-4">
          <h3 className="mb-4 flex items-center gap-2 font-semibold"><Building2 size={18} className="text-info-strong" />Rol y ubicación</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Select
              etiqueta="Rol"
              value={rolNuevo}
              error={errores.rol}
              onChange={(evento) => setRolNuevo(evento.target.value)}
              opciones={ROLES.filter((opcion) => sesion.usuario?.rol === 'administrador' || opcion.valor !== 'administrador')}
            />
            <Select
              etiqueta="Zona"
              value={zonaNueva}
              error={errores.zona_id}
              onChange={(evento) => {
                setZonaNueva(evento.target.value)
                setOficinaNueva('')
              }}
              placeholder="Sin zona asignada"
              opciones={(zonas.data?.items ?? []).map((zona) => ({ valor: zona.id, etiqueta: zona.nombre }))}
            />
            <Select
              etiqueta="Oficina del usuario"
              value={oficinaNueva}
              error={errores.oficina_id}
              onChange={(evento) => setOficinaNueva(evento.target.value)}
              placeholder="Sin oficina asignada"
              opciones={(oficinas.data?.items ?? [])
                .filter((oficina) => !zonaNueva || oficina.zona_id === zonaNueva)
                .map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
              ayuda="La zona se toma de la oficina elegida."
            />
          </div>
          </section>
          </fieldset>
        </form>
      </DialogModal>
    </>
  )
}

/**
 * Avatar de una fila del listado, con la foto si la tiene.
 *
 * Va en su propio componente porque es un gancho: `useFotoUsuario` no se puede
 * llamar dentro de la función de la celda, que React llama como texto.
 */
function AvatarConFoto({ usuario }: { usuario: UsuarioResumen }) {
  const foto = useFotoUsuario(usuario.id, usuario.tiene_foto)
  return <Avatar nombre={usuario.nombre} tamano="sm" foto={foto} />
}
