import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Building2, Headset, MessageCircle, UserRound } from 'lucide-react'
import { api } from '../../api/cliente'
import { DialogModal } from '../base/Sobreposiciones'
import { Avatar, ErrorState, SkeletonPanel } from '../base/Estructura'
import { Button } from '../base/Button'
import './PerfilTecnicoTicket.css'

type Perfil = { nombre: string; cargo: string; oficina?: string | null; especialidades: string[] }

export function PerfilTecnicoTicket({ ticketId, tecnicoId, nombre }: { ticketId: string; tecnicoId: string; nombre: string }) {
  const [abierto, setAbierto] = useState(false)
  const perfil = useQuery({ queryKey: ['perfil-tecnico-ticket', ticketId, tecnicoId], queryFn: () => api.obtener<Perfil>(`/tickets/${ticketId}/tecnico-perfil`), enabled: abierto, retry: false })
  return <>
    <button type="button" onClick={() => setAbierto(true)} aria-label={`Ver perfil de ${nombre}`} className="inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-md px-1 font-semibold text-info-strong underline decoration-info-strong/30 underline-offset-4 hover:decoration-current focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"><span className="break-words">{nombre}</span><UserRound size={15} className="shrink-0" aria-hidden="true" /></button>
    <DialogModal abierto={abierto} alCerrar={() => setAbierto(false)} titulo="Tu técnico de soporte" descripcion="Conoce a la persona que atiende tu reporte." tamano="sm" className="perfil-ti-dialogo">
      {perfil.isPending ? <SkeletonPanel filas={3} /> : perfil.isError ? <ErrorState compacto mensaje="No pudimos cargar el perfil del técnico." alReintentar={() => void perfil.refetch()} /> : perfil.data ? <div className="flex flex-col gap-5">
        <div className="perfil-ti-identidad"><div className="perfil-ti-avatar"><Avatar nombre={perfil.data.nombre} tamano="lg" /></div><div className="min-w-0"><span className="perfil-ti-eyebrow"><Headset size={13} aria-hidden="true" />EQUIPO TI</span><h3 className="mt-1 break-words text-xl font-bold tracking-tight">{perfil.data.nombre}</h3><p className="mt-1 break-words text-sm text-muted-foreground">{perfil.data.cargo}</p></div></div>
        <div className="perfil-ti-contacto"><span className="perfil-ti-icono"><Building2 size={21} aria-hidden="true" /></span><div className="min-w-0 flex-1"><p className="text-xs text-muted-foreground">Oficina</p><p className="mt-1 text-sm font-semibold leading-relaxed [overflow-wrap:anywhere]">{perfil.data.oficina || 'Sin oficina asignada'}</p></div></div>
        {perfil.data.especialidades.length ? <div><p className="mb-2 text-xs font-semibold text-muted-foreground">Especialidades</p><div className="flex flex-wrap gap-2">{perfil.data.especialidades.map(especialidad => <span key={especialidad} className="perfil-ti-especialidad">{especialidad}</span>)}</div></div> : null}
        <div className="perfil-ti-conversacion"><MessageCircle size={19} className="shrink-0" aria-hidden="true" /><p>Puedes comunicarte con tu técnico en la conversación de este reporte.</p></div>
        <Button variante="primario" anchoCompleto onClick={() => setAbierto(false)}>Volver al reporte</Button>
      </div> : null}
    </DialogModal>
  </>
}
