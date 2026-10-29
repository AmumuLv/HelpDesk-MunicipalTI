import type { ActivoDetalle } from '../api/tipos'
import { CircleCheck, Cpu, FileText, Fingerprint, HardDrive, MemoryStick, Monitor, Network, Package, ScanBarcode, ShieldCheck, Tag, type LucideIcon } from 'lucide-react'

export type CampoEquipo = keyof NonNullable<ActivoDetalle['campos']>
type EstadoDato = 'completo' | 'pendiente' | 'no_aplica' | 'no_disponible'
export type CampoPresentacion = { campo: CampoEquipo; etiqueta: string }
export const ICONOS_DATOS: Record<string, LucideIcon> = { nombre_equipo: Monitor, codigo_patrimonial: ScanBarcode, marca: Tag, modelo: Package, tamano_pantalla: Monitor, procesador: Cpu, memoria_ram: MemoryStick, almacenamiento: HardDrive, direccion_ip: Network, direccion_mac: Fingerprint, propiedad: ShieldCheck, estado: CircleCheck, observaciones: FileText }

export function estadoDatoEquipo(datos: ActivoDetalle, campo: CampoEquipo): EstadoDato {
  const info = datos.campos?.[campo]
  if (info?.estado === 'no_aplica' || info?.estado === 'no_disponible') return info.estado
  const valor = datos[campo as keyof ActivoDetalle] ?? info?.valor
  return typeof valor === 'string' && valor.trim() ? 'completo' : 'pendiente'
}
