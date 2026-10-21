import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const archivo = path.join(raiz, 'frontend', 'src', 'dominio', 'textos-ia.ts')
const contenido = await readFile(archivo, 'utf8')
const bloque = contenido.match(/export const TEXTOS_IA\s*=\s*\{([\s\S]*?)\}\s*as const/)

if (!bloque) {
  console.error('No se encontró el catálogo TEXTOS_IA.')
  process.exitCode = 1
} else {
  const textos = [...bloque[1].matchAll(/^\s*(\w+):\s*'([^']*)',?\s*$/gm)]
  const largos = textos.filter(([, , texto]) => texto.length > 100)

  if (textos.length === 0) {
    console.error('El catálogo TEXTOS_IA no contiene textos verificables.')
    process.exitCode = 1
  } else if (largos.length > 0) {
    for (const [ , clave, texto] of largos) {
      console.error(`${clave}: ${texto.length} caracteres (máximo 100).`)
    }
    process.exitCode = 1
  } else {
    console.log(`OK: ${textos.length} textos de IA tienen como máximo 100 caracteres.`)
  }
}
