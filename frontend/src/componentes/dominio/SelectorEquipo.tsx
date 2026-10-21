import { useId, useMemo, useState } from 'react'
import {
  BatteryCharging,
  Check,
  Cpu,
  HardDrive,
  Keyboard,
  Laptop,
  Monitor,
  Mouse,
  Printer,
  Router,
  Server,
  Smartphone,
  Speaker,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEquiposDe } from '../../api/hooks'
import { Select } from '../base/Campo'

type Equipo = {
  id: string
  nombre_equipo?: string | null
  tipo?: string | null
  zona_nombre?: string | null
  codigo_patrimonial?: string | null
}

type Grupo = { nombre: string; equipos: Equipo[] }

/**
 * Elegir el equipo de un ticket: **de una lista, nunca escribiendo un nombre.**
 *
 * La regla está aquí porque es la que evita un enlace falso. El alta manual tenía
 * un cuadro de texto libre que al guardar buscaba lo escrito en el inventario con
 * una coincidencia *sin ancar* —que el texto esté dentro del nombre— y se quedaba
 * con la primera. Medido en el inventario real:
 *
 * - «CPU» coincide con **6 equipos de 5 zonas**, y se quedaba con uno de PALACIO;
 * - «COMPUTADORA N°01 - TECLADO» aparece **52 veces** en cinco zonas.
 *
 * Escribir el nombre exacto tampoco dice cuál es: solo el código patrimonial
 * identifica un equipo, y 461 de 876 lo tienen. Así que aquí solo hay dos salidas:
 * un equipo de la lista de la persona, que sí es suyo, o ninguno con el tipo
 * anotado aparte, que es información verdadera.
 */
export function SelectorEquipo({
  usuarioId,
  equipoId,
  alCambiarEquipo,
  tipo,
  alCambiarTipo,
  tipos,
}: {
  /** Persona cuyos equipos se ofrecen. Sin `usuarioId`, no se ofrece lista. */
  usuarioId?: string | null
  equipoId: string | null
  alCambiarEquipo: (id: string | null) => void
  /** Tipo anotado cuando no hay equipo enlazado. */
  tipo: string
  alCambiarTipo: (tipo: string) => void
  tipos: string[]
  personaNombre?: string
}) {
  const equipos = useEquiposDe(usuarioId)
  const selectorId = useId()
  const [vista, setVista] = useState<{ persona?: string | null; oficina: boolean }>({ oficina: false })
  const verOficina = vista.persona === usuarioId && vista.oficina

  /*
   * Agrupado por conjunto, que es como están de verdad: una persona con una
   * computadora tiene un conjunto con varias piezas, y verlas en una lista plana
   * no dice cuáles forman parte de la misma máquina. El agrupado lo da la propia
   * API, así que aquí no hay que adivinar nada.
  */
  const grupos = useMemo<Grupo[]>(() => {
    if (!equipos.data) return []
    return equipos.data.por_conjunto.map((grupo) => ({
      nombre: grupo.conjunto ?? 'Equipos individuales',
      equipos: grupo.equipos as Equipo[],
    }))
  }, [equipos.data])

  const personales = grupos.reduce((total, grupo) => total + grupo.equipos.length, 0)
  const comunes = (equipos.data?.uso_comun_oficina ?? []) as Equipo[]
  const cargando = equipos.isLoading && Boolean(usuarioId)
  const cambiarVista = (oficina: boolean) => {
    setVista({ persona: usuarioId, oficina })
    alCambiarEquipo(null)
    alCambiarTipo('')
  }

  return (
    <div className="flex flex-col gap-3">
      {usuarioId ? <>
        <div role="radiogroup" aria-label="Origen del equipo" className="inline-flex self-start rounded-lg border border-border bg-surface-2 p-0.5 text-2xs font-semibold">
          {[{ oficina: false, texto: 'Sus equipos', cantidad: personales }, { oficina: true, texto: 'De la oficina', cantidad: comunes.length }].map(opcion => <label key={opcion.texto} className="cursor-pointer">
            <input type="radio" name={selectorId} className="peer sr-only" checked={verOficina === opcion.oficina} onChange={() => cambiarVista(opcion.oficina)} />
            <span className="block rounded-md px-2.5 py-1.5 text-muted-foreground peer-checked:bg-surface peer-checked:text-foreground peer-checked:shadow-sm peer-focus-visible:outline-2 peer-focus-visible:outline-ring">{opcion.texto} <span className="opacity-70">({opcion.cantidad})</span></span>
          </label>)}
        </div>
        {cargando ? <p role="status" className="text-sm text-muted-foreground">Cargando equipos…</p> : equipos.isError ? <p role="alert" className="text-sm text-destructive-strong">No pudimos cargar los equipos. <button type="button" className="font-semibold underline" onClick={() => void equipos.refetch()}>Reintentar</button></p> : verOficina ? (
          <div role="group" aria-label="Equipos de uso común">
            {comunes.length ? <ul className="flex flex-col gap-1.5">{comunes.map(equipo => <li key={equipo.id}><FilaEquipo equipo={equipo} elegido={equipoId === equipo.id} onElegir={() => alCambiarEquipo(equipoId === equipo.id ? null : equipo.id)} /></li>)}</ul> : <p className="text-sm text-muted-foreground">Sin equipos de uso común.</p>}
          </div>
        ) : (
          <div role="group" aria-label="Equipos a cargo de la persona" className="flex flex-col gap-2.5">
            {personales ? grupos.map(grupo => grupo.equipos.length ? <div key={grupo.nombre}>
              <p className="mb-1.5 truncate text-2xs font-medium text-muted-foreground" title={grupo.nombre}>{grupo.nombre}</p>
              <ul className="flex flex-col gap-1.5">{grupo.equipos.map(equipo => <li key={equipo.id}><FilaEquipo equipo={equipo} elegido={equipoId === equipo.id} onElegir={() => alCambiarEquipo(equipoId === equipo.id ? null : equipo.id)} /></li>)}</ul>
            </div> : null) : <p className="text-sm text-muted-foreground">Sin equipos a su cargo.</p>}
          </div>
        )}
      </> : null}

      {/* El tipo solo aparece sin equipo elegido: con equipo, el tipo sale de él. */}
      {!equipoId ? (
        <Select
          etiqueta="Tipo de equipo"
          value={tipo}
          onChange={(evento) => alCambiarTipo(evento.target.value)}
          opciones={[
            { valor: '', etiqueta: 'No aplica a un equipo concreto' },
            ...tipos.map((valor) => ({ valor, etiqueta: `Es un ${valor}` })),
          ]}
        />
      ) : null}
    </div>
  )
}

/**
 * El icono sale del tipo, no de una imagen fija.
 *
 * Se puso primero un icono de disco duro en todas las filas y quedaba tonto: al
 * lado de «Mause17 — Mouse» un disco duro afirma algo falso, que es el mismo
 * error que buscaba este componente pero en pequeño. El tipo decide.
 */
const ICONOS: Array<{ claves: string[]; icono: LucideIcon }> = [
  { claves: ['cpu', 'computadora', 'escritorio', 'pc'], icono: Cpu },
  { claves: ['laptop', 'notebook', 'portatil'], icono: Laptop },
  { claves: ['monitor', 'pantalla', 'televisor', 'tv'], icono: Monitor },
  { claves: ['impresora', 'multifuncion', 'escanner'], icono: Printer },
  { claves: ['mouse', 'raton'], icono: Mouse },
  { claves: ['teclado'], icono: Keyboard },
  { claves: ['router', 'switch', 'access point', 'punto de acceso', 'red'], icono: Router },
  { claves: ['celular', 'telefono', 'movil', 'tablet'], icono: Smartphone },
  { claves: ['servidor'], icono: Server },
  { claves: ['ups', 'nobreak', 'bateria', 'planta'], icono: BatteryCharging },
  { claves: ['disco duro', 'usb', 'memoria', 'almacenamiento'], icono: HardDrive },
  { claves: ['audio', 'parlante', 'microfono', 'mic'], icono: Speaker },
]

/** El tipo puede venir con acentos o mayúsculas: se comparan sin ellos. */
function iconoDe(tipo: string | null | undefined): LucideIcon {
  const limpio = (tipo ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
  return ICONOS.find((fila) => fila.claves.some((clave) => limpio.includes(clave)))?.icono ?? HardDrive
}

/**
 * Una fila de equipo elegible.
 *
 * Se lee como una fila, no como un botón suelto: el nombre manda, el tipo y la
 * zona apoyan. La marca de elegido va a la derecha para que la columna de texto
 * quede limpia y el ojo vaya al texto primero.
 */
function FilaEquipo({
  equipo,
  elegido,
  onElegir,
}: {
  equipo: Equipo
  elegido: boolean
  onElegir: () => void
}) {
  const nombre = equipo.nombre_equipo || equipo.tipo || 'Equipo sin nombre'
  const Icono = iconoDe(equipo.tipo)
  const detalle = [equipo.tipo, equipo.zona_nombre].filter(Boolean).join(' · ') || 'Sin zona'
  return (
    <button
      type="button"
      aria-pressed={elegido}
      onClick={onElegir}
      title={equipo.codigo_patrimonial ? `${nombre} · código ${equipo.codigo_patrimonial}` : nombre}
      className="group flex w-full items-center gap-2.5 rounded-[var(--radius-control)] border border-border bg-surface px-2.5 py-2 text-left transition-colors hover:border-primary/40 hover:bg-primary-soft/40 aria-pressed:border-primary aria-pressed:bg-primary-soft"
    >
      <Icono size={15} className="shrink-0 text-muted-foreground group-aria-pressed:text-primary-strong" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{nombre}</span>
        <span className="block truncate text-2xs text-muted-foreground">{detalle}</span>
      </span>
      {elegido ? (
        <Check size={15} className="shrink-0 text-primary-strong" aria-hidden="true" />
      ) : null}
    </button>
  )
}
