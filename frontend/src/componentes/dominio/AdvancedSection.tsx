/**
 * Opciones avanzadas del equipo.
 *
 * Ocultas por diseño: la mayoría de los usuarios del sistema nunca las necesita.
 * Se abren bajo petición y su contenido depende del tipo de equipo, porque una
 * computadora y una impresora no se describen igual.
 *
 * Borrarlas es una acción con consecuencia, así que pide confirmación.
 */

import { ChevronDown, ChevronUp, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { api } from '../../api/cliente'
import { Button } from '../base/Button'
import { Nota } from '../base/Estructura'
import { useAvisos } from '../../estado/useAvisos'

const CAMPOS = [
  ['placa_madre', 'Placa madre'], ['procesador_detalle', 'Detalle del procesador'],
  ['fuente_poder', 'Fuente de poder'], ['gabinete', 'Gabinete'],
  ['bateria', 'Batería'], ['cargador', 'Cargador'], ['pantalla', 'Pantalla'],
  ['sistema_operativo', 'Sistema operativo'], ['compra_garantia', 'Compra y garantía'],
  ['mantenimiento', 'Mantenimiento'], ['tipo_impresora', 'Tipo de impresora'],
  ['conexion', 'Conexión'], ['resolucion', 'Resolución'],
] as const

function seccion(detalle: Record<string, unknown> | null | undefined, campo: string): Record<string, unknown> {
  const valor = detalle?.[campo]
  return valor && typeof valor === 'object' && !Array.isArray(valor) ? valor as Record<string, unknown> : {}
}

export function AdvancedSection({
  titulo,
  descripcion,
  equipoId,
  detalleActual,
  puedeEditar,
  alQuitar,
  alActualizar,
}: {
  titulo: string
  descripcion: string
  equipoId: string
  tipo?: string
  detalleActual?: Record<string, unknown> | null
  puedeEditar: boolean
  alQuitar: () => void
  alActualizar: () => void
}) {
  const avisos = useAvisos()
  const [abierto, setAbierto] = useState(false)
  const [valores, setValores] = useState<Record<string, string>>({})
  const [guardando, setGuardando] = useState(false)

  const guardar = async () => {
    setGuardando(true)
    try {
      const detalle = { ...detalleActual }
      for (const [campo, valor] of Object.entries(valores)) {
        detalle[campo] = { ...seccion(detalleActual, campo), descripcion: valor.trim() || null }
      }
      await api.editar(`/activos/${equipoId}`, { opciones_avanzadas: true, detalle_avanzado: detalle })
      await alActualizar()
      setValores({})
      avisos.exito('Datos avanzados guardados')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="rounded-[var(--radius-panel)] border border-border bg-surface">
      <header className="flex items-start justify-between gap-2 p-3">
        <div className="min-w-0">
          <h2 className="font-semibold">{titulo}</h2>
          <p className="text-sm text-muted-foreground">{descripcion}</p>
        </div>
        <Button
          variante="fantasma"
          soloIcono
          tamano="sm"
          onClick={() => setAbierto((valor) => !valor)}
          aria-expanded={abierto}
          aria-label={abierto ? 'Ocultar las opciones avanzadas' : 'Mostrar las opciones avanzadas'}
        >
          {abierto ? <ChevronUp size={18} aria-hidden="true" /> : <ChevronDown size={18} aria-hidden="true" />}
        </Button>
      </header>

      {abierto ? (
        <div className="border-t border-border p-3">
          <Nota tono="info">
            <p>
              Estos datos solo se piden para compras y reparaciones. No son obligatorios para registrar el equipo.
            </p>
          </Nota>

          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {CAMPOS.map(([campo, etiqueta]) => (
              <label key={campo} className="flex flex-col gap-1">
                <span className="text-sm font-semibold">{etiqueta}</span>
                <input
                  value={valores[campo] ?? String(seccion(detalleActual, campo).descripcion ?? '')}
                  disabled={!puedeEditar}
                  onChange={(evento) => setValores((actual) => ({ ...actual, [campo]: evento.target.value }))}
                  className="h-[var(--spacing-control)] rounded-[var(--radius-control)] border border-input bg-surface px-3 disabled:bg-muted"
                />
              </label>
            ))}
          </div>

          {puedeEditar ? (
            <div className="mt-3 flex flex-wrap justify-end gap-2">
              <Button
                variante="secundario"
                icono={<Trash2 size={16} aria-hidden="true" />}
                onClick={alQuitar}
              >
                Eliminar estos datos
              </Button>
              <Button variante="primario" cargando={guardando} disabled={!Object.keys(valores).length} onClick={() => void guardar()}>
                Guardar
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
