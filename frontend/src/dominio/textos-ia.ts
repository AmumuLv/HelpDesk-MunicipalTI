export const TEXTOS_IA = {
  pocosCasos: 'Pocos casos parecidos: sugerencia aproximada.',
  basica: 'IA básica: usa reglas y tu historial.',
  desactivada: 'La IA está desactivada. Puedes reportar igual.',
  disponible: 'La ayuda automática está disponible.',
} as const

export function limitarTextoIA(texto: string, limite = 90): string {
  if (texto.length <= limite) return texto
  const corte = Math.max(0, limite - 3)
  return `${texto.slice(0, corte).trimEnd()}...`
}
