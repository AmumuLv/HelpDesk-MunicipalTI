import { useMiPerfil } from '../../api/hooks'
import { useFotoUsuario } from '../../api/fotos'
import { useSesion } from '../../estado/useSesion'
import { Avatar } from '../base/Estructura'

export function AvatarCuenta({ tamano = 'sm' }: { tamano?: 'sm' | 'md' | 'lg' }) {
  const sesion = useSesion()
  const perfil = useMiPerfil()
  const foto = useFotoUsuario(sesion.usuario?.id, perfil.data?.tiene_foto)
  return <Avatar nombre={sesion.usuario?.nombre} rol={sesion.rol} foto={foto} tamano={tamano} />
}
