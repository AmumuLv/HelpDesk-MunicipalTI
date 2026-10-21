import { useFotoUsuario } from '../../api/fotos'
import { Avatar } from '../base/Estructura'

export function AvatarTecnico({ id, nombre, tieneFoto, tamano = 'md' }: {
  id: string; nombre: string; tieneFoto?: boolean; tamano?: 'sm' | 'md' | 'lg'
}) {
  const foto = useFotoUsuario(id, tieneFoto)
  return <Avatar nombre={nombre} foto={foto} tamano={tamano} />
}
