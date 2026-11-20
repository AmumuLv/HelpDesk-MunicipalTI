import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, BarChart3 } from 'lucide-react'
import { api } from '../../api/cliente'
import { Button } from '../base/Button'
import { DialogModal } from '../base/Sobreposiciones'

type Fila = Record<string, unknown>
type Descriptor = { herramienta: string; filtros?: Record<string, unknown>; argumentos?: Record<string, unknown>; equipo_id?: string }
export type TablaConsulta = { columnas: { clave: string; titulo: string }[]; filas: Fila[]; total?: number; indicadores?: Fila; exploracion?: Descriptor; grafico?: TablaConsulta; fecha_consulta?: string }
type Datos = { tabla: TablaConsulta; total: number; pagina: number; total_paginas: number; texto?: string; cobertura?: string; solicitado?: string; aviso?: string; vista?: string; consultado_en?: string }
const valor = (v: unknown) => v == null ? 'Sin datos' : typeof v === 'object' ? 'Ver detalle' : String(v)

export function GraficoConsulta({ tabla, alSeleccionar }: { tabla: TablaConsulta; alSeleccionar: (fila: Fila) => void }) {
  const [activa, setActiva] = useState<Fila | null>(null)
  const datos = tabla.grafico || tabla
  const actual = activa && datos.filas.includes(activa) ? activa : null
  const medida = ['faltantes', 'total', 'valor', 'pendientes_actuales', 'tickets_12m', 'resueltos', 'carga_asignados', 'lecturas'].find(c => datos.columnas.some(col => col.clave === c) && datos.filas.some(f => typeof f[c] === 'number'))
  const etiqueta = ['nombre', 'campo', 'oficina', 'zona', 'tipo', 'tecnico', 'guia', 'relacion', 'categoria', 'intervalo', 'estado', 'fecha'].find(c => datos.columnas.some(col => col.clave === c))
  if (!medida || !etiqueta || !datos.filas.length) return null
  const maximo = Math.max(1, ...datos.filas.map(f => Math.max(0, Number(f[medida]) || 0)))
  const linea = medida === 'valor' && etiqueta === 'fecha'
  const descripcion = (fila: Fila) => datos.columnas.map(c => `${c.titulo}: ${valor(fila[c.clave])}`).join(' · ')
  return <figure className={`datos-ranking${linea ? ' datos-timeline' : ''}`} aria-label="Comparación de resultados">
    <figcaption>{linea ? <Activity size={15} aria-hidden="true" /> : <BarChart3 size={15} aria-hidden="true" />}{linea ? 'Tickets creados por día' : 'Comparación · ' + datos.columnas.find(c => c.clave === medida)?.titulo}</figcaption>
    {linea ? <svg className="datos-chart-line" viewBox="0 0 600 150" role="group" aria-label={`Actividad de ${datos.filas.length} días; escala de 0 a ${maximo} tickets.`}>
      <line x1="15" x2="585" y1="130" y2="130" /><polyline fill="none" points={datos.filas.map((f, i) => `${15 + i / Math.max(1, datos.filas.length - 1) * 570},${130 - Math.max(0, Number(f[medida]) || 0) / maximo * 115}`).join(' ')} />
      {datos.filas.map((f, i) => <g key={i} role="button" tabIndex={0} aria-label={descripcion(f)} onMouseEnter={() => setActiva(f)} onFocus={() => setActiva(f)} onClick={() => alSeleccionar(f)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); alSeleccionar(f) } }}><title>{descripcion(f)}</title><circle cx={15 + i / Math.max(1, datos.filas.length - 1) * 570} cy={130 - Math.max(0, Number(f[medida]) || 0) / maximo * 115} r={datos.filas.length > 60 ? 3 : 5} /></g>)}
    </svg> : <div className="datos-ranking-scroll" tabIndex={0} aria-label={`${datos.filas.length} categorías; desplázate para ver todas`}>
      {datos.filas.map((f, i) => <button className="datos-ranking-row" type="button" key={String(f.id ?? i)} title={descripcion(f)} aria-label={`Ver registros de ${valor(f[etiqueta])}`} onMouseEnter={() => setActiva(f)} onFocus={() => setActiva(f)} onClick={() => alSeleccionar(f)}>
        <span className="datos-ranking-name">{valor(f[etiqueta])}</span><strong>{Number(f[medida]).toLocaleString('es-PE')}</strong><span className="datos-ranking-track"><span style={{ width: `${Math.max(0, Number(f[medida]) || 0) / maximo * 100}%` }} /></span>
      </button>)}
    </div>}
    {actual ? <div className="datos-chart-tooltip" role="tooltip">{datos.columnas.map(c => <span key={c.clave}><b>{c.titulo}: </b>{valor(actual[c.clave])}</span>)}</div> : <p>Selecciona una barra o un punto para ver su detalle. {datos.filas.length} resultados representados.</p>}
  </figure>
}

function Tabla({ datos, seleccionar }: { datos: TablaConsulta; seleccionar?: (fila: Fila) => void }) {
  return <div className="datos-table-scroll"><table><thead><tr>{datos.columnas.map(c => <th scope="col" key={c.clave}>{c.titulo}</th>)}{seleccionar ? <th scope="col">Detalle</th> : null}</tr></thead><tbody>{datos.filas.map((f, i) => <tr key={String(f.id ?? i)}>{datos.columnas.map(c => <td key={c.clave} title={valor(f[c.clave])}>{c.clave === 'codigo' && /^[a-f\d]{24}$/i.test(String(f.ticket_id ?? '')) ? <Link to={`/panel/tickets/${String(f.ticket_id)}`}>{valor(f[c.clave])}</Link> : c.clave === 'nombre' && /^[a-f\d]{24}$/i.test(String(f.equipo_id ?? '')) ? <Link to={`/panel/equipos/${String(f.equipo_id)}`}>{valor(f[c.clave])}</Link> : valor(f[c.clave])}</td>)}{seleccionar ? <td><Button tamano="sm" onClick={() => seleccionar(f)} aria-label={`Ver registros de ${valor(f.nombre ?? f.oficina ?? f.tipo ?? f.campo ?? f.tecnico ?? i + 1)}`}>Ver registros</Button></td> : null}</tr>)}</tbody></table>{!datos.filas.length ? <p role="status">No se encontraron registros con los filtros seleccionados.</p> : null}</div>
}

function Paginador({ datos, cambiar, ocupado }: { datos: Datos; cambiar: (pagina: number) => void; ocupado: boolean }) {
  return <div className="datos-result-pages"><span>Mostrando {datos.tabla.filas.length} de {datos.total} registros disponibles · página {datos.pagina} de {datos.total_paginas}{datos.consultado_en ? <small className="block">Desglose actualizado: {new Date(datos.consultado_en).toLocaleString('es-PE', { timeZone: 'America/Lima' })} · Lima</small> : null}</span><Button tamano="sm" disabled={ocupado || datos.pagina <= 1} onClick={() => cambiar(datos.pagina - 1)}>Anterior</Button><Button tamano="sm" disabled={ocupado || datos.pagina >= datos.total_paginas} onClick={() => cambiar(datos.pagina + 1)}>Siguiente</Button></div>
}

export function ResultadosConsulta({ tabla }: { tabla: TablaConsulta }) {
  const descriptor = tabla.exploracion
  const [datos, setDatos] = useState<Datos>({ tabla, total: tabla.total ?? tabla.filas.length, pagina: 1, total_paginas: Math.max(1, Math.ceil((tabla.total ?? tabla.filas.length) / 20)) })
  const [detalle, setDetalle] = useState<Datos | null>(null)
  const [titulo, setTitulo] = useState('')
  const [opciones, setOpciones] = useState<Record<string, unknown>>({})
  const [seleccion, setSeleccion] = useState<Record<string, unknown>>({})
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')
  const [ultimo, setUltimo] = useState<{ pagina: number; extras: Record<string, unknown>; modal: boolean } | null>(null)
  const [abierto, setAbierto] = useState(false)
  const [formulario, setFormulario] = useState({ texto: String(descriptor?.argumentos?.equipo || ''), oficina: '', responsable: '', tipo: '', grupo: '', fecha: tabla.fecha_consulta || '', orden: 'cantidad' })
  const inventario = descriptor && ['resumen_inventario', 'calidad_inventario', 'equipos_datos_pendientes', 'oficinas_datos_pendientes', 'responsables_inventario'].includes(descriptor.herramienta)
  const cargar = async (pagina: number, extras: Record<string, unknown>, modal = false) => {
    if (!descriptor || ocupado) return
    setUltimo({ pagina, extras, modal })
    setOcupado(true); setError('')
    try {
      const resultado = await api.crear<Datos>('/ia/asistente/explorar', { ...descriptor, ...extras, pagina })
      if (modal) setDetalle(resultado)
      else setDatos(resultado)
    } catch (e) { setError(e instanceof Error ? e.message : 'No pudimos consultar los registros. Reintenta la consulta.') }
    finally { setOcupado(false) }
  }
  const seleccionar = (fila: Fila) => {
    setTitulo(valor(fila.nombre ?? fila.oficina ?? fila.tipo ?? fila.campo ?? fila.tecnico ?? fila.fecha ?? 'Detalle del resultado'))
    setAbierto(true); setDetalle(null); setError('')
    if (!descriptor) { setDetalle({ tabla: { columnas: tabla.columnas, filas: [fila] }, total: 1, pagina: 1, total_paginas: 1 }); return }
    const nuevas: Record<string, unknown> = { ...opciones, vista: 'detalle' }
    if (descriptor.herramienta === 'resumen_equipo_ti') nuevas.filtros = { ...descriptor.filtros, tecnico_id: fila.id }
    if (fila.grupo && !fila.nombre) nuevas.grupo = fila.grupo
    else if (fila.campo_id) nuevas.campo = fila.campo_id
    else if (descriptor.herramienta === 'resumen_inventario' && fila.tipo) nuevas.tipo = fila.tipo
    else if (descriptor.herramienta === 'oficinas_datos_pendientes' || fila.es_oficina) {
      if (fila.id) nuevas.oficina_id = fila.id
      else nuevas.oficina = fila.oficina
    } else if (fila.id && descriptor.herramienta !== 'auditoria_cambios') nuevas.equipo_id = fila.id
    if (['horarios_manana', 'auditoria_cambios', 'tickets_pendientes_detalle', 'guias_consultadas', 'guias_valoradas', 'brechas_guias', 'conjuntos_incompletos', 'inventarios_disponibles'].includes(descriptor.herramienta) || (descriptor.herramienta === 'auditoria_responsables' && !fila.seleccionable)) {
      setDetalle({ tabla: { columnas: datos.tabla.columnas, filas: [fila] }, total: 1, pagina: 1, total_paginas: 1 }); return
    }
    setSeleccion(nuevas)
    void cargar(1, nuevas, true)
  }
  const filtrar = () => {
    const nuevas: Record<string, unknown> = Object.fromEntries(Object.entries(formulario).filter(([, v]) => v))
    nuevas.texto = formulario.texto
    if (descriptor?.herramienta === 'auditoria_responsables') nuevas.equipo_id = null
    setOpciones(nuevas)
    void cargar(1, nuevas)
  }
  const indicadores = datos.tabla.indicadores ?? tabla.indicadores
  return <div className="datos-explorable">
    {indicadores ? <dl className="datos-indicators">{Object.entries(indicadores).map(([clave, numero]) => <div key={clave}><dt>{({ dispositivos: 'Dispositivos físicos', completos: 'Dispositivos completos', datos_faltantes: 'Datos pendientes', datos_aplicables: 'Datos aplicables', sin_responsable_registrado: 'Sin responsable registrado', sin_cuenta_activa: 'Sin cuenta activa', vinculado: 'Cuenta activa', pendiente: 'Vinculación pendiente', compartido: 'Compartidos', confirmar: 'Uso por confirmar', conjuntos: 'Conjuntos de escritorio (separados)' } as Record<string, string>)[clave] || clave}</dt><dd><strong>{valor(numero)}</strong></dd></div>)}</dl> : null}
    <GraficoConsulta tabla={datos.tabla} alSeleccionar={seleccionar} />
    {descriptor ? <>
      <div className="datos-result-filters">
        {inventario || descriptor.herramienta === 'auditoria_responsables' ? <>
          <label>Equipo, patrimonio o serie<input value={formulario.texto} maxLength={160} onChange={e => setFormulario({ ...formulario, texto: e.target.value })} /></label>
          <label>Oficina<input value={formulario.oficina} maxLength={160} onChange={e => setFormulario({ ...formulario, oficina: e.target.value })} /></label>
          <label>Tipo<input value={formulario.tipo} maxLength={80} onChange={e => setFormulario({ ...formulario, tipo: e.target.value })} /></label>
          <label>Responsable<input value={formulario.responsable} maxLength={160} onChange={e => setFormulario({ ...formulario, responsable: e.target.value })} /></label>
        </> : null}
        {descriptor.herramienta === 'responsables_inventario' ? <label>Vinculación / uso<select value={formulario.grupo} onChange={e => setFormulario({ ...formulario, grupo: e.target.value })}><option value="">Sin cuenta activa</option><option value="todos">Todos</option><option value="vinculado">Cuenta activa</option><option value="pendiente">Vinculación pendiente</option><option value="compartido">Compartidos</option><option value="confirmar">Uso por confirmar</option></select></label> : null}
        {descriptor.herramienta === 'oficinas_datos_pendientes' ? <label>Ordenar oficinas<select value={formulario.orden} onChange={e => setFormulario({ ...formulario, orden: e.target.value })}><option value="cantidad">Cantidad de datos pendientes</option><option value="porcentaje">Porcentaje de registros incompletos</option></select></label> : null}
        {descriptor.herramienta === 'horarios_manana' ? <label>Fecha de programación<input type="date" value={formulario.fecha} onChange={e => setFormulario({ ...formulario, fecha: e.target.value })} /></label> : null}
        {inventario || ['auditoria_responsables', 'horarios_manana'].includes(descriptor.herramienta) ? <Button tamano="sm" disabled={ocupado} onClick={filtrar}>Aplicar filtros</Button> : null}
      </div>
      {datos.cobertura ? <p>Periodo solicitado: {datos.solicitado}. Intervalo cubierto: {datos.cobertura}.</p> : null}
      <Tabla datos={datos.tabla} seleccionar={seleccionar} />
      <Paginador datos={datos} ocupado={ocupado} cambiar={p => void cargar(p, opciones)} />
      {datos.aviso ? <p className="datos-detail-note">{datos.aviso}</p> : null}
    </> : null}
    {error && !abierto ? <div role="alert">{error}{ultimo ? <><Button disabled={ocupado} onClick={() => void cargar(ultimo.pagina, ultimo.extras, ultimo.modal)}>Reintentar</Button><Button disabled={ocupado} onClick={() => void cargar(1, ultimo.extras, ultimo.modal)}>Volver a la primera página</Button></> : null}</div> : null}
    <DialogModal abierto={abierto} alCerrar={() => { setAbierto(false); setDetalle(null) }} titulo={titulo} tamano="xl">
      <div className="datos-detail">{error ? <div role="alert">{error}<Button disabled={ocupado} onClick={() => void cargar(ultimo?.pagina ?? 1, ultimo?.extras ?? seleccion, true)}>Reintentar</Button></div> : ocupado ? <p role="status">Consultando registros…</p> : detalle ? <><p>{detalle.texto}</p><Tabla datos={detalle.tabla} seleccionar={detalle.vista === 'buscar_equipo' ? seleccionar : undefined} /><Paginador datos={detalle} ocupado={ocupado} cambiar={p => void cargar(p, seleccion, true)} />{detalle.aviso ? <p>{detalle.aviso}</p> : null}</> : null}</div>
    </DialogModal>
  </div>
}
