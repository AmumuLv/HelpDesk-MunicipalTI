/**
 * Icono del tipo de equipo.
 *
 * El mapa cubre **los catorce tipos del catálogo** (`/equipos/catalogos`), no unos
 * cuantos. Antes solo reconocía laptop, monitor, impresora, red, teclado, mouse y
 * CPU: los otros seis —Tablet, Celular, Servidor, UPS, Disco duro externo y Sistema
 * de audio— caían todos en el mismo icono genérico, así que seis equipos distintos
 * se veían iguales.
 *
 * Además reconoce lo que llega escrito de otra manera, porque el tipo viene del
 * Excel y de lo que escribió la gente: «portátil», «ratón», «multifuncional»,
 * «no-break», «parlante»… Y **«LAPTO»**, que antes caía en el genérico porque
 * `/laptop/` no encuentra «lapto».
 *
 * Cuando no se reconoce ninguno, el icono es una caja neutra y el texto del tipo
 * sigue siendo el que escribió quien lo registró: aquí no se inventa nada.
 */

import { Box, Cpu, HardDrive, Keyboard, Laptop, Monitor, Mouse, Network, Printer, Router, Server, Smartphone, Speaker, Tablet, BatteryCharging } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { colorTipoEquipo } from '../../dominio/color-equipo'

/**
 * Se prueban en orden y gana el primero que encuentra su palabra, así que lo más
 * específico va antes que lo más genérico: «sistema de audio» antes que «sistema»,
 * «disco duro externo» antes que «disco».
 */
export function IconoTipoEquipo({ tipo, tamano = 26, conFondo = false }: { tipo?: string | null; tamano?: number; conFondo?: boolean }) {
  /* El icono sale **siempre** del mapa, incluido el del tipo sin reconocer. Antes la
     rama de «no reconocido» traía su propio `HardDrive` escrito a mano, así que el
     mapa decía una cosa y el dibujo otra: cambiar el icono genérico en el mapa no
     cambiaba nada y «Otro» seguía viéndose igual que «Disco duro externo». */
  const token = colorTipoEquipo(tipo)
  const Icono = ICONOS[token] ?? ICONOS['--icono-default']

  const dibujo = <Icono size={tamano} aria-hidden="true" className="shrink-0" style={{ color: `var(${token})` }} />
  return conFondo ? <span aria-hidden="true" className="flex size-12 shrink-0 items-center justify-center rounded-xl border"
    style={{ backgroundColor: `color-mix(in srgb, var(${token}) 12%, transparent)`, borderColor: `color-mix(in srgb, var(${token}) 25%, transparent)` }}>{dibujo}</span> : dibujo
}

/**
 * El dibujo de cada token.
 *
 * Vive aparte de las reglas para que se lea largo, pero **no** para evitar que se
 * desincronicen: separar los dos fue justo lo que pasó —la regla y el mapa decían
 * una cosa y la rama del tipo desconocido, escrita aparte, hacía otra—. Un solo
 * sitio donde se decide el icono.
 */
const ICONOS: Record<string, LucideIcon> = {
  '--icono-cpu': Cpu,
  '--icono-laptop': Laptop,
  '--icono-monitor': Monitor,
  '--icono-teclado': Keyboard,
  '--icono-mouse': Mouse,
  '--icono-impresora': Printer,
  '--icono-router': Router,
  '--icono-switch': Network,
  '--icono-tablet': Tablet,
  '--icono-celular': Smartphone,
  '--icono-servidor': Server,
  '--icono-ups': BatteryCharging,
  '--icono-disco': HardDrive,
  '--icono-audio': Speaker,
  /* Una caja, no un disco: con `HardDrive` el tipo genérico era indistinguible del
     «Disco duro externo» del catálogo, que sí tiene su propio icono. */
  '--icono-default': Box,
}
