/**
 * Dónde está: oficina y zona, siempre en el mismo orden y siempre igual.
 *
 * Antes cada pantalla montaba el dato a su manera y el resultado cambiaba según el
 * ancho de la columna: en unas cabía «Sin oficina» y la pastilla de zona en la
 * misma línea, y en otras la pastilla saltaba a una línea aparte. La misma celda
 * se leía de dos maneras según la vista.
 *
 * Aquí se conserva el diseño que ya se conoce —la oficina con su raya de color y
 * debajo la pastilla de zona con su recuadro— y lo único que se fija es que sea
 * **igual en todas partes**, que es lo que faltaba. La pastilla de zona se mantiene
 * aunque no haya zona: con su recuadro gris y su punto avisa de que ahí no hay
 * dato, que es información.
 */

import { EnlaceOficina } from './EnlaceOficina'
import { ZonaBadge } from './ZonaBadge'

export function Ubicacion({
  zonaId,
  zonaNombre,
  colorIndice,
  oficinaId,
  oficinaNombre,
}: {
  zonaId?: string | null
  zonaNombre?: string | null
  colorIndice?: number
  oficinaId?: string | null
  oficinaNombre?: string | null
}) {
  return (
    <span className="flex min-w-0 flex-col items-start gap-1">
      <span className="block min-w-0 max-w-full">
        <EnlaceOficina id={oficinaId} nombre={oficinaNombre} zonaId={zonaId} colorIndice={colorIndice} />
      </span>
      <ZonaBadge id={zonaId} nombre={zonaNombre} colorIndice={colorIndice} />
    </span>
  )
}