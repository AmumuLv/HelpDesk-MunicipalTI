import { ReaccionesArticulo } from '../../componentes/dominio/ReaccionesArticulo'
/**
 * Base de conocimiento: artículos y respuestas rápidas.
 *
 * Dos pestañas porque son dos cosas distintas: los artículos los lee el usuario
 * final; las respuestas rápidas las inserta el técnico en el chat sin volver a
 * escribir lo mismo.
 */

import { BookOpen, FileText, ListOrdered, MessageSquareQuote, Pencil, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api, erroresDeValidacion } from '../../api/cliente'
import { useArticulos, useCategoriasKb, useRespuestasRapidas } from '../../api/hooks'
import type { ArticuloKbDetalle, FiltrosArticulos } from '../../api/tipos'
import { Button } from '../../componentes/base/Button'
import { Input, SearchInput, Select, Textarea } from '../../componentes/base/Campo'
import { ConfirmDialog, DialogModal } from '../../componentes/base/Sobreposiciones'
import {
  ContenidoTab,
  EmptyState,
  ErrorState,
  ListaTabs,
  PageHeader,
  Panel,
  SkeletonPanel,
  Tab,
  TabsPanel,
} from '../../componentes/base/Estructura'
import { fechaCorta, numero } from '../../dominio/formato'
import { useAvisos } from '../../estado/Avisos'
import { useSesion } from '../../estado/Sesion'

export function Conocimiento() {
  const sesion = useSesion()
  const avisos = useAvisos()
  const consultas = useQueryClient()

  const [pestana, setPestana] = useState('articulos')
  const [texto, setTexto] = useState('')
  const [categoria, setCategoria] = useState('')
  const [pagina, setPagina] = useState(1)
  const [visibilidad, setVisibilidad] = useState<'todos' | 'equipo_ti' | ''>('')
  const articulos = useArticulos({ ...(texto.trim() ? { texto: texto.trim() } : {}), ...(visibilidad ? { visibilidad } : {}), categoria, pagina, por_pagina: 4 })
  const categorias = useCategoriasKb()
  const rapidas = useRespuestasRapidas()

  const [editando, setEditando] = useState<{ id?: string; titulo: string; cuerpo: string; resumen: string; categoria: string; pasos?: string; visibilidad?: 'todos' | 'equipo_ti' } | null>(null)
  const [articuloAbierto, setArticuloAbierto] = useState<string | null>(null)
  const [editarAlCargar, setEditarAlCargar] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [respuesta, setRespuesta] = useState<{ id?: string; titulo: string; cuerpo: string } | null>(null)
  const [guardandoRespuesta, setGuardandoRespuesta] = useState(false)
  const [borrando, setBorrando] = useState(false)
  const [eliminar, setEliminar] = useState<{ ruta: string; titulo: string } | null>(null)
  const eliminarContenido = async () => {
    if (!eliminar || borrando) return
    setBorrando(true)
    try {
      await api.borrar(eliminar.ruta)
      setEliminar(null)
      setArticuloAbierto(null)
      await Promise.all([articulos.refetch(), rapidas.refetch()])
      avisos.exito('Contenido retirado')
    } catch (fallo) { avisos.desdeError(fallo) }
    finally { setBorrando(false) }
  }
  const guardarRespuesta = async () => {
    if (!respuesta || guardandoRespuesta) return
    setGuardandoRespuesta(true)
    try {
      if (respuesta.id) await api.editar(`/kb/respuestas-rapidas/${respuesta.id}`, respuesta)
      else await api.crear('/kb/respuestas-rapidas', respuesta)
      setRespuesta(null)
      await rapidas.refetch()
      avisos.exito('Plantilla guardada')
    } catch (fallo) { avisos.desdeError(fallo) }
    finally { setGuardandoRespuesta(false) }
  }
  const detalleArticulo = useQuery({
    queryKey: ['kb-articulo', articuloAbierto],
    queryFn: () => api.obtener<ArticuloKbDetalle>(`/kb/articulos/${articuloAbierto}`),
    enabled: Boolean(articuloAbierto),
    placeholderData: undefined,
  })
  const articulosUnicos = articulos.data?.items ?? []

  useEffect(() => {
    document.title = 'Base de conocimiento · Mesa de Ayuda TI'
  }, [])

  useEffect(() => {
    if (!editarAlCargar || !detalleArticulo.data || detalleArticulo.data.id !== articuloAbierto) return
    setEditando({
      id: detalleArticulo.data.id,
      titulo: detalleArticulo.data.titulo,
      cuerpo: detalleArticulo.data.cuerpo,
      resumen: detalleArticulo.data.resumen,
      categoria: detalleArticulo.data.categoria,
      pasos: (detalleArticulo.data.pasos ?? []).join('\n'),
      visibilidad: detalleArticulo.data.visibilidad ?? 'todos',
    })
    setArticuloAbierto(null)
    setEditarAlCargar(false)
  }, [detalleArticulo.data, editarAlCargar, articuloAbierto])

  const abrirEditor = (articuloId: string) => {
    setEditarAlCargar(true)
    setArticuloAbierto(articuloId)
  }

  const guardarArticulo = async () => {
    if (!editando || guardando) return
    setGuardando(true)
    try {
      const cuerpo = {
        titulo: editando.titulo.trim(),
        cuerpo: editando.cuerpo.trim(),
        resumen: editando.resumen.trim(),
        categoria: editando.categoria.trim() || 'General',
        visibilidad: editando.visibilidad ?? 'todos',
        pasos: (editando.pasos ?? '').split('\n').map((paso) => paso.trim()).filter(Boolean),
      }
      if (editando.id) await api.editar(`/kb/articulos/${editando.id}`, cuerpo)
      else await api.crear('/kb/articulos', cuerpo)
      await consultas.invalidateQueries({ queryKey: ['kb-articulo'] })
      await consultas.invalidateQueries({ queryKey: ['kb'] })
      avisos.exito(editando.id ? 'Artículo actualizado' : 'Artículo creado', cuerpo.titulo)
      setEditando(null)
      setErrores({})
      await Promise.all([articulos.refetch(), categorias.refetch()])
    } catch (fallo) {
      const validacion = erroresDeValidacion(fallo)
      setErrores(validacion)
      if (Object.keys(validacion).length === 0) avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
      <PageHeader
        titulo="Base de conocimiento"
        descripcion="Biblioteca compartida de tutoriales, soluciones y recomendaciones de software. Los artículos también se pueden consultar desde Ayuda."
        acciones={
          sesion.esTecnico ? (
            <Button
              variante="destacado"
              icono={<Plus size={16} aria-hidden="true" />}
              onClick={() =>
                setEditando({
                  titulo: '',
                  cuerpo: '',
                  resumen: '',
                  categoria: categorias.data?.items[0] ?? 'Otros',
                })
              }
            >
              Nuevo artículo
            </Button>
          ) : null
        }
      />

      <TabsPanel valor={pestana} alCambiar={setPestana}>
        <ListaTabs>
          <Tab valor="articulos">Artículos</Tab>
          <Tab valor="rapidas">Respuestas rápidas</Tab>
        </ListaTabs>

        <ContenidoTab valor="articulos">
          <div className="grid gap-3 sm:grid-cols-3">
            <SearchInput etiqueta="Buscar artículos" valor={texto} alCambiar={(valor) => { setTexto(valor); setPagina(1) }} placeholder="Título, tema o palabra clave…" />
            <Select etiqueta="Filtrar por categoría" value={categoria} onChange={(evento) => { setCategoria(evento.target.value); setPagina(1) }} opciones={[{ valor: '', etiqueta: 'Todas las categorías' }, ...(categorias.data?.items ?? []).map((c) => ({ valor: c, etiqueta: c }))]} />
            <Select etiqueta="Visibilidad" value={visibilidad} onChange={evento => { setVisibilidad(evento.target.value as typeof visibilidad); setPagina(1) }} opciones={[{ valor: '', etiqueta: 'Todos los artículos' }, { valor: 'todos', etiqueta: 'Para todos los usuarios' }, { valor: 'equipo_ti', etiqueta: 'Solo equipo TI' }]} />
          </div>
          {editarAlCargar && detalleArticulo.isError ? <ErrorState mensaje="No pudimos abrir el editor." alReintentar={() => void detalleArticulo.refetch()} /> : null}

          {articulos.isLoading ? (
            <SkeletonPanel filas={4} />
          ) : articulos.isError ? (
            <ErrorState mensaje="No pudimos cargar los artículos." alReintentar={() => void articulos.refetch()} />
          ) : (articulos.data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icono={<BookOpen size={20} aria-hidden="true" />}
              titulo="No hay artículos publicados"
              descripcion="Un artículo por pregunta frecuente evita muchos tickets repetidos."
            />
          ) : (
            <ul aria-label="Artículos de la biblioteca" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {articulosUnicos.map((articulo) => (
                <li key={articulo.id} className="flex min-h-44 min-w-0 flex-col rounded-[var(--radius-panel)] border border-border bg-surface p-4 transition-colors hover:border-primary/40">
                  <span className="mb-2 flex flex-wrap items-center gap-1.5 text-xs font-medium text-primary-strong"><BookOpen size={14} aria-hidden="true" /><span className="truncate">{articulo.categoria}</span>{articulo.visibilidad === 'equipo_ti' ? <span className="rounded-full bg-info-soft px-2 py-1 text-info-strong">Solo equipo TI</span> : null}</span>
                  <p className="flex items-start justify-between gap-2">
                    <button type="button" className="line-clamp-2 text-left text-sm font-semibold hover:text-primary-strong" onClick={() => setArticuloAbierto(articulo.id)}>
                      {articulo.titulo}
                    </button>
                    {sesion.puede('kb.editar') ? (
                      <button
                        type="button"
                        aria-label={`Editar ${articulo.titulo}`}
                        onClick={() => abrirEditor(articulo.id)}
                        className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
                      >
                        <Pencil size={14} aria-hidden="true" />
                      </button>
                    ) : null}
                  </p>
                  <p className="mt-1 mb-3 line-clamp-2 text-sm text-muted-foreground">{articulo.resumen}</p>
                  <p className="mt-auto border-t border-border pt-2 text-2xs text-muted-foreground">
                    {numero(articulo.visualizaciones)} lecturas ·{' '}
                    {fechaCorta(articulo.actualizado_en)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {(articulos.data?.total_paginas ?? 0) > 1 ? <div className="mt-3 flex items-center justify-end gap-3"><Button disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</Button><span>Página {pagina} de {articulos.data?.total_paginas}</span><Button disabled={pagina >= (articulos.data?.total_paginas ?? 1)} onClick={() => setPagina(pagina + 1)}>Siguiente</Button></div> : null}
        </ContenidoTab>

        <ContenidoTab valor="rapidas">
          <Panel titulo="Plantillas para responder tickets" descripcion="Mensajes escritos por el equipo TI, como instrucciones o solicitudes de información. En la conversación de un ticket elige una plantilla, revísala y envíala. No son conversaciones con la IA.">
            {sesion.puede('kb.editar') ? <Button onClick={() => setRespuesta({ titulo: '', cuerpo: '' })} icono={<Plus size={16} />}>Nueva respuesta rápida</Button> : null}
            {rapidas.isLoading ? (
              <SkeletonPanel filas={3} />
            ) : rapidas.isError ? (
              <ErrorState mensaje="No pudimos cargar las plantillas." alReintentar={() => void rapidas.refetch()} />
            ) : (rapidas.data?.items.length ?? 0) === 0 ? (
              <EmptyState
                compacto
                icono={<MessageSquareQuote size={20} aria-hidden="true" />}
                titulo="No hay respuestas rápidas"
                descripcion="Crea las que más repites para no escribirlas cada vez."
              />
            ) : (
              <ul className="flex flex-col gap-2">
                {rapidas.data?.items.map((rapida) => (
                  <li key={rapida.id} className="rounded-[var(--radius-panel)] border border-border p-3">
                    <p className="font-semibold">{rapida.titulo}</p>
                    <p className="mt-0.5 text-sm text-muted-foreground">{rapida.cuerpo}</p>
                    {sesion.puede('kb.editar') ? <div className="mt-2 flex gap-2"><Button tamano="sm" onClick={() => setRespuesta({ id: rapida.id, titulo: rapida.titulo, cuerpo: rapida.cuerpo })}>Editar plantilla</Button><Button tamano="sm" onClick={() => setEliminar({ ruta: `/kb/respuestas-rapidas/${rapida.id}`, titulo: rapida.titulo })}>Eliminar plantilla</Button></div> : null}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </ContenidoTab>
      </TabsPanel>
      <ConfirmDialog abierto={Boolean(eliminar)} alCerrar={() => { if (!borrando) setEliminar(null) }} alConfirmar={() => void eliminarContenido()} titulo="Retirar contenido" mensaje={`Se retirará «${eliminar?.titulo ?? ''}» de las consultas del equipo.`} textoConfirmar="Retirar" peligro cargando={borrando} />
      <DialogModal abierto={Boolean(respuesta)} alCerrar={() => { if (!guardandoRespuesta) setRespuesta(null) }} titulo={respuesta?.id ? 'Editar plantilla' : 'Nueva respuesta rápida'} pie={<Button variante="primario" cargando={guardandoRespuesta} disabled={!respuesta || respuesta.titulo.trim().length < 2 || respuesta.cuerpo.trim().length < 2} onClick={() => void guardarRespuesta()}>Guardar plantilla</Button>}>
        {respuesta ? <div className="space-y-4"><Input etiqueta="Nombre de la plantilla" maxLength={120} value={respuesta.titulo} onChange={(e) => setRespuesta({ ...respuesta, titulo: e.target.value })} /><Textarea etiqueta="Mensaje" maxLength={4000} value={respuesta.cuerpo} onChange={(e) => setRespuesta({ ...respuesta, cuerpo: e.target.value })} ayuda="Se insertará como borrador en el ticket. Puedes adaptarlo antes de enviarlo." /></div> : null}
      </DialogModal>

      <DialogModal
        abierto={Boolean(articuloAbierto) && !editarAlCargar}
        alCerrar={() => setArticuloAbierto(null)}
        titulo={detalleArticulo.data?.titulo ?? 'Artículo'}
        tamano="lg"
        descripcion="Biblioteca de ayuda del equipo TI"
        pie={detalleArticulo.data && sesion.puede('kb.editar') ? <><Button variante="secundario" icono={<Pencil size={14} aria-hidden="true" />} onClick={() => abrirEditor(detalleArticulo.data.id)}>Editar artículo</Button><Button onClick={() => { const articulo = detalleArticulo.data; setArticuloAbierto(null); setEliminar({ ruta: `/kb/articulos/${articulo.id}`, titulo: articulo.titulo }) }}>Retirar artículo</Button></> : undefined}
      >
        {detalleArticulo.isPending ? (
          <SkeletonPanel filas={3} />
        ) : detalleArticulo.isError ? (
          <ErrorState compacto mensaje="No pudimos abrir el artículo." alReintentar={() => void detalleArticulo.refetch()} />
        ) : detalleArticulo.data ? (
          <article className="space-y-5">
            <div className="rounded-lg border border-primary/15 bg-primary-soft p-4">
              <p className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground"><span className="flex items-center gap-1.5 font-semibold text-primary-strong"><BookOpen size={16} aria-hidden="true" />{detalleArticulo.data.categoria}</span><span>Actualizado: {fechaCorta(detalleArticulo.data.actualizado_en)}</span></p>
              <p className="text-base leading-relaxed">{detalleArticulo.data.resumen}</p>
            </div>
            <section><h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><FileText size={17} className="text-primary-strong" aria-hidden="true" />Lo que necesitas saber</h3><p className="whitespace-pre-line break-words leading-relaxed">{detalleArticulo.data.cuerpo.split(/(https?:\/\/[^\s<>]+)/g).map((parte, indice) => /^https?:\/\//i.test(parte) ? <a key={indice} href={parte} target="_blank" rel="noopener noreferrer" className="text-primary-strong underline">{parte}</a> : parte)}</p></section>
            {detalleArticulo.data.pasos.length ? (
              <section><h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><ListOrdered size={17} className="text-primary-strong" aria-hidden="true" />Guía paso a paso</h3><ol className="space-y-2">
                {detalleArticulo.data.pasos.map((paso, indice) => <li key={`${indice}-${paso}`} className="flex items-start gap-3 rounded-lg border border-border bg-surface-2 p-3"><span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-sm font-bold text-primary-strong" aria-hidden="true">{indice + 1}</span><p className="min-w-0 pt-0.5 leading-relaxed">{paso}</p></li>)}
              </ol>
              </section>
            ) : null}
            <ReaccionesArticulo key={detalleArticulo.data.id} articulo={detalleArticulo.data} />
          </article>
        ) : null}
      </DialogModal>

      <DialogModal
        abierto={Boolean(editando)}
        alCerrar={() => { if (!guardando) setEditando(null) }}
        titulo={editando?.id ? 'Editar artículo' : 'Nuevo artículo'}
        descripcion="Organiza la información y escribe una guía fácil de seguir."
        tamano="lg"
        pie={
          <>
            <Button disabled={guardando} onClick={() => setEditando(null)}>Cancelar</Button>
            <Button
              variante="primario"
              cargando={guardando}
              disabled={!editando || editando.titulo.trim().length < 4 || editando.resumen.trim().length < 10 || editando.cuerpo.trim().length < 10}
              onClick={() => void guardarArticulo()}
            >
              Guardar
            </Button>
          </>
        }
      >
        {editando ? (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
            <section className="min-w-0 space-y-4 rounded-lg border border-border bg-surface-2 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold"><BookOpen size={17} aria-hidden="true" />Ficha del artículo</h3>
            <Select etiqueta="¿Quién puede leer este artículo?" value={editando.visibilidad ?? 'todos'} onChange={evento => setEditando({ ...editando, visibilidad: evento.target.value as 'todos' | 'equipo_ti' })} opciones={[{ valor: 'todos', etiqueta: 'Todos, incluidos los usuarios' }, { valor: 'equipo_ti', etiqueta: 'Solo técnicos TI y administradores' }]} />
            <Input
              etiqueta="Título"
              maxLength={200}
              value={editando.titulo}
              error={errores.titulo}
              onChange={(evento) => setEditando({ ...editando, titulo: evento.target.value })}
            />
            <Select
              etiqueta="Categoría"
              value={editando.categoria}
              error={errores.categoria}
              onChange={(evento) => setEditando({ ...editando, categoria: evento.target.value })}
              opciones={[...new Set([...(categorias.data?.items ?? []), editando.categoria])].filter(Boolean).map((categoria) => ({ valor: categoria, etiqueta: categoria }))}
            />
            <Input
              etiqueta="Resumen"
              value={editando.resumen}
              error={errores.resumen}
              onChange={(evento) => setEditando({ ...editando, resumen: evento.target.value })}
              maxLength={600}
              ayuda="Entre 10 y 600 caracteres."
            />
            <p className="text-xs text-muted-foreground">El título y el resumen aparecerán en la biblioteca. Usa la categoría para facilitar la búsqueda.</p>
            </section>
            <section className="min-w-0 space-y-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold"><FileText size={17} className="text-primary-strong" aria-hidden="true" />Desarrolla tu guía</h3>
            <Textarea
              etiqueta="Contenido"
              filas={10}
              style={{ minHeight: 240 }}
              value={editando.cuerpo}
              error={errores.cuerpo}
              onChange={(evento) => setEditando({ ...editando, cuerpo: evento.target.value })}
              ayuda="Explica la solución, tutorial o recomendación. Puedes incluir enlaces completos; usa solo fuentes confiables. Mínimo 10 caracteres."
            />
            <div className="rounded-lg border border-border p-3"><p className="mb-2 flex items-center gap-2 text-xs text-muted-foreground"><ListOrdered size={16} aria-hidden="true" />Instrucciones en orden</p><Textarea etiqueta="Pasos (opcional)" filas={4} value={editando.pasos ?? ''} onChange={(evento) => setEditando({ ...editando, pasos: evento.target.value })} ayuda="Un paso por línea. Se mostrarán numerados al leer el artículo." /></div>
            </section>
          </div>
        ) : null}
      </DialogModal>
    </>
  )
}

export type { FiltrosArticulos }
export { Select }
