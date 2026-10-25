import { AvatarTecnico } from '../../componentes/dominio/AvatarTecnico'
import { ListaEquiposPerfil } from '../../componentes/dominio/ListaEquiposPerfil'
/**
 * Ficha de zona y de oficina.
 *
 * Rehecha tras recorrer las oficinas una por una. Lo que se corrigió y por qué:
 *
 * **El nombre repetido tres veces.** Salía en las migas, en el título y otra vez en la tarjeta
 * grande, con el nombre de la zona debajo dos veces. La tarjeta repite el título; se queda con los
 * números y el color de la zona, que es lo que aporta.
 *
 * **El estado del equipo era texto suelto.** «· OPERATIVO» con un punto medio delante, mientras
 * que en Inventario y en la ficha de equipo el estado es una insignia con su color y su icono. En
 * una lista de equipos eso es justo lo que se lee de un vistazo: ahora usa la misma insignia.
 *
 * **Los mensajes de vacío eran los mismos en tres sitios.** «No hay registros para mostrar» en
 * tickets, en tendencia y en incidencias. Que no haya tickets abiertos en una oficina es una buena
 * noticia y se lee como un fallo si el texto dice «no hay registros». Ahora cada uno dice el suyo.
 *
 * **No se podía answering «quién tiene equipos» sin cruzando dos paneles.** Las personas y los
 * equipos por responsable son dos listas separadas, y para saber quién tiene algo había que
 * mentalmente cruzarlas. Ahora cada persona dice cuántos equipos tiene, y el bloque de uso común
 * se separa del resto con su propia insignia: un equipo sin responsable no es un equipo de nadie,
 * es un equipo **de la oficina**, y son cosas distintas al de una persona.
 */

import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, MapPin, Monitor, User } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useTickets } from '../../api/hooks'
import { TicketsAtencion } from '../../componentes/dominio/TicketsAtencion'
import { Button } from '../../componentes/base/Button'
import {
  ContenidoTab,
  ErrorState,
  ListaTabs,
  PageHeader,
  Panel,
  PantallaFormulario,
  SkeletonPanel,
  Tab,
  TabsPanel,
} from '../../componentes/base/Estructura'
import { BarraProgreso } from '../../componentes/dominio/BarraProgreso'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { EnlaceOficina } from '../../componentes/dominio/EnlaceOficina'
import { TarjetaPerfil } from '../../componentes/dominio/TarjetaPerfil'
import { fechaCorta, numero, plural } from '../../dominio/formato'
import { useSesion } from '../../estado/Sesion'



/**
 * Equipos de uso común por página.
 *
 * Las oficinas grandes tienen decenas: GERENCIA DE ADMINISTRACIÓN TRIBUTARIA tiene
 * 27 y PALACIO LOGISTICA 25. En una sola lista son 27 filas idénticas de largo, y lo
 * que se busca —«cuáles son»— se lee en la primera pantalla. Es el mismo corte de 10
 * que usa Zonas y oficinas, con el mismo paginador.
 */
const EQUIPOS_POR_PAGINA = 10

type Equipo = {
  id: string
  nombre?: string
  tipo: string
  estado?: string
  responsable_id?: string | null
  responsable_nombre?: string | null
}
type Oficina = { id: string; nombre: string; total_equipos: number; total_usuarios: number }
type Comun = {
  id: string
  nombre: string
  descripcion?: string | null
  total_equipos: number
  total_usuarios: number
  tickets_abiertos: number
  completitud_inventario: number
}
type Zona = Comun & {
  color_indice: number
  total_oficinas: number
  oficinas: Oficina[]
  categorias_frecuentes: { categoria: string; total: number }[]
  oficinas_con_mas_fallas: { id: string | null; nombre: string | null; tickets: number }[]
}
type Persona = { id: string; nombre: string; cargo?: string | null; tiene_foto?: boolean; equipos?: number }
type OficinaPerfil = Comun & {
  zona_id: string
  zona_nombre: string
  zona_color_indice: number
  usuarios: Persona[]
  equipos_uso_comun: Equipo[]
  equipos_por_usuario: { responsable_id?: string | null; responsable: string; equipos: Equipo[] }[]
  tickets_recientes: { id: string; codigo: string; asunto: string; estado: string }[]
  tendencia: { mes: string; total: number }[]
  incidencias_recurrentes: { categoria: string; equipo?: string; total: number }[]
}

export function PerfilZona() {
  const { id } = useParams()
  const datos = useQuery({
    queryKey: ['zona', id],
    queryFn: () => api.obtener<Zona>(`/zonas/${id}`),
    enabled: Boolean(id),
    retry: false,
    refetchOnMount: 'always',
    refetchInterval: 30_000,
  })
  if (datos.isLoading) return <SkeletonPanel />
  if (!datos.data) return <ErrorState mensaje="No pudimos cargar la zona." alReintentar={() => void datos.refetch()} />
  const zona = datos.data

  return (
    <PantallaFormulario>
      <PageHeader
        titulo="Resumen de zona"
        descripcion={zona.descripcion}
        acciones={
          /* También aquí: entrar en una zona y no tener forma de salir de ella con un
             clic es lo mismo que no tener el botón. Va a Zonas y oficinas, que es
             de donde se llega. */
          <Button variante="secundario" asChild>
            <Link to="/panel/organizacion">
              <ArrowLeft size={16} aria-hidden="true" />
              Volver a zonas y oficinas
            </Link>
          </Button>
        }
        migas={[
          { texto: 'Zonas y oficinas', enlace: '/panel/organizacion' },
          { texto: zona.nombre },
        ]}
      />
      <TarjetaPerfil
        /* Sin nombre: ya está en el título de arriba, y repetirlo tres veces
           —migas, título y tarjeta— hace que la pantalla parezca un formulario
           rellenado tres veces con lo mismo. */
        titulo={zona.nombre}
        subtitulo={`${plural(zona.total_oficinas, 'oficina')} · ${plural(zona.total_usuarios, 'persona')} · ${plural(zona.total_equipos, 'equipo')}`}
        icono={<MapPin size={26} />}
        colorIndice={zona.color_indice}
        metricas={[
          { etiqueta: 'Oficinas', valor: zona.total_oficinas },
          { etiqueta: 'Personas', valor: zona.total_usuarios },
          { etiqueta: 'Equipos', valor: zona.total_equipos },
          { etiqueta: 'Avisos abiertos', valor: zona.tickets_abiertos },
        ]}
      />
      <BarraProgreso etiqueta="Totalidad del inventario" valor={zona.completitud_inventario} />

      <Panel titulo="Oficinas" descripcion={`${numero(zona.oficinas.length)} en esta zona`}>
        {zona.oficinas.length === 0 ? (
          <Vacio texto="Esta zona todavía no tiene oficinas." />
        ) : (
          <ListaPaginada key={id} items={zona.oficinas} porPagina={25}>{(items) => <ul className="divide-y divide-border">
            {items.map((oficina) => (
              <li key={oficina.id} className="flex flex-wrap items-center justify-between gap-3 py-3 transition-colors hover:bg-muted/40">
                <EnlaceOficina id={oficina.id} nombre={oficina.nombre} zonaId={zona.id} colorIndice={zona.color_indice} />
                {/* El plural se ajusta: había oficinas con «1 personas». */}
                <span className="text-sm text-muted-foreground">
                  {plural(oficina.total_usuarios, 'persona')} · {plural(oficina.total_equipos, 'equipo')}
                </span>
              </li>
            ))}
          </ul>}</ListaPaginada>
        )}
      </Panel>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Panel titulo="Categorías frecuentes">
          {zona.categorias_frecuentes.length === 0 ? (
            <Vacio texto="Sin avisos registrados en esta zona." />
          ) : (
            <ListaPaginada key={id} items={zona.categorias_frecuentes}>{(items) => <ul className="divide-y divide-border">
              {items.map((c) => (
                <li key={c.categoria} className="flex items-center justify-between gap-2 py-2">
                  <span className="truncate">{c.categoria}</span>
                  <span className="shrink-0 text-sm font-semibold">{numero(c.total)}</span>
                </li>
              ))}
            </ul>}</ListaPaginada>
          )}
        </Panel>
        <Panel titulo="Oficinas con más fallas" descripcion="Total de incidencias registradas en esta zona, de mayor a menor.">
          {zona.oficinas_con_mas_fallas.length === 0 ? (
            <Vacio texto="No hay incidencias registradas en las oficinas de esta zona." />
          ) : (
            <ListaPaginada key={id} items={zona.oficinas_con_mas_fallas}>{(items) => <ul className="divide-y divide-border">
              {items.map((e, i) => (
                <li key={e.id || i} className="flex items-center justify-between gap-2 py-2">
                  {e.id ? (
                    <Link className="truncate text-primary-strong hover:underline" to={`/panel/oficinas/${e.id}`}>
                      {e.nombre || 'Ver oficina'}
                    </Link>
                  ) : (
                    <span className="truncate">{e.nombre || 'Oficina sin identificar'}</span>
                  )}
                  <span className="shrink-0 text-sm font-semibold">{plural(e.tickets, 'aviso')}</span>
                </li>
              ))}
            </ul>}</ListaPaginada>
          )}
        </Panel>
      </div>
    </PantallaFormulario>
  )
}

export function PerfilOficina() {
  const sesion = useSesion()
  const { id } = useParams()
  const datos = useQuery({
    queryKey: ['oficina', id],
    queryFn: () => api.obtener<OficinaPerfil>(`/oficinas/${id}`),
    enabled: Boolean(id),
    retry: false,
    refetchOnMount: 'always',
    refetchInterval: 30_000,
  })
  /* Qué pestaña está abierta y qué página del uso común. Se guardan en estado y no en
     la URL: son dos listas de la misma pantalla, no dos pantallas distintas. */
  const [pestana, setPestana] = useState('personas')
  const [paginaComun, setPaginaComun] = useState(1)
  const [paginaTickets, setPaginaTickets] = useState(1)
  const ticketsOficina = useTickets({ oficina_id: id, solo_abiertos: true, pagina: paginaTickets, por_pagina: 25 }, Boolean(id))
  if (datos.isLoading) return <SkeletonPanel />
  if (!datos.data) return <ErrorState mensaje="No pudimos cargar la oficina." alReintentar={() => void datos.refetch()} />
  const oficina = datos.data

  const totalPaginasComun = Math.max(1, Math.ceil(oficina.equipos_uso_comun.length / EQUIPOS_POR_PAGINA))
  /* Acotada a las páginas que existen: si el equipo quedó en la 3 de una lista que
     ahora tiene 2, se queda en la última en vez de mostrar una lista vacía. */
  const paginaComunNumero = Math.min(paginaComun, totalPaginasComun)
  const equiposComunPagina = oficina.equipos_uso_comun.slice(
    (paginaComunNumero - 1) * EQUIPOS_POR_PAGINA,
    paginaComunNumero * EQUIPOS_POR_PAGINA,
  )

  /* Cuántos equipos tiene cada persona. Venía en la respuesta pero no se usaba, y sin
     eso la respuesta a «quién de esta oficina tiene equipos asignados» obligaba a
     cruzar dos listas a ojo.

     El cruce es por **id**. Con el nombre, dos personas homónimas sumaban sus equipos
     en una sola fila, y un nombre con un espacio o una tilde de más dejaba a alguien
     marcado «Sin equipo» teniendo los suyos. El nombre solo se usa como reserva para
     los grupos que el backend no pudo asociar a una cuenta. */
  const equiposPorResponsable = new Map<string, number>()
  for (const grupo of oficina.equipos_por_usuario) {
    const clave = grupo.responsable_id ?? `nombre:${grupo.responsable}`
    equiposPorResponsable.set(clave, grupo.equipos.length)
  }
  const equiposDe = (persona: Persona) =>
    equiposPorResponsable.get(persona.id) ?? equiposPorResponsable.get(`nombre:${persona.nombre}`) ?? 0
  const usoComun = oficina.equipos_uso_comun.length
  /*
    Personas **de la lista** sin equipo asignado.

    Antes se restaba `total_usuarios - usuarios.length`, que da siempre 0 cuando la
    lista está completa: salía «0 sin equipos asignados» en una oficina donde las tres
    personas tenían uno. Era un número que no contaba nada.
  */
  const sinEquipos = oficina.usuarios.filter((persona) => equiposDe(persona) === 0).length

  return (
    <PantallaFormulario>
      <PageHeader
        titulo="Ficha de la oficina"
        descripcion={oficina.descripcion}
        acciones={
          <Button variante="secundario" asChild>
            <Link to="/panel/organizacion">
              <ArrowLeft size={16} aria-hidden="true" />
              Volver a zonas y oficinas
            </Link>
          </Button>
        }
        migas={[
          { texto: 'Zonas y oficinas', enlace: '/panel/organizacion' },
          { texto: oficina.zona_nombre, enlace: `/panel/zonas/${oficina.zona_id}` },
          { texto: oficina.nombre },
        ]}
      />

      <TarjetaPerfil
        titulo={oficina.nombre}
        subtitulo={<Link to={`/panel/zonas/${oficina.zona_id}`} className="text-info-strong hover:underline">Zona: {oficina.zona_nombre}</Link>}
        icono={<Building2 size={26} />}
        colorIndice={oficina.zona_color_indice}
        metricas={[
          { etiqueta: 'Personas', valor: oficina.total_usuarios },
          { etiqueta: 'Equipos', valor: oficina.total_equipos },
          { etiqueta: 'Uso común', valor: usoComun },
          { etiqueta: 'Avisos abiertos', valor: oficina.tickets_abiertos },
        ]}
      />
      <BarraProgreso etiqueta="Totalidad del inventario" valor={oficina.completitud_inventario} />

      {/*
        Los equipos de uso común no son «de nadie»: son **de la oficina**. Es la
        diferencia entre una impresora compartida y un equipo al que se le olvidó
        asignar, y sin decirlo las dos se leen igual.

        Va como una línea de texto apagado, no como un recuadro. Antes era una `Nota`
        de tema ámbar y ocupaba media pantalla para decir algo que ya está en el título
        de la pestaña y en la insignia de cada equipo: un aviso grande invita a leer
        algo que no es una alerta.
      */}
      {usoComun > 0 ? (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Monitor size={14} className="shrink-0" aria-hidden="true" />
          <span>
            Los {plural(usoComun, 'equipo')} de uso común los usa quien esté en la oficina. Para que
            aparezcan en «Equipos asignados», asígnales un responsable desde la ficha del equipo.
          </span>
        </p>
      ) : null}

      {/*
        Pestañas en vez de dos columnas.

        Medido: «Personas» con 6 filas al lado de «Equipos por responsable» con 11
        dejaba media pantalla en blanco bajo la columna corta. Y con oficinas grandes
        la diferencia era de 6 contra 38. Ninguna de las dos columnas se puede
        acortar sin dejar de ver algo, así que no es un problema de tamaño: es que
        ponerlas una al lado de la otra no funciona. En pestañas cada lista usa el
        ancho completo y solo se ve la que se está mirando.
      */}
      <TabsPanel valor={pestana} alCambiar={setPestana}>
        <ListaTabs>
          <Tab valor="personas">
            Personas{oficina.usuarios.length ? ` (${oficina.usuarios.length})` : ''}
          </Tab>
          <Tab valor="asignados">
            Equipos asignados
            {oficina.equipos_por_usuario.length
              ? ` (${oficina.total_equipos - usoComun})`
              : ''}
          </Tab>
          <Tab valor="comun">
            Uso común{usoComun ? ` (${usoComun})` : ''}
          </Tab>
        </ListaTabs>

        <ContenidoTab valor="personas" className="pt-4">
          <Panel
            titulo="Personas"
            descripcion={sinEquipos > 0 ? `${plural(sinEquipos, 'persona')} sin equipos asignados` : undefined}
          >
            {oficina.usuarios.length === 0 ? (
              <Vacio texto="No hay personas asignadas a esta oficina." />
            ) : (
              <ListaPaginada key={id} items={oficina.usuarios}>{(items) => <ul className="divide-y divide-border">
                {items.map((persona) => {
                  const suyos = equiposDe(persona)
                  return (
                    <li key={persona.id} className="flex items-center gap-3 px-1 py-3.5 transition-colors hover:bg-muted/30">
                      <AvatarTecnico id={persona.id} nombre={persona.nombre} tieneFoto={persona.tiene_foto} tamano="sm" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold" title={persona.nombre}>
                          {sesion.puede('usuarios.ver') ? (
                            <Link className="rounded-sm hover:text-primary-strong hover:underline focus-visible:outline-2 focus-visible:outline-primary" to={`/panel/usuarios/${persona.id}`}>
                              {persona.nombre}
                            </Link>
                          ) : (
                            persona.nombre
                          )}
                        </span>
                        {persona.cargo ? (
                          <span className="mt-0.5 block truncate text-xs text-muted-foreground" title={persona.cargo}>{persona.cargo}</span>
                        ) : null}
                      </span>
                      {suyos > 0 ? (
                        <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-muted-foreground">
                          <Monitor size={14} className="text-info-strong" aria-hidden="true" />
                          {plural(suyos, 'equipo')}
                        </span>
                      ) : (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          Sin equipo
                        </span>
                      )}
                    </li>
                  )
                })}
              </ul>}</ListaPaginada>
            )}
          </Panel>
        </ContenidoTab>

        <ContenidoTab valor="asignados" className="pt-4">
          <Panel titulo="Equipos asignados" descripcion="Equipos agrupados por responsable. Las páginas cuentan personas y mantienen todos sus equipos juntos.">
            {oficina.equipos_por_usuario.length === 0 ? (
              <Vacio texto="Ningún equipo de esta oficina tiene responsable asignado." />
            ) : (
              <ListaPaginada key={id} porPagina={5} items={oficina.equipos_por_usuario}>{(items) => <ul className="flex flex-col gap-4">
                {items.map((grupo) => {
                  const cuenta = grupo.equipos.length
                  const responsableId = grupo.responsable_id ?? grupo.equipos.find((equipo) => equipo.responsable_id)?.responsable_id
                  const sinCuenta = equipoDe(grupo.equipos) && !responsableId
                  return (
                    <li key={grupo.responsable_id ?? grupo.responsable} className="overflow-hidden rounded-lg border border-border">
                      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-2/60 px-3 py-2.5">
                        <User size={17} className="shrink-0 text-info-strong" aria-hidden="true" />
                        {responsableId && sesion.puede('usuarios.ver') ? (
                          <Link to={`/panel/usuarios/${responsableId}`} className="min-w-0 flex-1 truncate font-semibold text-primary-strong hover:underline" title={grupo.responsable}>{grupo.responsable}</Link>
                        ) : <span className="min-w-0 flex-1 truncate font-semibold" title={grupo.responsable}>{grupo.responsable}</span>}
                        <span className="shrink-0 text-xs text-muted-foreground">{plural(cuenta, 'equipo')}</span>
                        {/* Sin cuenta vinculada no se puede enlazar, y decirlo evita
                            que el nombre parezca un enlace roto. */}
                        {sinCuenta ? (
                          <span className="rounded-full border border-warning-borde px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-warning-strong">
                            Sin cuenta vinculada
                          </span>
                        ) : null}
                      </div>
                      <div className="px-3"><ListaEquipos equipos={grupo.equipos} /></div>
                    </li>
                  )
                })}
              </ul>}</ListaPaginada>
            )}
          </Panel>
        </ContenidoTab>

        <ContenidoTab valor="comun" className="pt-4">
          <Panel titulo="Equipos de uso común" descripcion="De la oficina, sin persona asignada">
            {oficina.equipos_uso_comun.length === 0 ? (
              <Vacio texto="Todos los equipos de esta oficina tienen responsable asignado." />
            ) : (
              <ListaEquipos equipos={equiposComunPagina} />
            )}
            {totalPaginasComun > 1 ? (
              <div className="border-t border-border pt-3">
                <Paginacion
                  pagina={paginaComunNumero}
                  totalPaginas={totalPaginasComun}
                  total={oficina.equipos_uso_comun.length}
                  porPagina={EQUIPOS_POR_PAGINA}
                  alCambiar={setPaginaComun}
                />
              </div>
            ) : null}
          </Panel>
        </ContenidoTab>
      </TabsPanel>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
      <Panel titulo="Tickets abiertos">
        {ticketsOficina.isPending ? <SkeletonPanel filas={4} /> : ticketsOficina.isError ? <ErrorState compacto mensaje="No pudimos cargar los tickets de la oficina." alReintentar={() => void ticketsOficina.refetch()} /> : <><TicketsAtencion tickets={ticketsOficina.data?.items ?? []} /><Paginacion pagina={paginaTickets} totalPaginas={ticketsOficina.data?.total_paginas ?? 1} total={ticketsOficina.data?.total ?? 0} porPagina={25} alCambiar={setPaginaTickets} /></>}
      </Panel>
      <aside className="flex min-w-0 flex-col gap-4">
        <Panel titulo="Tendencia de los últimos 30 días">
          {oficina.tendencia.length === 0 ? (
            <Vacio texto="No se han registrado avisos en los últimos 30 días." />
          ) : (
            <ListaPaginada key={id} items={oficina.tendencia}>{(items) => <ul className="divide-y divide-border">
              {items.map((t) => (
                <li key={t.mes} className="flex items-center justify-between gap-2 py-2">
                  <span>{/^\d{4}-\d{2}-\d{2}$/.test(t.mes) ? fechaCorta(t.mes) : t.mes}</span>
                  <span className="text-sm font-semibold">{numero(t.total)}</span>
                </li>
              ))}
            </ul>}</ListaPaginada>
          )}
        </Panel>
        <Panel titulo="Incidencias recurrentes">
          {oficina.incidencias_recurrentes.length === 0 ? (
            <Vacio texto="Ninguna categoría se repite en esta oficina." />
          ) : (
            <ListaPaginada key={id} items={oficina.incidencias_recurrentes}>{(items) => <ul className="divide-y divide-border">
              {items.map((r, i) => (
                <li key={i} className="flex items-center justify-between gap-2 py-2">
                  <span className="min-w-0 truncate">
                    {r.categoria}
                    {r.equipo ? <span className="text-muted-foreground"> · {r.equipo}</span> : null}
                  </span>
                  <span className="shrink-0 text-sm font-semibold">{numero(r.total)}</span>
                </li>
              ))}
            </ul>}</ListaPaginada>
          )}
        </Panel>
      </aside>
      </div>
    </PantallaFormulario>
  )
}

/** ¿Todo el grupo de equipos quedó sin persona con cuenta vinculada? */
function equipoDe(equipos: Equipo[]): boolean {
  return equipos.every((equipo) => !equipo.responsable_id)
}

/**
 * Lista de equipos de un grupo.
 *
 * El estado va como insignia —la misma de Inventario— y no como texto con un punto
 * medio delante: en una lista de equipos el estado es lo primero que se mira, y el
 * color es lo que lo dice de un vistazo.
 *
 * El **tipo** va en su propia columna, apagado y en letra pequeña. El icono ya dice
 * algo —un monitor, un teclado— pero no se sabe si es un «Monitor» suelto o el de un
 * conjunto, y en «DESKTPO-AOAAH4T» no dice nada.
 *
 * El tipo se muestra **siempre**, incluso cuando el nombre ya lo contiene. Antes se
 * ocultaba en ese caso para no repetir la palabra, y el resultado fue justo el
 * contrario de lo que se quería: como casi todos los equipos se llaman
 * «Computadora N°01 - Mouse», «Computadora N°01 - Teclado» o «Computadora N°01 -
 * Monitor», la columna quedaba vacía justo en los equipos que más la necesitan.
 * Que el nombre lo repita no es un estorbo: es la forma rápida de confirmar que el
 * tipo guardado es el que se cree.
 *
 * Es una rejilla y no una fila de `flex` porque, con el panel al ancho de la pantalla,
 * la insignia quedaba pegada al borde derecho y a 800 px del nombre al que pertenece.
 * En columnas, el tipo y el estado se leen en vertical sin tener que seguir la fila con
 * la vista.
 */
function ListaEquipos({ equipos }: { equipos: Equipo[] }) {
  return <ListaEquiposPerfil equipos={equipos} />
}
function Vacio({ texto }: { texto: string }) { return <p className="text-sm text-muted-foreground">{texto}</p> }

function ListaPaginada<T>({ items, children, porPagina = 10 }: { items: T[]; children: (items: T[]) => ReactNode; porPagina?: number }) {
  const [pagina, setPagina] = useState(1)
  const totalPaginas = Math.max(1, Math.ceil(items.length / porPagina))
  const actual = Math.min(pagina, totalPaginas)
  return <div className="flex flex-col gap-3">
    {children(items.slice((actual - 1) * porPagina, actual * porPagina))}
    {totalPaginas > 1 && <Paginacion pagina={actual} totalPaginas={totalPaginas} total={items.length} porPagina={porPagina} alCambiar={setPagina} />}
  </div>
}
