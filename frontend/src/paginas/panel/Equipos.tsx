import { etiquetaPropiedad } from '../../dominio/propiedad'
/**
 * Equipos: el inventario.
 *
 * Tabla con filtros por zona, oficina, tipo, estado y texto libre. El buscador
 * por código patrimonial es propio: el backend lo resuelve por texto o código y
 * devuelve un solo equipo, así que va en su propia caja.
 *
 * El alta de equipos vive en un panel lateral (Sheet) con el asistente de
 * registro, para no sacar a nadie del contexto de la lista.
 */

import { Boxes, Download, MoreHorizontal, Plus, Wrench } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { disponibilidadDe, type TonoUrgencia } from '../../dominio/estados'
import { useActivos, useBuscarEquipos, useCatalogoEquipos, useOficinas, useZonas } from '../../api/hooks'
import { consulta } from '../../api/cliente'
import { descargarDeLaApi, nombreDeArchivo } from '../../api/descarga'
import { useAvisos } from '../../estado/useAvisos'
import type { ItemActivo, FiltrosActivos, ItemEquipoBuscado } from '../../api/tipos'
import { CompletitudBadge, DisponibilidadBadge, EstadoCampoBadge } from '../../componentes/dominio/Badge'
import { DataTable, Paginacion, CeldaVacia, type ColumnaTabla } from '../../componentes/dominio/DataTable'
import { RegistroEquipo } from '../../componentes/dominio/RegistroEquipo'
import { Button } from '../../componentes/base/Button'
import { SearchInput, Select } from '../../componentes/base/Campo'
import { PopoverSimple, Sheet } from '../../componentes/base/Sobreposiciones'
import { EmptyState, ErrorState, PageHeader } from '../../componentes/base/Estructura'
import { useSesion } from '../../estado/useSesion'
import { ZonaBadge } from '../../componentes/dominio/ZonaBadge'
import { EnlaceOficina } from '../../componentes/dominio/EnlaceOficina'
import { IconoTipoEquipo } from '../../componentes/dominio/IconoTipoEquipo'

/**
 * Celda del equipo: siempre se ve **qué es**, aunque el nombre no lo diga.
 *
 * El Excel nombra las cosas como quiere: las computadoras traen el nombre del
 * equipo en la red («PULL-D-GV53JNV3») y los monitores, mouses y teclados traen
 * «Computadora N°03 - Monitor». Con el nombre arriba y el tipo en la tercera
 * línea, unas filas parecían nombres y otras parecían tipos.
 *
 *   1. El nombre, o el tipo si el equipo no tiene nombre.
 *   2. **El tipo siempre**, en negrita, seguido de marca, modelo y código.
 *   3. El conjunto como distintivo corto, no como otra línea de texto.
 *
 * Se probó la variante «discreta» —nombre en negrita, tipo en versalita pequeña y
 * el conjunto en un distintivo gris neutro— y no fue la que se quiso: en una tabla
 * de quince filas el tipo en negrita y el distintivo en color son los que dejaban
 * ver de un vistazo de qué equipo se trata. La discreción se queda para el
 * encabezado.
 */
function CeldaEquipo({ equipo }: { equipo: ItemActivo }) {
  /* Antes ponía «Equipo» cuando faltaba el tipo, que es un tipo inventado: parece
     que el equipo es de una categoría llamada «Equipo» y no que falta el dato. Ahora
     se dice «Sin tipo», que es lo que se puede corregir. */
  const tipo = (equipo.tipo ?? '').trim()
  const marcaModelo = [equipo.marca, equipo.modelo].filter(Boolean).join(' ')
  const codigo = equipo.codigo_patrimonial || (equipo.propiedad?.trim().toLocaleLowerCase('es') === 'personal' ? 'No aplica' : 'Sin código')

  /*
    El conjunto solo se muestra cuando **aporta algo**. Con estos datos casi nunca
    lo hace: el equipo se llama «Computadora N°01 - Monitor» y su conjunto es
    «Computadora N°01». Poner el distintivo ahí era repetir el nombre con otras
    palabras, y de paso el nombre se cortaba: «Computadora N°01 -…».

    Es la misma regla que ya usa la columna EQUIPO de la bandeja: si el nombre
    empieza por el del conjunto, el conjunto ya está dicho.
  */
  const conjunto = (equipo.conjunto_nombre || '').trim()
  const conjuntoAporta =
    conjunto.length > 0 && !(equipo.nombre_equipo || '').trim().toLowerCase().startsWith(conjunto.toLowerCase())

  return (
    <span className="flex min-w-0 items-start gap-2">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted">
        <IconoTipoEquipo tipo={equipo.tipo} tamano={24} />
      </span>
      <span className="min-w-0">
        {/*
          El distintivo del conjunto iba en una tercera línea, y eso hacía que las
          filas tuvieran dos alturas: **68 px sin conjunto y 87 px con él**. En la
          tabla se veía el salto: unas filas muy juntas y otras con un hueco debajo.

          Va en la **primera** línea, junto al nombre, y no en la segunda. Se
          probó en la segunda y era peor: al cerrarse el distintivo se comía el
          espacio y el **código patrimonial se cortaba** —«CPU · CYBERLINK CASE…» en
          vez de «CPU · CYBERLINK CASE · 740899500012»—. El código es lo que
          identifica el equipo —461 de 876 lo tienen y **ninguno está repetido**—,
          y el conjunto lo tiene **1 de 876**. No pueden competir por el mismo hueco.

          Así todas las filas miden 68 px y la segunda línea no se toca nunca.
        */}
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0 flex-1 truncate font-medium">{equipo.nombre_equipo || 'Equipo sin nombre'}</span>
          {conjuntoAporta ? (
            <span
              className="flex max-w-[8.5rem] shrink-0 items-center gap-1 rounded-full bg-primary-soft px-1.5 py-px text-2xs font-medium text-primary-strong"
              title={`Forma parte de ${conjunto}`}
            >
              <Boxes size={11} aria-hidden="true" className="shrink-0" />
              <span className="truncate">{conjunto}</span>
            </span>
          ) : null}
        </span>
        <span className="mt-0.5 block truncate text-2xs text-muted-foreground">
          <span className="font-semibold text-foreground">{tipo || 'Sin tipo'}</span>
          {marcaModelo ? ` · ${marcaModelo}` : ''} · {codigo}
        </span>
      </span>
    </span>
  )
}

/**
 * Franja lateral de la fila según el estado del equipo.
 *
 * Se saca del **mismo sitio que la insignia** —`disponibilidadDe`, que es quien
 * normaliza el vocabulario del Excel («inoperativa», «De Baja», «NO LOCALIZADO»
 *…) y decide el color—. Comparar el texto a mano fallaba: el teclado marcado como
 * «Dado de baja» traía otra clave desde la API, se leía bien el color y la fila
 * se quedaba sin franja. Con un solo lugar que decide, insignia y fila nunca
 * pueden contradecirse.
 */
function tonoDeFila(estado: string | null | undefined): TonoUrgencia {
  const tono = disponibilidadDe(estado ?? '').tono
  if (tono === 'destructive') return 'peligro'
  return tono === 'warning' ? 'aviso' : null
}

function leerUbicacionInventario(clave: string): { zona: string; oficina: string; soloFaltantes: boolean; responsablesPendientes: boolean } {
  try {
    const datos = JSON.parse(sessionStorage.getItem(clave) ?? '{}')
    return { zona: typeof datos?.zona === 'string' ? datos.zona : '', oficina: typeof datos?.oficina === 'string' ? datos.oficina : '', soloFaltantes: datos?.soloFaltantes === true, responsablesPendientes: datos?.responsablesPendientes === true }
  } catch { return { zona: '', oficina: '', soloFaltantes: false, responsablesPendientes: false } }
}

export function Equipos() {
  const sesion = useSesion()
  const navegar = useNavigate()
  const [parametros, cambiarParametros] = useSearchParams()
  const claveUbicacion = `inventario.ubicacion.${sesion.usuario?.id ?? ''}`
  const enlaceConUbicacion = parametros.has('zona_id') || parametros.has('oficina_id')
  const responsablesPendientes = parametros.has('responsables_pendientes')
    ? ['1', 'true'].includes(parametros.get('responsables_pendientes') ?? '')
    : leerUbicacionInventario(claveUbicacion).responsablesPendientes
  /*
    «Solo los que les faltan datos». Es el filtro que usan los enlaces de la
    pestaña Calidad: al pulsar una zona no tiene sentido abrir **todas** sus
    máquinas, sino las que están incompletas, que es lo que se va a arreglar.
    El backend ya lo tenía; la pantalla no lo ofrecía.
  */
  const soloFaltantes = parametros.has('solo_faltantes')
    ? ['1', 'true'].includes(parametros.get('solo_faltantes') ?? '')
    : leerUbicacionInventario(claveUbicacion).soloFaltantes

  const soloUsoComun = parametros.get('solo_uso_comun') === '1'
  const [texto, setTexto] = useState(() => parametros.get('texto') ?? '')
  const [zonaId, setZonaId] = useState(() => enlaceConUbicacion ? parametros.get('zona_id') ?? '' : leerUbicacionInventario(claveUbicacion).zona)
  const [oficinaId, setOficinaId] = useState(() => enlaceConUbicacion ? parametros.get('oficina_id') ?? '' : leerUbicacionInventario(claveUbicacion).oficina)
  /*
    El tipo también vive en la URL, como el resto. Antes arrancaba siempre vacío y
    no se escribía nunca, de modo que un enlace como
    `/panel/equipos?tipo=CPU` —el que debería llevar la pestaña «Por tipo de
    equipo» de Calidad— llegaba al inventario **sin filtrar**: un control que
    parece funcionar y no hace nada.
  */
  const [tipo, setTipo] = useState(() => parametros.get('tipo') ?? '')
  const [pagina, setPagina] = useState(1)
  const [agruparPor, setAgruparPor] = useState<'oficina' | 'zona' | 'ninguno'>('oficina')
  const [registrando, setRegistrando] = useState(false)

  const zonaDeEnlace = parametros.get('zona_id') ?? ''
  const oficinaDeEnlace = parametros.get('oficina_id') ?? ''
  useEffect(() => {
    if (!enlaceConUbicacion) return
    setZonaId(zonaDeEnlace)
    setOficinaId(oficinaDeEnlace)
    setPagina(1)
  }, [enlaceConUbicacion, zonaDeEnlace, oficinaDeEnlace])

  useEffect(() => {
    try { sessionStorage.setItem(claveUbicacion, JSON.stringify({ zona: zonaId, oficina: oficinaId, soloFaltantes, responsablesPendientes })) } catch { /* La tabla sigue funcionando si el almacenamiento no está disponible. */ }
  }, [claveUbicacion, zonaId, oficinaId, soloFaltantes, responsablesPendientes])

  useEffect(() => {
    document.title = 'Equipos · Mesa de Ayuda TI'
  }, [])

  const zonas = useZonas()
  const catalogos = useCatalogoEquipos()
  const oficinas = useOficinas(oficinaId || zonaId ? { zona_id: zonaId } : {})
  const avisos = useAvisos()

  const filtros: FiltrosActivos = {
    ...(soloUsoComun ? { solo_uso_comun: 'true' } : {}),
    ...(responsablesPendientes ? { responsables_pendientes: true } : {}),
    ...(soloFaltantes ? { solo_faltantes: true } : {}),
    ...(texto.trim() ? { texto: texto.trim() } : {}),
    ...(zonaId ? { zona_id: zonaId } : {}),
    ...(oficinaId ? { oficina_id: oficinaId } : {}),
    ...(tipo ? { tipo } : {}),
    orden: 'creado_en',
    pagina,
    por_pagina: 25,
  }
  const activos = useActivos(filtros)

  /*
    Descargar el inventario en el Excel del municipio.

    Se manda **la consulta con la que se está viendo la pantalla**, no «todo el
    inventario»: si estás filtrando por una zona y descargas, esperas los equipos de
    esa zona. Y el archivo sale con una hoja por zona y las columnas de la plantilla
    oficial, de modo que se puede volver a subir tal cual —ida y vuelta—.

    La descarga puede tardar con 877 equipos: por eso el botón avisa mientras se arma
    en vez de parecer que no ha pasado nada.
  */
  const [descargando, setDescargando] = useState(false)
  const descargarExcel = async () => {
    setDescargando(true)
    try {
      const parametros = consulta({
        zona_id: zonaId || undefined,
        oficina_id: oficinaId || undefined,
        tipo: tipo || undefined,
        texto: textoBusqueda.trim() || undefined,
        solo_faltantes: soloFaltantes || undefined,
        solo_uso_comun: soloUsoComun || undefined,
      })
      const partes = ['inventario']
      const zonaNombre = zonas.data?.items.find((z) => z.id === zonaId)?.nombre
      if (zonaNombre) partes.push(zonaNombre.toLowerCase().replace(/\s+/g, '-'))
      await descargarDeLaApi(`/activos/excel${parametros}`, nombreDeArchivo(partes.join('-'), 'inventario') + '.xlsx')
      avisos.exito('Inventario descargado', 'El archivo tiene una hoja por zona y se puede volver a subir.')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setDescargando(false)
    }
  }

  /*
    * ¿Hay algún filtro puesto? Es lo que separa «el inventario está vacío» de
    * «los filtros no dejan pasar nada». Sin esto los dos mensajes salían juntos.
    * Se lee de los propios filtros y no del resultado: el total que devuelve la
    * API ya viene filtrado, así que con cero no se puede saber por qué.
    */
  const hayFiltroPuesto = Boolean(
    soloUsoComun || responsablesPendientes || soloFaltantes || texto.trim() || zonaId || oficinaId || tipo,
  )

  // Las coincidencias se consultan con retardo: antes salía una petición por
  // tecla y las respuestas podían llegar desordenadas, dejando en pantalla
  // resultados que no correspondían a lo último escrito.
  const [textoBusqueda, setTextoBusqueda] = useState(texto.trim())
  useEffect(() => {
    const temporizador = window.setTimeout(() => setTextoBusqueda(texto.trim()), 300)
    return () => window.clearTimeout(temporizador)
  }, [texto])

  const resultadosBusqueda = useBuscarEquipos({ texto: textoBusqueda }, textoBusqueda.length > 2)

  const tipos = useMemo(() => {
    const conjunto = new Set<string>()
    for (const item of catalogos.data?.tipos_dispositivo ?? []) conjunto.add(item.valor)
    for (const equipo of activos.data?.items ?? []) if (equipo.tipo) conjunto.add(equipo.tipo)
    return [...conjunto].sort()
  }, [activos.data, catalogos.data])

  const columnas: ColumnaTabla<ItemActivo>[] = useMemo(
      () => [
        {
          accessorKey: 'nombre_equipo',
          header: 'Equipo',
          enableSorting: false,
          cell: ({ row }) => <CeldaEquipo equipo={row.original} />,
        },
        {
          accessorKey: 'oficina_nombre',
          header: 'Ubicación',
          enableSorting: false,
          // Sin recorte: la celda lleva la insignia de zona, y con el recorte de la
          // tabla quedaba partida por la mitad. Los textos de dentro ya se
          // recortan ellos solos con puntos suspensivos.
          meta: { celdaLibre: true },
          cell: ({ row }) => {
            const indice = zonas.data?.items.find((zona) => zona.id === row.original.zona_id)?.color_indice
            /*
              La raya de color de la zona la dibuja `EnlaceOficina`, en su propio
              canto. Antes la celda tenía además un `border-l-4` y la columna
              salía con **dos** rayas paralelas de la zona separadas por un hueco:
              parecía un carácter mal escrito, no un color.
            */
            return <span className="block min-w-0">
              {agruparPor === 'zona' ? (
                <>
                  <ZonaBadge id={row.original.zona_id} nombre={row.original.zona_nombre} colorIndice={indice} />
                  <span className="mt-1 block truncate"><EnlaceOficina id={row.original.oficina_id} nombre={row.original.oficina_nombre} zonaId={row.original.zona_id} colorIndice={indice} /></span>
                </>
              ) : agruparPor === 'oficina' ? (
                <>
                  <span className="block truncate"><EnlaceOficina id={row.original.oficina_id} nombre={row.original.oficina_nombre} zonaId={row.original.zona_id} colorIndice={indice} /></span>
                  <ZonaBadge id={row.original.zona_id} nombre={row.original.zona_nombre} colorIndice={indice} />
                </>
              ) : (
                <span className="block truncate">
                  <EnlaceOficina id={row.original.oficina_id} nombre={row.original.oficina_nombre} zonaId={row.original.zona_id} colorIndice={indice} /> · {row.original.zona_nombre || 'Sin zona'}
                </span>
              )}
            </span>
          },
        },
        { accessorKey: 'responsable_nombre', header: 'Responsable', enableSorting: false, cell: ({ row }) => row.original.responsable_id ? <Link to={`/panel/usuarios/${row.original.responsable_id}`} className="font-medium text-info-strong hover:underline">{row.original.responsable_nombre || 'Ver perfil'}</Link> : <span className="font-medium">Uso común</span> },
        {
          accessorKey: 'estado',
          header: 'Estado',
          enableSorting: false,
          // Sin recorte: aquí vive una insignia, y una insignia recortada aparece
          // partida por la mitad en vez de decir lo que dice.
          meta: { celdaLibre: true },
          cell: ({ row }) => <DisponibilidadBadge estado={row.original.estado} tamano="sm" />,
        },
        {
          accessorKey: 'completitud',
          header: 'Datos',
          enableSorting: false,
          meta: { celdaLibre: true },
          cell: ({ row }) => (
            <CompletitudBadge porcentaje={row.original.completitud} faltantes={row.original.faltantes} />
          ),
        },
        { accessorKey: 'tipo', header: 'Tipo', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.tipo || <CeldaVacia /> },
        { accessorKey: 'conjunto_nombre', header: 'Conjunto', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.conjunto_nombre || <CeldaVacia texto="Este equipo no pertenece a ningún conjunto" /> },
        { accessorKey: 'propiedad', header: 'Propiedad', meta: { soloEscritorio: true }, cell: ({ row }) => etiquetaPropiedad(row.original.propiedad || '') || <CeldaVacia /> },
        { accessorKey: 'tamano_pantalla', header: 'Pantalla', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.tamano_pantalla || <CeldaVacia /> },
        { accessorKey: 'procesador', header: 'Procesador', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.procesador || <CeldaVacia /> },
        { accessorKey: 'memoria_ram', header: 'RAM', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.memoria_ram || <CeldaVacia /> },
        { accessorKey: 'almacenamiento', header: 'Almacenamiento', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.almacenamiento || <CeldaVacia /> },
        { accessorKey: 'direccion_ip', header: 'IP', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.direccion_ip || <CeldaVacia /> },
        { accessorKey: 'direccion_mac', header: 'MAC', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.direccion_mac || <CeldaVacia /> },
        { accessorKey: 'observaciones', header: 'Observaciones', meta: { soloEscritorio: true }, cell: ({ row }) => row.original.observaciones || <CeldaVacia texto="Sin observaciones" /> },
        {
          id: 'menu',
          header: () => <span title="Acciones disponibles para esta fila">Menú</span>,
          enableSorting: false,
          // El botón de acciones siempre está: si se oculta, la fila se queda
          // sin forma de abrirse. Por eso no sale en «Columnas visibles».
          enableHiding: false,
          /*
            Sin `ancho` esta columna era la que impedía que la tabla usara
            `table-fixed`: `conAnchosFijos` exige que **todas** las columnas
            visibles declaren uno, y al faltar este la tabla entera pasaba a
            reparto automático —midiendo 1.028 px dentro de 1.181 y dejando 153
            px de vacío. Con 68 px declarados cabe el botón y la tabla vuelve a
            repartirse igual en todas las vistas.
          */
          meta: { ancho: '68px' },
          cell: ({ row }) => <PopoverSimple
            disparador={<Button tamano="sm" soloIcono variante="fantasma" aria-label={`Acciones de ${row.original.nombre_equipo || row.original.tipo}`} onClick={(evento) => evento.stopPropagation()}><MoreHorizontal size={18} /></Button>}
            contenido={<Link onClick={(evento) => evento.stopPropagation()} className="block rounded px-2 py-1 text-sm hover:bg-muted" to={`/panel/equipos/${row.original.id}`}>Abrir ficha</Link>}
          />,
        },
      ],
      [agruparPor, zonas.data],
    )

  return (
    <>
      <PageHeader
        titulo="Equipos"
        descripcion={
          soloFaltantes
            ? 'Solo los equipos que tienen algún dato sin escribir. Abre su ficha y rellena lo que falte.'
            : responsablesPendientes
              ? 'Equipos con un responsable nombrado en el Excel que todavía no está vinculado a una cuenta. Abre su ficha para asignarlo.'
              : 'Inventario OTIC: cada hoja del Excel corresponde a una zona y cada área a una oficina.'
        }
        acciones={
          <div className="flex flex-wrap items-center gap-2">
            {/*
              Descargar lo que se está viendo. Va antes de «Registrar equipo» y no
              es la acción principal: registrar es lo raro, descargar es lo que se
              hace al entregar el inventario o pasarlo a otra oficina.
            */}
            {sesion.puede('equipos.editar') ? (
              <Button
                variante="secundario"
                icono={<Download size={16} aria-hidden="true" />}
                cargando={descargando}
                onClick={() => void descargarExcel()}
              >
                Descargar Excel
              </Button>
            ) : null}
            {sesion.puede('equipos.crear') ? (
              <Button variante="destacado" icono={<Plus size={16} aria-hidden="true" />} onClick={() => setRegistrando(true)}>
                Registrar equipo
              </Button>
            ) : null}
          </div>
        }
      />

      {/*
        Todas las celdas tienen la misma forma: rótulo arriba y control abajo.
        Antes el buscador y la casilla entraban en la fila de los controles sin
        rótulo propio, y al alternarse con las que sí lo tenían la barra se leía
        como desalineada aunque las medidas coincidieran.
      */}
      <div className="grid grid-cols-1 items-start gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {/*
          El rótulo lo pone `SearchInput`, que ahora lo pinta como `Input` y `Select`.
          Aquí había además una etiqueta propia con `htmlFor="buscar-equipos"`: al no
          existir ese id —el real lo genera `useId`— no enlazaba con nada, y como
          además `SearchInput` pintaba el suyo, se veían **dos** «Buscar equipos» y el
          campo quedaba **150 px** más abajo que los desplegables de al lado. Medido.
        */}
        <SearchInput
          etiqueta="Buscar equipos"
          valor={texto}
          alCambiar={(valor) => {
            setTexto(valor)
            setPagina(1)
          }}
          // Sin palabras que el navegador reconozca como campo de correo o de
          // identidad, que es lo que hacía que ofreciera rellenarlo solo.
          placeholder="Escribe para filtrar…"
          ayuda="Busca en el código patrimonial, el nombre, la marca, el modelo, la IP, la MAC, el conjunto y el responsable."
        />
        <Select
          etiqueta="Zona"
          value={zonaId}
          onChange={(evento) => {
            setZonaId(evento.target.value)
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
          placeholder="Todas"
          opciones={(oficinas.data?.items ?? []).map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
        />
        <Select
          etiqueta="Tipo"
          value={tipo}
          onChange={(evento) => {
            setTipo(evento.target.value)
            const nuevos = new URLSearchParams(parametros)
            if (evento.target.value) nuevos.set('tipo', evento.target.value)
            else nuevos.delete('tipo')
            cambiarParametros(nuevos)
            setPagina(1)
          }}
          placeholder="Todos"
          opciones={tipos.map((valor) => ({ valor, etiqueta: valor }))}
        />
        <Select etiqueta="Asignación" value={soloUsoComun ? 'comun' : 'todos'} onChange={evento => { const nuevos = new URLSearchParams(parametros); if (evento.target.value === 'comun') nuevos.set('solo_uso_comun', '1'); else nuevos.delete('solo_uso_comun'); cambiarParametros(nuevos); setPagina(1) }} opciones={[{ valor: 'todos', etiqueta: 'Todos los equipos' }, { valor: 'comun', etiqueta: 'Compartidos de la oficina' }]} />
        <Select
          etiqueta="Agrupar por"
          value={agruparPor}
          onChange={(evento) => {
            setAgruparPor(evento.target.value as 'oficina' | 'zona' | 'ninguno')
            setPagina(1)
          }}
          opciones={[
            { valor: 'oficina', etiqueta: 'Oficina' },
            { valor: 'zona', etiqueta: 'Zona' },
            { valor: 'ninguno', etiqueta: 'Sin agrupar' },
          ]}
        />
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Datos</span>
          <div className="flex flex-col gap-1.5">
            <label
              className={cn(
                'flex h-[var(--spacing-control)] cursor-pointer items-center gap-2 rounded-[var(--radius-control)] border bg-surface px-3 text-sm transition-colors',
                soloFaltantes ? 'border-primary bg-primary-soft' : 'border-border hover:bg-muted',
              )}
            >
              <input
                type="checkbox"
                checked={soloFaltantes}
                onChange={(evento) => {
                  const nuevos = new URLSearchParams(parametros)
                  if (evento.target.checked) nuevos.set('solo_faltantes', '1')
                  else nuevos.set('solo_faltantes', '0')
                  cambiarParametros(nuevos)
                  setPagina(1)
                }}
              />
              <span className="truncate">Solo los que tienen algún dato sin escribir</span>
            </label>
            <span className="text-2xs text-muted-foreground">
              Para ordenar el trabajo de campo: son los que se pueden completar desde la ficha.
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Responsable del Excel</span>
          <label
            className={cn(
              'flex h-[var(--spacing-control)] cursor-pointer items-center gap-2 rounded-[var(--radius-control)] border bg-surface px-3 text-sm transition-colors',
              responsablesPendientes ? 'border-primary bg-primary-soft' : 'border-border hover:bg-muted',
            )}
          >
            <input
              type="checkbox"
              checked={responsablesPendientes}
              onChange={(evento) => {
                const nuevos = new URLSearchParams(parametros)
                if (evento.target.checked) nuevos.set('responsables_pendientes', '1')
                else nuevos.set('responsables_pendientes', '0')
                cambiarParametros(nuevos)
                setPagina(1)
              }}
            />
            <span className="truncate">El responsable no tiene cuenta</span>
          </label>
          <span className="text-2xs text-muted-foreground">
            Sirve para localizar a quién hay que crearle un acceso. Los equipos de «Uso común» no entran.
          </span>
        </div>
      </div>
      {/*
        Coincidencias de la búsqueda. Antes la lista no tenía alto máximo: con
        25 resultados empujaba la tabla entera y no se veía de un vistazo que
        eran las coincidencias y no la tabla.
      */}
      {textoBusqueda.length > 2 ? (
        <div className="rounded-[var(--radius-panel)] border border-border bg-surface">
          <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
            <p className="text-sm font-semibold">
              {resultadosBusqueda.isLoading
                ? 'Buscando…'
                : `${resultadosBusqueda.data?.items.length ?? 0} coincidencias para «${texto.trim()}»`}
            </p>
            <button
              type="button"
              onClick={() => {
                setTexto('')
                setPagina(1)
              }}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Cerrar
            </button>
          </div>
          {resultadosBusqueda.isError ? (
            <p role="alert" className="px-3 py-2 text-sm text-destructive-strong">
              No se pudieron cargar las coincidencias.
            </p>
          ) : null}
          {!resultadosBusqueda.isLoading && !resultadosBusqueda.isError && (resultadosBusqueda.data?.items.length ?? 0) === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              No hay coincidencias con ese dato. La búsqueda mira el código patrimonial, el nombre, la marca, el modelo, la
              IP, la MAC, el conjunto y el responsable.
            </p>
          ) : null}
          <ul className="sin-barra flex max-h-80 flex-col gap-1 overflow-y-auto p-2">
            {(resultadosBusqueda.data?.items ?? []).map((equipo: ItemEquipoBuscado) => (
              <li key={equipo.id}>
                <button
                  type="button"
                  onClick={() => {
                    // Se limpia antes de navegar: si se vuelve atrás, la tabla
                    // no aparece ya filtrada por un texto que nadie ve.
                    setTexto('')
                    navegar(`/panel/equipos/${equipo.id}`)
                  }}
                  className="flex w-full items-center gap-3 rounded-[var(--radius-control)] p-2 text-left hover:bg-muted"
                >
                  <IconoTipoEquipo tipo={equipo.tipo} tamano={24} />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{equipo.nombre || equipo.tipo}</span>
                    <span className="block truncate text-sm text-muted-foreground">
                      {[equipo.codigo_patrimonial, equipo.oficina_nombre, equipo.responsable_nombre]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {activos.isError ? (
        <ErrorState
          mensaje="No pudimos cargar el inventario."
          detalle={activos.error instanceof Error ? activos.error.message : undefined}
          alReintentar={() => void activos.refetch()}
        />
      ) : (activos.data?.items.length ?? 0) === 0 && !activos.isLoading ? (
        /*
          Aquí faltaba una pregunta: **¿está vacío el inventario, o es que los
          filtros no dejan pasar nada?**

          No se preguntaba, y por eso al buscar «zzzznoexiste» salían **dos**
          estados vacíos a la vez: la franja de «0 coincidencias» y, debajo, este,
          que decía *«registra el primer equipo si el inventario está vacío»*.
          El inventario tiene 876 equipos. Faltaba exactamente el dato que
          distingue las dos cosas, y se daba una instrucción que no tocaba el
          problema: buscar otra cosa no se arregla registrando un equipo.
        */
        hayFiltroPuesto ? (
          <EmptyState
            icono={<Wrench size={20} aria-hidden="true" />}
            titulo="Ningún equipo sale con estos filtros"
            descripcion="Prueba a quitar alguno, o cambia la búsqueda."
          />
        ) : (
          <EmptyState
            icono={<Wrench size={20} aria-hidden="true" />}
            titulo="El inventario está vacío"
            descripcion="Registra el primer equipo para empezar."
            accion={
              sesion.puede('equipos.crear') ? (
                <Button variante="destacado" icono={<Plus size={16} aria-hidden="true" />} onClick={() => setRegistrando(true)}>
                  Registrar equipo
                </Button>
              ) : null
            }
          />
        )
      ) : (
        <>
          <DataTable
            columnas={columnas}
            datos={activos.data?.items ?? []}
            claveFila={(fila) => fila.id}
            cargando={activos.isLoading}
            columnasConfigurables
            columnasKey={`inventario-equipos:${sesion.usuario?.id ?? 'sin-sesion'}`}
            ocultasIniciales={['tipo', 'conjunto_nombre', 'propiedad', 'tamano_pantalla', 'procesador', 'memoria_ram', 'almacenamiento', 'direccion_ip', 'direccion_mac', 'observaciones']}
            permitirOrdenar={false}
            /*
              Franja roja en el canto izquierdo de las filas fuera de servicio.
              La insignia de estado ya lo dice con palabras, pero está en una
              columna a media tabla: quien va escaneando nombres la encuentra tarde.
              La franja se ve al entrar en la página y se lee sin leer nada. Las
              que están en reparación van en ámbar: también fuera de servicio,
              pero no son una baja.
            */
            tonoFila={(equipo) => tonoDeFila(equipo.estado)}
            alPulsarFila={(fila) => navegar(`/panel/equipos/${fila.id}`)}
            etiquetaVacia="No hay equipos con estos filtros."
            tarjeta={(equipo) => (
              <>
                <p className="font-semibold">{equipo.nombre_equipo || equipo.tipo}</p>
                <p className="text-sm text-muted-foreground">
                  {equipo.marca} {equipo.modelo} · {equipo.oficina_nombre}
                </p>
                {equipo.responsable_id ? <Link to={`/panel/usuarios/${equipo.responsable_id}`} className="text-sm font-medium text-info-strong hover:underline">{equipo.responsable_nombre || 'Ver responsable'}</Link> : null}
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <DisponibilidadBadge estado={equipo.estado} tamano="sm" />
                  <CompletitudBadge porcentaje={equipo.completitud} faltantes={equipo.faltantes} />
                  <EstadoCampoBadge estado={equipo.campos_faltantes?.length ? 'pendiente' : 'completo'} tamano="sm" />
                </div>
              </>
            )}
          />
          <Paginacion
            pagina={activos.data?.pagina ?? 1}
            totalPaginas={activos.data?.total_paginas ?? 1}
            total={activos.data?.total ?? 0}
            porPagina={25}
            alCambiar={setPagina}
          />
        </>
      )}

      <Sheet abierto={registrando} alCerrar={() => setRegistrando(false)} titulo="Registrar equipo" ancho="md" cerrarFuera={false}>
        <RegistroEquipo
          alCerrar={() => setRegistrando(false)}
          alGuardar={() => {
            setRegistrando(false)
            void activos.refetch()
          }}
        />
      </Sheet>
    </>
  )
}
