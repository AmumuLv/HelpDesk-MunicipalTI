import { Children, useLayoutEffect, useRef, type ReactNode } from 'react'

/** Cada tarjeta ocupa su altura real, también al desplegar sus datos. */
export function MosaicoGraficos({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const contenedor = ref.current
    if (!contenedor) return
    const medir = () => {
      for (const tarjeta of contenedor.children) {
        const elemento = tarjeta as HTMLElement
        const contenido = elemento.firstElementChild as HTMLElement | null
        if (contenido) elemento.style.gridRowEnd = `span ${Math.ceil((contenido.getBoundingClientRect().height + 24) / 32)}`
      }
    }
    const observador = new ResizeObserver(medir)
    for (const tarjeta of contenedor.children) {
      if (tarjeta.firstElementChild) observador.observe(tarjeta.firstElementChild)
    }
    medir()
    return () => observador.disconnect()
  }, [children])
  return <div ref={ref} data-testid="mosaico-graficos" className="grid auto-rows-[8px] grid-flow-row-dense grid-cols-1 items-start gap-6 xl:grid-cols-2">
    {Children.map(children, (tarjeta) => tarjeta ? <div className="min-w-0"><div className="flow-root">{tarjeta}</div></div> : null)}
  </div>
}
