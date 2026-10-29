/**
 * Genera los tipos de TypeScript de las RESPUESTAS de la API.
 *
 * Por qué desde la API viva y no desde el OpenAPI: el backend no declara
 * `response_model`, así que en el esquema todas las respuestas salen como `{}`
 * sin forma. La única fuente veraz es lo que el servidor responde de verdad,
 * que es lo que recoge `tools/formas_vivas.py` en `frontend/forma-api.json`.
 *
 * Para lo que sí está declarado (cuerpos de petición y parámetros de consulta)
 * se usa `src/api/esquema-api.ts`, generado con openapi-typescript.
 *
 *   python tools/formas_vivas.py              # refresca forma-api.json
 *   node tools/generar-tipos-respuesta.mjs    # regenera estos tipos
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = fileURLToPath(new URL('..', import.meta.url))
const FORMAS = join(RAIZ, 'forma-api.json')
const OPENAPI = join(RAIZ, 'openapi.json')
const SALIDA = join(RAIZ, 'src', 'api', 'respuestas-api.ts')

const formas = JSON.parse(readFileSync(FORMAS, 'utf8'))
const openapi = JSON.parse(readFileSync(OPENAPI, 'utf8'))

/** Identificador válido a partir de la ruta: /api/tickets/{id}/ia → TicketsIdIa. */
function nombreDe(ruta) {
  return ruta
    .split('?')[0]
    .replace(/^\/api\//, '')
    .split('/')
    .filter(Boolean)
    .map((parte) => {
      if (parte.startsWith('{')) return `Por${parte.replace(/[{}]/g, '')}`
      return parte
        .split(/[^a-zA-Z0-9]+/)
        .filter(Boolean)
        .map((p) => p[0].toUpperCase() + p.slice(1))
        .join('')
    })
    .join('')
}

/**
 * Pistas de tipo por nombre de campo, sacadas de los cuerpos de petición.
 *
 * Un campo que en toda la muestra sale nulo se quedaria como `unknown`, y eso
 * obliga a castear en cada pantalla. Los esquemas de peticion si declaran su
 * tipo, asi que si el nombre coincide se usa como pista.
 */
const pistas = new Map()
for (const esquema of Object.values(openapi.components?.schemas ?? {})) {
  for (const [nombre, definicion] of Object.entries(esquema?.properties ?? {})) {
    if (pistas.has(nombre)) continue
    // Pydantic declara los opcionales como anyOf [tipo, null]
    if (definicion.anyOf) {
      const sinNulo = definicion.anyOf.filter((p) => p.type && p.type !== 'null')
      if (sinNulo.length === 1) pistas.set(nombre, sinNulo[0].type)
      continue
    }
    const tipo = definicion.$ref?.split('/').pop() ?? definicion.type
    if (tipo) pistas.set(nombre, tipo)
  }
}
/**
 * Pistas escritas a mano para campos que la API devuelve siempre nulos en la
 * muestra, y que en los esquemas de peticion no aparecen con el mismo nombre
 * (por ejemplo `oficina_nombre` en el directorio de usuarios).
 *
 * Se declaran aqui y no en cada pantalla, para que el tipo seعرa el mismo en
 * todas partes. Si el backend cambia la forma, verificar_contratos lo avisa.
 */
const PISTAS_EXTRAS = {
  oficina_nombre: 'string',
  zona_nombre: 'string',
  zona_id: 'string',
  oficina_id: 'string',
  conjunto_nombre: 'string',
  conjunto_id: 'string',
  responsable_nombre: 'string',
  responsable_id: 'string',
  codigo_patrimonial: 'string',
  telefono: 'string',
  anexo: 'string',
  cargo: 'string',
  descripcion: 'string',
  notas: 'string',
  observaciones: 'string',
  motivo: 'string',
  error: 'string',
  cierra_en: 'string',
  cerrado_en: 'string',
  valoracion_promedio: 'number',
  relacionados: 'string',
  codigo: 'string',
  activo_codigo: 'string',
  problema: 'string',
  estado_texto: 'string',
}

const pistaDe = (nombre) => {
  const tipo = pistas.get(nombre)
  if (tipo === 'string' || tipo === 'integer' || tipo === 'number') return tipo === 'string' ? 'string' : 'number'
  if (tipo === 'boolean') return 'boolean'
  return PISTAS_EXTRAS[nombre] ?? null
}

/** Traduce la forma deduccionada por formas_vivas.py a TypeScript. */
function aTs(forma, sangria = '', nombreCampo = null) {
  const dentro = `${sangria}  `

  // Campo que nunca tuvo valor: se declara por la pista del esquema de peticion
  if (forma.tipo === 'nulo' && nombreCampo) {
    const pista = pistaDe(nombreCampo)
    return pista ? `${pista} | null` : 'unknown'
  }

  // Un objeto que en la muestra dio valores de tipos distintos y no se pudo
  // deducir: se declara como texto o null, nunca como unknown
  if (forma.tipo === 'desconocido' && nombreCampo) {
    const pista = pistaDe(nombreCampo)
    if (pista === 'string') return 'string'
    if (pista === 'number') return 'number'
    if (pista === 'boolean') return 'boolean'
  }

  if (forma.tipo === 'texto') return forma.nulo ? 'string | null' : 'string'
  if (forma.tipo === 'numero') return forma.nulo ? 'number | null' : 'number'
  if (forma.tipo === 'booleano') return forma.nulo ? 'boolean | null' : 'boolean'
  if (forma.tipo === 'nulo') return nombreCampo ? 'unknown' : 'null'
  if (forma.tipo === 'desconocido') return forma.nulo ? 'unknown | null' : 'unknown'

  if (forma.tipo === 'lista') {
    // Una lista vacía no dice nada del tipo de sus elementos: si el nombre del
    // campo tiene pista, se usa; si no, se declara unknown[]
    if (forma.elemento === undefined || forma.vacia) {
      const pista = nombreCampo ? pistaDe(nombreCampo) : null
      return pista === 'string' ? 'string[]' : pista === 'number' ? 'number[]' : 'unknown[]'
    }
    // El elemento ya viene como tipo (los objetos se declaran en línea, porque
    // no hay un nombre al que referenciarse); solo hay que añadir los corchetes.
    return `${aTs(forma.elemento, dentro)}[]`
  }

  if (forma.tipo === 'objeto') {
    const campos = forma.campos ?? {}
    const nombres = Object.keys(campos)
    if (nombres.length === 0) return 'Record<string, never>'
    const opcionales = forma.nulo ? ' | null' : ''
    const lineas = nombres.map((clave) => {
      const tipo = aTs(campos[clave], dentro, clave)
      return `${dentro}${JSON.stringify(clave)}: ${tipo},`
    })
    return `{\n${lineas.join('\n')}\n${sangria}}${opcionales}`
  }

  return 'unknown'
}

/** Respuestas */
const bloques = []
const usados = new Set()

for (const [ruta, forma] of Object.entries(formas).sort(([a], [b]) => a.localeCompare(b))) {
  // Los endpoints que devuelven archivo o error no son JSON: no hay tipo que hacer
  if (!forma || typeof forma !== 'object' || forma.tipo === undefined) continue
  let nombre = `Respuesta${nombreDe(ruta)}`
  // Si dos rutas colapsan al mismo nombre, se numeran
  let numero = 2
  while (usados.has(nombre)) nombre = `Respuesta${nombreDe(ruta)}${numero++}`
  usados.add(nombre)
  bloques.push(`/** Respuesta de \`GET ${ruta}\` */\nexport type ${nombre} = ${aTs(forma)}\n`)
}

/** Parámetros de consulta declarados por la API */
const consultables = []
for (const [ruta, operaciones] of Object.entries(openapi.paths)) {
  const consulta = (operaciones.get?.parameters ?? []).filter((p) => p.in === 'query')
  if (consulta.length === 0) continue
  const nombre = `Consulta${nombreDe(ruta)}`
  const campos = consulta.map((p) => {
    const tipo = ['integer', 'number'].includes(p.schema?.type)
      ? 'number'
      : p.schema?.type === 'boolean'
        ? 'boolean'
        : 'string'
    return `  ${JSON.stringify(p.name)}?: ${tipo}`
  })
  consultables.push(`/** Parámetros de \`GET ${ruta}\` */\nexport type ${nombre} = {\n${campos.join('\n')}\n}\n`)
}

const salida = `/**
 * Tipos de RESPUESTA de la API, generados desde las formas observadas.
 *
 * GENERADO AUTOMÁTICAMENTE con tools/generar-tipos-respuesta.mjs. No editar a mano.
 * Origen: frontend/forma-api.json, que recoge lo que el servidor responde de
 * verdad y que backend/app/scripts/verificar_contratos.py vuelve a comprobar.
 *
 * Estos tipos existen porque el backend no declara \`response_model\`: sin ellos,
 * la interfaz no podría leer un solo campo sin adivinar.
 */

/* ═══════════════════════ Respuestas ═══════════════════════ */

${bloques.join('\n')}
/* ═══════════ Parámetros de consulta declarados por la API ═══════════ */

${consultables.join('\n')}`

writeFileSync(SALIDA, salida, 'utf8')
console.log(`Tipos generados: ${bloques.length} respuestas y ${consultables.length} conjuntos de parámetros.`)
console.log(`Escrito en ${SALIDA}`)