/**
 * Foto de perfil: elegir un archivo, ver el resultado y quitarlo.
 *
 * No recorta ni reencoda en el navegador. Se sube tal cual y quien lo pone decide si
 * encaja. Lo que sí hace el control es lo que evita el susto:
 *
 * - **Dice el límite antes de subir**, no después del error.
 * - **Filtra el selector** por tipo, pero no confía en eso: el backend vuelve a mirar
 *   los bytes del archivo, porque el filtro del selector lo decide el navegador y se
 *   cambia en dos clics.
 * - **Avisa si el archivo pesa más de 2 MB** antes de gastarlo en subirlo.
 */

import { useRef, useState } from 'react'
import { Camera, Trash2, Upload } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { claves } from '../../api/consultas'

import { MAX_FOTO_MB, quitarFoto, subirFoto } from '../../api/fotos'
import { useAvisos } from '../../estado/Avisos'
import { Button } from '../base/Button'
import { Nota } from '../base/Estructura'

export function ControlFoto({
  usuarioId,
  nombre,
  alCambiar,
  puedeEditar,
  discreto = false,
}: {
  usuarioId: string
  nombre: string
  /** Avisa de si la foto cambió, para que quien la puso recargue su avatar. */
  alCambiar: (tieneFoto: boolean) => void
  puedeEditar: boolean
  discreto?: boolean
}) {
  const avisos = useAvisos()
  const consultas = useQueryClient()
  const archivoRef = useRef<HTMLInputElement>(null)
  const [subiendo, setSubiendo] = useState(false)
  const [fallo, setFallo] = useState<string | null>(null)

  if (!puedeEditar) return null

  const elegir = () => archivoRef.current?.click()

  const recibido = async (archivo: File) => {
    setFallo(null)
    if (archivo.size > MAX_FOTO_MB * 1024 * 1024) {
      setFallo(`«${archivo.name}» pesa ${(archivo.size / 1048576).toFixed(1)} MB y el límite son ${MAX_FOTO_MB} MB.`)
      return
    }
    setSubiendo(true)
    try {
      await subirFoto(usuarioId, archivo)
      await Promise.all([claves.miPerfil, ['usuario', usuarioId], ['usuarios'], ['oficina'], ['zona'], ['equipo-ti']].map(queryKey => consultas.invalidateQueries({ queryKey })))
      avisos.exito('Foto actualizada', `Se verá como la de ${nombre}.`)
      alCambiar(true)
    } catch (falloSubida) {
      setFallo(falloSubida instanceof Error ? falloSubida.message : 'No se pudo subir la foto.')
    } finally {
      setSubiendo(false)
      if (archivoRef.current) archivoRef.current.value = ''
    }
  }

  const quitar = async () => {
    setSubiendo(true)
    setFallo(null)
    try {
      await quitarFoto(usuarioId)
      await Promise.all([claves.miPerfil, ['usuario', usuarioId], ['usuarios'], ['oficina'], ['zona'], ['equipo-ti']].map(queryKey => consultas.invalidateQueries({ queryKey })))
      avisos.exito('Foto quitada', 'El avatar vuelve a las iniciales.')
      alCambiar(false)
    } catch (error) {
      setFallo(error instanceof Error ? error.message : 'No se pudo quitar la foto.')
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* El `<input>` se esconde y se abre desde el botón: un «Elegir archivo» nativo
          en medio del perfil rompe el aspecto sin ganar nada. */}
      <input
        aria-label={`Foto de ${nombre}`}
        ref={archivoRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="sr-only"
        onChange={(evento) => {
          const archivo = evento.target.files?.[0]
          if (archivo) void recibido(archivo)
        }}
      />
      <div className="flex flex-wrap gap-2">
        <Button variante={discreto ? 'fantasma' : 'secundario'} tamano="sm" icono={discreto ? <Camera size={14} aria-hidden /> : <Upload size={14} aria-hidden />} cargando={subiendo} onClick={elegir} title={`JPG, PNG, WEBP o GIF, hasta ${MAX_FOTO_MB} MB`}>
          Cambiar la foto
        </Button>
        <Button variante="fantasma" tamano="sm" icono={<Trash2 size={14} aria-hidden />} disabled={subiendo} onClick={() => void quitar()}>
          Quitar
        </Button>
      </div>
      {!discreto ? <p className="flex items-center gap-1.5 text-2xs text-muted-foreground">
        <Camera size={12} aria-hidden className="shrink-0" />
        {`JPG, PNG, WEBP o GIF, hasta ${MAX_FOTO_MB} MB. Se muestra solo a quien tiene cuenta.`}
      </p> : null}
      {fallo ? <Nota tono="peligro">{fallo}</Nota> : null}
    </div>
  )
}
