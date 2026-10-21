/**
 * Avisos emergentes: éxito, error e información.
 *
 * Un solo lugar donde se comunica el resultado de una acción. Los mensajes del
 * backend ya vienen escritos en lenguaje claro y se muestran tal cual: no se
 * reescriben en el cliente, porque ese texto ya está pensado para la persona.
 *
 * Implementado sobre Radix Toast para que el foco, el lector de pantalla y el
 * gesto de descartar funcionen sin reescribirlos.
 */

import * as Toast from '@radix-ui/react-toast'
import { AlertTriangle, CheckCircle2, CircleAlert, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'

import { ErrorPeticion } from '../api/cliente'

export type TipoAviso = 'exito' | 'error' | 'aviso' | 'info'

type Aviso = {
  id: number
  tipo: TipoAviso
  texto: string
  detalle?: string
}

type ValorContexto = {
  exito: (texto: string, detalle?: string) => void
  error: (texto: string, detalle?: string) => void
  aviso: (texto: string, detalle?: string) => void
  info: (texto: string, detalle?: string) => void
  /** Traduce el error de la API a un aviso legible, sin perder el detalle. */
  desdeError: (fallo: unknown, contexto?: string) => void
}

const Contexto = createContext<ValorContexto | null>(null)

const ESTILO: Record<TipoAviso, string> = {
  exito: 'border-success/40 bg-success-soft text-success-strong',
  error: 'border-destructive/40 bg-destructive-soft text-destructive-strong',
  aviso: 'border-warning/40 bg-warning-soft text-warning-strong',
  info: 'border-primary/30 bg-primary-soft text-primary-strong',
}

const ICONO: Record<TipoAviso, typeof Info> = {
  exito: CheckCircle2,
  error: CircleAlert,
  aviso: AlertTriangle,
  info: Info,
}

export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([])
  const contador = useRef(1)

  const quitar = useCallback((id: number) => {
    setAvisos((actuales) => actuales.filter((aviso) => aviso.id !== id))
  }, [])

  const agregar = useCallback(
    (tipo: TipoAviso, texto: string, detalle?: string) => {
      const id = contador.current++
      setAvisos((actuales) => {
        if (actuales.some((aviso) => aviso.tipo === tipo && aviso.texto === texto && aviso.detalle === detalle)) {
          return actuales
        }
        return [...actuales.slice(-3), { id, tipo, texto, detalle }]
      })
      // Los errores no desaparecen solos: nadie debe perder un aviso importante
      if (tipo !== 'error') window.setTimeout(() => quitar(id), 6000)
    },
    [quitar],
  )

  const valor = useMemo<ValorContexto>(
    () => ({
      exito: (texto, detalle) => agregar('exito', texto, detalle),
      error: (texto, detalle) => agregar('error', texto, detalle),
      aviso: (texto, detalle) => agregar('aviso', texto, detalle),
      info: (texto, detalle) => agregar('info', texto, detalle),
      desdeError: (fallo, contexto) => {
        const mensaje = fallo instanceof Error ? fallo.message : 'Ocurrió un error inesperado.'
        agregar('error', mensaje, [contexto, detallesLegibles(fallo)].filter(Boolean).join('. '))
      },
    }),
    [agregar],
  )

  return (
    <Contexto.Provider value={valor}>
      <Toast.Provider swipeDirection="right" duration={6000}>
        {children}
        {avisos.map((aviso) => {
          const Icono = ICONO[aviso.tipo]
          return (
            <Toast.Root
              key={aviso.id}
              onOpenChange={(estado) => !estado && quitar(aviso.id)}
              className={`pointer-events-auto flex items-start gap-2.5 rounded-[var(--radius-panel)] border p-3 shadow-popover ${ESTILO[aviso.tipo]}`}
            >
              <Icono size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <Toast.Title className="text-sm font-semibold">{aviso.texto}</Toast.Title>
                {aviso.detalle ? (
                  <Toast.Description className="mt-0.5 text-sm opacity-90">{aviso.detalle}</Toast.Description>
                ) : null}
              </div>
              <Toast.Close aria-label="Cerrar aviso" className="shrink-0 rounded p-1 hover:bg-foreground/10">
                <X size={14} aria-hidden="true" />
              </Toast.Close>
            </Toast.Root>
          )
        })}
        <Toast.Viewport className="no-imprimir pointer-events-none fixed right-0 bottom-0 z-50 flex w-[min(28rem,calc(100vw-1rem))] flex-col gap-2 p-4" />
      </Toast.Provider>
    </Contexto.Provider>
  )
}

export function useAvisos(): ValorContexto {
  const valor = useContext(Contexto)
  if (!valor) throw new Error('useAvisos debe usarse dentro de ProveedorAvisos')
  return valor
}

/** Los detalles de validación del backend, en una frase legible. */
function detallesLegibles(fallo: unknown): string | undefined {
  if (!(fallo instanceof ErrorPeticion) || !fallo.detalles) return undefined
  const detalles = fallo.detalles
  if (Array.isArray(detalles)) {
    const texto = detalles
      .map((item) => {
        const d = item as { campo?: string; mensaje?: string }
        return d.campo ? `${d.campo.replace(/_/g, ' ')}: ${d.mensaje}` : d.mensaje
      })
      .filter(Boolean)
      .join('. ')
    return texto || undefined
  }
  if (typeof detalles === 'object') {
    return (
      Object.entries(detalles as Record<string, unknown>)
        .map(([campo, valor]) => `${campo.replace(/_/g, ' ')}: ${String(valor)}`)
        .join('. ') || undefined
    )
  }
  return undefined
}