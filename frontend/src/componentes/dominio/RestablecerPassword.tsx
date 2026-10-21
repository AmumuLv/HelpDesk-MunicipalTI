import { useState } from 'react'
import { api, erroresDeValidacion } from '../../api/cliente'
import { useAvisos } from '../../estado/Avisos'
import { Button } from '../base/Button'
import { CampoPassword } from '../base/CampoPassword'
import { Nota } from '../base/Estructura'
import { useSesion } from '../../estado/Sesion'
import { useNavigate } from 'react-router-dom'

export function RestablecerPassword({ usuarioId, nombre }: { usuarioId: string; nombre: string }) {
  const avisos = useAvisos()
  const sesion = useSesion()
  const navegar = useNavigate()
  const [password, setPassword] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exito, setExito] = useState(false)
  const valido = password.length >= 8 && password === confirmacion
  if (!sesion.esAdmin) return <Nota tono="info">El restablecimiento de contraseñas lo realiza el administrador.</Nota>

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (!valido || guardando) return
    setGuardando(true)
    setError(null)
    setExito(false)
    try {
      await api.crear(`/usuarios/${usuarioId}/restablecer-password`, { password })
      if (usuarioId === sesion.usuario?.id) { await sesion.salir(); navegar('/acceder', { replace: true }); return }
      setPassword('')
      setConfirmacion('')
      setExito(true)
      avisos.exito('Contraseña restablecida', `La nueva contraseña de ${nombre} ya está activa.`)
    } catch (fallo) {
      setError(erroresDeValidacion(fallo).password ?? (fallo instanceof Error ? fallo.message : 'No se pudo restablecer la contraseña.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar} autoComplete="off" className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">Define una contraseña nueva para {nombre}. Al guardar se cierran sus sesiones anteriores. Entrégasela antes de cerrar este formulario.</p>
      {error ? <Nota tono="peligro" titulo="No se pudo restablecer">{error}</Nota> : null}
      {exito ? <p role="status" className="text-sm font-medium">Contraseña actualizada. La persona puede iniciar sesión con la nueva clave.</p> : null}
      <CampoPassword etiqueta="Nueva contraseña" name="usuario-password-temporal" requerido minLength={8}
        value={password} disabled={guardando} onChange={(evento) => { setPassword(evento.target.value); setExito(false) }}
        ayuda="Mínimo 8 caracteres. Usa Mostrar contraseña para revisarla antes de guardar." />
      <CampoPassword etiqueta="Confirmar nueva contraseña" name="usuario-password-confirmacion" requerido minLength={8}
        value={confirmacion} disabled={guardando} onChange={(evento) => setConfirmacion(evento.target.value)}
        error={confirmacion && password !== confirmacion ? 'Las contraseñas no coinciden.' : undefined} />
      <Button type="submit" variante="primario" className="self-start" disabled={!valido} cargando={guardando}>Restablecer contraseña</Button>
    </form>
  )
}
