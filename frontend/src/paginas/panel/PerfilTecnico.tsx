import { useEffect, useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import { BriefcaseBusiness, Building2, ContactRound, Mail, MapPin, Phone } from 'lucide-react'
import { useTecnico, useTickets, useZonas } from '../../api/hooks'
import { ContenidoTab, ErrorState, ListaTabs, PageHeader, Panel, SkeletonPanel, Tab, TabsPanel } from '../../componentes/base/Estructura'
import { Button } from '../../componentes/base/Button'
import { DisponibilidadBadge, EstadoBadge } from '../../componentes/dominio/Badge'
import { TarjetaPerfil } from '../../componentes/dominio/TarjetaPerfil'
import { DatoPerfil } from '../../componentes/dominio/DatoPerfil'
import { EnlaceOficina } from '../../componentes/dominio/EnlaceOficina'
import { ZonaBadge } from '../../componentes/dominio/ZonaBadge'
import { AvatarTecnico } from '../../componentes/dominio/AvatarTecnico'
import { HorarioTecnico } from '../../componentes/dominio/HorarioTecnico'
import { CalendarioEquipoTi } from '../../componentes/dominio/CalendarioEquipoTi'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { fechaCorta } from '../../dominio/formato'
import { useSesion } from '../../estado/useSesion'

export function PerfilTecnico() {
  const { id } = useParams()
  return <ContenidoPerfil key={id} id={id} />
}
function ContenidoPerfil({ id }: { id?: string }) {
  const sesion = useSesion()
  const perfil = useTecnico(id)
  const zonas = useZonas()
  const [tab, setTab] = useState('resumen')
  const [pagina, setPagina] = useState(1)
  const cola = useTickets({ tecnico_id: id, por_pagina: 10, pagina, solo_abiertos: true }, Boolean(id) && tab === 'tickets' && sesion.puede('tickets.operar'))
  useEffect(() => { document.title = `${perfil.data?.nombre || 'Perfil TI'} - Equipo TI` }, [perfil.data?.nombre])
  if (perfil.isLoading) return <SkeletonPanel />
  if (perfil.isError || !perfil.data) return <ErrorState mensaje="No pudimos cargar el perfil TI." detalle={perfil.error?.message} alReintentar={() => void perfil.refetch()} />
  const t = perfil.data
  const d = t.disponibilidad
  const puedeEditar = t.id === sesion.usuario?.id ? sesion.puede('horarios.editar_propio') : sesion.puede('horarios.editar_todos')
  const indiceZona = zonas.data?.items.find((z) => z.id === t.zona_id)?.color_indice
  const colorZona = indiceZona && indiceZona >= 1 && indiceZona <= 8 ? `var(--zona-${indiceZona})` : 'var(--color-muted-foreground)'
  const colorFuerte = `color-mix(in srgb, ${colorZona} 75%, var(--color-foreground))`
  const colorSuave = `color-mix(in srgb, ${colorZona} 10%, var(--color-surface))`
  const colorBorde = `color-mix(in srgb, ${colorZona} 28%, var(--color-border))`
  const colores = {
    '--perfil-acento': colorZona, '--color-primary': colorZona, '--color-primary-strong': colorFuerte,
    '--color-primary-soft': colorSuave, '--color-primary-borde': colorBorde,
    '--rol-relleno': colorZona, '--rol-fuerte': colorFuerte, '--rol-suave': colorSuave, '--rol-borde': colorBorde,
  } as CSSProperties
  return <div className="flex min-w-0 flex-col gap-4" style={colores}>
    <PageHeader titulo="Perfil TI" descripcion="La misma cuenta de Usuarios, con su disponibilidad y jornada laboral."
      migas={[{ texto: 'Equipo TI', enlace: '/panel/equipo-ti' }, { texto: 'Perfil' }]}
      acciones={<>
        <Button asChild variante="secundario"><Link to="/panel/equipo-ti">Volver al equipo</Link></Button>
        {sesion.puede('usuarios.ver') ? <Button asChild variante="primario"><Link to={`/panel/usuarios/${t.id}`}>{sesion.puede('usuarios.editar') && (t.rol !== 'administrador' || sesion.esAdmin) ? 'Ver y editar datos personales' : 'Ver datos personales'}</Link></Button> : null}
      </>} />
    <TarjetaPerfil titulo={t.nombre} subtitulo={<span className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <span className="inline-flex max-w-full items-center gap-1"><BriefcaseBusiness size={13} className="shrink-0" /><span className="truncate">{t.cargo && !t.cargo.includes('@') ? t.cargo : 'Equipo de soporte TI'}</span></span>
      <ZonaBadge id={t.zona_id} nombre={t.zona_nombre} />
    </span>}
      icono={<AvatarTecnico id={t.id} nombre={t.nombre} tieneFoto={t.tiene_foto} tamano="lg" />} colorIndice={indiceZona}
      metricas={[
        { etiqueta: 'Atendidos (90 días)', valor: t.metricas.tickets_atendidos },
        { etiqueta: 'Pendientes ahora', valor: d.carga_asignados },
        { etiqueta: 'En espera', valor: d.carga_espera },
        { etiqueta: 'Cumplimiento SLA', valor: t.metricas.insuficientes_datos || t.metricas.cumplimiento_sla === null ? 'Sin datos' : `${t.metricas.cumplimiento_sla}%` },
      ]} />
    <div className="flex flex-wrap items-center gap-3"><DisponibilidadBadge estado={d.estado} etiqueta={d.etiqueta} />
      <span className="text-sm text-muted-foreground">{d.carga_asignados} tickets abiertos · referencia de capacidad: {t.perfil.capacidad_diaria} tickets/día</span>
    </div>
    <TabsPanel valor={tab} alCambiar={setTab} className="flex flex-col gap-4">
      <ListaTabs><Tab valor="resumen">Resumen</Tab>{sesion.puede('tickets.operar') ? <Tab valor="tickets">Trabajo pendiente</Tab> : null}<Tab valor="horario">Horario</Tab><Tab valor="ausencias">Ausencias</Tab><Tab valor="calendario">Calendario</Tab></ListaTabs>
      <ContenidoTab valor="resumen">
        <Panel titulo="Datos de contacto" descripcion="Estos datos y la foto se mantienen desde Usuarios.">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <DatoPerfil etiqueta="Correo" icono={Mail}>{t.email || 'Sin correo'}</DatoPerfil>
            <DatoPerfil etiqueta="Cargo" icono={BriefcaseBusiness}>{t.cargo || 'Sin cargo'}</DatoPerfil>
            <DatoPerfil etiqueta="Oficina" icono={Building2}><EnlaceOficina id={t.oficina_id} nombre={t.oficina_nombre} zonaId={t.zona_id} /></DatoPerfil>
            <DatoPerfil etiqueta="Zona" icono={MapPin}><ZonaBadge id={t.zona_id} nombre={t.zona_nombre} /></DatoPerfil>
            <DatoPerfil etiqueta="Teléfono" icono={Phone}>{t.telefono || 'Sin teléfono'}</DatoPerfil>
            <DatoPerfil etiqueta="Anexo" icono={ContactRound}>{t.anexo || 'Sin anexo'}</DatoPerfil>
          </dl>
          <p className="mt-4 text-sm text-muted-foreground">Especialidades: {t.perfil.especialidades.join(', ') || 'Sin especialidades registradas'}</p>
        </Panel>
      </ContenidoTab>
      {sesion.puede('tickets.operar') ? <ContenidoTab valor="tickets"><Panel titulo="Trabajo pendiente" descripcion="Tickets abiertos asignados a esta persona, de diez en diez.">
        {cola.isError ? <ErrorState mensaje="No pudimos cargar la cola." alReintentar={() => void cola.refetch()} /> : cola.isPending ? <SkeletonPanel /> : !cola.data?.items.length ? <p className="text-sm text-muted-foreground">No hay tickets pendientes asignados.</p> : <>
          <ul className="divide-y divide-border">{cola.data.items.map((ticket) => <li key={ticket.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <Link className="text-sm font-semibold text-warning-strong hover:underline" to={`/panel/tickets/${ticket.id}`}>{ticket.codigo} · {ticket.asunto}</Link><EstadoBadge estado={ticket.estado} />
          </li>)}</ul>
          <div className="mt-4"><Paginacion pagina={cola.data.pagina} totalPaginas={cola.data.total_paginas} total={cola.data.total} porPagina={10} alCambiar={setPagina} /></div>
        </>}
      </Panel></ContenidoTab> : null}
      <ContenidoTab valor="horario"><Panel titulo="Horario laboral"><HorarioTecnico id={t.id} nombre={t.nombre} puedeEditar={puedeEditar} /></Panel></ContenidoTab>
      <ContenidoTab valor="ausencias"><Panel titulo="Ausencias de esta persona" acciones={puedeEditar ? <Button asChild variante="secundario"><Link to={`/panel/equipo-ti?tab=ausencias&tecnico_id=${t.id}`}>Gestionar ausencias</Link></Button> : undefined}>
        {t.ausencias.length ? <ul className="divide-y divide-border">{t.ausencias.map((a) => <li key={a.id} className="py-3 text-sm"><span className="font-medium">{a.tipo}</span> · {fechaCorta(a.inicio)} - {fechaCorta(a.fin)}{a.motivo ? ` · ${a.motivo}` : ''}</li>)}</ul> : <p className="text-sm text-muted-foreground">No hay ausencias registradas.</p>}
      </Panel></ContenidoTab>
      <ContenidoTab valor="calendario"><Panel titulo="Semana de esta persona"><CalendarioEquipoTi tecnicoInicial={t.id} /></Panel></ContenidoTab>
    </TabsPanel>
  </div>
}
