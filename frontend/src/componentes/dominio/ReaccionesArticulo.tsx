import { ThumbsUp, Users } from 'lucide-react'
import { useId, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { claves } from '../../api/consultas'
import type { ArticuloKbDetalle } from '../../api/tipos'
import { useAvisos } from '../../estado/Avisos'
import { Button } from '../base/Button'
import { ErrorState } from '../base/Estructura'
import { Paginacion } from './DataTable'

type Reaccion = { me_gusta: number; mi_valoracion: boolean | null; valoraciones: number; valoracion_promedio: number | null }
type Personas = { items: { usuario_id: string; nombre: string }[]; total: number; total_paginas: number }

export function ReaccionesArticulo({ articulo }: { articulo: ArticuloKbDetalle }) {
  const cache = useQueryClient()
  const avisos = useAvisos()
  const listaId = useId()
  const bloqueo = useRef(false)
  const [guardando, setGuardando] = useState(false)
  const [mostrar, setMostrar] = useState(false)
  const [pagina, setPagina] = useState(1)
  const personas = useQuery({ queryKey: ['kb', 'me-gusta', articulo.id, pagina], queryFn: () => api.obtener<Personas>(`/kb/articulos/${articulo.id}/me-gusta?pagina=${pagina}&por_pagina=10`), enabled: mostrar, placeholderData: undefined })
  const gusta = articulo.mi_valoracion === true
  const votar = async () => {
    if (bloqueo.current) return
    bloqueo.current = true; setGuardando(true)
    try {
      const ruta = `/kb/articulos/${articulo.id}/valorar`
      const datos = gusta ? await api.borrar<Reaccion>(ruta) : await api.crear<Reaccion>(ruta, { util: true })
      cache.setQueryData<ArticuloKbDetalle>(claves.kbArticulo(articulo.id), anterior => anterior ? { ...anterior, ...datos } : anterior)
      setPagina(1)
      void cache.invalidateQueries({ queryKey: ['kb', 'articulos'] })
      void cache.invalidateQueries({ queryKey: ['kb', 'me-gusta', articulo.id] })
      if (!datos.me_gusta) setMostrar(false)
    } catch (fallo) { avisos.desdeError(fallo, 'No pudimos guardar tu me gusta. Puedes reintentar.') }
    finally { bloqueo.current = false; setGuardando(false) }
  }
  return <section className="mt-4 border-t border-border pt-4" aria-label="Me gusta del artículo">
    <div className="flex flex-wrap items-center gap-2"><Button variante={gusta ? 'exito' : 'secundario'} aria-pressed={gusta} aria-label={gusta ? 'Quitar me gusta' : 'Me gusta'} cargando={guardando} onClick={() => void votar()} icono={<ThumbsUp size={17} fill={gusta ? 'currentColor' : 'none'} />}>{gusta ? 'Te gusta' : 'Me gusta'} · {articulo.me_gusta ?? 0}</Button>
      {(articulo.me_gusta ?? 0) > 0 ? <Button variante="fantasma" tamano="sm" aria-expanded={mostrar} aria-controls={listaId} icono={<Users size={15} />} onClick={() => { setPagina(1); setMostrar(!mostrar) }}>{mostrar ? 'Ocultar personas' : 'Ver a quiénes les gusta'}</Button> : null}
    </div>
    {mostrar ? <div id={listaId} className="mt-3" aria-label="Personas a las que les gusta">{personas.isPending ? <p role="status" className="text-sm text-muted-foreground">Cargando personas…</p> : personas.isError ? <ErrorState compacto mensaje="No pudimos cargar a las personas." alReintentar={() => void personas.refetch()} /> : <><ul className="divide-y divide-border">{personas.data?.items.map(persona => <li key={persona.usuario_id} className="flex min-w-0 items-center gap-2 py-2 text-sm"><span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-info-soft font-semibold text-info-strong" aria-hidden="true">{persona.nombre.slice(0, 1).toUpperCase()}</span><span className="truncate" title={persona.nombre}>{persona.nombre}</span></li>)}</ul><Paginacion pagina={pagina} totalPaginas={personas.data?.total_paginas ?? 1} total={personas.data?.total ?? 0} porPagina={10} alCambiar={setPagina} /></>}</div> : null}
  </section>
}
