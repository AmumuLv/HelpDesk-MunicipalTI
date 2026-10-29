/**
 * Bandeja de tickets: la pantalla de trabajo del equipo TI.
 *
 * Vistas guardadas encima (las trae la API), filtros debajo y tabla con
 * columnas configurables. En móvil cada ticket es una tarjeta con lo esencial:
 * código, asunto, persona, estado y SLA.
 *
 * Los parámetros de la URL mandan sobre los filtros: así un enlace a
 * «Sin asignar» desde el resumen funciona, y el navegador permite recargar y
 * compartir la vista.
 */

import { useQueryClient } from '@tanstack/react-query'
import { Bookmark, Check, Filter, Inbox, Plus, RotateCw, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useOficinas, useTecnicos, useTickets, useVistasGuardadas, useZonas } from '../../api/hooks'
import type { FiltrosTicket, TicketResumen, VistaGuardada } from '../../api/tipos'
import { EstadoBadge, PrioridadBadge, SlaBadge } from '../../componentes/dominio/Badge'
import { BarraProgreso } from '../../componentes/dominio/BarraProgreso'
import { DataTable, Paginacion, type ColumnaTabla } from '../../componentes/dominio/DataTable'
import { Button } from '../../componentes/base/Button'
import { SearchInput, Select, Input } from '../../componentes/base/Campo'
import { ConfirmDialog, DialogModal } from '../../componentes/base/Sobreposiciones'
import { EmptyState, ErrorState, PageHeader, Panel } from '../../componentes/base/Estructura'
import { desdeHace, fechaCorta } from '../../dominio/formato'
import { ESTADOS, PRIORIDADES, estadoDe, tonoUrgenciaTicket } from '../../dominio/estados'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'
import { Ubicacion } from '../../componentes/dominio/Ubicacion'
import { cn } from '../../lib/cn'

/**
 * Vistas rápidas. La `clave` es lo que viaja en `?vista=` y también lo que
 * enlazan los indicadores del resumen, así que los dos caminos entran por la
 * misma puerta.
 *
 * La primera vista es la cola de trabajo: solo lo que sigue abierto. Antes se
 * llamaba «Todos» y no filtraba nada, así que un ticket recién resuelto se
 * quedaba en la lista de activos hasta que alguien lo cerraba de verdad. Lo ya
 * terminado vive en «Cerrados».
 *
 * `sin_asignar` y `criticos` no son filtros del cliente: se delegan en la API con
 * su parámetro `vista`, que es quien sabe si un ticket cuenta como crítico. El
 * resto se traduce a los filtros que `GET /api/tickets` acepta.
 */
const VISTAS_RAPIDAS: { clave: string; texto: string; filtros: Partial<FiltrosTicket> }[] = [
  { clave: 'abiertos', texto: 'Abiertos', filtros: { solo_abiertos: true } },
  { clave: 'sin_asignar', texto: 'Sin asignar', filtros: { vista: 'sin_asignar' } },
  { clave: 'sla_riesgo', texto: 'SLA en riesgo', filtros: { sla: 'riesgo' } },
  { clave: 'criticos', texto: 'Críticos', filtros: { vista: 'criticos' } },
  { clave: 'cerrados', texto: 'Cerrados', filtros: { vista: 'cerrados', estado: ['cerrado'] } },
]

/** `todos` era la clave antigua de la vista por defecto; sigue significando lo mismo. */
const CLAVES_ANTIGUAS: Record<string, string> = { todos: 'abiertos' }

/**
 * Filtros que viven en la URL, con la forma en que se escriben y en que se leen.
 *
 * La lista es explícita a propósito: una vista guardada vuelve por la URL, así
 * que cualquier filtro que no esté aquí se guardaría pero al abrir la vista no
 * se aplicaría. `forma` y `lectura` no se pueden fundir en un solo sitio: una
 * misma clave se escribe de una manera y se lee de otra (`1`/`true`, fechas,
 * listas de estados).
 */
type FiltroUrl = {
  etiqueta?: string
  /** Convierte el valor guardado en lo que se escribe en la URL. */
  forma?: (valor: unknown) => string
  /** Lee la URL y devuelve el valor del filtro, o `null` si no está. */
  lectura?: (params: URLSearchParams) => string | string[] | boolean | null
}

const FILTROS_URL: Record<string, FiltroUrl> = {
  estado: { lectura: (p) => p.getAll('estado') },
  prioridad: { lectura: (p) => p.get('prioridad') },
  zona_id: { lectura: (p) => p.get('zona_id') },
  oficina_id: { lectura: (p) => p.get('oficina_id') },
  tecnico_id: { lectura: (p) => p.get('tecnico_id') },
  activo_id: { lectura: (p) => p.get('activo_id') },
  categoria: { lectura: (p) => p.get('categoria') },
  sla: { lectura: (p) => p.get('sla') },
  fecha_desde: { lectura: (p) => p.get('fecha_desde') },
  fecha_hasta: { lectura: (p) => p.get('fecha_hasta') },
  // `solo_abiertos` se escribía como `1` y las vistas guardadas lo dejaban como
  // `true`; al releerlo no coincidía con nada y el filtro se perdía en silencio.
  solo_abiertos: {
    forma: (valor) => (valor ? '1' : ''),
    lectura: (p) => {
      const bruto = p.get('solo_abiertos')
      return bruto === null ? null : bruto === '1' || bruto === 'true'
    },
  },
}

/** Un filtro con valor no vacío. */
function conValor(valor: string | string[] | boolean | null | undefined): boolean {
  if (valor === null || valor === undefined || valor === '') return false
  if (Array.isArray(valor)) return valor.length > 0
  return true
}

/**
 * Reconstruye los filtros que la tabla entiende a partir de una vista rápida y
 * de los filtros guardados, con la misma regla que usa `filtrosGuardados`.
 *
 * Sirve para dos cosas: guardar la vista con lo que de verdad filtra, y decidir
 * después si lo que se está viendo es esa vista o ya se le cambió algo.
 */
function filtrosEffectivos(
  vista: string | null | undefined,
  guardados: Record<string, unknown>,
): Partial<FiltrosTicket> {
  const deVista = VISTAS_RAPIDAS.find((item) => item.clave === vista)?.filtros ?? {}
  const sueltos: Record<string, unknown> = {}
  for (const nombre of Object.keys(FILTROS_URL)) {
    const valor = guardados[nombre]
    if (conValor(valor as string | string[] | boolean | null)) sueltos[nombre] = valor
  }
  return { ...deVista, ...sueltos }
}

/**
 * Huella de un conjunto de filtros, comparable entre dos momentos.
 *
 * No se compara con `JSON.stringify` a pelo porque el orden de las claves y de
 * las listas no significa nada: `estado=resuelto&estado=cerrado` y
 * `estado=cerrado&estado=resuelto` son la misma vista. Cada valor se ordena y
 * se recorre siempre en el mismo orden de claves.
 */
function huellaDe(filtros: Partial<FiltrosTicket>, textoBusqueda = ''): string {
  const partes: string[] = []
  for (const clave of Object.keys(filtros).sort()) {
    const valor = (filtros as Record<string, unknown>)[clave]
    if (!conValor(valor as string | string[] | boolean | null)) continue
    const lista = (Array.isArray(valor) ? valor : [valor]).map(String).sort()
    partes.push(`${clave}=${lista.join(',')}`)
  }
  if (textoBusqueda.trim()) partes.push(`texto=${textoBusqueda.trim()}`)
  return partes.join('&')
}

/**
 * Opciones de SLA. Solo se ofrecen las que la API filtra de verdad: el backend
 * entiende `riesgo`, `vencido` e `incumplido`. Antes la lista traía `ok`,
 * `por_vencer` y `en_pausa`, que el servidor ignoraba en silencio y devolvía la
 * cola completa.
 */
const OPCIONES_SLA = [
  { valor: 'riesgo', etiqueta: 'En riesgo (por vencer)' },
  { valor: 'vencido', etiqueta: 'Vencido, sin resolver' },
  { valor: 'incumplido', etiqueta: 'Incumplió el tiempo acordado' },
]

/**
 * Leyenda de la franja lateral. El color no se descifra solo: aquí está escrito
 * qué significa, y además cada fila dice su estado y su tiempo en palabras.
 */
const LEYENDA = [
  { clave: 'peligro', texto: 'Vencido, a punto de vencer o crítico', franja: 'h-3 w-1 rounded-full bg-destructive' },
  { clave: 'aviso', texto: 'Queda poco, prioridad alta o sin asignar', franja: 'h-3 w-1 rounded-full bg-warning' },
  { clave: 'exito', texto: 'Atendido o cerrado', franja: 'h-3 w-1 rounded-full bg-success' },
]

/**
 * Filtros que se pueden guardar en una vista, con la palabra que se le enseña a
 * la persona. El diálogo los lista con su valor actual, para que quede claro qué
 * se está guardando.
 */
const ETIQUETAS_FILTRO: [string, string][] = [
  ['estado', 'Estado'],
  ['prioridad', 'Prioridad'],
  ['zona_id', 'Zona'],
  ['oficina_id', 'Oficina'],
  ['tecnico_id', 'Técnico'],
  ['sla', 'SLA'],
  ['categoria', 'Categoría'],
  ['fecha_desde', 'Creado desde'],
  ['fecha_hasta', 'Creado hasta'],
  ['activo_id', 'Equipo'],
]

/**
 * La celda de «Equipo»: el nombre arriba y debajo qué clase de equipo es.
 *
 * El nombre del equipo en el inventario importado ya lleva el tipo pegado al
 * final —«Computadora N°01 - CPU»— y el conjunto al que pertenece es su prefijo.
 * Antes se mostraba el nombre y debajo el conjunto: la misma línea dos veces, y
 * como la columna es estrecha el «- CPU» era justo lo que se cutraba, así que no
 * había forma de saber si lo que se veía era una CPU o una impresora.
 *
 * Aquí el tipo baja a su propia línea y, si ya estaba escrito al final del nombre,
 * se quita de ahí para no repetirlo. El conjunto solo aparece cuando aporta algo:
 * cuando no es el comienzo del nombre.
 */
function CeldaEquipo({
  ticket,
}: {
  ticket: { activo_nombre?: string | null; activo_tipo?: string | null; conjunto_nombre?: string | null }
}) {
  const nombre = (ticket.activo_nombre ?? '').trim()
  const tipo = ticket.activo_tipo?.trim() || ''
  const conjunto = ticket.conjunto_nombre?.trim() || ''

  // «Computadora N°01 - CPU» con tipo CPU pasa a «Computadora N°01». Solo se toca
  // si el final coincide de verdad con el tipo: si el nombre dice otra cosa, se
  // deja intacto, porque ahí el guion forma parte del nombre y no del tipo.
  const limpio = tipo && nombre.toLowerCase().endsWith(`- ${tipo.toLowerCase()}`)
    ? nombre.slice(0, -(tipo.length + 2)).trim()
    : nombre

  const conjuntoAporta = Boolean(conjunto) && !limpio.toLowerCase().startsWith(conjunto.toLowerCase())
  const detalle = tipo || (conjuntoAporta ? conjunto : '')

  return (
    <span className="block min-w-0" title={nombre}>
      {/* `truncate` y no `line-clamp-1`. Antes se eligió `line-clamp-1` porque
          `truncate` —que impide el ajuste— dejaba que el navegador ensanchara esta
          columna por su cuenta y el ancho declarado no se cumplía. Eso ya no
          pasa: con `table-fixed` y el `<colgroup>` manda el ancho, y un texto más
          largo que la celda se corta con puntos en vez de ensancharla.

          El cambio de verdad es porque `line-clamp-1` **no estaba recortando**:
          «Mouse · Computadora N°2» salía partido en dos líneas —«Mouse ·
          Computadora» y «N°2»— y descuadraba el alto de esa fila frente a las
          demás. Las dos líneas de esta celda son una cosa cada una —el nombre y
          el detalle—, así que cada una tiene que ocupar exactamente una. */}
      <span className="block truncate">{limpio || nombre}</span>
      {detalle ? (
        <span className="block truncate text-2xs text-muted-foreground">
          {tipo}
          {tipo && conjuntoAporta ? ` · ${conjunto}` : ''}
        </span>
      ) : null}
    </span>
  )
}

/**
 * Un caso sin equipo enlazado, pero con el tipo anotado.
 *
 * Salía «Sin equipo» y con eso tiraba el dato: quien registra el caso elige
 * «Es un CPU» y al guardarlo la celda decía que no había equipo. El tipo estaba
 * guardado y no se enseñaba, que es peor que no tenerlo —parecía que al registrar
 * se hubiera perdido algo—.
 *
 * El tipo solo no lleva nombre ni zona porque es que no los tiene: no se sabe qué
 * máquina es. Por eso la segunda línea lo dice, en vez de dejar un «CPU» suelto que
 * parece el nombre de un equipo.
 */
function CeldaEquipoSinEquipo({ tipo }: { tipo?: string | null }) {
  return (
    <span className="block min-w-0" title={tipo ? `Es un ${tipo}, sin identificar` : undefined}>
      <span className="block truncate font-medium text-foreground">{tipo ?? 'Sin equipo'}</span>
      <span className="block truncate text-2xs text-muted-foreground">
        {tipo ? 'Sin identificar' : 'No se eligió ninguno'}
      </span>
    </span>
  )
}

function etiquetaDeFiltro(
  clave: string,
  valor: string,  listas: { zonas: { id: string; nombre: string }[]; oficinas: { id: string; nombre: string }[]; tecnicos: { id: string; nombre: string }[] },
): string {
  if (clave === 'prioridad') return PRIORIDADES[valor]?.texto ?? valor
  if (clave === 'estado') return estadoDe(valor).texto
  if (clave === 'sla') return OPCIONES_SLA.find((item) => item.valor === valor)?.etiqueta ?? valor
  if (clave === 'fecha_desde' || clave === 'fecha_hasta') return fechaCorta(valor)
  if (clave === 'zona_id') return listas.zonas.find((zona) => zona.id === valor)?.nombre ?? valor
  if (clave === 'oficina_id') return listas.oficinas.find((oficina) => oficina.id === valor)?.nombre ?? valor
  if (clave === 'tecnico_id') return listas.tecnicos.find((tecnico) => tecnico.id === valor)?.nombre ?? valor
  return valor
}

export function Bandeja({
  vistaFija = false,
  vistaInicial = 'abiertos',
  /** Fija el filtro por técnico: así «Mis asignaciones» no puede mostrar otras. */
  soloTecnico,
  /**
   * Recorta la fila de vistas rápidas a las que tienen sentido aquí.
   *
   * En «Historial y casos críticos» la fila completa era una segunda navegación
   * sobre una pantalla que ya tiene sus propias pestañas: ofrecía «Abiertos»,
   * «Sin asignar» y «SLA en riesgo», que son atajos de la cola abierta, dentro
   * de la página del historial. Se ofrecen solo las dos que esa pantalla muestra.
   */
  vistas,
  titulo,
  accionesExtra,
}: {
  vistaFija?: boolean
  vistaInicial?: string
  soloTecnico?: string
  /** Claves permitidas de `VISTAS_RAPIDAS`. Sin este valor, se ofrecen todas. */
  vistas?: readonly string[]
  titulo?: string
  /** Botones extra en el encabezado (los usa «Tickets cerrados»). */
  accionesExtra?: React.ReactNode
}) {
  const sesion = useSesion()
  const avisos = useAvisos()
  const navegar = useNavigate()
  const invalidar = useQueryClient()
  const [parametros, setParametros] = useSearchParams()

  /**
   * Las vistas que esta pantalla ofrece, ya recortadas.
   *
   * Sin recorte son las cinco. Una clave que no exista en la lista se descarta,
   * para que un `?vista=` escrito a mano no rompa la fila.
   */
  const vistasDisponibles = useMemo(
    () => (vistas ? VISTAS_RAPIDAS.filter((item) => vistas.includes(item.clave)) : VISTAS_RAPIDAS),
    [vistas],
  )

  const [texto, setTexto] = useState(parametros.get('texto') ?? '')
  const [mostrarFiltros, setMostrarFiltros] = useState(false)
  const [guardandoVista, setGuardandoVista] = useState(false)
  const [vistaGuardada, setVistaGuardada] = useState(false)
  const [nombreVista, setNombreVista] = useState('')
  const [eliminandoVista, setEliminandoVista] = useState<string | null>(null)
  const [destacados, setDestacados] = useState<string[]>([])
  const [columnasVisibles, setColumnasVisibles] = useState<string[]>([])
  /** Columnas que trajo una vista guardada al abrirla; `null` si no hay. */
  const [columnasDeVista, setColumnasDeVista] = useState<string[] | null>(null)

  /**
   * Vista rápida activa. La URL manda porque es la que usan los indicadores del
   * resumen; `vistaInicial` solo decide cuando no viene ninguna.
   */
  const vistaActiva = useMemo(() => {
    if (vistaFija) return vistaInicial
    if (soloTecnico) return 'mios'
    const pedida = CLAVES_ANTIGUAS[parametros.get('vista') ?? ''] ?? parametros.get('vista') ?? vistaInicial
    // Si la página recorta las vistas, la URL no puede dejar una que no existe:
    // se cae en la inicial de esa página, no en la primera de la fila.
    const permitidas = vistasDisponibles.map((item) => item.clave)
    return permitidas.includes(pedida) ? pedida : permitidas.includes(vistaInicial) ? vistaInicial : permitidas[0]
  }, [parametros, vistaInicial, soloTecnico, vistasDisponibles, vistaFija])

  const filtrosGuardados = useMemo(() => {
    // Un filtro fijo tiene prioridad sobre la URL: es la definición de la vista
    if (soloTecnico) return { tecnico_id: soloTecnico, solo_abiertos: true } as Partial<FiltrosTicket>

    // Antes esta función ignoraba `?vista=`, así que las pestañas y los enlaces
    // del resumen cambiaban la URL sin cambiar una sola fila de la tabla.
    const deVista = VISTAS_RAPIDAS.find((item) => item.clave === vistaActiva)?.filtros ?? {}

    const sueltos: Partial<FiltrosTicket> = {}
    for (const [clave, definicion] of Object.entries(FILTROS_URL)) {
      const valor = (definicion.lectura ?? ((p: URLSearchParams) => p.get(clave)))(parametros)
      if (conValor(valor)) (sueltos as Record<string, unknown>)[clave] = valor
    }

    // Lo explícito va después de la vista, así que un filtro puesto a mano gana;
    // los valores vacíos se descartan para no borrar lo que la vista trajo.
    return {
      ...deVista,
      ...sueltos,
    }
  }, [vistaActiva, parametros, soloTecnico])

  const [filtros, setFiltros] = useState<FiltrosTicket>({ pagina: 1, por_pagina: 20 })

  // La URL es la fuente: si alguien recarga o comparte, vuelve al mismo filtro
  useEffect(() => {
    const nuevos: FiltrosTicket = {
      ...(texto.trim() ? { texto: texto.trim() } : {}),
      ...Object.fromEntries(
        Object.entries(filtrosGuardados).filter(([, valor]) => Boolean(valor) && valor !== ''),
      ),
      pagina: Number(parametros.get('pagina') ?? 1),
      por_pagina: 20,
      orden: 'antiguedad',
      direccion: 'desc',
    }
    setFiltros(nuevos)
  }, [texto, filtrosGuardados, parametros])

  const tickets = useTickets(filtros)
  const zonas = useZonas()
  const oficinas = useOficinas(filtros.zona_id ? { zona_id: filtros.zona_id } : {})
  const tecnicos = useTecnicos()
  const guardadas = useVistasGuardadas()

  useEffect(() => {
    document.title = 'Bandeja de tickets · Mesa de Ayuda TI'
  }, [])

  const cambiarFiltro = (clave: string, valor: string | boolean) => {
    const nuevos = new URLSearchParams(parametros)
    if (!valor) nuevos.delete(clave)
    else nuevos.set(clave, String(valor))
    nuevos.set('pagina', '1')
    setParametros(nuevos)
    // A partir de aquí ya no es la vista guardada la que manda: sus columnas
    // dejarían de corresponder a lo que se está viendo.
    setColumnasDeVista(null)
  }

  const irPagina = (pagina: number) => {
    const nuevos = new URLSearchParams(parametros)
    nuevos.set('pagina', String(pagina))
    setParametros(nuevos)
  }

  const refrescar = async () => {
    await invalidar.invalidateQueries({ queryKey: ['tickets'] })
    setDestacados(tickets.data?.items.map((ticket) => ticket.id) ?? [])
    window.setTimeout(() => setDestacados([]), 2000)
  }

  const columnas: ColumnaTabla<TicketResumen>[] = useMemo(
    () => [
      {
        accessorKey: 'codigo',
        header: 'Ticket',
        meta: { ancho: '17%' },
        cell: ({ row }) => (
          <span className="block min-w-0">
            <span className="block font-mono text-2xs font-bold">{row.original.codigo}</span>
            <span className="line-clamp-2 font-medium" title={row.original.asunto}>{row.original.asunto}</span>
          </span>
        ),
      },
      {
        accessorKey: 'afectado_nombre',
        header: 'Afectado',
        // Sin recorte, por lo mismo que el estado: aquí viven insignias de zona y
        // de oficina, y recortadas se partían a media palabra. El nombre largo de
        // verdad se recorta con puntos suspensivos, que es lo único que funciona
        // con texto.
        meta: { celdaLibre: true, ancho: '12%' },
        cell: ({ row }) => (
          <span className="block min-w-0">
            <span className="block truncate" title={row.original.reporte_para === 'oficina' ? 'Equipo compartido de la oficina' : row.original.afectado_nombre}>{row.original.reporte_para === 'oficina' ? 'Reporte de oficina' : row.original.afectado_nombre}</span>
            {/* Oficina con su raya y debajo la pastilla de zona, siempre en ese
                orden y siempre en dos líneas. Antes el reparto dependía del hueco
                que dejaba la columna de estado, y la misma celda se leía de una
                manera en «Cerrados» y de otra en «Abiertos». */}
            <Ubicacion
              zonaId={row.original.zona_id}
              zonaNombre={row.original.zona_nombre}
              colorIndice={zonas.data?.items.find((zona) => zona.id === row.original.zona_id)?.color_indice}
              oficinaId={row.original.oficina_id}
              oficinaNombre={row.original.oficina_nombre}
            />
          </span>
        ),
      },
      {
        accessorKey: 'estado',
        /*
          Estado y prioridad van en la misma casilla, así que la cabecera explica
          qué es cada pastilla y cada pastilla se explica al pasar el ratón. Antes
          eran dos círculos de colores sin rótulo: no se sabía cuál era cuál, y
          encima «Resuelto» y «Cerrado» son dos finales parecidos, lo que hace
          todavía más difícil leerlos de un vistazo.
        */
        header: () => (
          <span title="El estado dice en qué situación está el caso; la prioridad, cuánta urgencia tiene.">
            Estado y prioridad
          </span>
        ),
        // Sin recorte: una insignia no puede encogerse, y con la celda recortada
        // aparecía partida por la mitad, con el borde redondeado cortado. Aquí las
        // dos ocupan las líneas que necesiten y siempre se leen enteras.
        // El ancho está declarado porque «Estado y prioridad» es el título más
        // largo de la tabla: con menos de 190 px se partía en dos líneas en una
        // vista y no en la otra, y el encabezado quedaba descuadrado.
        meta: { celdaLibre: true, ancho: '15%' },
        cell: ({ row }) => (
          <span className="flex flex-col items-start gap-1.5">
            <EstadoBadge estado={row.original.estado} tamano="sm" />
            <PrioridadBadge prioridad={row.original.prioridad} tamano="sm" />
          </span>
        ),
      },
      {
        id: 'sla',
        accessorFn: ticket => {
          const minutos = ticket.sla?.activo === false ? ticket.sla.minutos_transcurridos : ticket.sla?.minutos_restantes
          return typeof minutos === 'number' ? minutos : undefined
        },
        header: 'SLA',
        sortUndefined: 'last',
        sortDescFirst: false,
        meta: { ancho: '17%' },
        cell: ({ row }) => row.original.sla ? <span className="block min-w-32 whitespace-nowrap">
          <SlaBadge estado={row.original.sla.estado} minutos={row.original.sla.minutos_restantes} minutosTranscurridos={row.original.sla.minutos_transcurridos} activo={row.original.sla.activo} modo={row.original.sla.modo} tamano="sm" />
          <BarraProgreso etiqueta={row.original.sla.activo ? 'Parte del tiempo permitido ya usada' : 'Tiempo de trabajo que se tardó, sobre el que tenía'} valor={row.original.sla.progreso} tono={row.original.sla.activo ? 'carga' : 'neutro'} rotuloVisible={false} />
        </span> : <span className="text-sm text-muted-foreground">—</span>,
      },
      {
        accessorKey: 'activo_nombre',
        header: 'Equipo',
        // `celdaLibre` porque aquí solo hay texto, y el envoltorio que recorta en
        // una línea impedía que la columna encogiera a su ancho declarado: el
        // navegador la ensanchaba al contenido y el ancho depended de qué
        // equipos hubiera en cada vista. Sin el recorte la celda sí baja al ancho
        // declarado, y el nombre se corta con `line-clamp-1` por dentro.
        // 15 % porque el nombre del equipo es lo más largo de la fila después del
        // asunto: «Computadora N°01» no cabía en 13 % y se partía en dos líneas,
        // lo que descuadraba el alto de todas las filas de la tabla.
        meta: { celdaLibre: true, ancho: '15%' },
        // Sin esta columna el historial no decía qué equipo se reparó, que es
        // justo lo que se busca al revisar casos ya cerrados.
        cell: ({ row }) =>
          row.original.activo_nombre ? (
            <CeldaEquipo ticket={row.original} />
          ) : (
            <CeldaEquipoSinEquipo tipo={row.original.activo_tipo} />
          ),
      },
      {
        accessorKey: 'tecnico_nombre',
        header: 'Técnico',
        meta: { celdaLibre: true, ancho: '11%' },
        cell: ({ row }) =>
          row.original.tecnico_nombre ? (
            <span className="line-clamp-1 break-words">{row.original.tecnico_nombre}</span>
          ) : (
            <span className="text-sm font-semibold text-warning-strong">Sin asignar</span>
          ),
      },
      {
        accessorKey: 'actualizado_en',
        header: 'Actualizado',
        // 13 % para que el contenido («hace 15 horas», que no se parte nunca) quepa
        // sin barra horizontal. Los siete porcentajes suman 100: por eso las
        // columnas salen exactamente iguales en las tres vistas y en cualquier
        // ancho de pantalla.
        meta: { ancho: '13%' },
        cell: ({ row }) => <span className="text-sm whitespace-nowrap">{desdeHace(row.original.actualizado_en)}</span>,
      },
    ],
    [zonas.data],
  )

  /**
   * Qué se guarda en una vista, en palabras y con los valores reales de ahora.
   * El diálogo la muestra antes de guardar: si no se dice qué incluye, el botón
   * parece no filtrar nada porque no se sabe qué se está guardando.
   */
  const partesDeLaVista = useMemo(() => {
    const partes: string[] = []
    const vista = VISTAS_RAPIDAS.find((item) => item.clave === vistaActiva)
    if (vista) partes.push(`Vista: ${vista.texto}`)
    if (texto.trim()) partes.push(`Búsqueda: «${texto.trim()}»`)
    const listas = {
      zonas: zonas.data?.items ?? [],
      oficinas: oficinas.data?.items ?? [],
      tecnicos: tecnicos.data?.items ?? [],
    }
    for (const [clave, etiqueta] of ETIQUETAS_FILTRO) {
      // `estado` admite varios: se muestran todos, no solo el primero.
      const valores = clave === 'estado' ? parametros.getAll(clave) : [parametros.get(clave) ?? '']
      const conValor = valores.filter((valor) => Boolean(valor))
      if (conValor.length) {
        partes.push(`${etiqueta}: ${conValor.map((valor) => etiquetaDeFiltro(clave, valor, listas)).join(', ')}`)
      }
    }
    return partes
  }, [vistaActiva, texto, parametros, zonas.data, oficinas.data, tecnicos.data])

  /**
   * Abre una vista guardada.
   *
   * Todo lo que la vista guardó vuelve por la URL, que es la fuente de la tabla.
   * Antes se perdían tres cosas y por eso el botón «parecía que no hacía nada»:
   *
   * 1. La vista rápida de la que se guardó (`sin_asignar`, `criticos`,
   *    `cerrados`): se guardaba en el campo `vista` del registro y al abrirla no
   *    se leía, así que la cola volvía a la de por defecto.
   * 2. Las listas de valores: un `estado: ['cerrado']` se volcaba con
    *    `String(...)` y quedaba una lista de valores mogida en un solo parametro, que
    *    no corresponde a ningun estado.
   * 3. El texto buscado, que quedaba solo en el registro.
   *
   * Además se invalidan los tickets: si el filtro resultante es el mismo que ya
   * se está viendo, la consulta no se vuelve a lanzar y la tabla no se mueve.
   */
  const aplicarVista = async (vista: VistaGuardada) => {
    const guardados = (vista.filtros ?? {}) as Record<string, unknown>
    const nuevos = new URLSearchParams()

    // 1. La vista rápida, que es un filtro en sí misma
    const clave = typeof guardados.vista === 'string' ? guardados.vista : (vista.vista ?? '')
    if (VISTAS_RAPIDAS.some((item) => item.clave === clave)) nuevos.set('vista', clave)

    // 2. Los filtros de la lista, cada valor por separado
    for (const [nombre, definicion] of Object.entries(FILTROS_URL)) {
      const valor = guardados[nombre]
      if (!conValor(valor as string | string[] | boolean | null)) continue
      for (const elemento of Array.isArray(valor) ? valor : [valor]) {
        const escrito = definicion.forma ? definicion.forma(elemento) : String(elemento)
        if (escrito) nuevos.append(nombre, escrito)
      }
    }
    nuevos.set('pagina', '1')

    // 3. El texto de la búsqueda
    const textoGuardado = typeof guardados.texto === 'string' ? guardados.texto : ''

    setParametros(nuevos)
    setTexto(textoGuardado)

    // Las columnas que guardó la vista; si no trajo, manda la preferencia
    const propias = Array.isArray(vista.columnas)
      ? vista.columnas.filter((columna): columna is string => typeof columna === 'string')
      : []
    setColumnasDeVista(propias.length ? propias : null)

    await invalidar.invalidateQueries({ queryKey: ['tickets'] })
    avisos.aviso(`Vista «${vista.nombre}» aplicada.`)
  }

  const guardarVista = async () => {
    setGuardandoVista(true)
    try {
      // Se guardan solo los filtros que la tabla entiende, y se toman de
      // `filtrosGuardados` (lo que hay en la URL) en vez de `filtros` (que ya
      // trae la página y el tamaño): lo que se guarda es lo que filtra.
      const aGuardar: Record<string, unknown> = { vista: vistaActiva }
      for (const clave of Object.keys(FILTROS_URL)) {
        const valor = (filtrosGuardados as Record<string, unknown>)[clave]
        if (!conValor(valor as string | string[] | boolean | null)) continue
        aGuardar[clave] = valor
      }
      if (texto.trim()) aGuardar.texto = texto.trim()

      await api.crear('/vistas-guardadas', {
        nombre: nombreVista.trim(),
        vista: vistaActiva,
        filtros: aGuardar,
        columnas: columnasVisibles.length ? columnasVisibles : null,
        compartida: sesion.puede('vistas.compartidas'),
      })
      avisos.exito(
        'Vista guardada',
        partesDeLaVista.length
          ? `«${nombreVista.trim()}» guarda: ${partesDeLaVista.join(' · ')}.`
          : `«${nombreVista.trim()}» guarda la cola tal como está ahora, sin filtros.`,
      )
      setVistaGuardada(false)
      setNombreVista('')
      await guardadas.refetch()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardandoVista(false)
    }
  }

  const borrarVista = async (id: string) => {
    try {
      await api.borrar(`/vistas-guardadas/${id}`)
      setEliminandoVista(null)
      await guardadas.refetch()
      avisos.exito('Vista eliminada')
    } catch (fallo) {
      avisos.desdeError(fallo)
    }
  }

  const hayFiltros = Boolean(
    texto ||
      vistaActiva !== 'abiertos' ||
      ['estado', 'prioridad', 'zona_id', 'oficina_id', 'tecnico_id', 'sla', 'activo_id', 'categoria', 'fecha_desde', 'fecha_hasta']
        .some((clave) => parametros.get(clave)),
  )

  /**
   * Huella de lo que se está viendo ahora, y de cada vista guardada.
   *
   * La vista guardada que coincide se pinta distinta: es la forma de saber, de
   * un vistazo, por qué la tabla muestra lo que muestra. Y en cuanto se cambia
   * cualquier filtro a mano deja de coincidir y se apaga, porque ya no es esa
   * vista la que manda.
   */
  const huellaActual = useMemo(() => huellaDe(filtrosGuardados, texto), [filtrosGuardados, texto])

  const vistaAplicada = useMemo(() => {
    const candidatas: string[] = []
    for (const item of guardadas.data?.items ?? []) {
      const guardados = (item.filtros ?? {}) as Record<string, unknown>
      const textoGuardado = typeof guardados.texto === 'string' ? guardados.texto : ''
      const candidatos = filtrosEffectivos(item.vista ?? (typeof guardados.vista === 'string' ? guardados.vista : undefined), guardados)
      if (huellaDe(candidatos as Partial<FiltrosTicket>, textoGuardado) === huellaActual) {
        candidatas.push(item.id)
      }
    }
    return candidatas
  }, [guardadas.data, huellaActual])

  return (
    <>
      <PageHeader
        titulo={
          titulo ??
          /*
            El encabezado tiene que decir qué se está viendo. Antes salía siempre
            «Abiertos»: el título salía de la vista inicial, que no cambia al
            pulsar un botón, así que al abrir «Críticos» o «Sin asignar» seguía
           «Abiertos» encima de una tabla que no era esa.
          */
          (vistasDisponibles.find((v) => v.clave === vistaActiva)?.texto ?? 'Bandeja de tickets')
        }
        descripcion={parametros.get('activo_id')
          ? 'Tickets asociados al equipo seleccionado. Usa Limpiar para ver todos los tickets.'
          : 'Filtra por estado, prioridad, zona o persona. Guarda las combinaciones que repites.'}
        acciones={
          <>
            {accionesExtra}
            <Button
              variante="secundario"
              icono={<RotateCw size={16} aria-hidden="true" />}
              onClick={() => void refrescar()}
            >
              Actualizar
            </Button>
            <Button variante="destacado" icono={<Inbox size={16} aria-hidden="true" />} onClick={() => navegar('/panel/tickets/nuevo')}>
              Registrar ticket
            </Button>
          </>
        }
      />

      {/* Vistas guardadas por la API */}
      {(guardadas.data?.items.length ?? 0) > 0 ? (
        <div className="no-imprimir flex flex-wrap items-center gap-1.5">
          <span className="flex items-center gap-1 text-2xs font-semibold text-muted-foreground uppercase">
            <Bookmark size={12} aria-hidden="true" />
            Vistas guardadas
          </span>
          {guardadas.data?.items.map((item) => {
            const aplicada = vistaAplicada.includes(item.id)
            return (
              <span
                key={item.id}
                className={cn(
                  'inline-flex items-center overflow-hidden rounded-full border transition-colors',
                  aplicada
                    ? 'border-primary bg-primary-soft'
                    : 'border-border bg-surface hover:bg-muted',
                )}
                title={aplicada
                  ? `Estás viendo los tickets de «${item.nombre}». Cambia cualquier filtro y se desmarca.`
                  : `Ver los tickets de «${item.nombre}»`}
              >
                <button
                  type="button"
                  onClick={() => void aplicarVista(item)}
                  aria-current={aplicada ? 'true' : undefined}
                  className={cn(
                    'px-2.5 py-1 text-sm transition-colors',
                    // El grosor acompaña al color: no se señala solo con el tono.
                    aplicada ? 'font-semibold text-primary-strong' : 'font-medium text-foreground',
                  )}
                >
                  {item.nombre}
                </button>
                {item.puede_editar ? (
                  <button
                    type="button"
                    onClick={() => setEliminandoVista(item.id)}
                    aria-label={`Eliminar la vista ${item.nombre}`}
                    className={cn(
                      'border-l px-1.5 py-1 transition-colors',
                      aplicada
                        ? 'border-primary/30 text-primary-strong hover:bg-primary hover:text-primary-foreground'
                        : 'border-border text-muted-foreground hover:bg-muted hover:text-destructive-strong',
                    )}
                  >
                    <X size={12} aria-hidden="true" />
                  </button>
                ) : null}
              </span>
            )
          })}
        </div>
      ) : null}

      {/* Barra de búsqueda y filtros */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <SearchInput
          etiqueta="Buscar tickets"
          className="sm:flex-1"
          valor={texto}
          alCambiar={(valor) => {
            setTexto(valor)
            irPagina(1)
          }}
          placeholder="Por código, asunto, persona o equipo…"
        />
        <Button
          variante={mostrarFiltros ? 'primario' : 'secundario'}
          icono={<Filter size={16} aria-hidden="true" />}
          onClick={() => setMostrarFiltros((valor) => !valor)}
          aria-expanded={mostrarFiltros}
        >
          Filtros
        </Button>
        {hayFiltros ? (
          <Button
            variante="secundario"
            icono={<X size={16} aria-hidden="true" />}
            onClick={() => {
              setTexto('')
              setParametros(new URLSearchParams())
              setColumnasDeVista(null)
            }}
          >
            Limpiar
          </Button>
        ) : null}
        <Button variante="secundario" icono={<Bookmark size={16} aria-hidden="true" />} onClick={() => setVistaGuardada(true)}>
          Guardar vista
        </Button>
      </div>

      {mostrarFiltros ? (
        <Panel titulo="Filtros">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Select
              etiqueta="Estado"
              value={parametros.get('estado') ?? ''}
              onChange={(evento) => cambiarFiltro('estado', evento.target.value)}
              placeholder="Todos"
              opciones={Object.values(ESTADOS).map((item) => ({ valor: item.clave, etiqueta: item.texto }))}
            />
            <Select
              etiqueta="Prioridad"
              value={parametros.get('prioridad') ?? ''}
              onChange={(evento) => cambiarFiltro('prioridad', evento.target.value)}
              placeholder="Todas"
              opciones={Object.values(PRIORIDADES).map((item) => ({ valor: item.clave, etiqueta: item.texto }))}
            />
            <Select
              etiqueta="Zona"
              value={parametros.get('zona_id') ?? ''}
              onChange={(evento) => cambiarFiltro('zona_id', evento.target.value)}
              placeholder="Todas"
              opciones={(zonas.data?.items ?? []).map((zona) => ({ valor: zona.id, etiqueta: zona.nombre }))}
            />
            <Select
              etiqueta="Oficina"
              value={parametros.get('oficina_id') ?? ''}
              onChange={(evento) => cambiarFiltro('oficina_id', evento.target.value)}
              placeholder="Todas"
              opciones={(oficinas.data?.items ?? []).map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
            />
            <Select
              etiqueta="Técnico"
              value={parametros.get('tecnico_id') ?? ''}
              onChange={(evento) => cambiarFiltro('tecnico_id', evento.target.value)}
              placeholder="Todos"
              opciones={(tecnicos.data?.items ?? []).map((tecnico) => ({ valor: tecnico.id, etiqueta: tecnico.nombre }))}
            />
            <Select
              etiqueta="SLA"
              value={parametros.get('sla') ?? ''}
              onChange={(evento) => cambiarFiltro('sla', evento.target.value)}
              placeholder="Todos"
              opciones={OPCIONES_SLA}
            />
            <Select
              etiqueta="Categoría"
              value={parametros.get('categoria') ?? ''}
              onChange={(evento) => cambiarFiltro('categoria', evento.target.value)}
              placeholder="Todas"
              opciones={['Hardware', 'Software', 'Red', 'Accesos', 'Correo'].map((valor) => ({ valor, etiqueta: valor }))}
            />
          </div>

          {/* El rango de fechas filtra por día de creación, en la zona horaria de
              negocio: la API convierte el límite al día laborable correspondiente. */}
          <div className="mt-3 grid grid-cols-1 gap-3 border-t border-border pt-3 sm:grid-cols-2 xl:grid-cols-4">
            <Input
              type="date"
              etiqueta="Creado desde"
              ayuda="Incluye todo el día."
              value={parametros.get('fecha_desde') ?? ''}
              max={parametros.get('fecha_hasta') || undefined}
              onChange={(evento) => cambiarFiltro('fecha_desde', evento.target.value)}
            />
            <Input
              type="date"
              etiqueta="Creado hasta"
              ayuda="Incluye todo el día."
              value={parametros.get('fecha_hasta') ?? ''}
              min={parametros.get('fecha_desde') || undefined}
              onChange={(evento) => cambiarFiltro('fecha_hasta', evento.target.value)}
            />
          </div>
        </Panel>
      ) : null}

      {/* Las vistas rápidas no tienen sentido cuando el filtro ya viene fijo */}
      {!soloTecnico && !vistaFija ? (
        <div className="no-imprimir mt-3 flex flex-wrap gap-2" role="tablist" aria-label="Vistas rápidas">
          {vistasDisponibles.map((item) => {
            const activa = vistaActiva === item.clave
            return (
              <button
                key={item.clave}
                type="button"
                role="tab"
                aria-selected={activa}
                onClick={() => {
                  /*
                    «Abiertos» es la vista sin filtro, y por eso es la única que
                    borra la URL. Todas las demás van por `?vista=`. Se comprobaba
                    si la vista traía `vista` o `estado`, y «SLA en riesgo» no trae
                    ninguna de las dos: se quedaba sin filtro y saltaba a
                    «Abiertos». Se decide por la clave, que es lo único fiable.
                  */
                  setParametros(item.clave === 'abiertos' ? new URLSearchParams() : new URLSearchParams({ vista: item.clave }))
                  setTexto('')
                  setColumnasDeVista(null)
                }}
                className={cn(
                  /*
                    No se miden como los botones de al lado. Son navegación, no
                    acciones: alineados a los 40 px de «Filtros» y «Limpiar» la
                    fila pesaba más que la tabla que está debajo. A 36 px, que es
                    lo que mide el texto con aire alrededor, y se distinguen por el
                    borde y el relleno, no por el tamaño.
                  */
                  'inline-flex h-9 items-center rounded-full border px-3.5 text-sm font-medium transition-colors',
                  activa
                    ? 'border-primary bg-primary-soft font-semibold text-primary-strong'
                    : 'border-border bg-surface text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {item.texto}
              </button>
            )
          })}
        </div>
      ) : null}

      {/* La franja lateral no se descifra sola: la leyenda dice qué significa
          cada color, y cada fila sigue mostrando su estado y su SLA con palabras. */}
      {!soloTecnico ? (
        <ul className="no-imprimir mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-muted-foreground">
          {LEYENDA.map((item) => (
            <li key={item.clave} className="flex items-center gap-1.5">
              <span aria-hidden="true" className={item.franja} />
              {item.texto}
            </li>
          ))}
        </ul>
      ) : null}

      {tickets.isError ? (
        <ErrorState
          mensaje="No pudimos cargar los tickets."
          detalle={tickets.error instanceof Error ? tickets.error.message : undefined}
          alReintentar={() => void tickets.refetch()}
        />
      ) : (tickets.data?.items.length ?? 0) === 0 && !tickets.isLoading ? (
        <EmptyState
          icono={<Inbox size={20} aria-hidden="true" />}
          titulo={hayFiltros ? 'Ningún ticket coincide con estos filtros' : 'No hay tickets todavía'}
          descripcion={
            hayFiltros
              ? 'Prueba con otros filtros o límpialos para ver toda la cola.'
              : 'Cuando alguien reporte un problema aparecerá aquí.'
          }
          accion={
            hayFiltros ? (
              <Button
                onClick={() => {
                  setTexto('')
                  setParametros(new URLSearchParams())
                }}
              >
                Limpiar filtros
              </Button>
            ) : (
              <Button variante="primario" icono={<Plus size={16} aria-hidden="true" />} onClick={() => navegar('/panel/tickets/nuevo')}>
                Registrar un ticket
              </Button>
            )
          }
        />
      ) : (
        <>
          <DataTable
            columnas={columnas}
            datos={tickets.data?.items ?? []}
            claveFila={(fila) => fila.id}
            cargando={tickets.isLoading}
            destacados={destacados}
            columnasConfigurables
            columnasForzadas={columnasDeVista ?? undefined}
            tonoFila={tonoUrgenciaTicket}
            alCambiarColumnas={setColumnasVisibles}
            etiquetaVacia="Ningún ticket coincide con estos filtros."
            alPulsarFila={(fila) => navegar(`/panel/tickets/${fila.id}`)}
            tarjeta={(ticket) => (
              <>
                <div className="flex items-start justify-between gap-2">
                  <p className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-muted px-1.5 py-0.5 text-2xs font-bold">{ticket.codigo}</span>
                    <span className="font-semibold">{ticket.asunto}</span>
                  </p>
                </div>
                <p className="mt-1 flex min-w-0 items-center gap-1 text-sm text-muted-foreground">
                  <span className="min-w-0 max-w-[45%] truncate" title={ticket.reporte_para === 'oficina' ? 'Equipo compartido de la oficina' : ticket.afectado_nombre}>{ticket.reporte_para === 'oficina' ? 'Reporte de oficina' : ticket.afectado_nombre}</span>
                  <span aria-hidden="true">·</span>
                  <span className="min-w-0 flex-1 truncate" title={ticket.oficina_nombre ?? 'Sin oficina'}>{ticket.oficina_nombre ?? 'Sin oficina'}</span>
                  <span className="shrink-0">· {desdeHace(ticket.actualizado_en)}</span>
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <EstadoBadge estado={ticket.estado} tamano="sm" />
                  <PrioridadBadge prioridad={ticket.prioridad} tamano="sm" />
                  {ticket.sla ? <SlaBadge estado={ticket.sla.estado} minutos={ticket.sla.minutos_restantes} minutosTranscurridos={ticket.sla.minutos_transcurridos} activo={ticket.sla.activo} modo={ticket.sla.modo} tamano="sm" /> : null}
                  {ticket.tecnico_nombre ? (
                    <span className="text-2xs text-muted-foreground">{ticket.tecnico_nombre}</span>
                  ) : (
                    <span className="text-2xs font-semibold text-warning-strong">Sin asignar</span>
                  )}
                </div>
              </>
            )}
          />
          <Paginacion
            pagina={tickets.data?.pagina ?? 1}
            totalPaginas={tickets.data?.total_paginas ?? 1}
            total={tickets.data?.total ?? 0}
            porPagina={20}
            alCambiar={irPagina}
          />
        </>
      )}

      <DialogModal
        abierto={vistaGuardada}
        alCerrar={() => setVistaGuardada(false)}
        titulo="Guardar esta vista"
        descripcion="Ponle un nombre y aparecerá como un botón para volver aquí con un clic."
        tamano="sm"
        pie={
          <>
            <Button onClick={() => setVistaGuardada(false)}>Cancelar</Button>
            <Button variante="primario" cargando={guardandoVista} disabled={!nombreVista.trim()} onClick={() => void guardarVista()}>
              Guardar vista
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Input
            etiqueta="Nombre"
            requerido
            value={nombreVista}
            onChange={(evento) => setNombreVista(evento.target.value)}
            placeholder="Por ejemplo: Sin asignar de esta semana"
          />

          {/* Se enumera lo que se guarda con su valor actual. Antes el diálogo
              decía «los filtros y las columnas» sin decir cuáles, y además solo
              guardaba los filtros: por eso parecía no filtrara nada. */}
          <div className="rounded-[var(--radius-panel)] border border-border bg-muted/40 p-3">
            <p className="text-sm font-semibold">Se guarda</p>
            {partesDeLaVista.length ? (
              <ul className="mt-1.5 flex flex-col gap-1">
                {partesDeLaVista.map((parte) => (
                  <li key={parte} className="flex items-start gap-1.5 text-sm">
                    <Check size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-success-strong" />
                    <span>{parte}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                No hay filtros puestos: se guardaría la cola completa.
              </p>
            )}
            <ul className="mt-2 flex flex-col gap-0.5 text-2xs text-muted-foreground">
              <li>
                {columnasVisibles.length
                  ? `Las ${columnasVisibles.length} columnas que ves ahora, pero no su orden.`
                  : 'Las columnas que tengas visibles, pero no su orden.'}
              </li>
              <li>Siempre empieza en la primera página.</li>
              <li>
                {sesion.puede('vistas.compartidas')
                  ? 'La verán también los demás técnicos.'
                  : 'Solo la verás tú.'}
              </li>
            </ul>
          </div>
        </div>
      </DialogModal>

      <ConfirmDialog
        abierto={Boolean(eliminandoVista)}
        alCerrar={() => setEliminandoVista(null)}
        alConfirmar={() => void borrarVista(eliminandoVista as string)}
        titulo="Eliminar la vista"
        mensaje="Se quitará de tu lista de vistas guardadas. Los tickets no se modifican."
        textoConfirmar="Eliminar"
        peligro
      />
    </>
  )
}
