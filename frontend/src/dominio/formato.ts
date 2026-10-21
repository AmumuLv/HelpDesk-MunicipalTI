/**
 * Formato es-PE: fechas, horas, números y duraciones.
 *
 * Todo el sistema usa la zona horaria de negocio de la institución (viene en
 * `publico/configuracion.zona_horaria`) y el formato de Perú.
 */

import { format, formatDistanceToNowStrict, isValid, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'

const LOCALE = es

/** Convierte a Date desde ISO o desde una fecha "sin hora" (AAAA-MM-DD). */
function aFecha(valor: string | Date | null | undefined): Date | null {
  if (!valor) return null
  if (valor instanceof Date) return isValid(valor) ? valor : null
  // Una fecha sin hora se interpreta a mediodía local para que no cambie de día
  const fecha = /^\d{4}-\d{2}-\d{2}$/.test(valor) ? parseISO(`${valor}T12:00:00`) : parseISO(valor)
  return isValid(fecha) ? fecha : null
}

/** "5 oct 2026" */
export function fechaCorta(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, "d MMM yyyy", { locale: LOCALE }) : '—'
}

/** Fecha numérica para informes: 15/10/2026. */
export function fechaNumerica(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, 'dd/MM/yyyy') : '—'
}

export function duracionLegible(minutos: number | null | undefined): string {
  if (minutos == null || !Number.isFinite(minutos)) return '—'
  const total = Math.max(0, Math.round(minutos))
  const dias = Math.floor(total / 1440)
  const horas = Math.floor((total % 1440) / 60)
  const resto = total % 60
  return [dias ? `${dias} ${dias === 1 ? 'día' : 'días'}` : '', horas ? `${horas} ${horas === 1 ? 'hora' : 'horas'}` : '', resto || !total ? `${resto} min` : ''].filter(Boolean).join(' ')
}

/** "lun 5 oct" */
export function fechaDiaCorta(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, "EEE d MMM", { locale: LOCALE }) : '—'
}

/** "5 de octubre de 2026" */
export function fechaLarga(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, "d 'de' MMMM 'de' yyyy", { locale: LOCALE }) : '—'
}

/** "05/10/2026, 14:32" */
export function fechaHora(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, "dd/MM/yyyy, HH:mm", { locale: LOCALE }) : '—'
}

/** "14:32" */
export function hora(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, 'HH:mm', { locale: LOCALE }) : '—'
}

/** "hoy", "ayer", "hace 3 días" */
export function desdeHace(valor: string | Date | null | undefined): string {
  const fecha = aFecha(valor)
  if (!fecha) return '—'
  return formatDistanceToNowStrict(fecha, { locale: LOCALE, addSuffix: true })
}

/** Duración legible a partir de minutos: "2 h 15 min", "45 min", "3 días" */
export function duracionMinutos(minutos: number | null | undefined): string {
  if (minutos === null || minutos === undefined) return '—'
  const absoluto = Math.abs(Math.round(minutos))
  if (absoluto < 60) return `${absoluto} min`
  const horas = Math.floor(absoluto / 60)
  const resto = absoluto % 60
  if (horas < 24) return resto ? `${horas} h ${resto} min` : `${horas} h`
  const dias = Math.floor(horas / 24)
  const horasResto = horas % 24
  return horasResto ? `${dias} d ${horasResto} h` : `${dias} d`
}

/** Tiempo restante con signo: "2 h 15 min restantes", "Vencido hace 40 min" */
export function tiempoRestante(minutos: number | null | undefined): string {
  if (minutos === null || minutos === undefined) return 'Sin plazo'
  if (minutos < 0) return `Vencido hace ${duracionMinutos(minutos)}`
  return `${duracionMinutos(minutos)} restantes`
}

/** Números con separador de miles: 1234 → "1,234" */
export function numero(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  return new Intl.NumberFormat('es-PE').format(valor)
}

/**
 * Cómo se escribe cada rol, en un solo sitio.
 *
 * Antes el filtro decía «Técnico TI» y la tabla aplicaba `capitalize` sobre el valor
 * crudo, así que un técnico salía como **«Tecnico»**: sin tilde y con otro nombre.
 * `capitalize` de CSS pone mayúscula, no tilde.
 */
export const ETIQUETAS_ROL: Record<string, string> = {
  usuario: 'Usuario',
  tecnico: 'Técnico TI',
  administrador: 'Administrador',
  sistema: 'Sistema',
}

/** «tecnico» → «Técnico TI». Un rol desconocido se devuelve tal cual, no inventado. */
export function etiquetaRol(rol: string | null | undefined): string {
  if (!rol) return 'Sin rol'
  return ETIQUETAS_ROL[rol.toLocaleLowerCase('es')] ?? rol
}

/** Los roles que se pueden crear, para los desplegables de alta y filtro. */
export const ROLES: { valor: string; etiqueta: string }[] = [
  { valor: 'usuario', etiqueta: ETIQUETAS_ROL.usuario },
  { valor: 'tecnico', etiqueta: ETIQUETAS_ROL.tecnico },
  { valor: 'administrador', etiqueta: ETIQUETAS_ROL.administrador },
]

/**
 * Cantidad con su palabra concordada: `plural(1, 'persona')` → «1 persona».
 *
 * Existe porque el plural se estaba escribiendo a mano en cada sitio y se colaba:
 * en la zona COMPLEJO había una oficina que mostraba «1 personas». Un número al lado
 * de su palabra es de las cosas que más se notan cuando salen mal.
 */
export function plural(cantidad: number | null | undefined, palabra: string, plural_?: string): string {
  if (cantidad === null || cantidad === undefined) return `— ${palabra}`
  const muchas = plural_ ?? `${palabra}s`
  return `${numero(cantidad)} ${cantidad === 1 ? palabra : muchas}`
}

/** Porcentaje: 87.4 → "87.4%" */
export function porcentaje(valor: number | null | undefined, decimales = 1): string {
  if (valor === null || valor === undefined) return '—'
  return `${new Intl.NumberFormat('es-PE', {
    maximumFractionDigits: decimales,
    minimumFractionDigits: 0,
  }).format(valor)}%`
}

/** Variación con signo: 12.5 → "+12.5%", -3 → "−3%" */
export function variacion(valor: number | null | undefined, decimales = 1): string {
  if (valor === null || valor === undefined) return '—'
  const texto = new Intl.NumberFormat('es-PE', {
    maximumFractionDigits: decimales,
    minimumFractionDigits: 0,
    signDisplay: 'exceptZero',
  }).format(valor)
  return `${texto}%`
}

/** Tamaño de archivo legible: 1536 → "1.5 KB" */
export function tamano(bytes: number | null | undefined): string {
  if (!bytes) return '0 B'
  const unidades = ['B', 'KB', 'MB', 'GB']
  let indice = 0
  let valor = bytes
  while (valor >= 1024 && indice < unidades.length - 1) {
    valor /= 1024
    indice += 1
  }
  return `${new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 }).format(valor)} ${unidades[indice]}`
}

/** AAAA-MM-DD para <input type="date"> */
export function paraInputFecha(valor: Date | string | null | undefined): string {
  const fecha = aFecha(valor)
  return fecha ? format(fecha, 'yyyy-MM-dd') : ''
}

/** Fecha de hoy en la zona de negocio, como AAAA-MM-DD */
export function hoy(): string {
  return format(new Date(), 'yyyy-MM-dd')
}

/** Suma días a una fecha AAAA-MM-DD */
export function sumarDias(fecha: string, dias: number): string {
  const base = parseISO(`${fecha}T12:00:00`)
  base.setDate(base.getDate() + dias)
  return format(base, 'yyyy-MM-dd')
}

/** Iniciales para el avatar: "Ana Pérez Ruiz" → "AP" */
export function iniciales(nombre: string | null | undefined): string {
  if (!nombre) return '??'
  const partes = nombre.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return '??'
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase()
  return `${partes[0][0]}${partes[1][0]}`.toUpperCase()
}

/** Convierte texto a "Como está written por el usuario" */
export function aTextoLegible(valor: string | null | undefined): string {
  if (!valor) return '—'
  return valor.replace(/_/g, ' ').replace(/^\w/, (letra) => letra.toUpperCase())
}
