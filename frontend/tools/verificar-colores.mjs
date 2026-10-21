/**
 * Verificación de colores literales.
 *
 * Falla si encuentra un hexadecimal, rgb(), hsl() o oklch() fuera del archivo de
 * tokens. Los componentes solo pueden usar nombres de token.
 *
 *   node frontend/tools/verificar-colores.mjs
 */

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(RAIZ, 'src')
const TOKENS = join(SRC, 'estilos', 'tokens.css')

const PATRONES = [
  { nombre: 'hexadecimal', regex: /#[0-9a-fA-F]{3,8}\b/ },
  { nombre: 'rgb()/rgba()', regex: /\brgba?\s*\(/ },
  { nombre: 'hsl()/hsla()', regex: /\bhsla?\s*\(/ },
  { nombre: 'oklch()/oklab()', regex: /\boklch\s*\(/ },
  { nombre: 'color()', regex: /\bcolor\s*\(\s*#/ },
]

// Palabras clave de color que un componente no debería escribir
const PALABRAS = [
  'text-white',
  'bg-white',
  'bg-black',
  'text-black',
  'text-red-',
  'bg-red-',
  'text-blue-',
  'bg-blue-',
  'text-green-',
  'bg-green-',
  'text-yellow-',
  'bg-yellow-',
  'text-gray-',
  'bg-gray-',
  'text-slate-',
  'bg-slate-',
  'text-zinc-',
  'bg-zinc-',
  'text-neutral-',
  'bg-neutral-',
  'text-orange-',
  'bg-orange-',
]

const extensiones = new Set(['.tsx', '.ts', '.css'])

function recorrer(directorio) {
  const encontrados = []
  for (const entrada of readdirSync(directorio)) {
    const completa = join(directorio, entrada)
    if (statSync(completa).isDirectory()) {
      encontrados.push(...recorrer(completa))
    } else if ([...extensiones].some((extension) => entrada.endsWith(extension))) {
      encontrados.push(completa)
    }
  }
  return encontrados
}

const problemas = []

for (const archivo of recorrer(SRC)) {
  // El archivo de tokens es el único lugar permitido
  if (archivo === TOKENS) continue

  const contenido = readFileSync(archivo, 'utf8')
  const lineas = contenido.split('\n')

  lineas.forEach((linea, indice) => {
    const limpio = linea.trim()
    // Las líneas de comentario pueden mencionar colores como documentación
    if (limpio.startsWith('*') || limpio.startsWith('//') || limpio.startsWith('/*')) return

    for (const { nombre, regex } of PATRONES) {
      if (regex.test(linea)) {
        problemas.push({
          archivo: relative(RAIZ, archivo),
          linea: indice + 1,
          tipo: nombre,
          texto: limpio.slice(0, 90),
        })
      }
    }

    for (const palabra of PALABRAS) {
      if (new RegExp(`(?<![\\w-])${palabra}`).test(linea)) {
        problemas.push({
          archivo: relative(RAIZ, archivo),
          linea: indice + 1,
          tipo: 'color de paleta de Tailwind',
          texto: limpio.slice(0, 90),
        })
      }
    }
  })
}

if (problemas.length > 0) {
  console.error(`\nSe encontraron ${problemas.length} colores literales fuera de los tokens:\n`)
  for (const problema of problemas) {
    console.error(`  ${problema.archivo}:${problema.linea}  [${problema.tipo}]`)
    console.error(`      ${problema.texto}`)
  }
  console.error('\nUsa un token semántico. Si falta, agrégalo a src/estilos/tokens.css.\n')
  process.exit(1)
}

console.log('OK: ningún color literal fuera de src/estilos/tokens.css')