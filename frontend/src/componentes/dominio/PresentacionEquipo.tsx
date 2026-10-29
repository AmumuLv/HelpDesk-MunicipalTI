import { etiquetaPropiedad } from '../../dominio/propiedad'
import { Building2, CircleCheck, CircleHelp, Clock3, Cpu, Database, FileText, MapPin, MinusCircle, Network, ScanBarcode, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ActivoDetalle } from '../../api/tipos'
import { useSesion } from '../../estado/useSesion'
import { DisponibilidadBadge } from './Badge'
import { ICONOS_DATOS, estadoDatoEquipo, type CampoPresentacion } from '../../dominio/datosEquipo'

export type { CampoPresentacion } from '../../dominio/datosEquipo'

const ESTADOS = {
  completo: { texto: 'Dato registrado', icono: CircleCheck, clase: 'border-success-borde bg-success-soft text-success-strong' },
  pendiente: { texto: 'Pendiente', icono: Clock3, clase: 'border-warning-borde bg-warning-soft text-warning-strong' },
  no_aplica: { texto: 'No aplica', icono: MinusCircle, clase: 'border-border bg-muted text-muted-foreground' },
  no_disponible: { texto: 'No disponible', icono: CircleHelp, clase: 'border-info-borde bg-info-soft text-info-strong' },
} as const

export function IndicadorDato({ estado }: { estado: keyof typeof ESTADOS }) {
  const { texto, icono: Icono, clase } = ESTADOS[estado]
  return <span className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-2xs font-semibold ${clase}`}><Icono size={13} aria-hidden="true" />{texto}</span>
}

export function ResumenDisponibilidad({ datos, campos }: { datos: ActivoDetalle; campos: readonly CampoPresentacion[] }) {
  const registrados = campos.filter(c => estadoDatoEquipo(datos, c.campo) === 'completo').length
  const pendientes = campos.filter(c => estadoDatoEquipo(datos, c.campo) === 'pendiente').length
  return <div className="mb-4 grid grid-cols-3 gap-2" aria-label="Resumen de disponibilidad">
    {[{ cantidad: registrados, texto: 'Registrados', clase: 'text-success-strong bg-success-soft border-success-borde' }, { cantidad: pendientes, texto: 'Pendientes', clase: 'text-warning-strong bg-warning-soft border-warning-borde' }, { cantidad: campos.length - registrados - pendientes, texto: 'Excluidos', clase: 'text-muted-foreground bg-muted border-border' }].map(dato => <div key={dato.texto} className={`min-w-0 rounded-lg border p-2 text-center ${dato.clase}`}><p className="text-xl font-bold tabular-nums">{dato.cantidad}</p><p className="text-2xs">{dato.texto}</p></div>)}
  </div>
}

export function PresentacionEquipo({ datos, campos }: { datos: ActivoDetalle; campos: readonly CampoPresentacion[] }) {
  const sesion = useSesion()
  const org = sesion.puede('org.ver')
  const grupos = [
    { titulo: 'Identificación y propiedad', icono: ScanBarcode, clase: 'text-info-strong', claves: ['codigo_patrimonial', 'marca', 'modelo', 'propiedad', 'estado'] },
    { titulo: 'Características técnicas', icono: Cpu, clase: 'text-ai-strong', claves: ['tamano_pantalla', 'procesador', 'memoria_ram', 'almacenamiento'] },
    { titulo: 'Conectividad', icono: Network, clase: 'text-info-strong', claves: ['direccion_ip', 'direccion_mac'] },
    { titulo: 'Observaciones', icono: FileText, clase: 'text-muted-foreground', claves: ['observaciones'] },
  ]
  const ubicacion = [
    { etiqueta: 'Oficina', valor: datos.oficina_nombre || 'Sin oficina', icono: Building2, enlace: org && datos.oficina_id ? `/panel/oficinas/${datos.oficina_id}` : undefined },
    { etiqueta: 'Zona', valor: datos.zona_nombre || 'Sin zona', icono: MapPin, enlace: org && datos.zona_id ? `/panel/zonas/${datos.zona_id}` : undefined },
    { etiqueta: 'Responsable', valor: datos.responsable_nombre || 'Uso común de la oficina', icono: UserRound, enlace: sesion.puede('usuarios.ver') && datos.responsable_id ? `/panel/usuarios/${datos.responsable_id}` : undefined },
  ]
  return <div className="flex min-w-0 flex-col gap-5">
    <dl className="grid gap-3 sm:grid-cols-2">{ubicacion.map(({ etiqueta, valor, icono: Icono, enlace }) => <div key={etiqueta} className={`flex min-w-0 items-start gap-3 rounded-xl border border-border bg-surface-2/50 p-3 ${etiqueta === 'Responsable' ? 'sm:col-span-2' : ''}`}>
      <span className="rounded-lg bg-info-soft p-2 text-info-strong"><Icono size={18} aria-hidden="true" /></span>
      <div className="min-w-0"><dt className="text-2xs text-muted-foreground">{etiqueta}</dt><dd className="mt-0.5 break-words text-sm font-semibold">{enlace ? <Link to={enlace} className="text-info-strong hover:underline">{valor}</Link> : valor}</dd></div>
    </div>)}</dl>
    {grupos.map(({ titulo, icono: Icono, clase, claves }) => {
      const visibles = campos.filter(c => claves.includes(c.campo))
      if (!visibles.length) return null
      return <section key={titulo} aria-label={titulo} className="min-w-0">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Icono size={17} className={clase} aria-hidden="true" />{titulo}</h3>
        <dl className={`grid gap-3 ${titulo === 'Observaciones' ? '' : 'sm:grid-cols-2'}`}>{visibles.map(({ campo, etiqueta }) => {
          const estado = estadoDatoEquipo(datos, campo)
          const IconoCampo = ICONOS_DATOS[campo] || Database
          const valor = datos[campo as keyof ActivoDetalle] ?? datos.campos?.[campo]?.valor
          const usb = campo === 'direccion_ip' && datos.tipo.toLocaleLowerCase('es') === 'impresora' && datos.campos?.direccion_ip?.motivo === 'Cable USB'
          return <div key={campo} className={`min-w-0 rounded-xl border p-3 ${estado === 'completo' ? 'border-border bg-surface shadow-sm' : estado === 'pendiente' ? 'border-warning/25 bg-warning-soft/15' : 'border-border bg-surface-2/50'}`}>
            <dt className="flex items-center gap-2 text-2xs text-muted-foreground"><IconoCampo size={15} className={estado === 'completo' ? clase : ''} aria-hidden="true" />{etiqueta}</dt>
            <dd className="mt-2 break-words font-semibold whitespace-pre-wrap">{usb ? 'Cable USB' : estado === 'completo' ? campo === 'estado' ? <DisponibilidadBadge estado={String(valor)} /> : campo === 'propiedad' ? etiquetaPropiedad(String(valor)) : String(valor) : <span className="text-sm font-normal text-muted-foreground">{ESTADOS[estado].texto}</span>}</dd>
          </div>
        })}</dl>
      </section>
    })}
  </div>
}
