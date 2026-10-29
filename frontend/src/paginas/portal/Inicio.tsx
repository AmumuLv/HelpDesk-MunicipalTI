import { ArrowRight, BookOpen, CheckCircle2, Headphones, MessageCircle, Monitor, Siren } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useMisTickets } from '../../api/hooks'
import { Button } from '../../componentes/base/Button'
import { ErrorState, SkeletonPanel } from '../../componentes/base/Estructura'
import { EstadoReporte } from '../../componentes/dominio/EstadoReporte'
import { desdeHace } from '../../dominio/formato'
import { useSesion } from '../../estado/useSesion'

export function Inicio() {
  const sesion = useSesion()
  const reportes = useMisTickets({ solo_abiertos: true, por_pagina: 3 })
  useEffect(() => { document.title = 'Pedir ayuda · Mesa de Ayuda' }, [])
  return <>
    <div className="flex items-center gap-3">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-strong"><Headphones size={23} /></span>
      <div className="min-w-0"><p className="truncate text-xl font-bold sm:text-2xl">Hola, {sesion.usuario?.nombre?.split(' ')[0] || 'te damos la bienvenida'}</p><p className="text-sm text-muted-foreground">Tu soporte técnico, en un solo lugar.</p></div>
    </div>
    <section aria-labelledby="pedir-ayuda" className="relative overflow-hidden rounded-3xl border border-destructive-borde bg-surface px-5 py-8 text-center shadow-panel sm:px-10 sm:py-10">
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-destructive-soft to-transparent" />
      <div className="relative mx-auto flex max-w-xl flex-col items-center">
        <span aria-hidden="true" className="mb-5 flex size-24 items-center justify-center rounded-full border-8 border-destructive-soft bg-[#b72d3f] text-white shadow-md"><Siren size={42} strokeWidth={1.7} /></span>
        <h1 id="pedir-ayuda" className="text-2xl font-bold sm:text-3xl">¿Algo no funciona?</h1>
        <p className="mt-3 max-w-md text-base text-muted-foreground">Presiona el botón y cuéntanos qué ocurre. No necesitas saber de tecnología.</p>
        <Button asChild tamano="tactil" className="portal-boton-ayuda mt-6 min-h-16 w-full max-w-sm rounded-2xl text-lg shadow-md">
          <Link to="/reportar">Necesito ayuda <ArrowRight size={21} aria-hidden="true" /></Link>
        </Button>
        <p className="mt-3 text-sm text-muted-foreground">2 pasos para reportar · Luego podrás conversar con soporte</p>
      </div>
    </section>
    <section aria-labelledby="reportes-en-curso">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h2 id="reportes-en-curso" className="text-lg font-bold">Tu ayuda en curso</h2><Link to="/mis-tickets" className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-info-strong hover:underline">Mis reportes <ArrowRight size={15} /></Link></div>
      {reportes.isPending ? <SkeletonPanel filas={2} /> : reportes.isError ? <ErrorState compacto mensaje="No pudimos cargar tus reportes." alReintentar={() => void reportes.refetch()} /> : !reportes.data?.items.length ?
        <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface p-5"><CheckCircle2 size={24} className="shrink-0 text-success-strong" /><div><p className="font-semibold">No tienes reportes pendientes</p><p className="mt-1 text-sm text-muted-foreground">Si aparece un problema, usa el botón de arriba. Tus reportes anteriores siguen en «Mis reportes».</p></div></div> :
        <ul className="flex flex-col gap-3">{reportes.data.items.map(reporte => <li key={reporte.id}>
          <Link to={`/mis-tickets/${reporte.id}`} className="group block rounded-2xl border border-border bg-surface p-5 shadow-sm transition-colors hover:border-warning focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-semibold text-muted-foreground">{reporte.codigo} · {desdeHace(reporte.creado_en)}</span><EstadoReporte estado={reporte.estado} /></div>
            <h3 className="mt-2 line-clamp-2 break-words text-lg font-semibold [overflow-wrap:anywhere]" title={reporte.asunto}>{reporte.asunto}</h3>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><p className="min-w-0 truncate text-sm text-muted-foreground">{reporte.tecnico_nombre ? `Te atiende ${reporte.tecnico_nombre}` : 'Reporte recibido por soporte.'}</p><span className="inline-flex items-center gap-2 text-sm font-semibold text-info-strong"><MessageCircle size={17} />Ver seguimiento <ArrowRight size={16} /></span></div>
          </Link>
        </li>)}</ul>}
    </section>
    <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 border-t border-border pt-4">
      <Link to="/mis-equipos" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><Monitor size={17} />Ver mis equipos</Link>
      <Link to="/ayuda" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><BookOpen size={17} />Guías de ayuda</Link>
    </div>
  </>
}
