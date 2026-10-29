import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/cliente'
import { useAvisos } from '../../estado/useAvisos'
import { Button } from '../base/Button'
import { ConfirmDialog } from '../base/Sobreposiciones'

export function LimpiarRegistros({ ruta, titulo, descripcion, alLimpiar }: { ruta: string; titulo: string; descripcion: string; alLimpiar: () => unknown }) {
  const [abierto, setAbierto] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const avisos = useAvisos()
  const limpiar = async () => {
    if (ocupado) return
    setOcupado(true)
    try {
      const resultado = await api.borrar<{ eliminados: number }>(ruta)
      await alLimpiar()
      setAbierto(false)
      avisos.exito('Limpieza completada', `${resultado.eliminados} registros eliminados.`)
    } catch (error) { avisos.desdeError(error) }
    finally { setOcupado(false) }
  }
  return <><Button tamano="sm" variante="destructivo" icono={<Trash2 size={15} />} onClick={() => setAbierto(true)}>{titulo}</Button><ConfirmDialog abierto={abierto} alCerrar={() => { if (!ocupado) setAbierto(false) }} titulo={titulo} mensaje={descripcion} peligro textoConfirmar="Eliminar definitivamente" alConfirmar={() => void limpiar()} cargando={ocupado} /></>
}
