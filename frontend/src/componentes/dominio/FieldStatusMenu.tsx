/**
 * Menú de estado de un campo del inventario.
 *
 * El punto importante del sistema: un dato que el equipo no va a tener nunca
 * («este teclado no tiene código patrimonial») se marca «No aplica» y sale del
 * denominador de completitud. Un dato que todavía no se sabe es «No disponible».
 * No es lo mismo, y el menú lo explica.
 */

import { useState } from 'react'

import { ESTADOS_CAMPO, estadoCampoDe, type EstadoCampo } from '../../dominio/estados'
import { PopoverSimple } from '../base/Sobreposiciones'
import { Button } from '../base/Button'
import { Input } from '../base/Campo'

const MOTIVOS: Record<EstadoCampo, string> = {
  completo: 'El dato está escrito',
  pendiente: 'Falta escribir este dato',
  no_aplica: 'Este equipo no tiene este dato y no lo tendrá',
  no_disponible: 'Todavía no se sabe el dato',
}

export function FieldStatusMenu({
  valor,
  onCambiar,
  alMarcarVarios,
  deshabilitado,
}: {
  valor: string | null | undefined
  onCambiar: (estado: EstadoCampo, motivo?: string) => void
  /** Si se pasa, el menú ofrece marcar varios campos a la vez. */
  alMarcarVarios?: (estado: EstadoCampo, motivo?: string) => void
  deshabilitado?: boolean
}) {
  const [motivo, setMotivo] = useState('')
  const definicionActual = estadoCampoDe(valor)

  return (
    <PopoverSimple
      ancho="w-72"
      disparador={
        <Button variante="secundario" tamano="sm" disabled={deshabilitado}>
          {definicionActual.texto}
        </Button>
      }
      contenido={
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold">Estado del campo</p>
          <ul className="flex flex-col gap-1">
            {(Object.keys(ESTADOS_CAMPO) as EstadoCampo[]).map((clave) => {
              const item = estadoCampoDe(clave)
              const activo = definicionActual.clave === clave
              return (
                <li key={clave}>
                  <button
                    type="button"
                    onClick={() => {
                      onCambiar(clave, motivo.trim() || MOTIVOS[clave])
                      if (alMarcarVarios) alMarcarVarios(clave, motivo.trim() || MOTIVOS[clave])
                    }}
                    className={`w-full rounded-[var(--radius-control)] px-2 py-1.5 text-left text-sm hover:bg-muted ${
                      activo ? 'bg-primary-soft font-semibold text-primary-strong' : ''
                    }`}
                  >
                    <span className="block font-semibold">{item.texto}</span>
                    <span className="block text-2xs text-muted-foreground">{MOTIVOS[clave]}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          <Input
            etiqueta="Motivo (opcional)"
            value={motivo}
            onChange={(evento) => setMotivo(evento.target.value)}
            placeholder="Por ejemplo: equipo de préstamo"
          />
        </div>
      }
    />
  )
}
