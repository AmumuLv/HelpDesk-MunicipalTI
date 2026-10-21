import { useSugerenciasCampo } from '../../api/hooks'
import { Combobox } from '../base/Combobox'

export function CampoTecnicoSugerido({ campo, etiqueta, valor, alCambiar }: { campo: string; etiqueta: string; valor: string; alCambiar: (valor: string) => void }) {
  const datos = useSugerenciasCampo(campo, null, true)
  return <Combobox etiqueta={etiqueta} valor={valor || null} alCambiar={v => alCambiar(v || '')} sugerencias={(datos.data?.valores ?? []).map(s => ({ valor: s.valor, frecuencia: s.frecuencia }))} ayuda={datos.isError ? 'No pudimos cargar las sugerencias. Puedes escribir un valor nuevo.' : 'Valores existentes en el inventario; también puedes escribir otro.'} />
}
