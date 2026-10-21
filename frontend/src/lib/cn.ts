/**
 * Une clases de Tailwind sin dependencias externas.
 *
 * Tailwind reparte varias propiedades CSS bajo el mismo prefijo, de modo que
 * agrupar solo por el prefijo hace que una clase borre a otra que no compite con
 * ella. Hay dos Families distintas de fallo:
 *
 * 1. `text-2xl` (tamaño) y `text-foreground` (color) empiezan las dos por `text-`,
 *    así que el color se comía el tamaño y un indicador perdía su cifra grande.
 * 2. `flex` (display) y `flex-col` (dirección) empiezan las dos por `flex`, así que
 *    `flex` desaparecía y el contenedor dejaba de ser flex: el centrado, las
 *    columnas y el `text-center` se caían sin que se notara en el CSS.
 *
 * Aquí cada clase se reduce a la clave de la propiedad que realmente escribe.
 * Las raíces que solo tienen una propiedad (`p`, `gap`, `w`, `rounded`…) siguen
 * agrupándose por raíz, porque ahí sí compiten. Las raíces que reparten varias
 * tienen su tabla: lo que no aparece en ella se conserva siempre, porque no se
 * puede asegurar que dos clases desconocidas compitan entre sí.
 *
 * La variante se conserva en la clave porque `hover:bg-muted` y `bg-surface` son
 * reglas distintas y deben convivir.
 */

/**
 * Raíces que reparten más de una propiedad.
 *
 * `valores` dice a qué propiedad pertenece cada sufijo conocido.
 * `desconocido` es la propiedad de todo sufijo que no esté en la lista; si se
 * omite, un sufijo desconocido devuelve `null` y la clase se conserva siempre,
 * porque no se puede asegurar que dos clases desconocidas compitan.
 */
const POLIMORFICAS: Record<string, { desconocido?: string; valores: [string, string][] }> = {
  flex: {
    valores: [
      ['', 'display'],
      ['1', 'crecimiento'], ['auto', 'crecimiento'], ['none', 'crecimiento'], ['initial', 'crecimiento'],
      ['row', 'direccion'], ['row-reverse', 'direccion'], ['col', 'direccion'], ['col-reverse', 'direccion'],
      ['wrap', 'envoltura'], ['nowrap', 'envoltura'], ['wrap-reverse', 'envoltura'],
    ],
  },
  grid: {
    valores: [['', 'display'], ['cols', 'columnas'], ['rows', 'filas']],
  },
  text: {
    // `text-<lo que sea>` sigue siendo un color, así que dos colores compiten.
    desconocido: 'color',
    valores: [
      // Alineación: `text-center` no es ni un color ni un tamaño.
      ['center', 'alineacion'], ['left', 'alineacion'], ['right', 'alineacion'],
      ['justify', 'alineacion'], ['start', 'alineacion'], ['end', 'alineacion'],
      ['wrap', 'alineacion'], ['nowrap', 'alineacion'], ['balance', 'alineacion'], ['pretty', 'alineacion'],
      // Tamaño de fuente.
      ['2xs', 'tamano'], ['xs', 'tamano'], ['sm', 'tamano'], ['base', 'tamano'], ['lg', 'tamano'],
      ['xl', 'tamano'], ['2xl', 'tamano'], ['3xl', 'tamano'], ['4xl', 'tamano'], ['5xl', 'tamano'],
      ['6xl', 'tamano'], ['7xl', 'tamano'], ['8xl', 'tamano'], ['9xl', 'tamano'],
    ],
  },
  font: {
    desconocido: 'familia',
    valores: [
      ['', 'familia'],
      ['thin', 'grosor'], ['extralight', 'grosor'], ['light', 'grosor'], ['normal', 'grosor'],
      ['medium', 'grosor'], ['semibold', 'grosor'], ['bold', 'grosor'], ['extrabold', 'grosor'],
      ['black', 'grosor'],
    ],
  },
  place: {
    desconocido: 'ambos',
    valores: [['', 'ambos'], ['items', 'alineacion-items'], ['content', 'alineacion-content'], ['self', 'alineacion-self']],
  },
  align: {
    desconocido: 'ambos',
    valores: [['', 'ambos'], ['items', 'alineacion-items'], ['content', 'alineacion-content'], ['self', 'alineacion-self']],
  },
  justify: {
    // `justify-between`, `justify-center`… son todos `justify-content`.
    desconocido: 'alineacion-content',
    valores: [['items', 'alineacion-items'], ['self', 'alineacion-self']],
  },
  overflow: {
    desconocido: 'ambos',
    valores: [['', 'ambos'], ['x', 'eje-x'], ['y', 'eje-y']],
  },
  min: {
    desconocido: 'ambos',
    valores: [['', 'ambos'], ['w', 'ancho'], ['h', 'alto'], ['c', 'tamano']],
  },
  max: {
    desconocido: 'ambos',
    valores: [['', 'ambos'], ['w', 'ancho'], ['h', 'alto'], ['c', 'tamano']],
  },
  // Las transformaciones de Tailwind v4 viven en variables distintas, así que los
  // ejes NO compiten entre sí. Agruparlos hacía que `-translate-x-1/2` y
  // `-translate-y-1/2` se comieran: se quedaba solo el último y **todos** los
  // diálogos, que se centran con `top-1/2 left-1/2` más esas dos medias
  // traslaciones, se veían desplazados hacia la derecha.
  translate: {
    desconocido: 'desplazamiento',
    valores: [
      ['', 'desplazamiento'],
      ['x', 'eje-x'], ['y', 'eje-y'], ['z', 'eje-z'],
      ['full', 'eje-x'], ['none', 'transform'],
    ],
  },
  scale: {
    desconocido: 'escala',
    valores: [['', 'escala'], ['x', 'escala-x'], ['y', 'escala-y'], ['z', 'escala-z']],
  },
  skew: {
    desconocido: 'inclinacion',
    valores: [['', 'inclinacion'], ['x', 'inclinacion-x'], ['y', 'inclinacion-y']],
  },
  rotate: {
    desconocido: 'rotacion',
    valores: [['', 'rotacion'], ['none', 'rotacion']],
  },
  // `space-x-*` y `space-y-*` también son ejes distintos.
  space: {
    desconocido: 'espaciado',
    valores: [['', 'espaciado'], ['x', 'espaciado-x'], ['y', 'espaciado-y'], ['reverse', 'espaciado-inverso']],
  },
  // `inset-x`/`inset-y` son `inset-inline`/`inset-block`: propiedades distintas.
  inset: {
    desconocido: 'insets',
    valores: [
      ['', 'insets'],
      ['x', 'inset-inline'], ['y', 'inset-block'],
      ['inline', 'inset-inline'], ['block', 'inset-block'],
    ],
  },
}

const LADOS_BORDE = new Set(['t', 'r', 'b', 'l', 'x', 'y', 's', 'e'])

/**
 * `border` reparte grosor y color, y el orden de los segmentos lo decide:
 * `border`, `border-2` y `border-t-2` son grosor; `border-border`,
 * `border-red-500` y `border-t-red-500` son color.
 */
function propiedadDeBorde(resto: string): string {
  if (!resto) return 'border:grosor'
  const partes = resto.split('-')
  if (partes.length === 1 && (LADOS_BORDE.has(partes[0]) || /^\d+$/.test(partes[0]))) {
    return 'border:grosor'
  }
  if (partes.length === 2 && LADOS_BORDE.has(partes[0]) && /^\d+$/.test(partes[1])) {
    return 'border:grosor'
  }
  return 'border:color'
}

/**
 * La clave de una clase: qué propiedad CSS compite con ella.
 *
 * Para una raíz con una sola propiedad basta la raíz: `p-2` y `p-4` compiten.
 * Para una raíz polimórfica se consulta la tabla con el primer segmento del
 * sufijo, de modo que `text-primary-strong` cae en «color» y `grid-cols-2` en
 * «columnas».
 */
function propiedadDe(clase: string): string | null {
  // Un valor arbitrario lleva su corchete al final: se corta antes de buscar el
  // guion, porque `text-[15px]` es un tamaño aunque no esté en la tabla.
  const abre = clase.indexOf('[')
  if (abre !== -1) return `${clase.slice(0, abre)}:arbitrario`

  const guion = clase.indexOf('-')
  const raiz = guion === -1 ? clase : clase.slice(0, guion)
  const resto = guion === -1 ? '' : clase.slice(guion + 1)

  if (raiz === 'border') return propiedadDeBorde(resto)

  const tabla = POLIMORFICAS[raiz]
  if (!tabla) return raiz

  if (!resto) {
    const vacia = tabla.valores.find(([sufijo]) => sufijo === '')
    return vacia ? `${raiz}:${vacia[1]}` : null
  }

  const fila = tabla.valores.find(([sufijo]) => sufijo === resto.split('-')[0])
  if (fila) return `${raiz}:${fila[1]}`
  return tabla.desconocido ? `${raiz}:${tabla.desconocido}` : null
}

/** La clave completa: la variante, porque cada variante es una regla aparte. */
function claveDe(clase: string): string | null {
  const dosPuntos = clase.lastIndexOf(':')
  const variante = dosPuntos === -1 ? '' : clase.slice(0, dosPuntos + 1)
  let resto = dosPuntos === -1 ? clase : clase.slice(dosPuntos + 1)

  // El signo negativo también cambia la regla: `-mt-2` y `mt-2` no compiten.
  let signo = ''
  if (resto.startsWith('-')) {
    signo = 'negativo:'
    resto = resto.slice(1)
  }

  const propiedad = propiedadDe(resto)
  return propiedad === null ? null : `${variante}${signo}${propiedad}`
}

/**
 * Combina clases, resolviendo conflictos de Tailwind: la última gana.
 * `cn('p-2', 'p-4')` → `'p-4'`.
 *
 * `cn('flex flex-col')` conserva las dos, porque `display` y `flex-direction`
 * no son la misma propiedad; lo mismo con `cn('text-2xl', 'text-foreground')`.
 */
export function cn(...clases: (string | false | null | undefined)[]): string {
  const finales: string[] = []
  const grupos = new Map<string, string[]>()
  const sueltas: string[] = []

  for (const clase of clases) {
    if (!clase) continue
    for (const parte of clase.split(/\s+/).filter(Boolean)) {
      const clave = claveDe(parte)
      if (clave === null) {
        // Sin clave: no se puede decidir, así que la clase se queda tal cual.
        sueltas.push(parte)
        continue
      }
      const lista = grupos.get(clave) ?? []
      lista.push(parte)
      grupos.set(clave, lista)
    }
  }

  for (const lista of grupos.values()) finales.push(lista.at(-1)!)
  finales.push(...sueltas)

  return finales.filter(Boolean).join(' ')
}