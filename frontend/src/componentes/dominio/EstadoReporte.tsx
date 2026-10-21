import { Check, CheckCircle2, Clock3, PauseCircle, Wrench } from 'lucide-react'
import { cn } from '../../lib/cn'

const ESTADOS: Record<string, { texto: string; detalle: string; tono: string; icono: typeof Check; etapa: number }> = {
  nuevo: { texto: 'Recibido', detalle: 'Tu reporte llegó a soporte. Cuando se asigne, verás quién te atiende.', tono: 'bg-primary-soft text-primary-strong', icono: Clock3, etapa: 0 },
  en_progreso: { texto: 'En atención', detalle: 'Soporte está atendiendo tu caso. Puedes escribir en la conversación.', tono: 'bg-info-soft text-info-strong', icono: Wrench, etapa: 1 },
  en_espera: { texto: 'En espera', detalle: 'El caso está en espera. Revisa la conversación por si soporte necesita un dato.', tono: 'bg-warning-soft text-warning-strong', icono: PauseCircle, etapa: 1 },
  resuelto: { texto: 'Finalizado', detalle: 'El caso terminó. Consulta el resultado de la atención.', tono: 'bg-success-soft text-success-strong', icono: CheckCircle2, etapa: 2 },
  cerrado: { texto: 'Finalizado', detalle: 'El caso terminó. Si el problema continúa, puedes pedir que lo revisen otra vez.', tono: 'bg-success-soft text-success-strong', icono: CheckCircle2, etapa: 2 },
}

export function EstadoReporte({ estado, seguimiento = false }: { estado: string; seguimiento?: boolean }) {
  const actual = ESTADOS[estado] ?? { texto: 'En seguimiento', detalle: 'Consulta la conversación para conocer las novedades.', tono: 'bg-muted text-foreground', icono: Clock3, etapa: 0 }
  const Icono = actual.icono
  if (!seguimiento) return <span className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold', actual.tono)}><Icono size={14} aria-hidden="true" />{actual.texto}</span>
  return <section aria-label="Seguimiento del reporte" className="rounded-2xl border border-border bg-surface p-5">
    <div className="flex items-start gap-3"><span className={cn('flex size-11 shrink-0 items-center justify-center rounded-full', actual.tono)}><Icono size={22} /></span><div><h2 className="text-lg font-bold">{actual.texto}</h2><p className="mt-1 text-sm text-muted-foreground">{actual.detalle}</p></div></div>
    <ol className="mt-5 grid grid-cols-3 gap-2" aria-label="Progreso">{['Recibido', 'En atención', 'Finalizado'].map((texto, indice) => <li key={texto} aria-current={indice === actual.etapa ? 'step' : undefined} className="text-center text-xs"><span className={cn('mb-2 block h-1.5 rounded-full', indice <= actual.etapa ? 'bg-accion' : 'bg-muted')} /><span className={indice === actual.etapa ? 'font-bold text-foreground' : 'text-muted-foreground'}>{texto}</span></li>)}</ol>
  </section>
}
