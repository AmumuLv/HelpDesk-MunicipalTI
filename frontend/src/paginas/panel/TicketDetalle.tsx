/**
 * Detalle de ticket para el equipo TI.
 *
 * Tres bloques: la conversación (si la API dice que este ticket la tiene), las
 * notas internas (que el usuario nunca ve) y el panel de IA con su explicación.
 *
 * El AIPanel solo se monta si el backend devuelve sugerencias y la persona las
 * tiene activadas: si están desactivadas, no hay franja, no hay columna de
 * confianza y no se insinúa que falte algo.
 */

import { ArrowLeft, Building2, CircleAlert, FolderOpen, Lock, MessageSquare, Pencil, Save, Sparkles, UserCheck, Users } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useTiempoReal } from '../../api/tiempoReal'
import {
  useNotasTicket,
  useAjustesTicket,
  useSugerenciasTicket,
  useTecnicos,
  useTicket,
} from '../../api/hooks'
import type { CuerpoAsignarTicket, CuerpoCambiarEstado, CuerpoMensaje } from '../../api/tipos'
import { EstadoBadge, PrioridadBadge, SlaBadge } from '../../componentes/dominio/Badge'
import { AIPanel } from '../../componentes/dominio/AIPanel'
import { ChatThread } from '../../componentes/dominio/ChatThread'
import { Timeline } from '../../componentes/dominio/Timeline'
import { Button } from '../../componentes/base/Button'
import { Input, Select, Textarea } from '../../componentes/base/Campo'
import { ConfirmDialog, DialogModal } from '../../componentes/base/Sobreposiciones'
import { Avatar, ErrorState, PageHeader, Panel, SkeletonPanel } from '../../componentes/base/Estructura'
import { fechaHora } from '../../dominio/formato'
import { cn } from '../../lib/cn'
import { ESTADOS, origenDe, TRANSICIONES_TICKET } from '../../dominio/estados'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'
import { ZonaBadge } from '../../componentes/dominio/ZonaBadge'
import { EnlaceOficina } from '../../componentes/dominio/EnlaceOficina'
import { IconoTipoEquipo } from '../../componentes/dominio/IconoTipoEquipo'
import { EditorVinculoTicket, type VinculoTicket } from '../../componentes/dominio/VinculoTicket'
import { HistorialConjunto } from '../../componentes/dominio/HistorialConjunto'

export function TicketDetalle() {
  const { id } = useParams<{ id: string }>()
  const sesion = useSesion()
  const avisos = useAvisos()
  const consultas = useQueryClient()

  const ticket = useTicket(id)
  const ajustes = useAjustesTicket()
  const [edicion, setEdicion] = useState<({ asunto: string; categoria: string; version_esperada?: string } & VinculoTicket) | null>(null)
  const [guardandoFicha, setGuardandoFicha] = useState(false)
  useEffect(() => { setEdicion(null) }, [id])
  const guardarFicha = async () => {
    if (!edicion || guardandoFicha || edicion.asunto.trim().length < 4) return
    setGuardandoFicha(true)
    try {
      const { destino, ...campos } = edicion
      await api.editar(`/tickets/${id}`, { ...campos, activo_id: destino === 'equipo' ? campos.activo_id || null : null, conjunto_id: destino === 'conjunto' ? campos.conjunto_id || null : null })
      setEdicion(null)
      await Promise.all([ticket.refetch(), consultas.invalidateQueries({ queryKey: ['tickets'] }), consultas.invalidateQueries({ queryKey: ['mis-tickets'] }), consultas.invalidateQueries({ queryKey: ['activos-tickets'] }), consultas.invalidateQueries({ queryKey: ['destinos-ticket'] })])
      avisos.exito('Incidencia actualizada')
    } catch (error) { avisos.desdeError(error, 'No pudimos guardar los cambios') }
    finally { setGuardandoFicha(false) }
  }
  const datos = ticket.data
  const tieneChat = Boolean(datos?.tiene_chat)
  useTiempoReal('ticket', id, tieneChat)
  const aceptacion = datos?.aceptacion as Aceptacion | undefined
  const notas = useNotasTicket(id)
  const tecnicos = useTecnicos()
  // El AIPanel existe solo si hay sugerencias y la persona las quiere
  const sugerencias = useSugerenciasTicket(id, sesion.usuario?.recomendaciones_ia === true)

  const [mensaje, setMensaje] = useState('')
  const [nota, setNota] = useState('')
  const [tecnicoId, setTecnicoId] = useState('')
  const [nuevoEstado, setNuevoEstado] = useState('')
  const [notaResolucion, setNotaResolucion] = useState('')
  const [enviandoMensaje, setEnviandoMensaje] = useState(false)
  const [guardandoNota, setGuardandoNota] = useState(false)
  const [asignando, setAsignando] = useState(false)
  const [cambiandoEstado, setCambiandoEstado] = useState(false)
  const [confirmarEstado, setConfirmarEstado] = useState(false)
  const [confirmarCierre, setConfirmarCierre] = useState(false)
  const [confirmarReapertura, setConfirmarReapertura] = useState(false)
  const [solucionCierre, setSolucionCierre] = useState('')

  useEffect(() => {
    if (datos) document.title = `${datos.codigo} · Mesa de Ayuda TI`
  }, [datos])

  /*
    Refrescar todo lo que un cambio de estado deja anticuado.

    Antes solo se recargaba la ficha. Con `staleTime` de 30 s y
    `refetchOnWindowFocus: false` —que es como está configurado el cliente a
    propósito, para que la bandeja no parpadee—, la lista, el resumen y la campana
    se quedaban con lo viejo: **al cerrar un ticket, la bandeja de «Abiertos» lo
    seguía enseñando abierto** y el contador del resumen no bajaba.

    `['tickets']` es prefijo y cubre también `['tickets', 'resumen']` y las listas
    con filtros. La ficha va aparte porque su clave es `['ticket', id]`, en
    singular. Y los conteos por equipo son otra clave, `['activos-tickets']`: la
    ficha del equipo cuenta sus tickets abiertos, y con 60 s de caché también se
    quedaba diciendo que había uno abierto después de cerrarlo.
  */
  const refrescarTrasCambio = async () => {
    await Promise.all([
      ticket.refetch(),
      notas.refetch(),
      consultas.invalidateQueries({ queryKey: ['tickets'] }),
      consultas.invalidateQueries({ queryKey: ['ticket'] }),
      consultas.invalidateQueries({ queryKey: ['activos-tickets'] }),
      consultas.invalidateQueries({ queryKey: ['analitica'] }),
      consultas.invalidateQueries({ queryKey: ['campanas'] }),
      consultas.invalidateQueries({ queryKey: ['notificaciones'] }),
    ])
  }

  const enviarMensaje = async (adjuntos: string[] = []) => {
    if (!id || (!mensaje.trim() && !adjuntos.length) || enviandoMensaje) return false
    setEnviandoMensaje(true)
    try {
      const cuerpo: CuerpoMensaje = { cuerpo: mensaje.trim(), adjuntos }
      await api.crear(`/tickets/${id}/mensajes`, cuerpo)
      setMensaje('')
      await Promise.all([ticket.refetch(), notas.refetch()])
      await consultas.invalidateQueries({ queryKey: ['ticket', id, 'mensajes'] })
      return true
    } catch (fallo) {
      avisos.desdeError(fallo)
      return false
    } finally {
      setEnviandoMensaje(false)
    }
  }

  const enviarNota = async () => {
    if (!id || !nota.trim()) return
    setGuardandoNota(true)
    try {
      await api.crear(`/tickets/${id}/notas`, { cuerpo: nota.trim(), visible_usuario: false })
      setNota('')
      await notas.refetch()
      avisos.exito('Nota interna guardada', 'El usuario no la ve.')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardandoNota(false)
    }
  }

  const asignar = async () => {
    if (!id || !tecnicoId) return
    setAsignando(true)
    try {
      const cuerpo: CuerpoAsignarTicket = { tecnico_id: tecnicoId, confirmar_fuera_de_horario: true }
      await api.crear(`/tickets/${id}/asignar`, cuerpo)
      await refrescarTrasCambio()
      const tecnico = tecnicos.data?.items.find((item) => item.id === tecnicoId)
      avisos.exito(tecnico ? `Ticket asignado a ${tecnico.nombre}` : 'Ticket asignado')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setAsignando(false)
    }
  }

  const cambiarEstado = async () => {
    if (!id || !nuevoEstado) return
    setCambiandoEstado(true)
    try {
      const cuerpo: CuerpoCambiarEstado = {
        estado: nuevoEstado,
        ...(nuevoEstado === 'cerrado' && notaResolucion.trim() ? { nota_resolucion: notaResolucion.trim() } : {}),
      }
      await api.crear(`/tickets/${id}/estado`, cuerpo)
      setConfirmarEstado(false)
      setNuevoEstado('')
      setNotaResolucion('')
      await refrescarTrasCambio()
      avisos.exito('Estado actualizado')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setCambiandoEstado(false)
    }
  }

  const cerrarTicket = async () => {
    if (!id || (['nuevo', 'en_progreso', 'en_espera'].includes(datos?.estado ?? '') && !solucionCierre.trim())) return
    setCambiandoEstado(true)
    try {
      await api.crear(`/tickets/${id}/estado`, {
        estado: 'cerrado',
        ...(solucionCierre.trim() ? { nota_resolucion: solucionCierre.trim() } : {}),
      })
      setConfirmarCierre(false)
      setSolucionCierre('')
      await refrescarTrasCambio()
      avisos.exito('Ticket cerrado')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setCambiandoEstado(false)
    }
  }

  const reabrirTicket = async () => {
    if (!id) return
    setCambiandoEstado(true)
    try {
      await api.crear(`/tickets/${id}/estado`, { estado: 'en_progreso' })
      setConfirmarReapertura(false)
      await refrescarTrasCambio()
      avisos.exito('Ticket reabierto', 'Volvió a En progreso.')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setCambiandoEstado(false)
    }
  }

  if (ticket.isLoading) return <SkeletonPanel filas={6} />

  if (ticket.isError || !datos) {
    return (
      <ErrorState
        mensaje="No pudimos cargar el ticket."
        detalle={ticket.error instanceof Error ? ticket.error.message : undefined}
        alReintentar={() => void ticket.refetch()}
      />
    )
  }

  return (
    <>
      <PageHeader
        titulo={datos.codigo}
        descripcion={`Detalle de la incidencia · registrado el ${fechaHora(datos.creado_en)}`}
        migas={[
          { texto: 'Panel', enlace: '/panel' },
          { texto: 'Tickets', enlace: '/panel/tickets' },
          { texto: datos.codigo },
        ]}
        acciones={
          <Button asChild variante="secundario">
            <Link to="/panel/tickets" className="flex items-center gap-2">
              <ArrowLeft size={16} aria-hidden="true" />
              Volver a la bandeja
            </Link>
          </Button>
        }
      />

      {/*
        Las insignias de cabecera, en fila y con su etiqueta.

        Antes iban sueltas, pegadas unas a otras, cada una con su altura: dos
        cápsulas, un icono con su línea de tiempo debajo y un texto suelto al
        final. Se leía como una frase rota. Ahora cada bloque dice **qué es**
        —estado, prioridad, tiempo acordado, origen— y lleva su valor debajo,
        con separadores, para que se escanee de izquierda a derecha sin adivinar
        a qué corresponde cada trozo.
      */}
      <div className="grid grid-cols-2 gap-4 rounded-[var(--radius-panel)] border border-border bg-surface p-4 shadow-sm lg:grid-cols-4">
        <DatoCabecera etiqueta="Estado"><EstadoBadge estado={datos.estado} /></DatoCabecera>
        <DatoCabecera etiqueta="Prioridad"><PrioridadBadge prioridad={datos.prioridad} /></DatoCabecera>
        {datos.sla ? (
          <DatoCabecera
            etiqueta={datos.sla.modo === 'responder' ? 'Plazo de primera atención' : 'Plazo de resolución'}
          >
            <SlaBadge
              estado={datos.sla.estado}
              minutos={datos.sla.minutos_restantes}
              minutosTranscurridos={datos.sla.minutos_transcurridos}
              activo={datos.sla.activo}
              modo={datos.sla.modo}
            />
          </DatoCabecera>
        ) : null}
        <DatoCabecera etiqueta="Origen">
          <span className="text-sm font-medium text-foreground">{datos.reporte_para === 'oficina' ? 'Reportado para la oficina' : origenDe(datos.origen).texto}</span>
        </DatoCabecera>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(300px,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          {/*
            Este panel lleva un borde de color en el canto izquierdo para que se
            reconozca de un vistazo cuál es: es el texto del caso, lo primero que
            hay que leer al abrir un ticket, y hasta ahora era un recuadro más
            entre los de al lado.
          */}
          <Panel aria-label="Incidencia reportada" className="overflow-hidden border-t-[3px] border-t-warning shadow-sm" cuerpoClassName="p-0">
            <div className="flex items-start gap-3 border-b border-border bg-warning-soft/40 p-4 sm:p-5">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-warning/30 bg-warning-soft text-warning-strong"><CircleAlert size={22} aria-hidden="true" /></span>
              <div className="min-w-0 flex-1">
                <p className="text-2xs font-bold tracking-wide text-muted-foreground uppercase">Incidencia reportada</p>
                <h2 className="mt-1 break-words text-xl font-bold leading-snug [overflow-wrap:anywhere] sm:text-2xl">{datos.asunto}</h2>
              </div>
              {!edicion ? <Button tamano="sm" variante="fantasma" icono={<Pencil size={15} />} onClick={() => setEdicion({ version_esperada: datos.actualizado_en, asunto: datos.asunto, categoria: datos.categoria ?? '', alcance_incidencia: datos.alcance_incidencia ?? (datos.activo_id ? 'equipo' : datos.conjunto_id ? 'conjunto' : 'pendiente'), sistema_afectado: datos.sistema_afectado ?? '', activo_id: datos.activo_id ?? '', conjunto_id: datos.conjunto_id ?? '', destino: datos.activo_id ? 'equipo' : datos.conjunto_id ? 'conjunto' : 'ninguna' })}>Editar</Button> : null}
            </div>
            <div className="p-4 sm:p-5">
            {edicion ? <div className="mb-5 flex flex-col gap-3 border-b border-border pb-4">
              <Input etiqueta="Título de la incidencia" value={edicion.asunto} minLength={4} maxLength={200} onChange={evento => setEdicion({ ...edicion, asunto: evento.target.value })} />
              <Select etiqueta="Categoría" value={edicion.categoria} placeholder="Sin categoría" opciones={[...new Set([...(ajustes.data?.categorias ?? []), ...(datos.categoria ? [datos.categoria] : [])])].map(categoria => ({ valor: categoria, etiqueta: categoria }))} onChange={evento => setEdicion({ ...edicion, categoria: evento.target.value })} />
              <EditorVinculoTicket categoria={edicion.categoria} ticket={datos} valor={edicion} alCambiar={valor => setEdicion({ ...edicion, ...valor })} />
              <div className="flex justify-end gap-2"><Button tamano="sm" disabled={guardandoFicha} onClick={() => setEdicion(null)}>Cancelar</Button><Button tamano="sm" variante="primario" cargando={guardandoFicha} disabled={edicion.asunto.trim().length < 4 || (!edicion.activo_id && !edicion.conjunto_id)} onClick={() => void guardarFicha()}>Guardar cambios</Button></div>
            </div> : null}
            <section aria-label="Descripción del problema" className="min-w-0 rounded-xl bg-surface-2/50 p-4 sm:p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h3 className="flex items-center gap-2.5 text-sm font-semibold"><span className="rounded-lg bg-primary-soft p-2 text-info-strong"><MessageSquare size={17} aria-hidden="true" /></span>Descripción del problema</h3>
                {!edicion ? <>{datos.reporte_para === 'oficina' ? <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-warning-soft px-3 py-1 text-xs font-medium text-warning-strong"><Building2 size={14} className="shrink-0" aria-hidden="true" />Reporte de oficina</span> : datos.reporte_para === 'companero' || (datos.reportante_id && datos.afectado_id && datos.reportante_id !== datos.afectado_id) ? <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-info-strong"><Users size={14} className="shrink-0" aria-hidden="true" />Reporte para un compañero</span> : datos.reporte_para === 'propio' ? <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground"><UserCheck size={14} className="shrink-0" aria-hidden="true" />Reporte personal</span> : null}</> : null}
              </div>
              <div className="border-l-2 border-accion/40 pl-4">
                {datos.descripcion ? <p className="max-w-[72ch] whitespace-pre-wrap text-sm leading-7 [overflow-wrap:anywhere] sm:text-base">{datos.descripcion}</p> : <p className="text-sm text-muted-foreground">No se añadió una descripción.</p>}
              </div>
            </section>

            {/*
              Los datos van todos con la misma pinta. Antes tres rótulos salían en
              mayúsculas y otros dos no, y dos de ellos se montaban a mano aparte
              de los demás: se notaba que eran campos distintos hechos en
              momentos distintos.
            */}
            <div className="mt-5 grid min-w-0 gap-3 sm:grid-cols-2">
              <div className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-surface-2/50 p-3">
                <FolderOpen size={22} className="shrink-0 text-primary" aria-hidden="true" />
                <div className="min-w-0"><p className="text-2xs text-muted-foreground">Categoría</p><p className="truncate text-sm font-semibold" title={datos.categoria ?? undefined}>{datos.categoria || 'Sin categoría registrada'}</p></div>
              </div>
              <div className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-surface-2/50 p-3">
                <span className="shrink-0"><IconoTipoEquipo tipo={datos.activo_tipo} tamano={24} /></span>
                <div className="min-w-0"><p className="text-2xs text-muted-foreground">{datos.conjunto_id && !datos.activo_id ? 'Computadora afectada' : 'Equipo afectado'}</p>
                  {datos.activo_id ? <Link to={`/panel/equipos/${datos.activo_id}`} className="block truncate text-sm font-semibold text-primary-strong hover:underline" title={datos.activo_nombre ?? undefined}>{datos.activo_nombre || datos.activo_tipo || 'Ver ficha del equipo'}</Link> : <p className="truncate text-sm font-semibold" title={datos.conjunto_nombre ?? undefined}>{datos.conjunto_id ? datos.conjunto_nombre || 'Conjunto completo' : datos.activo_nombre ? `${datos.activo_nombre} · por identificar` : ['programa', 'servicio'].includes(datos.alcance_incidencia ?? '') ? 'Sin equipo: programa o servicio general' : 'Equipo por identificar'}</p>}
                  {datos.sistema_afectado ? <p className="truncate text-xs text-muted-foreground" title={datos.sistema_afectado}>{datos.sistema_afectado}</p> : null}
                </div>
              </div>
            </div>
            <div className="mt-2"><HistorialConjunto id={datos.conjunto_id} nombre={datos.conjunto_nombre} /></div>
            <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 border-t border-border pt-4 text-sm">
              <Campo
                etiqueta="Reportó"
                valor={datos.reportante_nombre}
                enlace={sesion.puede('usuarios.ver') && datos.reportante_id ? `/panel/usuarios/${datos.reportante_id}` : undefined}
              />
              {datos.reporte_para === 'oficina' ? <Campo etiqueta="Afecta a" valor="La oficina · equipo compartido" /> : datos.reportante_id && datos.reportante_id === datos.afectado_id ? <Campo etiqueta="Solicitud" valor="Para sí mismo" /> : <Campo
                etiqueta="Afecta a"
                valor={datos.afectado_nombre}
                enlace={sesion.puede('usuarios.ver') && datos.afectado_id ? `/panel/usuarios/${datos.afectado_id}` : undefined}
              />}
              <Campo etiqueta="Zona">
                <ZonaBadge id={datos.zona_id} nombre={datos.zona_nombre} />
              </Campo>
              <Campo etiqueta="Oficina">
                <EnlaceOficina id={datos.oficina_id} nombre={datos.oficina_nombre} zonaId={datos.zona_id} />
              </Campo>
            </dl>
            </div>
          </Panel>

          {tieneChat ? (
            <ChatThread
              ticketId={id as string}
              valor={mensaje}
              alCambiar={setMensaje}
              cargando={enviandoMensaje}
              onEnviar={enviarMensaje}
              />
          ) : (
            /*
              Esto no es un aviso: es una comprobación. Salía como un bloque ancho
              con el color del tema, y en la mitad de la columna era lo más
              llamativo de la página cuando es lo menos importante. Va como una
              línea discreta, con el icono al lado y sin ocupar media pantalla.
            */
            <p className="flex items-center gap-2 rounded-[var(--radius-panel)] border border-border/70 bg-surface-2/50 px-3 py-2 text-sm text-muted-foreground">
              <MessageSquare size={15} className="shrink-0" aria-hidden="true" />
              <span>
                Sin conversación: lo registró el equipo TI. El seguimiento queda en el
                estado y en las notas internas.
              </span>
            </p>
          )}

          {/*
            Cuándo se cogió el caso. Es el dato que responde a «¿cuánto
            tardarón en aceptarlo?» y no estaba en ninguna parte: el plazo de
            responder se calculaba y se guardaba, pero la fecha en que alguien se
            hizo cargo no se guardaba al asignar, solo cuando alguien movía el
            estado a mano. Ahora se guarda al aceptar, y para los casos anteriores
            se reconstruye del historial —por eso el aviso de «según el
            historial», que no es un adorno: avisa de que la cifra sale del
            registro y no de un campo nativo.
          */}
          {aceptacion?.consta ? (
            <Panel
              titulo="Cuándo se cogió"
              descripcion="Tiempo que tardó el equipo TI en hacerse cargo de la incidencia"
            >
              <dl className="grid gap-3 sm:grid-cols-3">
                <Dato valor={aceptacionTexto(aceptacion)} etiqueta="Se aceptó" />
                {/*
                  La etiqueta decía «Dentro del plazo de 4 h» **siempre**, y el
                  valor de debajo ponía «50 min tarde». Las dos cosas a la vez, en
                  la misma casilla: la tarjeta afirmaba que se cumplió el plazo
                  mientras el número decía que no.

                  Ahora la etiqueta dice qué se midió —el plazo, que es fijo— y el
                  veredicto lo lleva el valor, que es lo que cambia. El color ya
                  distinguía los dos casos.
                */}
                <Dato
                  valor={aceptacionPlazoTexto(aceptacion)}
                  etiqueta={`Plazo de respuesta: ${aceptacion.plazo_minutos ? Math.round(aceptacion.plazo_minutos / 60) : '—'} h`}
                  tono={aceptacion.cumplio === false ? 'aviso' : 'exito'}
                />
                <Dato valor={fechaHora(aceptacion.en)} etiqueta="El día" />
              </dl>
              {aceptacion.reconstruido ? (
                <p className="mt-3 text-2xs text-muted-foreground">
                  Sacado del historial del caso: es la fecha del primer movimiento que lo cogió.
                </p>
              ) : null}
            </Panel>
          ) : null}

          {sesion.puede('tickets.notas_internas') ? (
            <Panel
              titulo="Notas internas"
              descripcion="Solo las ve el equipo TI. El usuario nunca las recibe."
            >
              <ul className="mb-3 flex flex-col gap-2">
                {(notas.data?.items ?? []).map((item) => (
                  <li key={item.id} className="rounded-[var(--radius-panel)] border border-border bg-muted/40 p-3">
                    <p className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-semibold">{item.autor_nombre}</span>
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Lock size={12} aria-hidden="true" />
                        solo equipo TI
                      </span>
                      <span className="text-muted-foreground">{fechaHora(item.creado_en)}</span>
                    </p>
                    <p className="mt-1 whitespace-pre-line">{item.cuerpo}</p>
                  </li>
                ))}
                {(notas.data?.items.length ?? 0) === 0 ? (
                  <li className="py-3 text-center text-sm text-muted-foreground">
                    Todavía no hay notas internas en este ticket.
                  </li>
                ) : null}
              </ul>
              <Textarea
                etiqueta="Nueva nota interna"
                filas={3}
                value={nota}
                onChange={(evento) => setNota(evento.target.value)}
                placeholder="Ejemplo: llamado al proveedor, llega el repuesto el miércoles."
              />
              <div className="mt-2 flex justify-end">
                <Button
                  variante="primario"
                  cargando={guardandoNota}
                  disabled={!nota.trim()}
                  onClick={() => void enviarNota()}
                  icono={<Save size={16} aria-hidden="true" />}
                >
                  Guardar nota
                </Button>
              </div>
            </Panel>
          ) : null}

          {datos.nota_resolucion ? (
            <Panel titulo="Resultado de la atención" className="portal-resultado border-success-borde shadow-md">
              <p className="whitespace-pre-line">{datos.nota_resolucion}</p>
            </Panel>
          ) : null}

          <Timeline ticketId={id as string} />
        </div>

        {/* ══ Columna lateral: acciones e IA ══ */}
        <div className="flex min-w-0 flex-col gap-5">
          <Panel titulo="Gestionar ticket" descripcion="Responsable, avance y cierre del caso." className="shadow-sm">
            <div className="flex flex-col gap-4">
              {datos.tecnico_nombre ? (
                <dl className="text-sm">
                  <div>
                    <dt className="text-2xs text-muted-foreground uppercase">Técnico asignado</dt>
                    <dd className="mt-1">
                      {datos.tecnico_id && sesion.puede('horarios.ver') ? (
                        <Link to={`/panel/equipo-ti/${datos.tecnico_id}`} className="inline-flex items-center gap-2 font-medium text-primary-strong hover:underline">
                          <Avatar nombre={datos.tecnico_nombre} tamano="sm" />
                          {datos.tecnico_nombre}
                        </Link>
                      ) : (
                        <span className="inline-flex items-center gap-2 font-medium">
                          <Avatar nombre={datos.tecnico_nombre} tamano="sm" />
                          {datos.tecnico_nombre}
                        </span>
                      )}
                    </dd>
                  </div>
                </dl>
              ) : null}
              <Select
                etiqueta="Asignar a"
                value={tecnicoId}
                onChange={(evento) => setTecnicoId(evento.target.value)}
                placeholder={datos.tecnico_nombre ?? 'Elegir técnico'}
                opciones={(tecnicos.data?.items ?? []).map((tecnico) => ({
                  valor: tecnico.id,
                  etiqueta: tecnico.nombre,
                }))}
              />
              <Button
                variante="primario"
                anchoCompleto
                cargando={asignando}
                disabled={!tecnicoId}
                onClick={() => void asignar()}
                icono={<UserCheck size={16} aria-hidden="true" />}
              >
                Asignar
              </Button>

              {/*
                Aquí solo el **movimiento del caso**: quién lo atiende y en qué
                punto del trabajo está.

                «Cerrado» **no** aparece en esta lista, aunque el backend lo permita,
                porque cerrar no es un paso más del flujo: es el final, y exige
                escribir qué se hizo. Por eso tiene su propio botón y su propio
                diálogo, más abajo. Tener las dos cosas en el mismo sitio hacía que
                «Cerrado» pareciera un estado más entre «Asignado» y «En progreso»,
                que es justo la confusión que rompe el significado de cada palabra.
              */}
              <Select
                etiqueta="Cambiar estado"
                value={nuevoEstado}
                onChange={(evento) => setNuevoEstado(evento.target.value)}
                placeholder="Elegir paso siguiente"
                ayuda={
                  datos.estado === 'cerrado'
                    ? 'Un ticket cerrado solo se puede reabrir, con el botón de abajo.'
                    : 'Un ticket acaba cuando lo cierras, no antes.'
                }
                opciones={(TRANSICIONES_TICKET[datos.estado] ?? [])
                  .filter((clave) => clave !== 'cerrado')
                  .filter((clave) => !(datos.estado === 'cerrado' && clave === 'en_progreso'))
                  .map((clave) => ESTADOS[clave])
                  .map((item) => ({ valor: item.clave, etiqueta: item.texto }))}
              />
              <Button
                variante="secundario"
                anchoCompleto
                disabled={!nuevoEstado}
                onClick={() => setConfirmarEstado(true)}
              >
                Aplicar
              </Button>

              {/*
                El cierre es un acto aparte, con su consecuencia: la nota de
                solución. Va separado del flujo a propósito, y con un rótulo que
                dice qué pasa al cerrarlo.
              */}
              {datos.estado !== 'cerrado' ? (
                datos.puede_cerrar ? (
                  <div className="mt-2 flex flex-col gap-1.5 rounded-[var(--radius-control)] border border-border bg-muted/40 p-3">
                    <p className="text-xs font-semibold text-foreground">Terminar el caso</p>
                    <p className="text-2xs text-muted-foreground">
                      Al cerrar hay que escribir qué se hizo. La persona que lo reportó lo lee, y el caso sale de
                      la cola.
                    </p>
                    <Button variante="primario" anchoCompleto onClick={() => setConfirmarCierre(true)}>
                      Cerrar ticket
                    </Button>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">
                    No puedes cerrar este ticket: no eres su técnico asignado. Se necesita el permiso «Cerrar y
                    reabrir tickets», que concede el administrador.
                  </p>
                )
              ) : null}
              {datos.estado === 'cerrado' && datos.puede_reabrir !== false ? (
                <Button variante="secundario" anchoCompleto onClick={() => setConfirmarReapertura(true)}>
                  Reabrir ticket
                </Button>
              ) : null}
            </div>
          </Panel>

          {/* El AIPanel no se renderiza si no hay sugerencias habilitadas. Al decidir se
              refrescan las dos consultas: el ticket, para ver el cambio, y las
              sugerencias, para que la que se acaba de resolver deje de ofrecerse.
              Con una sola de las dos, el botón se quedaba ahí. */}
          {sesion.usuario?.recomendaciones_ia === true ? (
            <AIPanel
              ticketId={id as string}
              consulta={sugerencias}
              alAplicar={() => {
                void ticket.refetch()
                void sugerencias.refetch()
              }}
            />
          ) : (
            <Panel titulo="Ayudas automáticas">
              <p className="flex items-start gap-2 text-sm text-muted-foreground">
                <Sparkles size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>
                  Tienes las sugerencias desactivadas en tu perfil. El ticket se atiende sin ellas, pero no se te
                  propondrá nada.
                </span>
              </p>
              <Link to="/perfil" className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
                Activarlas en mi perfil
              </Link>
            </Panel>
          )}
        </div>
      </div>

      <ConfirmDialog
        abierto={confirmarEstado}
        alCerrar={() => setConfirmarEstado(false)}
        alConfirmar={() => void cambiarEstado()}
        titulo="Cambiar el estado del ticket"
        mensaje={
          <>
            El ticket pasará a <strong>{ESTADOS[nuevoEstado]?.texto ?? nuevoEstado}</strong>. Si lo cierras, la
            solución que escribas la verá la persona que lo reportó y el caso sale de la cola.
          </>
        }
        textoConfirmar="Cambiar estado"
        cargando={cambiandoEstado}
      />
      <DialogModal
        abierto={confirmarCierre}
        alCerrar={() => setConfirmarCierre(false)}
        titulo="Cerrar ticket"
        descripcion="El ticket queda cerrado y sale de la cola. Se puede reabrir si el problema vuelve."
        pie={
          <>
            <Button onClick={() => setConfirmarCierre(false)}>Cancelar</Button>
            <Button
              variante="destructivo"
              cargando={cambiandoEstado}
              disabled={['nuevo', 'en_progreso', 'en_espera'].includes(datos.estado) && !solucionCierre.trim()}
              onClick={() => void cerrarTicket()}
            >
              Cerrar ticket
            </Button>
          </>
        }
      >
        {['nuevo', 'en_progreso', 'en_espera'].includes(datos.estado) ? (
          <Textarea
            etiqueta="Resultado de la atención"
            filas={4}
            value={solucionCierre}
            onChange={(evento) => setSolucionCierre(evento.target.value)}
            ayuda="Explica lo que ocurrió y lo que se hizo. La persona afectada podrá leerlo."
          />
        ) : (
          <p className="text-sm text-muted-foreground">Se conservará la solución registrada.</p>
        )}
      </DialogModal>
      <ConfirmDialog
        abierto={confirmarReapertura}
        alCerrar={() => setConfirmarReapertura(false)}
        alConfirmar={() => void reabrirTicket()}
        titulo="Reabrir ticket"
        mensaje={<>Vas a reabrir el ticket <strong>{datos.codigo}</strong>. Volverá a <strong>En progreso</strong>.</>}
        textoConfirmar="Reabrir ticket"
        cargando={cambiandoEstado}
      />
    </>
  )
}

/**
 * Bloque de la cabecera: la etiqueta pequeña y el valor debajo.
 *
 * Las cuatro cosas que se muestran —estado, prioridad, tiempo acordado y
 * origen— son de la misma categoría y se leen de izquierda a derecha. Con la
 * etiqueta encima, no hay que adivinar a qué corresponde cada cápsula.
 */
function DatoCabecera({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col items-start gap-1 border-l-2 border-border pl-3 first:border-l-0 first:pl-0">
      <span className="text-2xs font-semibold tracking-wide text-muted-foreground uppercase">{etiqueta}</span>
      {children}
    </div>
  )
}

/** Lo que la API devuelve sobre cuándo se tomó el caso. */
type Aceptacion = {
  consta?: boolean
  en?: string | null
  minutos?: number | null
  plazo_minutos?: number | null
  cumplio?: boolean | null
  /** `true` cuando la fecha sale del historial y no de un campo del documento. */
  reconstruido?: boolean
}

/** Un dato suelto del bloque «Cuándo se cogió», con su color si va bien o mal. */
function Dato({ etiqueta, valor, tono }: { etiqueta: string; valor: string; tono?: 'exito' | 'aviso' }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs font-semibold tracking-wide text-muted-foreground uppercase">{etiqueta}</dt>
      <dd
        className={cn(
          'mt-1 font-semibold',
          tono === 'exito' && 'text-success-strong',
          tono === 'aviso' && 'text-warning-strong',
          !tono && 'text-foreground',
        )}
      >
        {valor}
      </dd>
    </div>
  )
}

/** «Se aceptó en 2 h 17 min», en la misma forma que el resto de tiempos del SLA. */
function aceptacionTexto(aceptacion: { minutos?: number | null }): string {
  const minutos = aceptacion.minutos ?? 0
  if (minutos < 60) return `En ${minutos} min`
  const horas = Math.floor(minutos / 60)
  const dias = Math.floor(horas / 24)
  if (dias > 0) return `En ${dias} ${dias === 1 ? 'día' : 'días'}`
  const resto = minutos % 60
  return resto ? `En ${horas} h ${resto} min` : `En ${horas} ${horas === 1 ? 'hora' : 'horas'}`
}

function aceptacionPlazoTexto(aceptacion: { minutos?: number | null; plazo_minutos?: number | null }): string {
  const plazo = aceptacion.plazo_minutos
  if (!plazo) return 'Sin plazo'
  if ((aceptacion.minutos ?? 0) <= plazo) return 'Cumplido'
  const tarde = (aceptacion.minutos ?? 0) - plazo
  const horas = Math.floor(tarde / 60)
  return horas > 0 ? `${horas} h tarde` : `${tarde} min tarde`
}

/**
 * Un dato de la ficha: la etiqueta pequeña encima y el valor debajo.
 *
 * Acepta un contenido propio además de un texto, porque no todos los valores son
 * texto: la zona es una pastilla con su color y la oficina lleva su raya. Antes
 * esos dos se montaban aparte y el resultado era una rejilla con tres rótulos en
 * mayúsculas y tres sin ellas.
 */
function Campo({
  etiqueta,
  valor,
  enlace,
  children,
}: {
  etiqueta: string
  valor?: string
  enlace?: string
  children?: ReactNode
}) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs font-semibold tracking-wide text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="mt-1 min-w-0 truncate font-medium" title={valor}>
        {children ??
          (enlace ? (
            <Link to={enlace} className="text-primary-strong hover:underline">
              {valor}
            </Link>
          ) : (
            valor
          ))}
      </dd>
    </div>
  )
}
