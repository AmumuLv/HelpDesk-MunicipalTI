/**
 * Comprobación de `cn()`: pruebas de la función y revisión de sus llamadas.
 *
 * `cn()` decide qué clases se conservan, así que un error suyo no da error de
 * compilación: desaparece una clase del CSS y algo se ve descentrado, sin marco
 * o sin color. Pasó con las ventanas emergentes, que se centran con `top-1/2
 * left-1/2` más `-translate-x-1/2 -translate-y-1/2`: las dos clases caían en la
 * misma clave y solo se quedaba la última.
 *
 * El módulo se carga de verdad (se compila con esbuild y se importa desde un
 * `data:` URL), no hay copia de la lógica aquí: si el archivo real cambia, esta
 * comprobación cambia con él.
 *
 *   node tools/verificar-clases.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const CN = join(RAIZ, 'frontend', 'src', 'lib', 'cn.ts')

// esbuild es dependencia de vite, así que vive en frontend/node_modules
const { transformSync } = createRequire(join(RAIZ, 'frontend', 'package.json'))('esbuild')

/* ── Cargar la función real ───────────────────────────────────── */

const fuente = readFileSync(CN, 'utf8')
const compilado = transformSync(fuente, { loader: 'ts', format: 'esm' }).code
const modulo = await import(`data:text/javascript;base64,${Buffer.from(compilado).toString('base64')}`)
const { cn } = modulo

/* ── Pruebas ──────────────────────────────────────────────────── */

const casos = [
  // Lo que sí compite: la última gana.
  ['p-2 p-4', 'p-4'],
  ['bg-surface bg-muted', 'bg-muted'],
  ['rounded-none rounded-full', 'rounded-full'],
  ['w-4 w-8', 'w-8'],
  ['z-10 z-20', 'z-20'],

  // El signo negativo es parte de la clave: `-mt-2` y `mt-2` no se pisan.
  ['-mt-2 mt-2', '-mt-2 mt-2'],

  // Propiedades distintas con la misma raíz: tienen que convivir.
  ['text-2xl text-foreground', 'text-2xl text-foreground'],
  ['flex flex-col', 'flex flex-col'],
  ['grid grid-cols-2', 'grid grid-cols-2'],
  ['overflow-hidden overflow-y-auto', 'overflow-hidden overflow-y-auto'],
  ['min-h-0 min-w-0', 'min-h-0 min-w-0'],
  ['max-h-96 max-w-md', 'max-h-96 max-w-md'],
  ['justify-center justify-items-start', 'justify-center justify-items-start'],
  ['focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background', 'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background'],
  ['ring-1 ring-2 ring-red-500 ring-blue-500', 'ring-2 ring-blue-500'],
  ['ring-offset-1 ring-offset-2 ring-offset-white ring-offset-background', 'ring-offset-2 ring-offset-background'],
  ['focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring', 'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring'],
  ['place-items-center place-content-between', 'place-items-center place-content-between'],
  ['items-center self-start', 'items-center self-start'],
  ['font-bold font-mono', 'font-bold font-mono'],
  ['text-center text-white', 'text-center text-white'],

  // Ejes de transformación: el caso que descentraba las ventanas emergentes.
  ['-translate-x-1/2 -translate-y-1/2', '-translate-x-1/2 -translate-y-1/2'],
  ['top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2', 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'],
  ['translate-x-5 translate-x-0', 'translate-x-0'],
  ['scale-x-95 scale-y-95', 'scale-x-95 scale-y-95'],
  ['skew-x-3 skew-y-3', 'skew-x-3 skew-y-3'],
  ['space-x-2 space-y-3', 'space-x-2 space-y-3'],
  ['inset-x-0 inset-y-0', 'inset-x-0 inset-y-0'],
  ['-translate-x-full lg:translate-x-0', '-translate-x-full lg:translate-x-0'],

  // Bordes: grosor y color no se comen entre sí.
  ['border border-border', 'border border-border'],
  ['border-2 border-t-2', 'border-t-2'],
  ['border-t-2 border-red-500', 'border-t-2 border-red-500'],
  ['border-border border-border-t-2', 'border-border-t-2'],

  // Variantes distintas: cada una es su propia regla.
  ['hover:bg-muted bg-surface', 'hover:bg-muted bg-surface'],
  ['bg-surface hover:bg-muted', 'bg-surface hover:bg-muted'],

  // Valores arbitrarios: se conservan siempre, no se pueden comparar.
  ['p-[15px] p-4', 'p-[15px] p-4'],
  ['text-[15px] text-2xl', 'text-[15px] text-2xl'],
  ['grid-cols-[repeat(2,minmax(0,1fr))]', 'grid-cols-[repeat(2,minmax(0,1fr))]'],

  // Ruido tolerado.
  ['  p-2   p-4  ', 'p-4'],
  ['', ''],
  [null, ''],
]

let fallos = 0
for (const [entrada, esperado] of casos) {
  const obtenido = cn(entrada)
  if (obtenido !== esperado) {
    console.error(`  ✗ cn('${entrada}')`)
    console.error(`      esperado: '${esperado}'`)
    console.error(`      obtenido: '${obtenido}'`)
    fallos += 1
  }
}
console.log(`  ${casos.length - fallos}/${casos.length} pruebas de cn()`)

/* ── Revisar las llamadas del proyecto ────────────────────────── */

/**
 * Raíces que en Tailwind v4 reparten el valor en varios ejes y NO compiten
 * entre sí. Si dos clases de una misma llamada caen en la misma clave y son de
 *_axes distintos_, `cn()` está borrando una.
 */
const EJES = {
  translate: ['x', 'y', 'z', ''],
  scale: ['x', 'y', 'z', ''],
  skew: ['x', 'y', ''],
  space: ['x', 'y', ''],
  inset: ['x', 'y', 'inline', 'block', ''],
  overflow: ['x', 'y', ''],
  place: ['items', 'content', 'self', ''],
  align: ['items', 'content', 'self', ''],
}

function ejeDe(clase) {
  const limpio = clase.startsWith('-') ? clase.slice(1) : clase
  const guion = limpio.indexOf('-')
  const raiz = guion === -1 ? limpio : limpio.slice(0, guion)
  const ejes = EJES[raiz]
  if (!ejes) return null
  if (guion === -1) return `${raiz}:`
  return `${raiz}:${limpio.slice(guion + 1).split('-')[0]}`
}

/** Clases literales de una llamada `cn(...)`, sin variantes ni condicionales. */
function literalesDe(archivo) {
  const texto = readFileSync(archivo, 'utf8')
  const encontradas = []
  let desde = 0
  for (;;) {
    const inicio = texto.indexOf('cn(', desde)
    if (inicio === -1) break
    // Que sea una llamada y no parte de un identificador más largo
    const antes = inicio === 0 ? '' : texto[inicio - 1]
    if (/[\w$.]/.test(antes)) {
      desde = inicio + 3
      continue
    }
    let nivel = 0
    let fin = inicio + 2
    for (let i = inicio + 2; i < texto.length; i += 1) {
      if (texto[i] === '(') nivel += 1
      else if (texto[i] === ')') {
        nivel -= 1
        if (nivel === 0) {
          fin = i
          break
        }
      }
    }
    const cuerpo = texto.slice(inicio + 3, fin)
    desde = fin + 1
    // Solo interesan las llamadas escritas con cadenas planas
    const clases = cuerpo
      .split(',')
      .map((parte) => parte.trim().replace(/^['"`]|['"`]$/g, ''))
      .filter((parte) => /^[a-z0-9:\[\]\/.\-_%]+$/i.test(parte) && !parte.includes('=>') && !parte.includes(' '))
    if (clases.length > 1) {
      const linea = texto.slice(0, inicio).split('\n').length
      encontradas.push({ linea, clases })
    }
  }
  return encontradas
}

function recorrer(directorio) {
  const salida = []
  for (const nombre of readdirSync(directorio)) {
    const ruta = join(directorio, nombre)
    if (statSync(ruta).isDirectory()) salida.push(...recorrer(ruta))
    else if (/\.tsx?$/.test(nombre)) salida.push(ruta)
  }
  return salida
}

const archivos = recorrer(join(RAIZ, 'frontend', 'src'))
let sospechosas = 0
for (const archivo of archivos) {
  for (const { linea, clases } of literalesDe(archivo)) {
    // Se prueban también las variantes: `hover:` cambia la regla, no el eje.
    const porEje = new Map()
    for (const clase of clases) {
      const i = clase.lastIndexOf(':')
      const variante = i === -1 ? '' : clase.slice(0, i + 1)
      const eje = ejeDe(i === -1 ? clase : clase.slice(i + 1))
      if (!eje) continue
      const clave = variante + eje
      const anterior = porEje.get(clave)
      if (anterior) {
        console.error(`  ✗ ${relative(RAIZ, archivo)}:${linea}  '${anterior}' y '${clase}' son el mismo eje`)
        sospechosas += 1
      } else {
        porEje.set(clave, clase)
      }
    }
  }
}
console.log(`  ${archivos.length} archivos revisados, ${sospechosas} pares de ejes que se pisan`)

if (fallos || sospechosas) {
  console.error('\nRevisar cn(): hay clases que se pierden.')
  process.exit(1)
}
console.log('\nTodo en orden.')
