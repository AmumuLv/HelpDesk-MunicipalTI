import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/cliente'
import { useAvisos } from '../../estado/useAvisos'
import { Button } from '../base/Button'
import { ConfirmDialog } from '../base/Sobreposiciones'
import { Nota } from '../base/Estructura'
import { EtiquetaEstadoActivo } from './EtiquetaActivo'

export function EstadoCuentaUsuario({ usuarioId, nombre, activo, propia }: {
  usuarioId: string; nombre: string; activo: boolean; propia: boolean
}) {
  const invalidar = useQueryClient()
  const avisos = useAvisos()
  const [confirmando, setConfirmando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cambiar = async () => {
    if (guardando || propia) return
    setGuardando(true)
    setError(null)
    try {
      await api.editar(`/usuarios/${usuarioId}`, { activo: !activo })
      await Promise.all([
        invalidar.invalidateQueries({ queryKey: ['usuario', usuarioId] }),
        invalidar.invalidateQueries({ queryKey: ['usuarios'] }),
        invalidar.invalidateQueries({ queryKey: ['equipo-ti'] }),
      ])
      setConfirmando(false)
      avisos.exito(activo ? 'Cuenta desactivada' : 'Cuenta reactivada')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo cambiar el estado.')
      setConfirmando(false)
    } finally {
      setGuardando(false)
    }
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="self-start"><EtiquetaEstadoActivo activo={activo} /></div>
      <p className="text-sm text-muted-foreground">{propia ? 'Esta es tu cuenta. Puedes editar tus datos; no puedes desactivarla desde aquí.' : 'Desactivar impide iniciar sesión y conserva los tickets, equipos e historial.'}</p>
      {error ? <Nota tono="peligro" titulo="No se pudo cambiar el estado">{error}</Nota> : null}
      {!propia ? <Button className="self-start" variante={activo ? 'destructivo' : 'exito'} onClick={() => setConfirmando(true)}>{activo ? 'Desactivar cuenta' : 'Reactivar cuenta'}</Button> : null}
      <ConfirmDialog abierto={confirmando} alCerrar={() => { if (!guardando) setConfirmando(false) }}
        alConfirmar={() => void cambiar()} titulo={activo ? 'Desactivar cuenta' : 'Reactivar cuenta'}
        mensaje={activo ? `${nombre} dejará de poder iniciar sesión. Sus tickets y equipos se conservan.` : `${nombre} volverá a poder iniciar sesión.`}
        textoConfirmar={activo ? 'Desactivar' : 'Reactivar'} peligro={activo} cargando={guardando} />
    </div>
  )
}
