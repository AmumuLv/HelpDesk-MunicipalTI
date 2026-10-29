/**
 * Ayuda: la base de conocimiento para el usuario final.
 *
 * Búsqueda por texto, filtro por categoría y una pestaña de los más leídos. Los
 * artículos sugeridos por la IA solo aparecen si la persona tiene las
 * recomendaciones activadas y la API los devuelve.
 */

import { BookOpen, Search, Eye, ThumbsUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useArticulos, useCategoriasKb, useSugerenciaReporte } from '../../api/hooks'
import type { FiltrosArticulos } from '../../api/tipos'
import { EtiquetaIA } from '../../componentes/dominio/Badge'
import { Button } from '../../componentes/base/Button'
import { SearchInput, Select } from '../../componentes/base/Campo'
import { EmptyState, ErrorState, PageHeader, Panel, SkeletonPanel } from '../../componentes/base/Estructura'
import { numero } from '../../dominio/formato'
import { useSesion } from '../../estado/useSesion'

export function Ayuda() {
  const sesion = useSesion()
  const [texto, setTexto] = useState('')
  const [categoria, setCategoria] = useState('')
  const [pestana, setPestana] = useState<'todos' | 'populares'>('todos')

  useEffect(() => {
    document.title = 'Ayuda · Mesa de Ayuda'
  }, [])

  const filtros: FiltrosArticulos = {
    ...(texto.trim() ? { texto: texto.trim() } : {}),
    ...(categoria ? { categoria } : {}),
    por_pagina: 20,
  }
  const articulos = useArticulos(filtros)
  const categorias = useCategoriasKb()

  // Las sugerencias solo se piden si la persona las tiene activadas
  const puedeSugerir = sesion.usuario?.recomendaciones_ia === true
  const sugeridos = useSugerenciaReporte({}, puedeSugerir)

  const items = articulos.data?.items ?? []
  // Los populares se ordenan por popularidad sobre los datos ya servidos:
  // el backend no expone un filtro de "más leídos"
  const visibles = pestana === 'populares' ? [...items].sort((a, b) => b.popularidad - a.popularidad) : items

  return (
    <>
      <PageHeader titulo="Ayuda" descripcion="Respuestas a las preguntas más comunes sobre el uso de equipos y sistemas." />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <SearchInput
          etiqueta="Buscar en la ayuda"
          className="sm:flex-1"
          valor={texto}
          alCambiar={setTexto}
          placeholder="Escribe lo que necesitas…"
        />
        <Select
          etiqueta="Tema"
          value={categoria}
          onChange={(evento) => setCategoria(evento.target.value)}
          placeholder="Todos los temas"
          opciones={(categorias.data?.items ?? []).map((valor) => ({ valor, etiqueta: valor }))}
        />
      </div>

      {/* Sugerencias de la IA: solo si están activadas y hay articles */}
      {puedeSugerir && (sugeridos.data?.articulos.length ?? 0) > 0 ? (
        <Panel
          titulo={
            <span className="flex items-center gap-2">
              Sugeridos para ti <EtiquetaIA />
            </span>
          }
          descripcion={sugeridos.data?.explicacion}
        >
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {sugeridos.data?.articulos.map((articulo) => (
              <li key={articulo.id}>
                <Link
                  to={`${sesion.esTecnico ? "/panel/ayuda" : "/ayuda"}/${articulo.id}`}
                  className="block h-full rounded-[var(--radius-panel)] border border-ai/25 bg-ai-soft p-3 transition-colors hover:border-ai/50"
                >
                  <p className="font-semibold">{articulo.titulo}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{articulo.resumen}</p>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <div className="flex gap-1 border-b border-border" role="tablist" aria-label="Orden de los artículos">
        {(['todos', 'populares'] as const).map((clave) => (
          <button
            key={clave}
            type="button"
            role="tab"
            aria-selected={pestana === clave}
            onClick={() => setPestana(clave)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold ${
              pestana === clave ? 'border-primary text-primary-strong' : 'border-transparent text-muted-foreground'
            }`}
          >
            {clave === 'todos' ? 'Todos' : 'Más leídos'}
          </button>
        ))}
      </div>

      {articulos.isLoading ? (
        <SkeletonPanel filas={4} />
      ) : articulos.isError ? (
        <ErrorState
          mensaje="No pudimos cargar los artículos."
          detalle={articulos.error instanceof Error ? articulos.error.message : undefined}
          alReintentar={() => void articulos.refetch()}
        />
      ) : visibles.length === 0 ? (
        <EmptyState
          icono={texto || categoria ? <Search size={20} aria-hidden="true" /> : <BookOpen size={20} aria-hidden="true" />}
          titulo={texto || categoria ? 'Ningún artículo coincide' : 'Todavía no hay artículos publicados'}
          descripcion={
            texto || categoria
              ? 'Prueba con otras palabras o quita el filtro de tema.'
              : 'El equipo TI puede publicar artículos desde su panel.'
          }
          accion={
            texto || categoria ? (
              <Button
                onClick={() => {
                  setTexto('')
                  setCategoria('')
                }}
              >
                Quitar filtros
              </Button>
            ) : null
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          {visibles.map((articulo) => (
            <li key={articulo.id}>
              <Link
                to={`${sesion.esTecnico ? "/panel/ayuda" : "/ayuda"}/${articulo.id}`}
                className="flex h-full flex-col rounded-[var(--radius-panel)] border border-border bg-surface p-3 transition-colors hover:bg-muted"
              >
                <p className="font-semibold">{articulo.titulo}</p>
                <p className="mt-1 flex-1 text-sm text-muted-foreground">{articulo.resumen}</p>
                <p className="mt-2 flex flex-wrap items-center gap-3 text-2xs text-muted-foreground">
                  <span className="rounded bg-muted px-1.5 py-0.5 font-medium">{articulo.categoria}</span>
                  <span className="flex items-center gap-1">
                    <Eye size={12} aria-hidden="true" />
                    {numero(articulo.visualizaciones)} lecturas
                  </span>
                  <span className="flex items-center gap-1"><ThumbsUp size={12} aria-hidden="true" />{numero(articulo.me_gusta ?? 0)} me gusta</span>
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
