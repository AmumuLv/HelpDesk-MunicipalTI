/**
 * Zonas y oficinas: la estructura de la institución.
 *
 * Las zonas contienen oficinas y cada una tiene sus contadores reales. La pantalla
 * sirve para crear, renombrar y activar o desactivar, no para mostrar un árbol bonito
 * que nadie puede tocar.
 *
 * Tres cosas que se corrigieron aquí, todas por lo mismo —**desactivar era una puerta
 * de un solo sentido**—:
 *
 * 1. **Desactivado se ve, y se puede volver a activar.** El backend servía solo lo
 *    activo (`solo_activas=True` por defecto), así que al desactivar una oficina
 *    desaparecía de la pantalla sin dejar rastro y **no había forma de recuperarla
 *    desde aquí**: había que entrar a la base de datos. Ahora la pantalla pide las
 *    inactivas también, las marca y ofrece reactivarlas. La puerta tiene que volver
 *    atrás, o no es una puerta: es una trampa.
 *
 * 2. **Desactivar avisa de lo que se lleva.** El mensaje decía «los registros
 *    históricos se conservarán», que era la mitad de la verdad: también desaparecen
 *    de los desplegables de zona, de oficina y de responsable en **todo** el
 *    sistema, y con ellos los equipos sin responsable asignado. Eso es justo lo que
 *    hay que saber antes de pulsar.
 *
 * 3. **Los botones por fila se fueron a un menú.** Renombrar y Desactivaraparecían
 *    en cada una de las 59 oficinas: 118 botones para tres acciones. Ahora hay un
 *    menú por fila, como en Inventario y en el resto de la aplicación.
 */

import { Building2, Check, EyeOff, MoreHorizontal, Network, Pencil, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/cliente'
import { cn } from '../../lib/cn'
import { ZonaBadge } from '../../componentes/dominio/ZonaBadge'
import { useOficinas, useZonas } from '../../api/hooks'
import type { ItemOficina } from '../../api/tipos'
import { Button } from '../../componentes/base/Button'
import { Input, SearchInput } from '../../componentes/base/Campo'
import { ConfirmDialog, DialogModal, PopoverSimple } from '../../componentes/base/Sobreposiciones'
import { EmptyState, ErrorState, Nota, PageHeader, Panel, PantallaFormulario, SkeletonPanel } from '../../componentes/base/Estructura'
import { EnlaceOficina } from '../../componentes/dominio/EnlaceOficina'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { numero, plural } from '../../dominio/formato'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'

type Elemento = { id: string; nombre: string }
type AEditar = Elemento & { tipo: 'zona' | 'oficina'; activa: boolean }

/**
 * Lo que hay detrás de una zona u oficina y si se puede borrar.
 *
 * Viene de `GET /{zonas|oficinas}/{id}/borrado`, que usa la misma función que el
 * borrado: el aviso y la razón del rechazo no pueden decir cosas distintas.
 */
type BloqueosBorrado = {
  nombre: string
  zona_nombre?: string | null
  oficinas: number
  personas: number
  equipos: number
  puede_eliminar: boolean
  motivo: string | null
}

/** Oficinas por página en cada zona. */
const OFICINAS_POR_ZONA = 10

/*
  Si mostrar los desactivados está marcado.

  Se guarda porque es una decisión de quien mira, no un estado de la pantalla: si al
  volver a entrar ya no aparecían, había que volver a marcarlos. Es un preferences de
  lectura —no un filtro— y por eso se guarda en vez de vivir en la URL: nadie va a
  pegar un enlace con «y enséñame también lo que está apagado».

  Se lee **fuera** de `useState` a propósito: si no, el valor guardado se aplicaría
  después del primer dibujado y la pantalla aparecería un instante con los
  desactivados y luego los quitaría, que es un parpadeo que parece un fallo.

  Como está en `localStorage`, puede venir corrupto —editado a mano, de otra versión—
  y eso no puede tumbar la pantalla: lo que no sea «false» se trata como marcado.
*/
const CLAVE_PREFERENCIA = 'org.ver-desactivados'
const mostrarDesactivadosGuardado = (() => {
  try {
    return window.localStorage.getItem(CLAVE_PREFERENCIA) !== 'false'
  } catch {
    // Modo privado o almacenamiento lleno: la preferencia no se guarda, pero la
    // pantalla sigue funcionando.
    return true
  }
})()

function textoBusqueda(valor: string) {
  return valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()
}

export function Organizacion() {
  const sesion = useSesion()
  const avisos = useAvisos()
  /* Se piden también las inactivas. Con `solo_activas` —el valor por defecto de la
     API— una oficina desactivada desaparecía de esta pantalla para siempre. */
  const zonas = useZonas({ solo_activas: false })
  const oficinas = useOficinas({ solo_activas: false })

  const [creandoZona, setCreandoZona] = useState(false)
  const [nombreZona, setNombreZona] = useState('')
  const [creandoOficina, setCreandoOficina] = useState<string | null>(null)
  const [nombreOficina, setNombreOficina] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [edicion, setEdicion] = useState<AEditar | null>(null)
  const [nombreEditado, setNombreEditado] = useState('')
  const [cambiando, setCambiando] = useState<(AEditar & { activar: boolean }) | null>(null)
  /** El que está a punto de borrarse. Es un diálogo aparte del de desactivar: son
      cosas muy distintas y una es irreversible. */
  const [borrando, setBorrando] = useState<AEditar | null>(null)
  /* Buscar entre las 59 oficinas y Renombrar y Desactivar salen de la vista de un
     vistazo. Sin buscador, encontrar una oficina era recorrer las cinco zonas. */
  const [busqueda, setBusqueda] = useState('')
  const [verInactivas, setVerInactivas] = useState(mostrarDesactivadosGuardado)
  /*
    Página de oficinas de cada zona, en un diccionario.

    Antes era un único botón «Ver las N más» por zona, y desplegarla era todo o nada:
    PALACIO tenía 27 oficinas y pasaban de golpe de 8 a 27, dejando la página descuadrada
    y obligando a volver arriba. Con páginas se avanza de diez en diez, se sabe cuántas
    quedan y se vuelve sin buscar.

    Un estado por zona y no uno compartido: si no, al paginar PALACIO cambiaba la página
    de MERCADO, que está al lado. El número de página se acota a las páginas que tiene
    esa zona, para que al buscar o al ocultar las desactivadas no se quede en una
    página que ya no existe.
  */
  const [paginasPorZona, setPaginasPorZona] = useState<Record<string, number>>({})

  useEffect(() => {
    document.title = 'Zonas y oficinas · Mesa de Ayuda TI'
  }, [])

  const puedeEditar = sesion.puede('org.editar')

  /* Cada cambio se guarda en el momento. */
  const cambiarVisibilidadInactivas = (valor: boolean) => {
    setVerInactivas(valor)
    try {
      window.localStorage.setItem(CLAVE_PREFERENCIA, valor ? 'true' : 'false')
    } catch {
      // Si no se puede guardar, el cambio se aplica igual en esta sesión.
    }
  }

  const crearZona = async () => {
    if (!nombreZona.trim()) return
    setGuardando(true)
    try {
      await api.crear('/zonas', { nombre: nombreZona.trim() })
      avisos.exito('Zona creada', nombreZona.trim())
      setCreandoZona(false)
      setNombreZona('')
      await zonas.refetch()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  const crearOficina = async () => {
    if (!creandoOficina || !nombreOficina.trim()) return
    setGuardando(true)
    try {
      await api.crear('/oficinas', { nombre: nombreOficina.trim(), zona_id: creandoOficina })
      setPaginasPorZona(anteriores => ({ ...anteriores, [creandoOficina]: 1 }))
      avisos.exito('Oficina creada', nombreOficina.trim())
      setCreandoOficina(null)
      setNombreOficina('')
      await oficinas.refetch()
      await zonas.refetch()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  const guardarNombre = async () => {
    if (!edicion || !nombreEditado.trim()) return
    setGuardando(true)
    try {
      await api.editar(`/${edicion.tipo === 'zona' ? 'zonas' : 'oficinas'}/${edicion.id}`, { nombre: nombreEditado.trim() })
      avisos.exito('Nombre actualizado', nombreEditado.trim())
      setEdicion(null)
      await Promise.all([zonas.refetch(), oficinas.refetch()])
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  /*
    Activar o desactivar.

    Desactivar no borra nada: el histórico se conserva. Pero la oficina —o la zona—
    deja de ofrecerse en los desplegables de zona, de oficina y de responsable de
    **todo** el sistema, y sus equipos se quedan sin oficina a la que asignarse. Por
    eso el diálogo lo dice antes, con números delante, y por eso reactivar está a la
    misma altura que el menú de la fila.
  */
  const cambiarEstado = async () => {
    if (!cambiando) return
    setGuardando(true)
    try {
      await api.editar(
        `/${cambiando.tipo === 'zona' ? 'zonas' : 'oficinas'}/${cambiando.id}`,
        { activa: cambiando.activar },
      )
      avisos.exito(
        cambiando.activar ? 'Reactivado' : 'Desactivado',
        cambiando.activar
          ? `${cambiando.nombre} vuelve a ofrecerse en todo el sistema.`
          : `${cambiando.nombre} deja de ofrecerse, pero sigue aquí y se puede reactivar.`,
      )
      setCambiando(null)
      await Promise.all([zonas.refetch(), oficinas.refetch()])
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  /*
    Borrar para siempre.

    Desactivar es reversible y por eso es lo que se ofrece primero. Pero hay un caso
    en que no vale: una zona u oficina que se creó por error, o que ya no existe y
    estorba en el desplegable.

    El diálogo **pregunta al backend qué hay detrás** en vez de usar los contadores de
    la lista, y por dos razones: los contadores filtran los equipos dados de baja y el
    borrado no —el aviso podría decir «0 equipos» y el borrado responder «tiene 3»—,
    y porque el número que importa es el del bloqueo, no el de la fila.
  */
  const bloqueos = useQuery({
    queryKey: ['borrado', borrando?.tipo, borrando?.id],
    queryFn: () =>
      api.obtener<BloqueosBorrado>(
        `/${borrando?.tipo === 'zona' ? 'zonas' : 'oficinas'}/${borrando?.id}/borrado`,
      ),
    enabled: Boolean(borrando),
    retry: false,
  })

  const eliminar = async () => {
    if (!borrando) return
    setGuardando(true)
    try {
      await api.borrar(`/${borrando.tipo === 'zona' ? 'zonas' : 'oficinas'}/${borrando.id}`)
      avisos.exito('Eliminado', `${borrando.nombre} se borró. No se puede deshacer.`)
      setBorrando(null)
      setCambiando(null)
      await Promise.all([zonas.refetch(), oficinas.refetch()])
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  /*
    Las oficinas se calculan antes que las zonas: el filtro de zonas usa esa lista
    para saber si lo que se busca es el nombre de una oficina o el de una zona.
  */
  const listaOficinas = useMemo(() => {
    const todas = oficinas.data?.items ?? []
    return verInactivas ? todas : todas.filter((oficina) => oficina.activa)
  }, [oficinas.data?.items, verInactivas])

  const listaZonas = useMemo(() => {
    const todas = zonas.data?.items ?? []
    const filtradas = verInactivas ? todas : todas.filter((zona) => zona.activa)
    const termino = textoBusqueda(busqueda)
    if (!termino) return filtradas
    return filtradas.filter((zona) => {
      if (textoBusqueda(zona.nombre).includes(termino)) return true
      // Buscar por el nombre de una oficina encuentra la zona que la contiene: es lo
      // que se busca cuando se recuerda dónde está, no el nombre de la zona.
      return listaOficinas.some(
        (oficina) => oficina.zona_id === zona.id && textoBusqueda(oficina.nombre).includes(termino),
      )
    })
  }, [zonas.data?.items, listaOficinas, busqueda, verInactivas])

  const inactivasDe = (zonaId: string) => listaOficinas.filter((o) => o.zona_id === zonaId && !o.activa).length

  /*
    Página y recorte por zona.

    La página se acota a las que existen **en ese momento**: al buscar, o al dejar de
    mostrar las desactivadas, la zona puede tener menos oficinas y quedarse en una
    página que ya no existe — la 3 de 2 — y la lista saldría en blanco sin explicación.
    Con la página acotada, lo que ocurre es que vuelve a la última que existe.
  */
  const paginaDe = (zonaId: string, total: number) => {
    const paginas = Math.max(1, Math.ceil(total / OFICINAS_POR_ZONA))
    return Math.min(Math.max(1, paginasPorZona[zonaId] ?? 1), paginas)
  }
  const oficinasVisibles = (zonaId: string, oficinas: ItemOficina[]) => {
    const termino = textoBusqueda(busqueda)
    if (termino) {
      const zona = listaZonas.find((item) => item.id === zonaId)
      // Buscar una zona muestra sus oficinas; buscar una oficina solo las coincidencias.
      if (zona && textoBusqueda(zona.nombre).includes(termino)) return oficinas
      return oficinas.filter((oficina) => textoBusqueda(oficina.nombre).includes(termino))
    }
    const pagina = paginaDe(zonaId, oficinas.length)
    const desde = (pagina - 1) * OFICINAS_POR_ZONA
    return oficinas.slice(desde, desde + OFICINAS_POR_ZONA)
  }

  if (zonas.isError) {
    return (
      <ErrorState
        mensaje="No pudimos cargar la estructura."
        detalle={zonas.error instanceof Error ? zonas.error.message : undefined}
        alReintentar={() => void zonas.refetch()}
      />
    )
  }

  const todasZonas = zonas.data?.items ?? []
  const totalInactivas = todasZonas.filter((z) => !z.activa).length + listaOficinas.filter((o) => !o.activa).length

  return (
    <PantallaFormulario>
      <PageHeader
        titulo="Zonas y oficinas"
        descripcion="Cómo está organizada la institución. Cada equipo, persona y ticket cuelga de aquí."
        acciones={
          puedeEditar ? (
            <Button variante="destacado" icono={<Plus size={16} aria-hidden="true" />} onClick={() => setCreandoZona(true)}>
              Nueva zona
            </Button>
          ) : null
        }
      />

      {/* Con 59 oficinas en 5 zonas, buscar es la acción de cada día: para llegar a
          una oficina hay que recorrer las cinco listas a ojo. */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <SearchInput
            etiqueta="Buscar zona u oficina"
            valor={busqueda}
            alCambiar={setBusqueda}
            placeholder="Nombre de la zona o de la oficina"
            ayuda="Al buscar el nombre de una oficina, aparece la zona que la contiene."
          />
        </div>
        {totalInactivas > 0 ? (
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={verInactivas}
              onChange={(evento) => cambiarVisibilidadInactivas(evento.target.checked)}
              className="size-4 accent-primary"
            />
            <span>
              Mostrar {numero(totalInactivas)} desactivados
              {totalInactivas === 1 ? '' : 's'}
            </span>
          </label>
        ) : null}
      </div>

      {zonas.isLoading ? (
        <SkeletonPanel filas={5} />
      ) : listaZonas.length === 0 ? (
        <EmptyState
          icono={<Network size={20} aria-hidden="true" />}
          titulo={busqueda.trim() ? 'Nada coincide con esa búsqueda' : 'No hay zonas registradas'}
          descripcion={
            busqueda.trim()
              ? `Ninguna zona ni ninguna de sus oficinas se llama «${busqueda.trim()}».`
              : 'Una zona agrupa oficinas: por ejemplo, el complejo municipal o el mercado.'
          }
          accion={
            busqueda.trim() ? (
              <Button variante="secundario" onClick={() => setBusqueda('')}>
                Quitar la búsqueda
              </Button>
            ) : puedeEditar ? (
              <Button variante="primario" onClick={() => setCreandoZona(true)}>
                Crear la primera zona
              </Button>
            ) : null
          }
        />
      ) : (
        <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-2">
          {listaZonas.map((zona) => {
            const inactivasZona = inactivasDe(zona.id)
            const oficinasZona = listaOficinas.filter((oficina) => oficina.zona_id === zona.id)
            return (
              <Panel
                key={zona.id}
                titulo={<ZonaBadge id={zona.id} nombre={zona.nombre} />}
                descripcion={zona.descripcion ?? undefined}
                acciones={
                  puedeEditar ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {zona.activa ? (
                        <Button tamano="sm" icono={<Plus size={14} aria-hidden="true" />} onClick={() => setCreandoOficina(zona.id)}>
                          Agregar oficina
                        </Button>
                      ) : null}
                      <MenuZona
                        zona={{ id: zona.id, nombre: zona.nombre, tipo: 'zona', activa: zona.activa }}
                        zonasConInactivas={inactivasZona}
                        alRenombrar={() => {
                          setEdicion({ id: zona.id, nombre: zona.nombre, tipo: 'zona', activa: zona.activa })
                          setNombreEditado(zona.nombre)
                        }}
                        alCambiarActiva={(activar) =>
                          setCambiando({ id: zona.id, nombre: zona.nombre, tipo: 'zona', activa: zona.activa, activar })
                        }
                        alEliminar={() =>
                          setBorrando({ id: zona.id, nombre: zona.nombre, tipo: 'zona', activa: zona.activa })
                        }
                      />
                    </div>
                  ) : null
                }
              >
                {!zona.activa ? (
                  <Nota tono="aviso" titulo="Zona desactivada">
                    <p>
                      No se ofrece en los desplegables de zona, de oficina ni de responsable.{' '}
                      {(zona.total_oficinas ?? 0) === 0
                        ? 'No tiene oficinas.'
                        : (() => {
                            /*
                              El verbo también tiene que concordar: con una sola
                              oficina, «Sus 1 oficinas siguen existiendo» no solo
                              tenía el plural mal, sino el verbo.
                            */
                            const oficinas = zona.total_oficinas ?? 0
                            const verbo = oficinas === 1 ? 'sigue existiendo' : 'siguen existiendo'
                            const extra =
                              inactivasZona > 0
                                ? `, y de esas ${plural(inactivasZona, 'oficina')} ${inactivasZona === 1 ? 'también está' : 'también están'} desactivada${inactivasZona === 1 ? '' : 's'}`
                                : ''
                            return `Su ${plural(oficinas, 'oficina')} ${verbo}${extra}.`
                          })()}
                    </p>
                  </Nota>
                ) : null}

                <dl className="mt-2 grid grid-cols-3 gap-2 text-center">
                  <Contador etiqueta="Oficinas" valor={zona.total_oficinas} />
                  <Contador etiqueta="Personas" valor={zona.total_usuarios} />
                  <Contador etiqueta="Equipos" valor={zona.total_equipos} />
                </dl>

                {oficinasZona.length === 0 ? (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-panel)] border border-dashed border-border p-3">
                    <p className="text-sm text-muted-foreground">Esta zona todavía no tiene oficinas.</p>
                    {puedeEditar && zona.activa ? (
                      <Button tamano="sm" onClick={() => setCreandoOficina(zona.id)}>
                        Agregar la primera
                      </Button>
                    ) : null}
                  </div>
                ) : (
                  <>
                    {/*
                      Una zona con 27 oficinas —PALACIO— hacía la página de cinco
                      pantallas, y el 80 % de lo que se veía eran oficinas de una zona
                      que no se estaba tocando. Van por páginas de diez: se avanza de
                      diez en diez, se sabe cuántas quedan y se vuelve sin buscar.
                    */}
                    <ul className="mt-3 divide-y divide-border">
                      {oficinasVisibles(zona.id, oficinasZona).map((oficina) => (
                      <li key={oficina.id} className="flex flex-wrap items-center gap-2 py-3 transition-colors hover:bg-muted/40">
                        <Building2
                          size={16}
                          className={oficina.activa ? 'shrink-0 text-info-strong' : 'shrink-0 text-muted-foreground/50'}
                          aria-hidden="true"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="flex min-w-0 items-center gap-2">
                            <EnlaceOficina
                              id={oficina.id}
                              nombre={oficina.nombre}
                              zonaId={oficina.zona_id}
                              colorIndice={zona.color_indice}
                            />
                            {!oficina.activa ? (
                              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide text-muted-foreground">
                                Desactivada
                              </span>
                            ) : null}
                          </span>
                          {!oficina.activa ? (
                            <span className="text-2xs text-muted-foreground">
                              No se ofrece al asignar responsables ni al elegir zona.
                            </span>
                          ) : null}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {plural(oficina.total_usuarios, 'persona')} · {plural(oficina.total_equipos, 'equipo')}
                        </span>
                        {puedeEditar ? (
                          <MenuOficina
                            oficina={{ id: oficina.id, nombre: oficina.nombre, tipo: 'oficina', activa: oficina.activa }}
                            alRenombrar={() => {
                              setEdicion({
                                id: oficina.id,
                                nombre: oficina.nombre,
                                tipo: 'oficina',
                                activa: oficina.activa,
                              })
                              setNombreEditado(oficina.nombre)
                            }}
                            alCambiarActiva={(activar) =>
                              setCambiando({
                                id: oficina.id,
                                nombre: oficina.nombre,
                                tipo: 'oficina',
                                activa: oficina.activa,
                                activar,
                              })
                            }
                            alEliminar={() =>
                              setBorrando({
                                id: oficina.id,
                                nombre: oficina.nombre,
                                tipo: 'oficina',
                                activa: oficina.activa,
                              })
                            }
                          />
                        ) : null}
                      </li>
                    ))}
                    </ul>
                    {oficinasZona.length > OFICINAS_POR_ZONA && !busqueda.trim() ? (
                      <div className="mt-2 border-t border-border pt-2">
                        <Paginacion
                          pagina={paginaDe(zona.id, oficinasZona.length)}
                          totalPaginas={Math.ceil(oficinasZona.length / OFICINAS_POR_ZONA)}
                          total={oficinasZona.length}
                          porPagina={OFICINAS_POR_ZONA}
                          alCambiar={(siguiente) => setPaginasPorZona((actuales) => ({ ...actuales, [zona.id]: siguiente }))}
                        />
                      </div>
                    ) : null}
                  </>
                )}
              </Panel>
            )
          })}
        </div>
      )}

      <DialogModal
        abierto={creandoZona}
        alCerrar={() => setCreandoZona(false)}
        titulo="Nueva zona"
        descripcion="Una zona agrupa oficinas. El nombre es el de la hoja en los archivos de Excel."
        tamano="sm"
        pie={
          <>
            <Button onClick={() => setCreandoZona(false)}>Cancelar</Button>
            <Button variante="primario" cargando={guardando} disabled={!nombreZona.trim()} onClick={() => void crearZona()}>
              Crear zona
            </Button>
          </>
        }
      >
        <Input etiqueta="Nombre de la zona" value={nombreZona} onChange={(evento) => setNombreZona(evento.target.value)} />
      </DialogModal>

      <DialogModal
        abierto={Boolean(creandoOficina)}
        alCerrar={() => setCreandoOficina(null)}
        titulo="Nueva oficina"
        descripcion={`En la zona «${todasZonas.find((zona) => zona.id === creandoOficina)?.nombre ?? ''}»`}
        tamano="sm"
        pie={
          <>
            <Button onClick={() => setCreandoOficina(null)}>Cancelar</Button>
            <Button variante="primario" cargando={guardando} disabled={!nombreOficina.trim()} onClick={() => void crearOficina()}>
              Crear oficina
            </Button>
          </>
        }
      >
        <Input
          etiqueta="Nombre de la oficina"
          value={nombreOficina}
          onChange={(evento) => setNombreOficina(evento.target.value)}
          placeholder="Ej.: OFICINA DE PLANIFICACIÓN"
          ayuda="Es la columna ÁREA de los archivos de Excel. Pon el mismo nombre que uses allí."
        />
      </DialogModal>

      <DialogModal
        abierto={Boolean(edicion)}
        alCerrar={() => setEdicion(null)}
        titulo={`Renombrar ${edicion?.tipo === 'zona' ? 'zona' : 'oficina'}`}
        descripcion={
          edicion?.tipo === 'zona'
            ? 'El nombre nuevo también reemplaza al que aparece junto a sus oficinas, personas y tickets.'
            : undefined
        }
        tamano="sm"
        pie={
          <>
            <Button onClick={() => setEdicion(null)}>Cancelar</Button>
            <Button variante="primario" cargando={guardando} disabled={!nombreEditado.trim()} onClick={() => void guardarNombre()}>
              Guardar
            </Button>
          </>
        }
      >
        <Input etiqueta="Nombre" value={nombreEditado} onChange={(evento) => setNombreEditado(evento.target.value)} maxLength={120} />
      </DialogModal>

      {/*
        El diálogo de desactivar. Antes decía «los registros históricos se conservarán»
        y seacababa: eso era la mitad. Lo que pasa es que el elemento **deja de
        ofrecerse** en los desplegables de todo el sistema y sus equipos se quedan sin
        oficina o zona a la que asignarse. Es reversible —por eso no lo llama
        «eliminar»— pero hay que saberlo antes de confirmar.
      */}
      <DialogModal
        abierto={Boolean(cambiando && !cambiando.activar)}
        alCerrar={() => setCambiando(null)}
        titulo="Desactivar"
        descripcion="No se borra nada. Se puede volver a activar desde aquí mismo."
        pie={
          <>
            <Button onClick={() => setCambiando(null)}>Cancelar</Button>
            <Button variante="destructivo" cargando={guardando} onClick={() => void cambiarEstado()}>
              Desactivar
            </Button>
          </>
        }
      >
        {cambiando ? (
          <ul className="flex flex-col gap-2 text-sm">
            <li>
              Se desactivará <strong>{cambiando.nombre}</strong>.
            </li>
            <li className="text-muted-foreground">
              Dejará de ofrecerse al elegir zona, oficina o responsable en <strong>todo</strong> el
              sistema. Sus equipos se quedan sin {cambiando.tipo === 'zona' ? 'zona' : 'oficina'} a la
              que asignarse.
            </li>
            <li className="text-muted-foreground">
              Los datos y el histórico se conservan, y aquí seguirá apareciendo marcada como
              desactivada, con la opción de volver a activarla.
            </li>
          </ul>
        ) : null}

        {/*
          Borrar no comparte diálogo con desactivar: uno es reversible y el otro no.
          Ahora «Eliminar» está en el menú de la fila, que es donde se busca.
        */}
      </DialogModal>

      {/*
          El diálogo de borrar, que **pregunta qué hay detrás** en vez de suponerlo.
          Los números salen del backend con la misma función que usa el borrado, así
          que el aviso y el rechazo no pueden discrepar.
        */}
      <DialogModal
        abierto={Boolean(borrando)}
        alCerrar={() => setBorrando(null)}
        titulo="Eliminar definitivamente"
        descripcion="No se puede deshacer."
        pie={
          <>
            <Button onClick={() => setBorrando(null)}>Cancelar</Button>
            <Button
              variante="destructivo"
              cargando={guardando}
              // Deshabilitado mientras no se sepa si se puede: un botón rojo que
              // rechaza la pulsación no explica nada; mejor no ofrecerlo.
              disabled={!bloqueos.data?.puede_eliminar || bloqueos.isLoading}
              onClick={() => void eliminar()}
            >
              Eliminar para siempre
            </Button>
          </>
        }
      >
        {borrando ? (
          bloqueos.isLoading ? (
            <p className="text-sm text-muted-foreground">Comprobando qué hay detrás…</p>
          ) : bloqueos.isError ? (
            <p className="text-sm text-destructive-strong">
              No se pudo comprobar qué tiene asociado. Ciérralo e inténtalo otra vez.
            </p>
          ) : bloqueos.data ? (
            <div className="flex flex-col gap-3 text-sm">
              <p>
                Se borrará <strong>{bloqueos.data.nombre}</strong> y no se podrá recuperar.
              </p>
              {/* Qué hay detrás, con los números del servidor. */}
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded border border-border bg-surface-2/60 p-3 sm:grid-cols-3">
                {borrando.tipo === 'zona' ? (
                  <DetalleBorrado etiqueta="Oficinas" valor={bloqueos.data.oficinas} />
                ) : null}
                <DetalleBorrado etiqueta="Personas" valor={bloqueos.data.personas} />
                <DetalleBorrado etiqueta="Equipos" valor={bloqueos.data.equipos} />
              </dl>
              {bloqueos.data.puede_eliminar ? (
                <p className="text-muted-foreground">
                  No tiene nada asociado, así que se puede borrar. Los equipos de otras zonas y
                  oficinas no se tocan.
                </p>
              ) : (
                <p className="font-medium text-destructive-strong">
                  No se puede borrar todavía: {bloqueos.data.motivo}.
                </p>
              )}
            </div>
          ) : null
        ) : null}
      </DialogModal>

      <ConfirmDialog
        abierto={Boolean(cambiando && cambiando.activar)}
        alCerrar={() => setCambiando(null)}
        alConfirmar={() => void cambiarEstado()}
        titulo="Reactivar"
        mensaje={
          cambiando
            ? `«${cambiando.nombre}» volverá a ofrecerse al elegir zona, oficina o responsable.`
            : ''
        }
        textoConfirmar="Reactivar"
        cargando={guardando}
      />
    </PantallaFormulario>
  )
}

/** Menú de acciones de una zona: renombrar, activar o desactivar, y eliminar. */
function MenuZona({
  zona,
  zonasConInactivas,
  alRenombrar,
  alCambiarActiva,
  alEliminar,
}: {
  zona: AEditar
  zonasConInactivas: number
  alRenombrar: () => void
  alCambiarActiva: (activar: boolean) => void
  alEliminar: () => void
}) {
  return (
    <PopoverSimple
      disparador={
        <Button
          tamano="sm"
          soloIcono
          variante="secundario"
          aria-label={`Acciones de la zona ${zona.nombre}`}
        >
          <MoreHorizontal size={18} />
        </Button>
      }
      ancho="w-56"
      contenido={
        <div className="-m-1.5 flex flex-col gap-0.5">
          <button type="button" onClick={alRenombrar} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted">
            <Pencil size={14} aria-hidden="true" />
            Renombrar
          </button>
          <button
            type="button"
            onClick={() => alCambiarActiva(!zona.activa)}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
          >
            {zona.activa ? <EyeOff size={14} aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}
            {zona.activa ? 'Desactivar' : 'Reactivar'}
          </button>
          {zona.activa && zonasConInactivas > 0 ? (
            <p className="border-t border-border px-2 pb-1 pt-1.5 text-2xs text-muted-foreground">
              {numero(zonasConInactivas)} de sus oficinas {zonasConInactivas === 1 ? 'está desactivada' : 'están desactivadas'}
            </p>
          ) : null}
          {/*
            Borrar va en el menú de la fila, no escondido dentro del diálogo de
            desactivar. Son dos puertas distintas —una reversible y otra no—, y al
            esconder la irreversible en dos clics dentro de la reversible, quien
            quiere quitar una zona creada por error tiene que desactivarla primero.
          */}
          <button
            type="button"
            onClick={alEliminar}
            className="flex w-full items-center gap-2 rounded-t-none border-t border-border px-2 pb-1.5 pt-2 text-left text-sm text-destructive-strong hover:bg-destructive-soft"
          >
            <Trash2 size={14} aria-hidden="true" />
            Eliminar
          </button>
        </div>
      }
    />
  )
}

/** Menú de acciones de una oficina: renombrar, activar o desactivar, y eliminar. */
function MenuOficina({
  oficina,
  alRenombrar,
  alCambiarActiva,
  alEliminar,
}: {
  oficina: AEditar
  alRenombrar: () => void
  alCambiarActiva: (activar: boolean) => void
  alEliminar: () => void
}) {
  return (
    <PopoverSimple
      disparador={
        <Button
          tamano="sm"
          soloIcono
          variante="fantasma"
          aria-label={`Acciones de la oficina ${oficina.nombre}`}
          onClick={(evento) => evento.stopPropagation()}
        >
          <MoreHorizontal size={18} />
        </Button>
      }
      ancho="w-48"
      contenido={
        <div className="-m-1.5 flex flex-col gap-0.5">
          <button type="button" onClick={alRenombrar} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted">
            <Pencil size={14} aria-hidden="true" />
            Renombrar
          </button>
          <button
            type="button"
            onClick={() => alCambiarActiva(!oficina.activa)}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
          >
            {oficina.activa ? <EyeOff size={14} aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}
            {oficina.activa ? 'Desactivar' : 'Reactivar'}
          </button>
          <button
            type="button"
            onClick={alEliminar}
            className="flex w-full items-center gap-2 rounded-t-none border-t border-border px-2 pb-1.5 pt-2 text-left text-sm text-destructive-strong hover:bg-destructive-soft"
          >
            <Trash2 size={14} aria-hidden="true" />
            Eliminar
          </button>
        </div>
      }
    />
  )
}

/** Una cifra del diálogo de borrar. El 0 se dice, no se esconde. */
function DetalleBorrado({ etiqueta, valor }: { etiqueta: string; valor: number }) {
  return (
    <div>
      <dt className="text-2xs text-muted-foreground">{etiqueta}</dt>
      <dd className={cn('text-lg font-bold', valor === 0 && 'text-muted-foreground')}>{numero(valor)}</dd>
    </div>
  )
}

function Contador({ etiqueta, valor }: { etiqueta: string; valor: number | null | undefined }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/60 px-2 py-3">
      <dt className="text-2xs text-muted-foreground">{etiqueta}</dt>
      <dd className="text-lg font-bold">{numero(valor ?? 0)}</dd>
    </div>
  )
}
