/**
 * Gráficos.
 *
 * Reglas que no se rompen en ningún gráfico de la aplicación:
 * - El azul es dato real; el teal es IA o predicción. Nunca se intercambian.
 * - El color nunca es la única señal: hay etiqueta directa, valor numérico y
 *   estados de carga, vacío y error.
 * - Cada gráfico lleva debajo su tabla de datos, que es la alternativa real
 *   para quien no ve colores o usa lector de pantalla.
 * - Si la API dice que no hay datos suficientes, se dice: no se dibuja una gráfica
 *   vacía con un título optimista.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChevronRight, CircleAlert, LineChart as IconoLinea } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { fechaNumerica, numero, porcentaje } from '../../dominio/formato'
import { EmptyState, Panel } from '../base/Estructura'

/* ══ Tarjeta de gráfico ═══════════════════════════════════════ */

export function ChartCard({
  titulo,
  descripcion,
  acciones,
  children,
  tabla,
  sufijo,
  className,
}: {
  titulo: string
  descripcion?: string
  acciones?: ReactNode
  children: ReactNode
  /** Tabla de datos: la alternativa accesible, siempre presente. */
  tabla: { etiqueta: string; valor: number | string }[]
  sufijo?: string
  className?: string
}) {
  return (
    <Panel
      titulo={titulo}
      descripcion={descripcion}
      acciones={acciones}
      className={cn('min-w-0', className)}
    >
      {children}
      <details className="mt-3">
        <summary className="cursor-pointer text-sm font-semibold text-primary-strong">Ver los datos en tabla</summary>
        <div className="sin-barra mt-2 max-h-56 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th scope="col" className="px-2 py-1 text-left font-semibold">
                  Categoría
                </th>
                <th scope="col" className="px-2 py-1 text-right font-semibold">
                  Valor{sufijo ? ` (${sufijo})` : ''}
                </th>
              </tr>
            </thead>
            <tbody>
              {tabla.map((fila, indice) => (
                <tr key={`${fila.etiqueta}-${indice}`} className="border-t border-border">
                  <td className="px-2 py-1">{/^\d{4}-\d{2}-\d{2}$/.test(fila.etiqueta) ? fechaNumerica(fila.etiqueta) : fila.etiqueta}</td>
                  <td className="px-2 py-1 text-right font-medium">
                    {typeof fila.valor === 'number' ? numero(fila.valor) : fila.valor}
                    {sufijo ? ` ${sufijo}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Panel>
  )
}

/* ══ Estado vacío honesto ═════════════════════════════════════ */

export function SinDatos({
  titulo = 'Datos insuficientes para el gráfico',
  descripcion,
}: {
  titulo?: string
  descripcion?: string
}) {
  return (
    <EmptyState
      compacto
      icono={<IconoLinea size={20} aria-hidden="true" />}
      titulo={titulo}
      descripcion={descripcion ?? 'La API no devolvió suficientes registros en este periodo para dibujar una tendencia.'}
    />
  )
}

/* ══ Barras horizontales: barras Campos ══════════════════════ */

export type FilaBarra = {
  etiqueta: string
  valor: number
  detalle?: string
  id?: string
}

export function BarrasCampos({
  datos,
  unidad,
  sufijo,
  maximo,
  className,
  /** Distingue las claves entre listas: dos listas pueden traer la misma etiqueta. */
  nombreLista = 'barras',
  alSeleccionar,
  pie,
  /** Ancho de la columna de etiquetas. Los nombres largos de oficina lo necesitan. */
  anchoEtiqueta = 'w-32',
  descripcionSeleccion = 'Abrir inventario filtrado.',
}: {
  datos: FilaBarra[]
  /** «equipos», «%», «min»… va en la etiqueta del eje y en la tabla. */
  unidad?: string
  sufijo?: string
  maximo?: number
  className?: string
  nombreLista?: string
  alSeleccionar?: (fila: FilaBarra) => void
  /** Explicación al pie. Si no se pasa, se escribe la suma de los valores. */
  pie?: string
  anchoEtiqueta?: string
  descripcionSeleccion?: string
}) {
  if (datos.length === 0) return <SinDatos titulo="Sin datos que graficar" />

  const techo = maximo ?? Math.max(...datos.map((fila) => fila.valor), 1)
  const total = datos.reduce((suma, fila) => suma + fila.valor, 0)

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {datos.map((fila, indice) => {
        const contenido = (
          <>
            <span
              className={cn('shrink-0 truncate text-left text-sm', anchoEtiqueta)}
              title={fila.detalle ? `${fila.etiqueta}: ${fila.detalle}` : fila.etiqueta}
            >
              {fila.etiqueta}
              {fila.detalle && <span className="block truncate text-2xs text-muted-foreground">{fila.detalle}</span>}
            </span>
            <div className="h-5 min-w-0 flex-1 overflow-hidden rounded-[4px] bg-muted">
              {/*
                A 0 no se dibuja nada. Antes había un mínimo de 2 px para que la
                barra se «notase», y el resultado era lo contrario de lo buscado:
                una fila a 0 % salía con un trocito de color, que se lee como
                «hay algo escrito». Si no hay nada escrito, la pista se queda
                vacía —que es exactamente lo que significa ese 0 %.
              */}
              {fila.valor > 0 ? (
                <div
                  className="h-full rounded-[4px]"
                  style={{
                    width: `${Math.min(100, (fila.valor / techo) * 100)}%`,
                    // El color lo aporta el token; la barra siempre lleva su número
                    backgroundColor: 'var(--color-chart-real)',
                    opacity: 1 - (indice / (datos.length * 1.6)),
                  }}
                />
              ) : null}
            </div>
            <span className="w-20 shrink-0 text-right text-sm font-semibold">
              {sufijo ? porcentaje(fila.valor, 0) : numero(fila.valor)}
              {sufijo ? '' : ` ${unidad ?? ''}`}
            </span>
          </>
        )
        const clave = `${nombreLista}-${fila.etiqueta}-${indice}`
        return alSeleccionar && fila.id ? (
          /*
            Las filas que llevan a otra pantalla tienen que decir **dónde está el
            ratón**. Antes el fondo cambiaba de `muted/60`, que es un gris tan
            cercano al de la pista que no se veía: había cinco barras pulsables y
            ninguna decía cuál. Ahora el hover es un bloque de color claro con
            una marca a la izquierda y una flecha a la derecha, que es lo que
            señala «esto se abre»; el resto de filas, las que no hacen nada, se
            quedan como estaban para que se distingan de un vistazo.
          */
          <button
            key={clave}
            type="button"
            className={cn(
              'group flex min-h-10 w-full cursor-pointer items-center gap-3 rounded-md border-l-[3px] border-l-transparent pl-1.5 pr-2 text-left',
              'transition-colors duration-100 hover:border-l-primary hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
            )}
            aria-label={`${fila.etiqueta}: ${fila.detalle ?? `${numero(fila.valor)} ${unidad ?? sufijo ?? ''}`}. ${descripcionSeleccion}`}
            onClick={() => alSeleccionar(fila)}
          >
            {contenido}
            <span
              aria-hidden="true"
              className="shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
            >
              <ChevronRight size={16} />
            </span>
          </button>
        ) : (
          <div key={clave} className="flex min-h-10 items-center gap-3">
            {contenido}
          </div>
        )
      })}
      {/*
        La suma solo tiene sentido cuando las barras cuentan la misma cosa.

        Con porcentajes —«Por zona», «Por tipo», «Por oficina»— se escribía
        «Suma: 1.096 %», que no significa nada: los porcentajes de zonas distintas
        no se suman entre sí, y 1.096 % era un número que no iba con nada. Con
        unidades de recuento la suma sí vale, pero quien la lee tiene que saber
        que un equipo puede aparecer en varias barras.
      */}
      <p className="text-2xs text-muted-foreground">
        {pie ??
          (sufijo
            ? 'Cada barra lleva su porcentaje escrito al lado.'
            : `Suma: ${numero(total)} ${unidad ?? ''}. Cada barra tiene su valor escrito al lado.`)}
      </p>
    </div>
  )
}

/* ══ Línea de tiempo ══════════════════════════════════════════ */

export type PuntoSerie = {
  etiqueta: string
  valor: number
  /** Si viene, la serie es de predicción y se dibuja en teal y discontinua. */
  previsto?: boolean
}

export function GraficoLinea({
  datos,
  titulo,
  descripcion,
  unidad,
  acciones,
  altura = 240,
}: {
  datos: PuntoSerie[]
  titulo: string
  descripcion?: string
  unidad?: string
  acciones?: ReactNode
  altura?: number
}) {
  if (datos.length < 2) {
    return (
      <ChartCard titulo={titulo} descripcion={descripcion} tabla={[]} acciones={acciones}>
        <SinDatos />
      </ChartCard>
    )
  }

  return (
    <ChartCard
      titulo={titulo}
      descripcion={descripcion}
      acciones={acciones}
      sufijo={unidad}
      tabla={datos.map((punto) => ({ etiqueta: punto.etiqueta, valor: punto.valor }))}
    >
      <ResponsiveContainer width="100%" height={altura}>
        <LineChart data={datos} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="var(--color-chart-grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="etiqueta"
            minTickGap={24}
            tickFormatter={(valor: string) => /^\d{4}-\d{2}-\d{2}$/.test(valor) ? `${valor.slice(8, 10)}/${valor.slice(5, 7)}` : valor}
            tick={{ fontSize: 12, fill: 'var(--color-muted-foreground)' }}
            stroke="var(--color-chart-grid)"
          />
          <YAxis allowDecimals={unidad !== 'tickets'} tick={{ fontSize: 12, fill: 'var(--color-muted-foreground)' }} stroke="var(--color-chart-grid)" />
          <Tooltip
            labelFormatter={(valor) => /^\d{4}-\d{2}-\d{2}$/.test(String(valor)) ? fechaNumerica(String(valor)) : valor}
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-control)',
              fontSize: '0.875rem',
            }}
            labelStyle={{ color: 'var(--color-foreground)' }}
          />
          <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
          <Line
            type="monotone"
            dataKey="valor"
            name={unidad ?? 'Valor'}
            stroke="var(--color-chart-real)"
            strokeWidth={2}
            dot={datos.length > 45 ? false : { r: 3, fill: 'var(--color-chart-real)' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/* ══ Barras verticales por categoría ═══════════════════════════ */

export function GraficoBarras({
  datos,
  titulo,
  descripcion,
  unidad,
  acciones,
  alto = 240,
  orden = false,
}: {
  datos: FilaBarra[]
  titulo: string
  descripcion?: string
  unidad?: string
  acciones?: ReactNode
  alto?: number
  /** Para rankings: la barra más larga arriba. */
  orden?: boolean
}) {
  if (datos.length === 0) {
    return (
      <ChartCard titulo={titulo} descripcion={descripcion} tabla={[]} acciones={acciones}>
        <SinDatos titulo="Sin datos que graficar" />
      </ChartCard>
    )
  }

  const ordenados = orden ? [...datos].sort((a, b) => b.valor - a.valor) : datos
  const alturaEtiquetas = Math.max(80, ordenados.length * 28)

  return (
    <ChartCard
      titulo={titulo}
      descripcion={descripcion}
      acciones={acciones}
      sufijo={unidad}
      tabla={ordenados.map((fila) => ({ etiqueta: fila.etiqueta, valor: fila.valor }))}
    >
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={ordenados} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="var(--color-chart-grid)" strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 12, fill: 'var(--color-muted-foreground)' }}
            stroke="var(--color-chart-grid)"
          />
          <YAxis
            type="category"
            dataKey="etiqueta"
            width={alturaEtiquetas > 80 ? 120 : 90}
            tick={{ fontSize: 12, fill: 'var(--color-muted-foreground)' }}
            stroke="var(--color-chart-grid)"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-control)',
              fontSize: '0.875rem',
            }}
          />
          <Bar dataKey="valor" name={unidad ?? 'Valor'} radius={[0, 4, 4, 0]}>
            {ordenados.map((fila, indice) => (
              <Cell
                key={`${fila.etiqueta}-${indice}`}
                fill={fila.detalle?.includes('previsto') ? 'var(--color-chart-ai)' : 'var(--color-chart-real)'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/* ══ Distribución ═════════════════════════════════════════════ */

export function GraficoDistribucion({
  datos,
  titulo,
  descripcion,
  acciones,
}: {
  datos: { etiqueta: string; valor: number; color?: string }[]
  titulo: string
  descripcion?: string
  acciones?: ReactNode
}) {
  if (datos.length === 0) {
    return (
      <ChartCard titulo={titulo} descripcion={descripcion} tabla={[]} acciones={acciones}>
        <SinDatos titulo="Sin datos que distribuir" />
      </ChartCard>
    )
  }

  const total = datos.reduce((suma, fila) => suma + fila.valor, 0)

  return (
    <ChartCard
      titulo={titulo}
      descripcion={descripcion}
      acciones={acciones}
      tabla={datos.map((fila) => ({
        etiqueta: fila.etiqueta,
        valor: `${numero(fila.valor)} (${porcentaje(total ? (fila.valor / total) * 100 : 0, 0)})`,
      }))}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <ResponsiveContainer width="100%" height={200} className="sm:w-1/2">
          <PieChart>
            <Pie
              data={datos}
              dataKey="valor"
              nameKey="etiqueta"
              innerRadius={45}
              outerRadius={80}
              paddingAngle={2}
              label={({ name, value }) => `${name}: ${value}`}
              labelLine={false}
            >
              {datos.map((fila, indice) => (
                <Cell key={`${fila.etiqueta}-${indice}`} fill={fila.color ?? colorPorIndice(indice)} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        {/* La leyenda lleva el número: no depende del color */}
        <ul className="flex flex-col gap-1.5 sm:w-1/2">
          {datos.map((fila, indice) => (
            <li key={fila.etiqueta} className="flex items-center gap-2 text-sm">
              <span
                aria-hidden="true"
                className="size-3 shrink-0 rounded-sm"
                style={{ backgroundColor: fila.color ?? colorPorIndice(indice) }}
              />
              <span className="min-w-0 flex-1 truncate">{fila.etiqueta}</span>
              <span className="font-semibold">{numero(fila.valor)}</span>
              <span className="text-sm text-muted-foreground">
                ({porcentaje(total ? (fila.valor / total) * 100 : 0, 0)})
              </span>
            </li>
          ))}
        </ul>
      </div>
    </ChartCard>
  )
}

/** Paleta categórica: todos los tonos son distinguibles sin depender del color. */
function colorPorIndice(indice: number): string {
  const paleta = [
    'var(--color-chart-real)',
    'var(--color-chart-ok)',
    'var(--color-chart-warn)',
    'var(--color-chart-ai)',
    'var(--color-chart-critical)',
    'var(--color-chart-neutral)',
  ]
  return paleta[indice % paleta.length]
}

/* ══ Aviso de periodo sin datos ══════════════════════════════ */

export function AvisoPeriodoVacio({ periodo }: { periodo?: string }) {
  return (
    <div className="flex items-start gap-2 rounded-[var(--radius-panel)] border border-warning/30 bg-warning-soft p-3 text-sm text-warning-strong">
      <CircleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>
        En {periodo ?? 'este periodo'} no hay tickets registrados todavía. Los gráficos se quedan esperando casos reales.
      </span>
    </div>
  )
}
