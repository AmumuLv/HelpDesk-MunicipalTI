import { Monitor, Smartphone, Tablet, CheckCircle2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/cliente'
import { useSesion } from '../../estado/Sesion'
import { useAvisos } from '../../estado/Avisos'
import { fechaHora } from '../../dominio/formato'
import { Button } from '../base/Button'
import { Panel, ErrorState } from '../base/Estructura'

type Conexiones = { total: number; limite: number; items: { id: string; agente: string; inicio: string; ultimo_uso?: string; actual: boolean }[] }
export function DispositivosCuenta({ usuarioId }: { usuarioId?: string }) {
  const sesion = useSesion()
  const avisos = useAvisos()
  const navegar = useNavigate()
  const ruta = usuarioId ? `/usuarios/${usuarioId}/dispositivos` : '/auth/dispositivos'
  const consulta = useQuery({ queryKey: ['dispositivos', usuarioId ?? sesion.usuario?.id], queryFn: () => api.obtener<Conexiones>(ruta), refetchInterval: 30_000 })
  const cerrar = async (id: string, actual: boolean) => {
    try {
      await api.borrar(`${ruta}/${id}`)
      if (actual) { await sesion.salir(); navegar('/acceder', { replace: true }) }
      else await consulta.refetch()
    } catch (fallo) { avisos.desdeError(fallo) }
  }
  return <Panel titulo={`Dispositivos conectados · ${consulta.data?.total ?? '…'} / 3`} descripcion="Máximo tres conexiones simultáneas. Al iniciar en un cuarto dispositivo se cierra la sesión más antigua. Cada navegador o perfil de navegador cuenta como una conexión.">
    {consulta.isError ? <ErrorState compacto mensaje="No pudimos consultar las conexiones." alReintentar={() => void consulta.refetch()} /> : <ul className="divide-y divide-border">{consulta.data?.items.map((conexion) => {
      const agente = conexion.agente
      const tablet = /iPad|Tablet|PlayBook|Silk/i.test(agente) || (/Android/i.test(agente) && !/Mobile/i.test(agente))
      const movil = !tablet && /Android|iPhone|iPod|Windows Phone|Mobile/i.test(agente)
      const Icono = tablet ? Tablet : movil ? Smartphone : Monitor
      const tipo = tablet ? 'Tablet' : movil ? 'Celular' : 'Computadora'
      const sistema = /Android/i.test(agente) ? 'Android' : /iPhone|iPad|iPod/i.test(agente) ? 'iOS / iPadOS' : /Windows/i.test(agente) ? 'Windows' : /CrOS/i.test(agente) ? 'ChromeOS' : /Macintosh|Mac OS X/i.test(agente) ? 'macOS' : /Linux/i.test(agente) ? 'Linux' : ''
      const navegador = /Edg(?:e|A|iOS)?\//i.test(agente) ? 'Edge' : /OPR\/|Opera/i.test(agente) ? 'Opera' : /Firefox|FxiOS/i.test(agente) ? 'Firefox' : /Chrome|CriOS/i.test(agente) ? 'Chrome' : /Safari/i.test(agente) ? 'Safari' : 'Navegador'
      return <li key={conexion.id} className="flex flex-wrap items-center gap-3 py-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-info-soft text-info-strong"><Icono size={21} aria-hidden="true" /></span>
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold">{tipo}</p>{conexion.actual && <span className="inline-flex items-center gap-1 text-xs font-medium text-success-strong"><CheckCircle2 size={13} aria-hidden="true" />Este dispositivo</span>}</div>
          <p className="text-xs text-muted-foreground">{[sistema, navegador].filter(Boolean).join(' · ')}</p>
          <p className="mt-1 text-xs text-muted-foreground">Inicio: {fechaHora(conexion.inicio)}</p>
          {conexion.ultimo_uso && <p className="text-xs text-muted-foreground">Última actividad: {fechaHora(conexion.ultimo_uso)}</p>}
        </div><Button tamano="sm" onClick={() => void cerrar(conexion.id, conexion.actual)}>Cerrar conexión</Button>
      </li>
    })}</ul>}
  </Panel>
}
