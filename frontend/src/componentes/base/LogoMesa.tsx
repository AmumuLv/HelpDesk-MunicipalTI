import { cn } from '../../lib/cn'

/** Identidad compartida: se conserva el escudo completo y su proporción. */
export function LogoMesa({ grande = false }: { grande?: boolean }) {
  return (
    <span className={cn('inline-flex shrink-0 items-center justify-center', grande ? 'size-20' : 'size-10')}>
      <img
        src="/identidad/escudo-casma.png"
        alt="Escudo de Casma · Mesa de Ayuda"
        title="Escudo de Casma · MiguelAngel2015 · CC BY-SA 4.0"
        width={1520}
        height={1182}
        className="h-full w-full object-contain"
        decoding="async"
      />
    </span>
  )
}
