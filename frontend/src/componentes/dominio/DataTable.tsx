/**
 * Tabla de datos.
 *
 * Sobre TanStack Table porque hace lo difícil bien: orden por columna,
 * selección múltiple, columnas configurables y virtualization si hace falta.
 * Encima se le pone lo que el sistema necesita: encabezado fijo, filas de 44 px,
 * cambio en vivo resaltado, y en móvil la misma información en tarjetas para que
 * nada desborde en horizontal.
 */

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type RowData,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from '@tanstack/react-table'

declare module '@tanstack/react-table' {
  // Permite marcar columnas que solo se ven en la tabla, no en la tarjeta móvil
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    soloEscritorio?: boolean
  }
}
import { ArrowDown, ArrowUp, ChevronsUpDown, RotateCcw, Settings2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import type { TonoUrgencia } from '../../dominio/estados'
import { cn } from '../../lib/cn'
import { Button } from '../base/Button'
import { PopoverSimple } from '../base/Sobreposiciones'
import { Checkbox } from '../base/Campo'

/**
 * `celdaLibre` se declara en el módulo de TanStack para que `columnDef.meta` lo
 * reconozca; la lista de columnas lo lee de ahí.
 */
declare module '@tanstack/react-table' {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    /** La celda no se recorta: lo que no cabe pasa a la línea siguiente. */
    celdaLibre?: boolean
    /**
     * Ancho de la columna, como valor de CSS (`'16%'`, `'204px'`).
     *
     * Sin esto el navegador reparte las columnas según el contenido de cada
     * tabla, y la misma lista se repartía distinta en cada vista: en «Abiertos»
     * la columna del ticket medía 205 px y en «Cerrados» 192, la fila pasaba de
     * 96 a 92 px y el título «Estado y prioridad» se partía en dos líneas en una
     * vista y en una en la otra. No es que una esté mal: es que al saltar de una
     * a otra el ojo tiene que volver a buscar cada columna.
     *
     * En porcentaje y no en píxeles a propósito: con `table-fixed`, si los anchos
     * en píxeles suman más que el panel la tabla no se encoge, se desborda y
     * aparece la barra horizontal en cuanto la ventana baja de 1440. En
     * porcentaje las columnas bajan todas juntas en la misma proporción —lo que
     * es lo que hace que la tabla se lea igual— sin barra ni contenido cortado.
     */
    ancho?: string
  }
}

/**
 * Definición de columna de la tabla, con un añadido propio.
 *
 * `meta.celdaLibre` saca el recorte automático a esa celda. Las celdas de datos se
 * dejan en una línea y lo que no cabe se recorta, pero eso solo funciona con texto:
 * `truncate` corta con `overflow: hidden`, y una insignia —un `inline-flex` con
 * su propio relleno— no puede encogerse por debajo de su contenido, así que
 * aparecía partida por la mitad, con el borde redondeado cortado. Las celdas con
 * insignias piden la suya entera.
 */
export type ColumnaTabla<T> = ColumnDef<T, unknown>

/** Lo que ya hace su propia cosa cuando se le pulsa o se le da Enter. */
const INTERACTIVO = 'a[href], button, input, select, textarea, [role="button"], [role="checkbox"]'

/**
 * Abrir una fila con el teclado, que antes no se podía.
 *
 * La fila era un `<tr>` con `onClick` y `cursor-pointer`: con el ratón abría, y sin
 * ratón no había forma de llegar al detalle. Ahora es alcanzable con Tab y se abre
 * con Enter o Espacio.
 *
 * Se guarda el caso de que el foco esté en algo interactivo **dentro** de la fila —
 * un enlace a la oficina, un enlace a la zona, la casilla de seleccionar: al pulsar
 * Enter ahí el evento sube hasta la fila, y sin este corte se abriría el detalle y
 * además el enlace. Solo se actúa si lo que tiene el foco es la propia fila.
 */
function alPulsarFilaConTeclado(
  evento: React.KeyboardEvent,
  abrir?: () => void,
) {
  if (!abrir || (evento.key !== 'Enter' && evento.key !== ' ')) return
  if ((evento.target as HTMLElement).closest(INTERACTIVO)) return
  evento.preventDefault()
  abrir()
}

/**
 * Franja lateral de la fila: una sombra interior de 3 px con el color del tono.
 * Se pinta como `box-shadow` y no como `border-left` para no mover el ancho de
 * las columnas al cambiar de tono. Los tres tonos usan tokens del sistema.
 */
const FRANJA: Record<'peligro' | 'aviso' | 'exito', string> = {
  peligro: 'shadow-[inset_3px_0_0_var(--color-destructive)]',
  aviso: 'shadow-[inset_3px_0_0_var(--color-warning)]',
  exito: 'shadow-[inset_3px_0_0_var(--color-success)]',
}

export type PropsTabla<T> = {
  columnas: ColumnaTabla<T>[]
  datos: T[]
  claveFila: (fila: T) => string
  /** Ids que acaban de cambiar: se resaltan sin mover el contenido. */
  destacados?: string[]
  alPulsarFila?: (fila: T) => void
  seleccionable?: boolean
  seleccionadas?: RowSelectionState
  alCambiarSeleccion?: (seleccion: RowSelectionState) => void
  accionesSeleccion?: (seleccion: string[], limpiar: () => void) => ReactNode
  /** Columnas que la persona puede ocultar. */
  columnasConfigurables?: boolean
  ocultasIniciales?: string[]
  /** Preferencia de columnas guardada para una persona concreta. */
  columnasKey?: string
  permitirOrdenar?: boolean
  cargando?: boolean
  etiquetaVacia?: string
  /** Contenido en formato tarjeta para móvil; si no se pasa, se generan Fields. */
  tarjeta?: (fila: T) => ReactNode
  /**
   * Tono de la franja lateral de cada fila (`peligro`, `aviso` o `exito`). Sirve
   * para escanear la cola de un vistazo. Nunca sustituye al texto: la insignia
   * de estado y la de SLA siguen diciendo lo mismo con palabras.
   */
  tonoFila?: (fila: T) => TonoUrgencia
  /** Avisa de qué columnas están a la vista (para poder guardar la vista). */
  alCambiarColumnas?: (columnasVisibles: string[]) => void
  /**
   * Columnas a la vista por omisión. Se usa al abrir una vista guardada, que
   * guarda cuáles son; sin esto el botón prometería columnas que no se aplican.
   */
  columnasForzadas?: string[]
  className?: string
}

/** Identificador estable de una columna: es lo que se guarda en las vistas. */
function claveColumna<T>(columna: ColumnaTabla<T>): string {
  const def = columna as { id?: string; accessorKey?: string }
  return String(def.id ?? def.accessorKey ?? '')
}

export function DataTable<T>({
  columnas,
  datos,
  claveFila,
  destacados = [],
  alPulsarFila,
  seleccionable = false,
  seleccionadas = {},
  alCambiarSeleccion,
  accionesSeleccion,
  columnasConfigurables = false,
  ocultasIniciales = [],
  columnasKey,
  permitirOrdenar = true,
  cargando = false,
  etiquetaVacia = 'No hay nada que mostrar.',
  tarjeta,
  tonoFila,
  alCambiarColumnas,
  columnasForzadas,
  className,
}: PropsTabla<T>) {
  const [orden, setOrden] = useState<SortingState>([])

  /*
   * Barra horizontal pegada abajo de la tabla, con su propio tirador.
   *
   * Con todas las columnas a la vista la tabla mide más de 2000 px y su barra
   * horizontal quedaba mil píxeles más abajo: había que bajar hasta el final de la
   * tabla para poder moverla, y al principio no se podía. Aquí hay una segunda
   * barra `sticky bottom-1` que está siempre a la mano y se va sola cuando la
   * tabla queda fuera de pantalla.
   *
   * El tirador se pinta a mano en vez de dejar el del navegador: en algunos
   * navegadores la barra es superpuesta y no se ve hasta que pasas el ratón por
   * encima, que es justo el problema que se quería quitar.
   */
  const contenedorScroll = useRef<HTMLDivElement | null>(null)
  const pistaRef = useRef<HTMLDivElement | null>(null)
  const arrastre = useRef<{ inicioX: number; inicioScroll: number } | null>(null)
  const [medida, setMedida] = useState({ desborde: 0, visible: 1, scroll: 0 })
  const { desborde, visible, scroll } = medida
  /** Fracción de la tabla que se ve: el tirador ocupa esa parte de la pista. */
  const fraccion = desborde > 4 ? visible / (visible + desborde) : 1
  /** Cuánto lleva el tirador recorrido, de 0 a 1. */
  const recorrido = desborde > 4 ? Math.min(1, Math.max(0, scroll / desborde)) : 0

  const medir = useCallback(() => {
    const contenedor = contenedorScroll.current
    if (!contenedor) return
    const anchoTabla = contenedor.querySelector('table')?.scrollWidth ?? contenedor.clientWidth
    setMedida({
      desborde: Math.max(0, anchoTabla - contenedor.clientWidth),
      visible: Math.max(1, contenedor.clientWidth),
      scroll: contenedor.scrollLeft,
    })
  }, [])

  useEffect(() => {
    const contenedor = contenedorScroll.current
    if (!contenedor) return
    medir()
    const observador = new ResizeObserver(medir)
    observador.observe(contenedor)
    const tablaHtml = contenedor.querySelector('table')
    if (tablaHtml) observador.observe(tablaHtml)
    return () => observador.disconnect()
  }, [medir])

  const anchoTirador = useCallback(
    (anchoPista: number) => {
      const total = visible + desborde
      return Math.max(36, Math.round(anchoPista * (visible / Math.max(1, total))))
    },
    [desborde, visible],
  )

  /** Mantiene pulsado y arrastrado: mueve la tabla, no la barra. */
  const moverTirador = useCallback(
    (evento: React.PointerEvent<HTMLDivElement>) => {
      if (!arrastre.current) return
      const ancho = anchoTirador(evento.currentTarget.offsetWidth)
      const movimiento = evento.clientX - arrastre.current.inicioX
      const total = contenedorScroll.current?.clientWidth ?? 1
      const factor = total / Math.max(1, ancho)
      if (contenedorScroll.current) {
        contenedorScroll.current.scrollLeft = arrastre.current.inicioScroll + movimiento * factor
      }
    },
    [anchoTirador],
  )

  const soltarTirador = useCallback(() => {
    arrastre.current = null
  }, [])

  /** Pulsar en la pista lleva a ese punto, como en cualquier barra. */
  const saltarEnLaPista = useCallback(
    (evento: React.PointerEvent<HTMLDivElement>) => {
      const contenedor = contenedorScroll.current
      if (!contenedor) return
      const caja = evento.currentTarget.getBoundingClientRect()
      const proporcion = (evento.clientX - caja.left) / caja.width
      contenedor.scrollLeft = proporcion * (contenedor.clientWidth + desborde) - contenedor.clientWidth / 2
      medir()
    },
    [desborde, medir],
  )
  const [visibles, setVisibles] = useState<VisibilityState>(() => {
    const iniciales = Object.fromEntries(ocultasIniciales.map((id) => [id, false]))
    if (!columnasKey) return iniciales
    let guardado: string | null
    try {
      guardado = localStorage.getItem(columnasKey)
    } catch (error) {
      console.warn('No se pudieron leer las columnas guardadas.', error)
      return iniciales
    }
    if (!guardado) return iniciales
    try {
      const parseado: unknown = JSON.parse(guardado)
      if (typeof parseado !== 'object' || parseado === null || Array.isArray(parseado)) return iniciales
      const booleanos = Object.entries(parseado).filter(([, valor]) => typeof valor === 'boolean')
      return { ...iniciales, ...Object.fromEntries(booleanos) }
    } catch (error) {
      console.warn('La preferencia de columnas guardada no es válida.', error)
      return iniciales
    }
  })

  useEffect(() => {
    if (!columnasKey) return
    try {
      localStorage.setItem(columnasKey, JSON.stringify(visibles))
    } catch (error) {
      console.warn('No se pudieron guardar las columnas visibles.', error)
    }
  }, [columnasKey, visibles])

  // Al abrir una vista guardada manda su lista de columnas, no la preferencia
  // local. Se compara el texto unido para no re-aplicar en cada render.
  const forzadas = columnasForzadas?.length ? columnasForzadas.join('|') : ''
  useEffect(() => {
    if (!forzadas) return
    const elegidas = new Set(forzadas.split('|'))
    setVisibles(
      Object.fromEntries(
        columnas.map((columna) => {
          const clave = claveColumna(columna)
          return [clave, elegidas.has(clave)]
        }),
      ),
    )
  }, [forzadas, columnas])

  // La pantalla que guarda vistas necesita saber qué columnas hay a la vista,
  // no solo la preferencia local de esta persona.
  useEffect(() => {
    if (!alCambiarColumnas) return
    alCambiarColumnas(
      columnas.map(claveColumna).filter((clave) => clave && visibles[clave] !== false),
    )
  }, [alCambiarColumnas, visibles, columnas])

  const tabla = useReactTable({
    data: datos,
    columns: columnas,
    state: { sorting: orden, rowSelection: seleccionadas, columnVisibility: visibles },
    enableSorting: permitirOrdenar,
    enableRowSelection: seleccionable,
    getRowId: (fila) => claveFila(fila),
    onSortingChange: setOrden,
    onRowSelectionChange: (cambio) => {
      const siguiente = typeof cambio === 'function' ? cambio(seleccionadas) : cambio
      alCambiarSeleccion?.(siguiente)
    },
    onColumnVisibilityChange: setVisibles,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const elegirTodas = () => {
    if (tabla.getIsAllPageRowsSelected()) tabla.toggleAllPageRowsSelected(false)
    else tabla.toggleAllPageRowsSelected(true)
  }
  const cantidadSeleccionada = Object.keys(seleccionadas).length
  const ocultables = tabla.getAllLeafColumns().filter((columna) => columna.getCanHide())

  /*
   * Si todas las columnas a la vista declaran su ancho, la tabla usa
   * `table-fixed` y todas miden lo mismo en todas las vistas. Si alguna no lo
   * declara —una columna sin ancho, o una vista con columnas que el usuario
   * declara —una columna sin ancho, o una vista con columnas que el usuario no
   * recuerda— se deja `auto` y cada una se reparte como pueda, que es lo de
   * antes: mejor un reparto feo que una columna de 0 px.
   */
  const conAnchosFijos = tabla
    .getVisibleLeafColumns()
    .every((columna) => typeof columna.columnDef.meta?.ancho === 'string')

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* Acciones sobre la selección: aparecen solo si hay algo seleccionado */}
      {seleccionable && cantidadSeleccionada > 0 && accionesSeleccion ? (
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius-panel)] border border-primary/25 bg-primary-soft p-2">
          <p className="text-sm font-semibold text-primary-strong">
            {cantidadSeleccionada} {cantidadSeleccionada === 1 ? 'elemento seleccionado' : 'elementos seleccionados'}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {accionesSeleccion(
              Object.entries(seleccionadas)
                .filter(([, activo]) => activo)
                .map(([id]) => id),
              () => alCambiarSeleccion?.({}),
            )}
          </div>
        </div>
      ) : null}

      {/* ══ Móvil: tarjetas ══ */}
      <div className="flex flex-col gap-2 md:hidden">
        {cargando ? (
          Array.from({ length: 3 }, (_, indice) => (
            <div key={`esqueleto-movil-${indice}`} className="h-24 animate-pulse rounded-[var(--radius-panel)] bg-muted" />
          ))
        ) : datos.length === 0 ? (
          <p className="rounded-[var(--radius-panel)] border border-border bg-surface p-6 text-center text-sm text-muted-foreground">
            {etiquetaVacia}
          </p>
        ) : (
          datos.map((fila) => {
            // Se reutiliza la fila real de la tabla, asi el valor se pinta con el
            // mismo componente que en escritorio y no con un formato adivinado
            const row = tabla.getRowModel().rows.find((candidata) => candidata.id === claveFila(fila))
            if (!row) return null
            const tono = tonoFila?.(fila)
            return (
              <div
                key={row.id}
                onClick={alPulsarFila ? (evento) => { if (!(evento.target as Element).closest(INTERACTIVO)) alPulsarFila(fila) } : undefined}
                onKeyDown={alPulsarFila ? (evento) => alPulsarFilaConTeclado(evento, () => alPulsarFila(fila)) : undefined}
                tabIndex={alPulsarFila ? 0 : undefined}
                className={cn(
                  'rounded-[var(--radius-panel)] border border-border bg-surface p-3 pl-4',
                  alPulsarFila && 'cursor-pointer active:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
                  destacados.includes(row.id) && 'fila-actualizada',
                  // Mismo código de color que la franja de la fila en escritorio
                  tono && FRANJA[tono],
                )}
              >
                {tarjeta ? (
                  tarjeta(fila)
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {row
                      .getVisibleCells()
                      .filter((celda) => celda.column.columnDef.meta?.soloEscritorio !== true)
                      .map((celda) => (
                        <li key={celda.id} className="flex items-start justify-between gap-3 text-sm">
                          <span className="shrink-0 text-muted-foreground">
                            {typeof celda.column.columnDef.header === 'string' ? celda.column.columnDef.header : ''}
                          </span>
                          <span className="min-w-0 text-right font-medium">
                            {flexRender(celda.column.columnDef.cell, celda.getContext())}
                          </span>
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* ══ Escritorio: tabla ══ */}
      <div className="hidden md:block">
      <div
        ref={contenedorScroll}
        onScroll={medir}
        /*
          `barra-oculta` y no `sin-barra`: la barra del navegador **no se quita a
          medias**. Este contenedor tiene siempre su propio tirador debajo —el
          bloque redondeado con el pulgar—, que es el que se arrastra; la del
          navegador era un segundo mando para lo mismo y se veían las dos. Con
          `sin-barra` tampoco se arreglaba: esa clase solo la adelgaza a 8 px, no la
          oculta, y en el inventario seguían apareciendo las dos.
        */
        className="barra-oculta overflow-x-auto rounded-[var(--radius-panel)] border border-border/80 bg-surface shadow-panel"
      >
        {/* `min-w-full` y no `w-full`: con el borde del contenedor, `w-full` se pasa
            unos píxeles y hace aparecer una barra horizontal que no hace falta. */}
        <table
          className={cn(
            'border-collapse text-sm text-foreground',
            // `w-full` **siempre**, y no solo con `table-fixed`.
            //
            // Medido en Inventario: la tabla se quedaba en 1.028 px dentro de un
            // hueco de 1.181 —153 px de vacío a la derecha— y al ocultar columnas
            // el hueco llegaba a **1.114 px**, porque «Menú» no declaraba ancho,
            // eso activaba el reparto automático y la tabla se encogía al
            // contenido en vez de ocupar lo que tenía.
            //
            // La regla que queda: una tabla que deja hueco a la derecha está
            // rota. Sin importar cuántas columnas haya visibles, ocupa el 100 %
            // y el sobrante lo reparten las que quedan.
            'w-full',
            // `table-fixed` es lo que hace que las columnas midan lo mismo en
            // todas las vistas. Con `auto` el navegador reparte según lo que hay
            // escrito en cada momento, y con cinco casos abiertos el reparto era
            // distinto que con cinco cerrados aunque las columnas fuesen las
            // mismas: la del ticket medía 188 en una y 192 en la otra, y «Estado y
            // prioridad» se partía en dos líneas en una vista y en una en la otra.
            //
            // `min-w-[1110px]`: por debajo de ese ancho la tabla deja de encogerse
            // y sale la barra horizontal —que ya tiene su tirador pegado abajo—
            // en lugar de recortar contenido. Recortar es peor que deslocar:
            // «hace 15 horas» cortado deja de ser una fecha. Con la barra se ve
            // entero, y la proporción de columnas —lo que hace que la tabla se
            // lea igual en todas las vistas— se mantiene en ambos casos.
            conAnchosFijos && 'table-fixed min-w-[1110px]',
          )}
        >
          {/*
          Los anchos declarados por columna. Se declaran aquí y no se tocan en
          cada página: los dos consumers de la tabla (bandeja, equipos,
          usuarios, auditoría, galería) los heredan todos del mismo sitio. */}
          {tabla.getVisibleLeafColumns().some((columna) => columna.columnDef.meta?.ancho) ? (
            <colgroup>
              {seleccionable ? <col /> : null}
              {tabla.getVisibleLeafColumns().map((columna) => {
                const ancho = columna.columnDef.meta?.ancho
                return <col key={columna.id} style={ancho ? { width: ancho } : undefined} />
              })}
            </colgroup>
          ) : null}
          {/*
          Encabezado. Ahora la fila entera lleva un fondo suave, un borde propio y
          más aire, que es lo que faltaba para que se leyera como una cabecera y
          no como palabras sueltas flotando sobre los datos.

          Las mayúsculas se quedan: se probaron en minúsculas y la fila perdía el
          golpe visual que hace que «Equipo», «Ubicación» y «Responsable» se
          distinguan de un vistazo sin tener que leerlas enteras. Lo que le faltaba no
          eran las mayúsculas sino que no había nada detrás.
        */}
        <thead className="sticky top-0 z-10 border-b border-border bg-surface-2">
          {tabla.getHeaderGroups().map((grupo) => (
              <tr key={grupo.id}>
                {seleccionable ? (
                  <th scope="col" className="w-10 px-4 py-3.5 text-left">
                    <Checkbox
                      etiqueta={<span className="solo-lectores">Seleccionar todo</span>}
                      valor={grupo.headers.length > 0 && tabla.getIsAllPageRowsSelected()}
                      alCambiar={elegirTodas}
                    />
                  </th>
                ) : null}
                {grupo.headers.map((cabecera) => {
                  const ordenActual = cabecera.column.getIsSorted()
                  const puedeOrdenar = cabecera.column.getCanSort()
                  return (
                    <th
                      key={cabecera.id}
                      scope="col"
                      aria-sort={ordenActual === 'asc' ? 'ascending' : ordenActual === 'desc' ? 'descending' : 'none'}
                      className="px-4 py-3.5 text-left"
                    >
                      {puedeOrdenar ? (
                        <button
                          type="button"
                          onClick={cabecera.column.getToggleSortingHandler()}
                          className={cn(
                            'group inline-flex items-center gap-1.5 rounded transition-colors',
                            'text-xs font-semibold tracking-wide text-foreground/70 uppercase hover:text-foreground',
                            'focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none',
                          )}
                        >
                          {flexRender(cabecera.column.columnDef.header, cabecera.getContext())}
                          {ordenActual === 'asc' ? (
                            <ArrowUp size={14} className="text-primary" aria-hidden="true" />
                          ) : ordenActual === 'desc' ? (
                            <ArrowDown size={14} className="text-primary" aria-hidden="true" />
                          ) : (
                            <ChevronsUpDown
                              size={14}
                              aria-hidden="true"
                              className="opacity-30 transition-opacity group-hover:opacity-70"
                            />
                          )}
                        </button>
                      ) : (
                        <span className="text-xs font-semibold tracking-wide text-foreground/70 uppercase">
                          {flexRender(cabecera.column.columnDef.header, cabecera.getContext())}
                        </span>
                      )}
                    </th>
                  )
                })}
              </tr>
          ))}
        </thead>
          <tbody>
            {cargando ? (
              Array.from({ length: 6 }, (_, indice) => (
                <tr key={`esqueleto-${indice}`} className="border-t border-border/50">
                  {columnas.map((columna, posicion) => (
                    <td key={`${columna.id ?? 'col'}-${posicion}`} className="px-4 py-3">
                      <div className="h-4 animate-pulse rounded bg-muted" />
                    </td>
                  ))}
                </tr>
              ))
            ) : tabla.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columnas.length + (seleccionable ? 1 : 0)} className="px-4 py-12 text-center text-muted-foreground font-medium">
                  {etiquetaVacia}
                </td>
              </tr>
            ) : (
              tabla.getRowModel().rows.map((fila) => {
                const tono = tonoFila?.(fila.original)
                return (
                <tr
                  key={fila.id}
                  onClick={alPulsarFila ? (evento) => { if (!(evento.target as Element).closest(INTERACTIVO)) alPulsarFila(fila.original) } : undefined}
                  onKeyDown={alPulsarFila ? (evento) => alPulsarFilaConTeclado(evento, () => alPulsarFila(fila.original)) : undefined}
                  tabIndex={alPulsarFila ? 0 : undefined}
                  className={cn(
                    'group h-12 border-t border-border/60 transition-colors duration-[var(--transition-ui)]',
                    /*
                      Resalte de la fila. Con 25 filas de tickets el puntero se
                      para medio segundo antes de decidir cuál abrir, y con un
                      tinte del 50 % no se veía cuál era. Ahora la fila se apaga
                      del resto al pasar por encima y se hunde un poco más al
                      pulsar, para que el clic se sienta como un clic y no como un
                      salto.
                    */
                    alPulsarFila &&
                      'cursor-pointer hover:bg-primary-soft/60 hover:shadow-[inset_3px_0_0_var(--color-primary)] active:bg-primary-soft/90 focus-visible:bg-primary-soft/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary',
                    destacados.includes(fila.id) && 'fila-actualizada',
                    fila.getIsSelected() && 'bg-primary-soft/40',
                    // El tono va al final: si una fila está seleccionada y a la vez
                    // es urgente, manda la franja, que es lo que hay que ver.
                    tono && FRANJA[tono],
                  )}
                >
                  {seleccionable ? (
                    <td className="w-10 px-3 py-3" onClick={(evento) => evento.stopPropagation()}>
                      <Checkbox
                        etiqueta={<span className="solo-lectores">Seleccionar la fila</span>}
                        valor={fila.getIsSelected()}
                        alCambiar={fila.getToggleSelectedHandler() ?? (() => {})}
                      />
                    </td>
                  ) : null}
                  {fila.getVisibleCells().map((celda, posicion) => {
                    /*
                      El recorte va en un envoltorio, no en el `<td>`.
                      `overflow: hidden` en la celda parte cualquier cosa que no
                      sea texto: una insignia es un `inline-flex` con relleno y no
                      puede encogerse, así que aparecía cortada por la mitad, con
                      el borde redondeado partido. Puesto en el envoltorio, cada
                      celda recorta su propio contenido —el texto sale con puntos
                      suspensivos, como antes— y una columna marcada con
                      `celdaLibre` no recorta nada y deja que el contenido baje a
                      la línea siguiente.
                    */
                    const libre = celda.column.columnDef.meta?.celdaLibre === true
                    const primera = posicion === 0
                    return (
                      <td
                        key={celda.id}
                        data-dato={/(^nombre$|_nombre$|nombre_equipo|responsable|reportante)/.test(celda.column.id) ? 'nombre' : undefined}
                        className={cn(
                          'px-4 py-3 align-middle',
                          // Una fila se estira cuando un texto largo parte en tres
                          // líneas. Con muchas columnas a la vista eso convertía la
                          // tabla en un muro. La primera columna es la que lleva el
                          // nombre y se la deja respirar; el resto se queda en una
                          // línea y lo que no cabe se recorta.
                          primera ? 'max-w-[22rem]' : 'max-w-[11rem]',
                        )}
                      >
                        {libre || primera ? (
                          flexRender(celda.column.columnDef.cell, celda.getContext())
                        ) : (
                          <span className="block truncate whitespace-nowrap">
                            {flexRender(celda.column.columnDef.cell, celda.getContext())}
                          </span>
                        )}
                      </td>
                    )
                  })}
                </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/*
        La barra pegada. Solo aparece si la tabla se sale de lado, y ocupa su
        sitio en el flujo: si la tabla no está a la vista, la barra se va con ella.
      */}
      {desborde > 4 ? (
        <div
          ref={pistaRef}
          onPointerDown={saltarEnLaPista}
          className="no-imprimir sticky bottom-1 z-20 mt-1 hidden h-3 w-full cursor-pointer items-center rounded-full border border-border bg-surface-2/90 px-0.5 backdrop-blur-sm md:flex"
          title="Arrastra para ver las columnas de la derecha"
        >
          <div
            role="presentation"
            onPointerDown={(evento) => {
              arrastre.current = {
                inicioX: evento.clientX,
                inicioScroll: contenedorScroll.current?.scrollLeft ?? 0,
              }
              ;(evento.target as HTMLElement).setPointerCapture(evento.pointerId)
              evento.stopPropagation()
            }}
            onPointerMove={moverTirador}
            onPointerUp={soltarTirador}
            onPointerCancel={soltarTirador}
            className="h-1.5 rounded-full bg-muted-foreground/45 transition-colors hover:bg-muted-foreground/70"
            style={{
              // El ancho es la parte visible de la tabla; el desplazamiento, la
              // parte recorrida del hueco que queda. Todo en porcentajes del
              // ancho de la pista, así no hay que medirla en píxeles.
              width: `calc(${fraccion * 100}% - 4px)`,
              marginLeft: `calc((1 - ${fraccion}) * 100% * ${recorrido})`,
            }}
          />
        </div>
      ) : null}
      </div>

      {/* Configuración de columnas: en escritorio, para no estorbar */}
      {columnasConfigurables && ocultables.length > 0 ? (
        <div className="no-imprimir hidden justify-end md:flex">
          <PopoverSimple
            ancho="w-64"
            disparador={
              <Button variante="secundario" tamano="sm" icono={<Settings2 size={14} aria-hidden="true" />}>
                Columnas
              </Button>
            }
            contenido={
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">Columnas visibles</p>
                  <Button
                    variante="fantasma"
                    tamano="sm"
                    icono={<RotateCcw size={14} aria-hidden="true" />}
                    onClick={() => setVisibles(Object.fromEntries(ocultasIniciales.map((id) => [id, false])))}
                  >
                    Restablecer
                  </Button>
                </div>
                {ocultables.map((columna) => (
                  <Checkbox
                    key={columna.id}
                    etiqueta={typeof columna.columnDef.header === 'string' ? columna.columnDef.header : (columna.id ?? '')}
                    valor={columna.getIsVisible()}
                    alCambiar={(valor) => columna.toggleVisibility(valor)}
                  />
                ))}
              </div>
            }
          />
        </div>
      ) : null}
    </div>
  )
}

/**
 * Celda sin dato.
 *
 * El inventario tiene columnas técnicas —RAM, IP, MAC, Almacenamiento— que no
 * aplican a todos los tipos: un mouse no tiene RAM y una impresora no tiene MAC.
 * Rellenarlas con un guion largo «—» en tinta fuerte convertía media tabla en una
 * columna de rayas: lo que no aplica parecía un dato pendiente, y las rayas
 * competían con los datos de verdad por la atención.
 *
 * Ahora es un punto muy tenue. La celda no se aparta de la retícula, así que las
 * filas siguen alineadas, pero el ojo pasa de largo y se queda con lo escrito.
 * El texto del `title` sigue estando para quien quiera saber qué significa.
 */
export function CeldaVacia({ texto = 'No hay dato aquí', className }: { texto?: string; className?: string }) {
  return (
    <span aria-label={texto} className={cn('select-none text-muted-foreground/40', className)} title={texto}>
      ·
    </span>
  )
}

/** Paginación: muestra el rango real y el total, no solo los números. */
export function Paginacion({
  pagina,
  totalPaginas,
  total,
  porPagina,
  alCambiar,
}: {
  pagina: number
  totalPaginas: number
  total: number
  porPagina: number
  alCambiar: (pagina: number) => void
}) {
  const desde = total === 0 ? 0 : (pagina - 1) * porPagina + 1
  const hasta = Math.min(pagina * porPagina, total)
  const numeros = useMemo(() => paginasVisibles(pagina, totalPaginas), [pagina, totalPaginas])

  if (total === 0) return null

  return (
    <nav aria-label="Paginación" className="no-imprimir flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">
        Mostrando <span className="font-semibold">{desde}</span> a <span className="font-semibold">{hasta}</span> de{' '}
        <span className="font-semibold">{total}</span>
      </p>
      {/* Los botones envuelven: nueve botones en una fila no caben en 390 px */}
      <div className="flex flex-wrap items-center gap-1">
        <Button tamano="sm" disabled={pagina <= 1} onClick={() => alCambiar(pagina - 1)}>
          Anterior
        </Button>
        {numeros.map((numero, indice) =>
          numero === '…' ? (
            <span key={`luego-${indice}`} className="px-1 text-muted-foreground">
              …
            </span>
          ) : (
            <Button
              key={numero}
              tamano="sm"
              variante={numero === pagina ? 'primario' : 'secundario'}
              onClick={() => alCambiar(numero as number)}
              aria-current={numero === pagina ? 'page' : undefined}
            >
              {numero}
            </Button>
          ),
        )}
        <Button tamano="sm" disabled={pagina >= totalPaginas} onClick={() => alCambiar(pagina + 1)}>
          Siguiente
        </Button>
      </div>
    </nav>
  )
}

/** Como máximo siete botones: primero, último, y lo que rodea la actual. */
function paginasVisibles(pagina: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, indice) => indice + 1)
  if (pagina <= 4) return [1, 2, 3, 4, 5, '…', total]
  if (pagina >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '…', pagina - 1, pagina, pagina + 1, '…', total]
}
