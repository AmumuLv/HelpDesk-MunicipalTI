/** Conserva la identidad de un envío al reintentar el mismo formulario. */
export function claveSolicitud(estado: { firma: string; clave: string }, cuerpo: unknown): string {
  const firma = JSON.stringify(cuerpo)
  if (estado.firma !== firma) {
    estado.firma = firma
    const bytes = crypto.getRandomValues(new Uint8Array(16))
    bytes[6] = (bytes[6] & 15) | 64
    bytes[8] = (bytes[8] & 63) | 128
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
    estado.clave = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }
  return estado.clave
}
