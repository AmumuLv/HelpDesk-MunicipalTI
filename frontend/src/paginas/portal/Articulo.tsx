/**
 * Artículo de ayuda: lectura y valoración.
 *
 * Los pasos van numerados porque así se leen cuando se sigue una instrucción.
 * El me gusta es opcional y en un solo toque.
 */

import { ArrowLeft, ChevronRight } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useSesion } from '../../estado/useSesion'

import { useArticulo } from '../../api/hooks'
import { ErrorState, Nota, Panel, SkeletonPanel } from '../../componentes/base/Estructura'
import { fechaLarga } from '../../dominio/formato'
import { ReaccionesArticulo } from '../../componentes/dominio/ReaccionesArticulo'

export function Articulo() {
  const sesion = useSesion()
  const { id } = useParams<{ id: string }>()
  const articulo = useArticulo(id)
  useEffect(() => {
    if (articulo.data) document.title = `${articulo.data.titulo} · Ayuda`
  }, [articulo.data])

  if (articulo.isLoading) return <SkeletonPanel filas={5} />

  if (articulo.isError || !articulo.data) {
    return (
      <ErrorState
        mensaje="No pudimos cargar este artículo."
        detalle={articulo.error instanceof Error ? articulo.error.message : undefined}
        alReintentar={() => void articulo.refetch()}
      />
    )
  }

  const datos = articulo.data

  return (
    <>
      <nav aria-label="Ruta de navegación">
        <ol className="flex flex-wrap items-center gap-1 text-sm">
          <li>
            <Link to={sesion.esTecnico ? "/panel/ayuda" : "/ayuda"} className="flex items-center gap-1 font-medium text-primary-strong hover:underline">
              <ArrowLeft size={14} aria-hidden="true" />
              Ayuda
            </Link>
          </li>
          <li aria-hidden="true" className="text-muted-foreground">
            <ChevronRight size={14} />
          </li>
          <li className="font-semibold">{datos.categoria}</li>
        </ol>
      </nav>

      <article className="flex flex-col gap-4">
        <header>
          <h1 className="titulo-pagina">{datos.titulo}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Actualizado el {fechaLarga(datos.actualizado_en)}</p>
        </header>

        <Panel>
          <p className="text-base whitespace-pre-line">{datos.cuerpo}</p>

          {datos.pasos?.length ? (
            <ol className="mt-4 flex flex-col gap-3">
              {datos.pasos.map((paso, indice) => (
                <li key={indice} className="flex gap-3">
                  <span
                    aria-hidden="true"
                    className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground"
                  >
                    {indice + 1}
                  </span>
                  <p className="min-w-0 flex-1 text-base whitespace-pre-line">{paso}</p>
                </li>
              ))}
            </ol>
          ) : null}
        </Panel>

        {datos.etiquetas?.length ? (
          <p className="flex flex-wrap gap-1.5">
            {datos.etiquetas.map((etiqueta) => (
              <span key={etiqueta} className="rounded bg-muted px-2 py-0.5 text-2xs">
                {etiqueta}
              </span>
            ))}
          </p>
        ) : null}

        <ReaccionesArticulo key={datos.id} articulo={datos} />

        {datos.relacionados?.length ? (
          <Panel titulo="Artículos relacionados">
            <ul className="flex flex-col gap-2">
              {datos.relacionados.map((relacionado) => (
                <li
                  key={relacionado}
                  className="rounded-[var(--radius-panel)] border border-border p-3 text-base"
                >
                  {relacionado}
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}

        <Nota tono="info" titulo="¿Sigue sin funcionar?">
          <p>
            Si después de seguir estos pasos el problema continúa,{' '}
            <Link to={sesion.esTecnico ? "/panel/tickets/nuevo" : "/reportar"} className="font-semibold underline">
              repórtalo
            </Link>{' '}
            para que el equipo TI lo revise.
          </p>
        </Nota>
      </article>
    </>
  )
}
