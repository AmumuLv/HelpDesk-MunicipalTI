import { Fragment, useState, type ReactNode } from 'react'
import { Check, Copy } from 'lucide-react'
import './TextoChat.css'

/** Markdown acotado: se crean elementos React, nunca se interpreta HTML. */
function destinoSeguro(destino: string): string | null {
  const limpio = destino.trim()
  if (!limpio || Array.from(limpio).some(caracter => caracter.charCodeAt(0) <= 32 || caracter === '\\')) return null
  if (/^\/panel(?:\/|$|[?#])/.test(limpio)) return limpio
  try {
    const url = new URL(limpio)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null
  } catch { return null }
}

function enLinea(texto: string, profundidad = 0): ReactNode[] {
  if (profundidad > 3) return [texto]
  const patron = /(`[^`\n]+`|\*\*[^\n]+?\*\*|__[^\n]+?__|\*[^*\n]+\*|_[^_\n]+_|\[[^\]\n]+\]\([^\s)]*\))/g
  const partes: ReactNode[] = []
  let desde = 0
  for (const coincidencia of texto.matchAll(patron)) {
    const indice = coincidencia.index ?? 0
    if (indice > desde) partes.push(texto.slice(desde, indice))
    const token = coincidencia[0]
    let contenido: ReactNode = token
    if (token.startsWith('`')) contenido = <code>{token.slice(1, -1)}</code>
    else if (token.startsWith('**') || token.startsWith('__')) contenido = <strong>{enLinea(token.slice(2, -2), profundidad + 1)}</strong>
    else if (token.startsWith('*') || token.startsWith('_')) contenido = <em>{enLinea(token.slice(1, -1), profundidad + 1)}</em>
    else {
      const enlace = /^\[([^\]]+)\]\((.*)\)$/.exec(token)
      if (enlace) {
        const destino = destinoSeguro(enlace[2])
        contenido = destino ? <a href={destino} target={destino.startsWith('/') ? undefined : '_blank'} rel={destino.startsWith('/') ? undefined : 'noopener noreferrer'}>{enLinea(enlace[1], profundidad + 1)}</a> : enlace[1]
      }
    }
    partes.push(<Fragment key={indice}>{contenido}</Fragment>)
    desde = indice + token.length
  }
  if (desde < texto.length) partes.push(texto.slice(desde))
  return partes
}

function celdas(linea: string): string[] {
  const texto = linea.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '')
  const resultado: string[] = []
  let celda = ''
  let codigo = false
  for (let i = 0; i < texto.length; i++) {
    const caracter = texto[i]
    if (caracter === '\\' && texto[i + 1] === '|') { celda += '|'; i++; continue }
    if (caracter === '`') codigo = !codigo
    if (caracter === '|' && !codigo) { resultado.push(celda.trim()); celda = '' }
    else celda += caracter
  }
  resultado.push(celda.trim())
  return resultado
}

function esTabla(lineas: string[], indice: number): boolean {
  if (!lineas[indice]?.includes('|') || !lineas[indice + 1]) return false
  const cabecera = celdas(lineas[indice])
  const separadores = celdas(lineas[indice + 1])
  return cabecera.length > 1 && cabecera.length === separadores.length && separadores.every(celda => /^:?-{3,}:?$/.test(celda))
}

function BloqueCodigo({ codigo, lenguaje }: { codigo: string; lenguaje: string }) {
  const [estado, setEstado] = useState<'inicial' | 'copiado' | 'error'>('inicial')
  const copiar = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Portapapeles no disponible')
      await navigator.clipboard.writeText(codigo)
      setEstado('copiado')
    } catch { setEstado('error') }
  }
  return <div className="texto-chat-codigo"><div className="texto-chat-codigo-barra"><span>{lenguaje || 'Código'}</span><button type="button" onClick={() => void copiar()} aria-label="Copiar código">{estado === 'copiado' ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}{estado === 'copiado' ? 'Copiado' : 'Copiar código'}</button></div><pre><code>{codigo}</code></pre><span role="status" className={estado === 'error' ? 'texto-chat-copia-error' : 'sr-only'}>{estado === 'copiado' ? 'Código copiado al portapapeles.' : estado === 'error' ? 'No se pudo copiar. Selecciona el código y cópialo manualmente.' : ''}</span></div>
}

function esInicioBloque(lineas: string[], indice: number) {
  return /^(?:\s{0,3}(?:`{3,}|~{3,})|#{1,6}\s|\s*(?:[-+*]|\d+[.)])\s|>\s?)/.test(lineas[indice]) || esTabla(lineas, indice) || /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(lineas[indice])
}

export function TextoChat({ texto }: { texto: string }) {
  const lineas = texto.replace(/\r\n?/g, '\n').split('\n')
  const bloques: ReactNode[] = []
  let indice = 0
  while (indice < lineas.length) {
    const linea = lineas[indice]
    const clave = indice
    if (!linea.trim()) { indice++; continue }
    const cerca = /^\s{0,3}(`{3,}|~{3,})(.*)$/.exec(linea)
    if (cerca) {
      const contenido: string[] = []
      const cierre = new RegExp(`^\\s{0,3}${cerca[1][0]}{${cerca[1].length},}\\s*$`)
      indice++
      while (indice < lineas.length && !cierre.test(lineas[indice])) contenido.push(lineas[indice++])
      if (indice < lineas.length) indice++
      const lenguaje = /^[\w+#.-]{1,40}$/.test(cerca[2].trim()) ? cerca[2].trim() : ''
      bloques.push(<BloqueCodigo key={clave} codigo={contenido.join('\n')} lenguaje={lenguaje} />)
      continue
    }
    const titulo = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(linea)
    if (titulo) {
      bloques.push(titulo[1].length <= 3 ? <h3 key={clave}>{enLinea(titulo[2])}</h3> : <h4 key={clave}>{enLinea(titulo[2])}</h4>)
      indice++; continue
    }
    if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(linea)) { bloques.push(<hr key={clave} />); indice++; continue }
    if (esTabla(lineas, indice)) {
      const cabeceras = celdas(linea)
      const alineaciones = celdas(lineas[indice + 1]).map(celda => celda.startsWith(':') && celda.endsWith(':') ? 'center' : celda.endsWith(':') ? 'right' : 'left') as ('center' | 'right' | 'left')[]
      const filas: string[][] = []
      indice += 2
      while (indice < lineas.length && lineas[indice].trim() && lineas[indice].includes('|')) filas.push(celdas(lineas[indice++]))
      bloques.push(<div className="texto-chat-tabla" key={clave} tabIndex={0} role="region" aria-label="Tabla de la respuesta"><table><thead><tr>{cabeceras.map((celda, i) => <th key={i} scope="col" style={{ textAlign: alineaciones[i] }}>{enLinea(celda)}</th>)}</tr></thead><tbody>{filas.map((fila, n) => <tr key={n}>{cabeceras.map((_, i) => <td key={i} style={{ textAlign: alineaciones[i] }}>{enLinea(fila[i] || '')}</td>)}</tr>)}</tbody></table></div>)
      continue
    }
    const lista = /^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$/.exec(linea)
    if (lista) {
      const ordenada = Boolean(lista[2])
      const items: ReactNode[] = []
      while (indice < lineas.length) {
        const item = /^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$/.exec(lineas[indice])
        if (!item || Boolean(item[2]) !== ordenada) break
        items.push(<li key={indice}>{enLinea(item[3])}</li>)
        indice++
      }
      bloques.push(ordenada ? <ol key={clave} start={Number(lista[2]) || 1}>{items}</ol> : <ul key={clave}>{items}</ul>)
      continue
    }
    if (/^>\s?/.test(linea)) {
      const citas: string[] = []
      while (indice < lineas.length && /^>\s?/.test(lineas[indice])) citas.push(lineas[indice++].replace(/^>\s?/, ''))
      bloques.push(<blockquote key={clave}>{enLinea(citas.join('\n'))}</blockquote>)
      continue
    }
    const parrafo = [linea]
    indice++
    while (indice < lineas.length && lineas[indice].trim() && !esInicioBloque(lineas, indice)) parrafo.push(lineas[indice++])
    bloques.push(<p key={clave}>{enLinea(parrafo.join('\n'))}</p>)
  }
  return <div className="texto-chat">{bloques}</div>
}
