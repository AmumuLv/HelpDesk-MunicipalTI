import type { ReactNode } from 'react'

export type MetricaPerfil = { etiqueta: string; valor: ReactNode }

export function TarjetaPerfil({
  titulo,
  subtitulo,
  icono,
  metricas,
  colorIndice,
}: {
  titulo: string
  subtitulo?: ReactNode
  icono: ReactNode
  metricas: MetricaPerfil[]
  colorIndice?: number
}) {
  const conZona = colorIndice && colorIndice >= 1 && colorIndice <= 8
  const color = conZona ? `var(--zona-${colorIndice})` : 'var(--color-primary)'
  /*
    La franja de arriba y el fondo de la cabecera usan **el mismo** color: el de
    la zona. Antes el fondo era el color de marca —un ámbar— mientras la franja
    era el violeta de la zona, y salía una cabecera mitad y mitad que no
    significaba nada: el ojo leía un color que no iba con ningún otro sitio de la
    pantalla. Con un solo color, la ficha se lee como «este equipo es de COMPLEJO»
    desde el primer golpe de vista.
  */
  const fondo = conZona
    ? `color-mix(in srgb, ${color} 9%, var(--color-surface))`
    : 'var(--color-primary-soft)'
  const circulo = conZona
    ? `color-mix(in srgb, ${color} 18%, var(--color-surface))`
    : 'var(--color-surface)'
  return (
    <section className="overflow-hidden rounded-[var(--radius-panel)] border border-border/80 bg-surface shadow-panel">
      <header
        className="flex items-center gap-3.5 border-b border-border/60 p-4"
        style={{ borderTop: `4px solid ${color}`, backgroundColor: fondo }}
      >
        <span className="flex size-12 shrink-0 items-center justify-center rounded-full" style={{ backgroundColor: circulo, color }}>
          {icono}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-lg font-bold">{titulo}</span>
          {subtitulo ? <span className="block min-w-0 text-sm text-muted-foreground">{subtitulo}</span> : null}
        </span>
      </header>
      <dl className="grid grid-cols-2 divide-x divide-y divide-border/70 bg-surface-2/30 sm:grid-cols-4 sm:divide-y-0">
        {metricas.slice(0, 4).map((metrica) => (
          <div key={metrica.etiqueta} className="min-w-0 p-3">
            <dt className="truncate text-sm text-muted-foreground">{metrica.etiqueta}</dt>
            <dd className="mt-0.5 truncate text-xl font-bold tabular-nums">{metrica.valor}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
