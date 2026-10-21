/** Etiqueta pública; conserva los valores históricos enviados a la API. */
export function etiquetaPropiedad(valor: string): string {
  return /^(institucional|propiedad de la municipalidad)$/i.test(valor.trim()) ? 'MUNICIPALIDAD' : valor
}
