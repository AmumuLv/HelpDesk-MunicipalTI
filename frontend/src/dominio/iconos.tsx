/**
 * Iconos de la API.
 *
 * El backend envía el nombre del icono como texto (`power`, `wifi`, `printer`…).
 * Aquí se traduce a un icono de Lucide. Si el backend manda uno que no está en
 * el catálogo, se usa el genérico y nunca se rompe la pantalla.
 */

import {
  Cloud,
  Disc3,
  Fingerprint,
  FolderKanban,
  FolderTree,
  MessageCircle,
  AppWindow,
  Mail,
  FileQuestion,
  HardDrive,
  Keyboard,
  Laptop,
  Monitor,
  Package,
  Power,
  Printer,
  Server,
  ShieldAlert,
  UserCog,
  Wifi,
  Wrench,
  type LucideIcon,
} from 'lucide-react'

const ICONOS: Record<string, LucideIcon> = {
  disc: Disc3,
  fingerprint: Fingerprint,
  'folder-network': FolderTree,
  'folder-shared': FolderKanban,
  'message-circle': MessageCircle,
  'app-window': AppWindow,
  mail: Mail,
  power: Power,
  wifi: Wifi,
  network: Wifi,
  printer: Printer,
  monitor: Monitor,
  display: Monitor,
  laptop: Laptop,
  computer: Monitor,
  desktop: Monitor,
  keyboard: Keyboard,
  hardware: Wrench,
  software: Package,
  program: FileQuestion,
  app: FileQuestion,
  cloud: Cloud,
  server: Server,
  drive: HardDrive,
  disco: HardDrive,
  cuenta: UserCog,
  user: UserCog,
  acceso: ShieldAlert,
  security: ShieldAlert,
  lento: Package,
  otros: FileQuestion,
  otro: FileQuestion,
  default: Wrench,
}

/** Nombre del icono que manda la API → icono de la librería. */
export function iconoDeNombre(nombre: string | null | undefined): LucideIcon {
  if (!nombre) return ICONOS.default
  const limpio = nombre.toLowerCase().trim()
  return ICONOS[limpio] ?? ICONOS.default
}

/** Devuelve el elemento listo para pintar en un RadioCard. */
export function elementoIcono(nombre: string | null | undefined, tamano = 18) {
  const Icono = iconoDeNombre(nombre)
  return <Icono size={tamano} aria-hidden="true" />
}
