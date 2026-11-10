import { useCallback, useEffect, useRef, useState } from 'react'

/** Sigue el texto que crece, sin desplazar la página ni arrastrar una lectura manual. */
export function useScrollChat() {
  const registro = useRef<HTMLDivElement>(null)
  const seguirFinal = useRef(true)
  const marco = useRef<number | null>(null)
  const ultimaPosicion = useRef<number | null>(null)
  const [lejosDelFinal, setLejosDelFinal] = useState(false)
  const cancelar = useCallback(() => {
    if (marco.current !== null) cancelAnimationFrame(marco.current)
    marco.current = null
  }, [])
  useEffect(() => cancelar, [cancelar])
  const distancia = useCallback(() => {
    const area = registro.current
    return area ? Math.max(0, area.scrollHeight - area.clientHeight - area.scrollTop) : 0
  }, [])
  const interrumpir = useCallback(() => {
    cancelar()
    seguirFinal.current = false
    setLejosDelFinal(distancia() > 80)
  }, [cancelar, distancia])
  const onScroll = useCallback(() => {
    // Los scroll emitidos por nuestra animación no son una decisión del lector.
    if (marco.current !== null) {
      const area = registro.current
      if (!area || ultimaPosicion.current === null || Math.abs(area.scrollTop - ultimaPosicion.current) < 3 || area.scrollHeight <= area.clientHeight + 3) return
      cancelar()
    }
    const lejos = distancia() > 80
    seguirFinal.current = !lejos
    setLejosDelFinal(lejos)
  }, [cancelar, distancia])
  const seguirEscritura = useCallback(() => {
    const area = registro.current
    if (!area) return
    if (!seguirFinal.current) { setLejosDelFinal(area.scrollHeight - area.clientHeight - area.scrollTop > 80); return }
    if (marco.current !== null) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      area.scrollTop = area.scrollHeight
      ultimaPosicion.current = area.scrollTop
      setLejosDelFinal(false)
      return
    }
    const avanzar = () => {
      const actual = registro.current
      if (!actual || !seguirFinal.current) { marco.current = null; return }
      const destino = Math.max(0, actual.scrollHeight - actual.clientHeight)
      const pendiente = destino - actual.scrollTop
      if (Math.abs(pendiente) < 1) {
        actual.scrollTop = destino
        ultimaPosicion.current = actual.scrollTop
        marco.current = null
        setLejosDelFinal(false)
        return
      }
      actual.scrollTop += Math.sign(pendiente) * Math.min(70, Math.max(.8, Math.abs(pendiente) * .2))
      ultimaPosicion.current = actual.scrollTop
      marco.current = requestAnimationFrame(avanzar)
    }
    marco.current = requestAnimationFrame(avanzar)
  }, [])
  const irAlFinal = useCallback(() => {
    seguirFinal.current = true
    setLejosDelFinal(false)
    seguirEscritura()
  }, [seguirEscritura])
  const restaurarFinal = useCallback((posicion?: number) => {
    cancelar()
    const area = registro.current
    if (!area) return
    area.scrollTop = posicion ?? area.scrollHeight
    ultimaPosicion.current = area.scrollTop
    const lejos = distancia() > 80
    seguirFinal.current = !lejos
    setLejosDelFinal(lejos)
  }, [cancelar, distancia])
  return { registro, seguirFinal, lejosDelFinal, onScroll, interrumpir, seguirEscritura, irAlFinal, restaurarFinal }
}
