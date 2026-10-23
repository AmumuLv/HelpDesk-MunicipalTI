import { Archive, ArrowDown, ArrowRightLeft, CalendarDays, CheckCircle2, Download, FileSpreadsheet, ShieldCheck, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, consulta, ErrorPeticion } from '../../api/cliente'
import { descargarDeLaApi } from '../../api/descarga'
import { useAvisos } from '../../estado/Avisos'
import { useSesion } from '../../estado/Sesion'
import { ConfirmDialog } from '../base/Sobreposiciones'
import { fechaHora, numero } from '../../dominio/formato'
import { Button } from '../base/Button'
import { Input, SearchInput, Select } from '../base/Campo'
import { ErrorState, Nota, Panel, SkeletonPanel } from '../base/Estructura'
import { DataTable, Paginacion, type ColumnaTabla } from './DataTable'
import { IconoTipoEquipo } from './IconoTipoEquipo'
import './ArchivoInventarioAnual.css'

type Version = { id: string; anio: number; codigo_campana: string; archivo_nombre?: string; archivo_hash?: string; archivo_hash_contenido?: string; zona_csv?: string | null; fuente?: string; cerrado_en: string; cerrado_por: string; total_items: number; sin_codigo?: number; ya_registrado?: boolean }
type Equipo = { codigo?: string; nombre: string; tipo?: string; zona?: string; oficina?: string; responsable?: string; conjunto_nombre?: string; campos?: Record<string, string | null> }
type Diferencia = { campo: string; antes: string | null; despues: string | null }
type Comparacion = { suficiente_datos: boolean; mensaje?: string; criterio?: string; versiones: { codigo: string; archivo?: string; fuente: string }[]; totales: Record<string, number>; altas: Equipo[]; bajas: Equipo[]; traslados: { codigo?: string; nombre: string; de?: string; a?: string }[]; cambios: { codigo?: string; nombre: string; diferencias: Diferencia[] }[]; sin_cambios: number }

export function ArchivoInventarioAnual() {
  const avisos = useAvisos()
  const sesion = useSesion()
  const cache = useQueryClient()
  const versiones = useQuery({ queryKey: ['campanas', 'historico'], queryFn: () => api.obtener<{ items: Version[] }>('/campanas/versiones/historico') })
  const [seleccion, setSeleccion] = useState('')
  const lista = versiones.data?.items ?? []
  const version = lista.find((v) => v.id === seleccion) ?? lista.find((v) => v.fuente === 'archivo_anual') ?? lista[0]
  const [archivo, setArchivo] = useState<File | null>(null)
  const [anio, setAnio] = useState(String(new Date().getFullYear()))
  const [zonaCsv, setZonaCsv] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [porEliminar, setPorEliminar] = useState<Version | null>(null)
  const [eliminando, setEliminando] = useState(false)
  const bloqueoEliminar = useRef(false)
  const [texto, setTexto] = useState('')
  const [pagina, setPagina] = useState(1)
  const entrada = useRef<HTMLInputElement>(null)
  const bloqueo = useRef(false)
  const equipos = useQuery({ queryKey: ['archivo-anual', version?.id, texto, pagina], queryFn: () => api.obtener<{ items: Equipo[]; total: number; pagina: number; total_paginas: number }>(`/campanas/versiones/${version!.id}/equipos${consulta({ texto, pagina, por_pagina: 25 })}`), enabled: Boolean(version), placeholderData: undefined })
  const guardar = async () => {
    if (!archivo || bloqueo.current) return
    bloqueo.current = true
    setGuardando(true); setError('')
    try {
      const cuerpo = new FormData()
      cuerpo.append('archivo', archivo); cuerpo.append('anio', anio)
      if (zonaCsv.trim()) cuerpo.append('zona_csv', zonaCsv.trim())
      let creado: Version
      try {
        creado = await api.subir<Version>('/campanas/anual/importar', cuerpo)
      } catch (fallo) {
        // La conexión puede perderse después del guardado. Verificar la huella
        // evita anunciar un fallo y exigir recargar para ver lo ya registrado.
        if (!(fallo instanceof ErrorPeticion) || (fallo.estado > 0 && fallo.estado < 500) || !crypto.subtle) throw fallo
        const huella = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await archivo.arrayBuffer()))].map(n => n.toString(16).padStart(2, '0')).join('')
        const existentes = await api.obtener<{ items: Version[] }>('/campanas/versiones/historico').catch(() => null)
        const esCsv = archivo.name.toLowerCase().endsWith('.csv')
        let registrado = existentes?.items.find(v => v.anio === Number(anio) && (
          esCsv ? v.archivo_hash_contenido === huella && v.zona_csv?.trim().toLocaleLowerCase() === zonaCsv.trim().toLocaleLowerCase() : v.archivo_hash === huella))
        if (!registrado && esCsv) {
          // Los CSV antiguos guardaban solo la huella del archivo. Verificar su
          // zona evita confundir una corrección con una versión de otra sede.
          const anterior = existentes?.items.find(v => v.anio === Number(anio) && v.archivo_hash === huella && v.archivo_nombre?.toLowerCase().endsWith('.csv'))
          if (anterior) {
            const detalle = await api.obtener<{ items: Equipo[] }>(`/campanas/versiones/${anterior.id}/equipos?por_pagina=1`).catch(() => null)
            if (detalle?.items[0]?.zona?.trim().toLocaleLowerCase() === zonaCsv.trim().toLocaleLowerCase()) registrado = anterior
          }
        }
        if (!registrado) throw fallo
        creado = { ...registrado, ya_registrado: true }
      }
      cache.setQueryData<{ items: Version[] }>(['campanas', 'historico'], anterior => ({ items: [creado, ...(anterior?.items ?? []).filter(v => v.id !== creado.id)].sort((a, b) => b.anio - a.anio || b.cerrado_en.localeCompare(a.cerrado_en)) }))
      setSeleccion(creado.id); setPagina(1); setTexto(''); setArchivo(null)
      void cache.invalidateQueries({ queryKey: ['campanas', 'historico'] })
      void cache.invalidateQueries({ queryKey: ['archivo-anual', creado.id] })
      void cache.invalidateQueries({ queryKey: ['comparar-inventarios'] })
      if (entrada.current) entrada.current.value = ''
      avisos.exito(creado.ya_registrado ? 'Este archivo ya estaba registrado' : `Inventario ${creado.anio} registrado`, `${numero(creado.total_items)} equipos conservados en esta versión.`)
    } catch (fallo) { setError(fallo instanceof Error ? fallo.message : 'No se pudo registrar el archivo.') }
    finally { bloqueo.current = false; setGuardando(false) }
  }
  const columnas: ColumnaTabla<Equipo>[] = [
    { accessorKey: 'nombre', header: 'Equipo', cell: ({ row }) => <div className="flex items-center gap-2"><IconoTipoEquipo tipo={row.original.tipo} tamano={21} /><div><p className="font-semibold">{row.original.nombre}</p><p className="text-xs text-muted-foreground">{row.original.tipo}</p></div></div> },
    { accessorKey: 'codigo', header: 'Patrimonio', cell: ({ row }) => row.original.codigo || (row.original.campos?.propiedad?.trim().toUpperCase() === 'PERSONAL' ? 'No aplica' : 'Sin código') },
    { accessorKey: 'zona', header: 'Zona / Oficina', cell: ({ row }) => <><p>{row.original.oficina}</p><p className="text-xs text-muted-foreground">{row.original.zona}</p></> },
    { accessorKey: 'conjunto_nombre', header: 'Conjunto', cell: ({ row }) => row.original.conjunto_nombre || row.original.campos?.tipo_equipo || 'Individual' },
    { accessorKey: 'responsable', header: 'Responsable', cell: ({ row }) => row.original.responsable || 'Uso común de la oficina' },
    { id: 'estado', header: 'Estado', cell: ({ row }) => row.original.campos?.estado || 'No indicado' },
  ]
  const aniosGuardados = [...new Set(lista.map(v => v.anio))].sort((a, b) => b - a)
  const eliminar = async () => {
    if (!porEliminar || bloqueoEliminar.current) return
    bloqueoEliminar.current = true; setEliminando(true)
    try {
      await api.borrar(`/campanas/versiones/${porEliminar.id}`)
      cache.setQueryData<{ items: Version[] }>(['campanas', 'historico'], previo => ({ items: (previo?.items ?? []).filter(v => v.id !== porEliminar.id) }))
      if (version?.id === porEliminar.id) { setSeleccion(''); setTexto(''); setPagina(1) }
      cache.removeQueries({ queryKey: ['archivo-anual', porEliminar.id] })
      await Promise.all([cache.invalidateQueries({ queryKey: ['campanas', 'historico'] }), cache.invalidateQueries({ queryKey: ['comparar-inventarios'] })])
      setPorEliminar(null)
      avisos.exito('Versión anual eliminada', 'El inventario actual se conserva.')
    } catch (fallo) { avisos.desdeError(fallo) }
    finally { bloqueoEliminar.current = false; setEliminando(false) }
  }
  return <div className="anual-workspace">
    <section className="anual-overview" aria-label="Resumen del archivo anual"><div className="anual-overview-title"><span className="anual-emblem"><Archive size={26} /></span><div><span className="anual-eyebrow">ARCHIVO HISTÓRICO</span><h2>Tu inventario, año por año</h2><p>Conserva cada revisión y encuentra qué cambió entre dos años.</p></div></div><div className="anual-stats"><div><strong>{numero(aniosGuardados.length)}</strong><span>Años guardados</span></div><div><strong>{numero(lista.length)}</strong><span>Versiones disponibles</span></div><div><ShieldCheck size={20} /><span>El inventario actual<br />se mantiene independiente</span></div></div></section>
    <nav className="anual-steps" aria-label="Acciones de inventario anual">{[{ id: 'anual-registro', numero: '01', titulo: 'Registrar archivo', detalle: 'Guarda el Excel o CSV de un año', Icono: Upload }, { id: 'anual-guardados', numero: '02', titulo: 'Consultar inventarios', detalle: 'Busca equipos o descarga una versión', Icono: Archive }, { id: 'anual-comparacion', numero: '03', titulo: 'Comparar años', detalle: 'Revisa altas, traslados y diferencias', Icono: ArrowRightLeft }].map(({ id, numero, titulo, detalle, Icono }) => <a key={id} href={`#${id}`}><span className="anual-step-number">{numero}</span><div><strong>{titulo}</strong><span>{detalle}</span></div><Icono size={18} aria-hidden="true" /></a>)}</nav>
    <Panel titulo={<span className="flex items-center gap-2"><Archive className="text-info-strong" size={21} />Archivo del inventario por año</span>} descripcion="Registra el Excel completo de cada año. Se conserva una copia independiente, sin cambiar los equipos del inventario operativo. Puedes guardar varias revisiones del mismo año."
      id="anual-registro" className="anual-panel"
      acciones={<Button tamano="sm" icono={<Download size={15} />} onClick={() => void descargarDeLaApi('/importacion/plantilla', 'plantilla-inventario.xlsx').catch((fallo) => avisos.desdeError(fallo))}>Descargar plantilla</Button>}>
      <div className="anual-upload-form">
        <Input etiqueta="Año del inventario" type="number" min={2000} max={2100} value={anio} disabled={guardando} onChange={(e) => setAnio(e.target.value)} />
        <label className="anual-file-field">Archivo Excel o CSV<input ref={entrada} type="file" accept=".xlsx,.xlsm,.csv" disabled={guardando} onChange={(e) => { setArchivo(e.target.files?.[0] ?? null); setError('') }} /></label>
        <Button variante="primario" icono={<Upload size={17} />} cargando={guardando} disabled={!archivo || !Number.isInteger(Number(anio)) || Number(anio) < 2000 || Number(anio) > 2100 || (archivo.name.toLowerCase().endsWith('.csv') && !zonaCsv.trim())} onClick={() => void guardar()}>Registrar inventario anual</Button>
      </div>
      {archivo ? <div className="anual-file-selected"><FileSpreadsheet size={21} aria-hidden="true" /><div><strong>{archivo.name}</strong><span>{(archivo.size / 1024).toLocaleString('es-PE', { maximumFractionDigits: 1 })} KB · Se guardará en {anio || 'el año indicado'}</span></div><CheckCircle2 size={18} aria-hidden="true" /></div> : <p className="anual-inline-help"><Upload size={14} />Elige el año y selecciona un archivo para habilitar el registro.</p>}
      {archivo?.name.toLowerCase().endsWith('.csv') ? <div className="mt-3 max-w-md"><Input etiqueta="Zona del CSV" value={zonaCsv} disabled={guardando} onChange={(e) => setZonaCsv(e.target.value)} ayuda="El CSV representa una sola zona. Para varias zonas usa una hoja de Excel por zona." /></div> : null}
      <details className="anual-file-guide"><summary>¿Cómo preparo mi archivo?</summary><p>En Excel, usa una hoja por zona. En CSV, indica la zona en el campo que aparece al elegir el archivo. Puedes descargar la plantilla para empezar.</p><p>Cabeceras: AREA, Tipo de equipo, Dispositivo, Código patrimonial, Marca, Modelo, Nombre Equipo, Estado y Responsable.</p><p>Corrige los códigos repetidos antes de registrar. Volver a cargar un archivo idéntico no crea otra copia.</p></details>
      {error ? <div className="mt-3" role="alert"><Nota tono="peligro" titulo="Revisa el archivo"><p className="max-h-72 overflow-y-auto whitespace-pre-line break-words">{error}</p></Nota></div> : null}
    </Panel>
    <Panel titulo={<span className="flex items-center gap-2"><CalendarDays className="text-success-strong" size={21} />Inventarios guardados</span>} descripcion="Selecciona un año y después la versión que quieres consultar." id="anual-guardados" className="anual-panel">
      {versiones.isPending ? <SkeletonPanel filas={3} /> : versiones.isError ? <ErrorState mensaje="No pudimos cargar los inventarios anuales." alReintentar={() => void versiones.refetch()} /> : !lista.length ? <div className="anual-empty"><Archive size={35} /><h3>Tu archivo anual empieza aquí</h3><p>Aún no hay inventarios anuales. Registra el primer archivo indicando su año.</p><a href="#anual-registro">Ir al registro <ArrowDown size={14} /></a></div> : <>
        <div className="anual-years" aria-label="Acceso rápido por año">{aniosGuardados.map(anio => <button type="button" key={anio} aria-pressed={version?.anio === anio} onClick={() => { const elegida = lista.find(v => v.anio === anio && v.fuente === 'archivo_anual') ?? lista.find(v => v.anio === anio); if (elegida) setSeleccion(elegida.id); setPagina(1); setTexto('') }}><CalendarDays size={15} /><strong>{anio}</strong><span>{lista.filter(v => v.anio === anio).length} {lista.filter(v => v.anio === anio).length === 1 ? 'versión' : 'versiones'}</span></button>)}</div>
        <div className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto]"><Select etiqueta="Año y versión del inventario" value={version?.id ?? ''} onChange={(e) => { setSeleccion(e.target.value); setPagina(1); setTexto('') }} opciones={lista.map((v) => ({ valor: v.id, etiqueta: `${v.anio} · ${v.archivo_nombre || v.codigo_campana} · ${fechaHora(v.cerrado_en)}` }))} /><Button icono={<Download size={16} />} onClick={() => { if (version) void descargarDeLaApi(`/campanas/versiones/${version.id}/excel`, `inventario-${version.anio}.xlsx`).catch((f) => avisos.desdeError(f)) }}>Descargar inventario</Button></div>
        <div className="anual-version-info"><span className="anual-version-count"><FileSpreadsheet size={16} /><strong>{numero(version?.total_items ?? 0)} equipos</strong></span><span>Registrado por {version?.cerrado_por || 'Equipo TI'}</span><span>{version ? fechaHora(version.cerrado_en) : ''}</span></div>
        {sesion.esAdmin && version?.fuente === 'archivo_anual' ? <div className="mb-3 flex justify-end"><Button variante="destructivo" tamano="sm" icono={<Trash2 size={15} />} disabled={guardando || eliminando} onClick={() => setPorEliminar(version)}>Eliminar versión</Button></div> : null}
        {version?.fuente !== 'archivo_anual' ? <Nota tono="aviso">Esta versión procede de una campaña de verificación y puede cubrir solo parte del inventario.</Nota> : null}
        {version?.sin_codigo ? <Nota tono="aviso">{numero(version.sin_codigo)} equipos no tienen código patrimonial. Se distinguen por zona, oficina, conjunto, tipo y nombre.</Nota> : null}
        <div className="my-3"><SearchInput etiqueta="Buscar en el año seleccionado" valor={texto} alCambiar={(t) => { setTexto(t); setPagina(1) }} /></div>
        {equipos.isError ? <ErrorState mensaje="No se pudo abrir esta versión." alReintentar={() => void equipos.refetch()} /> : <DataTable columnas={columnas} datos={equipos.data?.items ?? []} claveFila={(fila) => fila.codigo || `${fila.zona}-${fila.oficina}-${fila.conjunto_nombre || fila.campos?.tipo_equipo}-${fila.tipo}-${fila.nombre}`} cargando={equipos.isPending} permitirOrdenar={false} />}
        <Paginacion pagina={equipos.data?.pagina ?? 1} totalPaginas={equipos.data?.total_paginas ?? 1} total={equipos.data?.total ?? 0} porPagina={25} alCambiar={setPagina} />
      </>}
    </Panel>
    <CompararInventarios versiones={lista} />
    <ConfirmDialog abierto={Boolean(porEliminar)} alCerrar={() => { if (!bloqueoEliminar.current) setPorEliminar(null) }} alConfirmar={() => void eliminar()} titulo="Eliminar versión del inventario" mensaje={<><p>Se eliminará la versión de <strong>{porEliminar?.anio}</strong>: {porEliminar?.archivo_nombre || porEliminar?.codigo_campana}.</p><p className="mt-2">Esta acción no se puede deshacer. Los equipos del inventario actual y las demás versiones se conservan.</p></>} textoConfirmar="Eliminar versión" peligro cargando={eliminando} />
  </div>
}

function CompararInventarios({ versiones }: { versiones: Version[] }) {
  const anios = [...new Set(versiones.map((v) => v.anio))].sort((a, b) => a - b)
  const [origen, setOrigen] = useState('')
  const [destino, setDestino] = useState('')
  const a = anios.includes(Number(origen)) ? origen : String(anios[0] ?? '')
  const b = anios.includes(Number(destino)) ? destino : String(anios.at(-1) ?? '')
  const [pedido, setPedido] = useState<[string, string] | null>(null)
  const [grupo, setGrupo] = useState('altas')
  const [pagina, setPagina] = useState(1)
  const comparacion = useQuery({ queryKey: ['comparar-inventarios', pedido], queryFn: () => api.obtener<Comparacion>(`/campanas/versiones/comparar${consulta({ anio_a: pedido![0], anio_b: pedido![1] })}`), enabled: Boolean(pedido), placeholderData: undefined, retry: false })
  const datos = comparacion.data
  const grupos = datos?.suficiente_datos ? [{ id: 'altas', nombre: 'Altas', filas: datos.altas }, { id: 'bajas', nombre: 'No aparecen en el destino', filas: datos.bajas }, { id: 'traslados', nombre: 'Traslados', filas: datos.traslados }, { id: 'cambios', nombre: 'Cambios de datos', filas: datos.cambios }] : []
  const filas = grupos.find((g) => g.id === grupo)?.filas ?? []
  return <Panel titulo={<span className="flex items-center gap-2"><ArrowRightLeft size={21} className="text-warning-strong" />Comparar inventarios de dos años</span>} descripcion="Elige el año anterior y el año más reciente. Se utilizará la última revisión anual guardada de cada uno." id="anual-comparacion" className="anual-panel anual-compare">
    <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]"><Select etiqueta="Año de origen" value={a} opciones={anios.map((v) => ({ valor: String(v), etiqueta: String(v) }))} onChange={(e) => { setOrigen(e.target.value); setPedido(null) }} /><Select etiqueta="Año de destino" value={b} opciones={anios.map((v) => ({ valor: String(v), etiqueta: String(v) }))} onChange={(e) => { setDestino(e.target.value); setPedido(null) }} /><Button variante="primario" disabled={!a || !b || Number(a) >= Number(b)} cargando={comparacion.isFetching} onClick={() => { setPedido([a, b]); setPagina(1) }}>Comparar años</Button></div>
    {anios.length < 2 ? <p className="mt-3 text-sm text-muted-foreground">Registra al menos dos años distintos para comparar.</p> : Number(a) >= Number(b) ? <p className="mt-3 text-sm text-warning-strong">Selecciona un destino posterior al año de origen.</p> : null}
    {pedido && comparacion.isPending ? <SkeletonPanel filas={3} /> : comparacion.isError ? <ErrorState mensaje="No se pudo realizar la comparación." detalle={comparacion.error.message} alReintentar={() => void comparacion.refetch()} /> : datos && pedido ? !datos.suficiente_datos ? <Nota tono="aviso">{datos.mensaje}</Nota> : <div className="mt-5 space-y-4">
      <div className="anual-comparison-stats">{[{ titulo: `Equipos ${pedido[0]}`, valor: datos.totales[pedido[0]] }, { titulo: `Equipos ${pedido[1]}`, valor: datos.totales[pedido[1]] }, { titulo: 'Sin cambios', valor: datos.sin_cambios }].map((k) => <div key={k.titulo}><p>{k.titulo}</p><strong>{numero(k.valor)}</strong></div>)}</div>
      <p className="anual-comparison-note"><ShieldCheck size={16} />Si un equipo no aparece en el año de destino, se señala como diferencia. No se da de baja del inventario actual.</p>
      <details className="anual-file-guide"><summary>Ver archivos utilizados y criterio de comparación</summary><p>{datos.versiones.map((v) => v.archivo || v.codigo).join(' → ')}</p><p>{datos.criterio}</p></details>
      <div className="anual-comparison-groups">{grupos.map((g) => <Button key={g.id} variante={grupo === g.id ? 'primario' : 'secundario'} aria-pressed={grupo === g.id} onClick={() => { setGrupo(g.id); setPagina(1) }}>{g.nombre} ({g.filas.length})</Button>)}</div>
      <ul className="anual-differences">{filas.slice((pagina - 1) * 10, pagina * 10).map((fila, i) => <li key={`${fila.codigo}-${i}`}><p className="font-semibold">{fila.codigo || 'Sin código'} · {fila.nombre}</p>{'oficina' in fila ? <p className="text-sm text-muted-foreground">{fila.zona} · {fila.oficina}</p> : null}{'de' in fila ? <p className="anual-before-after">{fila.de || 'No indicado'} → {fila.a || 'No indicado'}</p> : null}{'diferencias' in fila ? <ul className="anual-changed-fields">{fila.diferencias.map((d) => <li key={d.campo}><span className="font-medium capitalize">{d.campo.replaceAll('_', ' ')}:</span> {d.antes || 'Sin dato'} → {d.despues || 'Sin dato'}</li>)}</ul> : null}</li>)}</ul>
      {!filas.length ? <p className="text-sm text-muted-foreground">No hay diferencias de este tipo.</p> : <Paginacion pagina={pagina} totalPaginas={Math.max(1, Math.ceil(filas.length / 10))} total={filas.length} porPagina={10} alCambiar={setPagina} />}
    </div> : null}
  </Panel>
}
