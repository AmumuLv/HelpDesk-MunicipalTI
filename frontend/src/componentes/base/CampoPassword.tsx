import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { Input, type PropsEntrada } from './Campo'
import { Button } from './Button'

/** La visibilidad solo afecta a la contraseña nueva que escribe el operador. */
export function CampoPassword(props: Omit<PropsEntrada, 'type'>) {
  const [visible, setVisible] = useState(false)
  return (
    <Input
      {...props}
      type={visible ? 'text' : 'password'}
      autoComplete="new-password"
      acciones={
        <Button tamano="sm" variante="fantasma" aria-pressed={visible}
          icono={visible ? <EyeOff size={16} /> : <Eye size={16} />}
          onClick={() => setVisible(!visible)}>
          {visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        </Button>
      }
    />
  )
}
