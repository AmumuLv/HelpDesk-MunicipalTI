/**
 * Registrar ticket manual: el técnico atiende un caso que no viene del portal.
 *
 * A diferencia del reporte del usuario, aquí el técnico decide la prioridad y
 * puede asignarlo en el mismo momento, porque ya conoce el caso.
 *
 * Se busca a la persona con el buscador real del backend (`/usuarios/buscar`):
 * escribir un nombre a mano crearía una persona que no existe en el padrón.
 */

import { ArrowLeft, Check, CircleAlert, ClipboardCheck, Search, TicketPlus, UserCheck } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useAjustesTicket, useBuscarUsuarios, useTecnicos } from '../../api/hooks'
import type { CuerpoTicketManual, TicketCreado } from '../../api/tipos'
import { Button } from '../../componentes/base/Button'
import { SelectorDestinoIncidencia, categoriaDePc, type OpcionesDestino } from '../../componentes/dominio/DestinoIncidencia'
import { claveSolicitud } from '../../api/solicitudes'
import { Input, Select, Textarea } from '../../componentes/base/Campo'
import { PageHeader, Panel, PantallaFormulario } from '../../componentes/base/Estructura'
import { useAvisos } from '../../estado/Avisos'
import { PrioridadBadge } from '../../componentes/dominio/Badge'


export function RegistrarTicketManual() {
  const avisos = useAvisos()
  const navegar = useNavigate()
  const consultas = useQueryClient()

  const catalogos = useAjustesTicket()
  const tecnicos = useTecnicos()

  const [textoPersona, setTextoPersona] = useState('')
  const [personaId, setPersonaId] = useState<string | null>(null)
  const [personaNombre, setPersonaNombre] = useState('')
  const [asunto, setAsunto] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [categoria, setCategoria] = useState('')
  const [prioridad, setPrioridad] = useState('media')
  const [equipoId, setEquipoId] = useState<string | null>(null)
  const [conjuntoId, setConjuntoId] = useState('')
  const [programaNombre, setProgramaNombre] = useState('')
  const [tecnicoId, setTecnicoId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bloqueoEnvio = useRef(false)
  const solicitud = useRef({ firma: '', clave: '' })
  const rutaDestinos = personaId ? `/usuarios/${personaId}/destinos-ticket` : undefined
  const destinos = useQuery({ queryKey: ['destinos-ticket', rutaDestinos], queryFn: () => api.obtener<OpcionesDestino>(rutaDestinos!), enabled: Boolean(rutaDestinos) })
  const equipoElegido = destinos.data?.equipos.find(e => e.id === equipoId)
  const computadoraElegida = destinos.data?.conjuntos.find(c => c.id === conjuntoId)


  useEffect(() => {
    document.title = 'Registrar ticket · Mesa de Ayuda TI'
  }, [])

  /*
    Este campo es un `<input>` escrito a mano, no el `SearchInput` común, así que
    también necesita la protección del navegador: se vacía al montar y al volver de
    la caché, con el setter nativo porque si se asigna `elemento.value` se pasa por el
    rastreador de React y este cree que nada ha cambiado. Medido: el navegador guarda
    los valores de los campos y los reaplica al recargar.
  */
  const campoPersona = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const vaciar = () => {
      const elemento = campoPersona.current
      if (!elemento || elemento.value === '') return
      const nativo = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
      if (nativo) nativo.call(elemento, '')
      else elemento.value = ''
    }
    vaciar()
    const alVolver = () => vaciar()
    window.addEventListener('pageshow', alVolver)
    return () => window.removeEventListener('pageshow', alVolver)
  }, [])

  /*
    El buscador solo pregunta cuando hay algo escrito: no se carga el padrón entero.

    Y **no pregunta con una persona ya elegida**. Al elegir a alguien se escribía su
    nombre en el campo —que es lo normal en un selector— y eso disparaba una búsqueda
    nueva con su nombre dentro: `/usuarios/buscar?texto=DEYSI LEYVA MINAYA`, con la
    lista de sugerencias quedando abierta mostrando solo a esa misma persona. Si a
    quien se busca se le busca por correo y no tiene cuenta, el campo se quedaba con el
    correo y la lista filtrada por él: «al elegir a alguien, el buscador busca solo».

    La lista se muestra solo si la consulta está **encendida**. Sin esta condición, al
    vaciar el campo la consulta se desactiva pero React Query conserva el último
    resultado, y la última persona encontrada se quedaba colgando bajo un campo vacío.
  */
  const hayTexto = textoPersona.trim().length > 1
  const consulta = useBuscarUsuarios(textoPersona.trim(), !personaId && hayTexto)
  const encontrados = !personaId && hayTexto ? (consulta.data?.items ?? []) : []

  const enviar = async () => {
    if (bloqueoEnvio.current || !personaId || asunto.trim().length < 4 || !(equipoId || conjuntoId)) return
    bloqueoEnvio.current = true
    setError(null)
    setEnviando(true)
    try {
      const cuerpo: CuerpoTicketManual = {
        // El backend exige el bloque `persona`; `detectado_por_tec` lo marca como
        // registrado por el equipo TI, y por eso no hay chat con el usuario.
        persona: {
          afectado_id: personaId,
          detectado_por_tec: true,
        },
        asunto: asunto.trim(),
        prioridad,
        origen: 'tecnico',
        adjuntos: [],
        ...(descripcion.trim() ? { descripcion: descripcion.trim() } : {}),
        ...(categoria ? { categoria } : {}),
        ...(tecnicoId ? { tecnico_id: tecnicoId } : {}),
        // Solo se guardan referencias al patrimonio real de la persona.
        ...(equipoId ? { activo_id: equipoId } : {}),
        ...(conjuntoId ? { conjunto_id: conjuntoId } : {}),
        ...(programaNombre ? { sistema_afectado: programaNombre } : {}),
      }
      const creado = await api.crear<TicketCreado>('/tickets/manual', cuerpo, { headers: { 'Idempotency-Key': claveSolicitud(solicitud.current, cuerpo) } })
      await consultas.invalidateQueries({ queryKey: ['tickets'] })
      avisos.exito('Ticket creado', `Código ${creado.ticket.codigo}`)
      navegar(`/panel/tickets/${creado.ticket.id}`)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No pudimos registrar el ticket.')
    } finally {
      bloqueoEnvio.current = false
      setEnviando(false)
    }
  }

  const computadoraIndividual = Boolean(equipoElegido && !equipoElegido.conjunto_id && /^(cpu|laptop|port[aá]til|computadora|pc)$/i.test(equipoElegido.tipo || ''))
  const puedeEnviar = Boolean(personaId && asunto.trim().length >= 4 && (categoriaDePc(categoria) ? (conjuntoId && !equipoId) || computadoraIndividual : categoria.toLowerCase().includes('formate') ? equipoId : equipoId || conjuntoId))

  return (
    <PantallaFormulario>
      <PageHeader
        titulo="Registrar ticket"
        descripcion="Registra la incidencia, identifica a la persona y prepara su atención."
        acciones={
          <Button variante="secundario" icono={<ArrowLeft size={16} aria-hidden="true" />} onClick={() => navegar('/panel/tickets')}>
            Volver a la bandeja
          </Button>
        }
      />

      <div className="grid min-w-0 grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(300px,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Panel titulo={<TituloPaso numero="1" titulo="Persona afectada" />} descripcion="Busca y selecciona a la persona que necesita ayuda." className="shadow-sm">
            <div className="flex flex-col gap-3">
              <label htmlFor="buscar-persona" className="text-sm font-semibold">
                Persona afectada
              </label>
              <div className="relative">
                <Search
                  size={16}
                  className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />
                <input
                  id="buscar-persona"
                  ref={campoPersona}
                  value={textoPersona}
                  onChange={(evento) => {
                    setTextoPersona(evento.target.value)
                    // Empezar a escribir de nuevo deshace la elección: si no, el texto
                    // de la persona elegida se quedaba y el filtro ya no era el que
                    // parecía.
                    setPersonaId(null)
                    setPersonaNombre('')
                    setEquipoId(null)
                    setConjuntoId(''); setProgramaNombre('')
                  }}
                  // Sin «correo» ni «email»: esa palabra es la que hace que el
                  // navegador ofrezca rellenarlo solo. Es el mismo motivo por el que
                  // `SearchInput` ya no lo dice.
                  placeholder="Escribe para buscar…"
                  className="h-[var(--spacing-control)] w-full rounded-[var(--radius-control)] border border-input bg-surface pr-3 pl-9"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={encontrados.length > 0}
                  aria-controls="resultados-persona"
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  name="persona-filtro"
                  data-1p-ignore="true"
                  data-lpignore="true"
                  data-form-type="other"
                  // Si el campo llega con algo puesto, la siguiente tecla lo sustituye.
                  onClick={(evento) => {
                    if (evento.currentTarget.value) evento.currentTarget.select()
                  }}
                />
              </div>

              {encontrados.length > 0 ? (
                <ul
                  id="resultados-persona"
                  className="sin-barra max-h-56 overflow-y-auto rounded-[var(--radius-control)] border border-border"
                >
                  {encontrados.map((persona) => (
                    <li key={persona.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setPersonaId(persona.id)
                          setPersonaNombre(persona.nombre)
                          setTextoPersona(persona.nombre)
                          setEquipoId(null)
                          setConjuntoId(''); setProgramaNombre('')
                        }}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                      >
                        <span className="min-w-0 flex-1 truncate font-medium">{persona.nombre}</span>
                        {persona.oficina_nombre ? (
                          <span className="max-w-[45%] truncate text-2xs text-muted-foreground" title={persona.oficina_nombre}>{persona.oficina_nombre}</span>
                        ) : null}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}

              {personaId ? (
                <p className="flex min-w-0 items-center gap-2 rounded-xl border border-success/25 bg-success-soft p-3 text-sm font-semibold text-success-strong">
                  <UserCheck size={18} className="shrink-0" aria-hidden="true" />
                  <span className="truncate" title={personaNombre}>{personaNombre}</span>
                </p>
              ) : consulta.isError && hayTexto ? (
                <p role="alert" className="text-sm text-destructive-strong">No pudimos buscar personas. <button type="button" onClick={() => void consulta.refetch()} className="font-semibold underline">Reintentar</button></p>
              ) : consulta.isFetching && hayTexto ? (
                <p role="status" className="text-sm text-muted-foreground">Buscando personas…</p>
              ) : textoPersona.trim().length > 1 && !consulta.isLoading && encontrados.length === 0 ? (
                <p className="break-words text-sm text-muted-foreground">
                  Nadie coincide con «{textoPersona.trim()}». Revisa la ortografía o pídele al administrador que registre a
                  la persona.
                </p>
              ) : null}
            </div>
          </Panel>

          {/* El canto de color marca el panel del texto libre, igual que «Descripción» en
              la ficha del ticket: son la misma tarea en las dos pantallas. */}
          <Panel titulo={<TituloPaso numero="2" titulo="Describe la incidencia" />} descripcion="Indica el problema con un título breve y los detalles necesarios." className="overflow-hidden border-t-[3px] border-t-warning shadow-sm">
            <div className="flex flex-col gap-4">
              <Input
                etiqueta="Asunto"
                requerido
                maxLength={200}
                value={asunto}
                onChange={(evento) => setAsunto(evento.target.value)}
                placeholder="Por ejemplo: no enciende el equipo de la ventanilla"
                ayuda={`${asunto.length} / 200 caracteres. Mínimo 4.`}
              />
              <Textarea
                etiqueta="Descripción"
                filas={5}
                maxLength={4000}
                value={descripcion}
                onChange={(evento) => setDescripcion(evento.target.value)}
                placeholder="Qué le pasa, desde cuándo, y qué se intentó."
                ayuda="Opcional, pero ayuda a que el caso avance sin pedir más datos."
              />
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Select
                  etiqueta="Categoría"
                  value={categoria}
                  onChange={(evento) => setCategoria(evento.target.value)}
                  placeholder="Sin categoría"
                  opciones={(catalogos.data?.categorias ?? []).map((valor) => ({ valor, etiqueta: valor }))}
                />
                <Select
                  etiqueta="Prioridad"
                  value={prioridad}
                  onChange={(evento) => setPrioridad(evento.target.value)}
                  opciones={PRIORIDADES_DISPONIBLES}
                  ayuda="Elige según el impacto en el trabajo de la persona."
                />
              </div>
            </div>
          </Panel>
          <Panel titulo={<TituloPaso numero="3" titulo="Equipo y atención" />} className="shadow-sm">
            <div className="flex flex-col gap-4">
              <div className="max-h-96 overflow-y-auto overscroll-contain px-1 py-1">
              <SelectorDestinoIncidencia ruta={rutaDestinos} categoria={categoria}
                valor={{ activo_id: equipoId || '', conjunto_id: conjuntoId, sistema_afectado: programaNombre }}
                alCambiar={valor => { setEquipoId(valor.activo_id || null); setConjuntoId(valor.conjunto_id); setProgramaNombre(valor.sistema_afectado) }} />
              </div>
              <Select
                etiqueta="Asignar a"
                value={tecnicoId}
                onChange={(evento) => setTecnicoId(evento.target.value)}
                placeholder="Dejar sin asignar"
                opciones={(tecnicos.data?.items ?? []).map((tecnico) => ({
                  valor: tecnico.id,
                  etiqueta: tecnico.nombre,
                }))}
              />
            </div>
          </Panel>

        </div>

        <div className="min-w-0 xl:sticky xl:top-24">
          <Panel titulo={<span className="flex items-center gap-2"><ClipboardCheck size={20} className="text-primary" aria-hidden="true" />Resumen del ticket</span>} descripcion="Revisa los datos antes de registrar." className="shadow-sm">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="rounded-xl border border-warning/30 bg-warning-soft/40 p-3">
              <p className="mb-1 text-2xs font-semibold text-muted-foreground uppercase">Incidencia</p>
              <p className="break-words font-semibold">{asunto.trim() || 'Escribe qué problema ocurre'}</p>
            </div>
            <dl className="grid min-w-0 gap-3 text-sm">
              <DatoResumen etiqueta="Persona" valor={personaId ? personaNombre : 'Pendiente de seleccionar'} />
              <DatoResumen etiqueta="Equipo" valor={equipoElegido?.nombre || computadoraElegida?.nombre || 'Selecciona su equipo o PC'} />
              <DatoResumen etiqueta="Categoría" valor={categoria || 'Sin categoría'} />
              <DatoResumen etiqueta="Asignación" valor={tecnicos.data?.items.find(tecnico => tecnico.id === tecnicoId)?.nombre || 'Sin asignar'} />
              <div className="flex items-center justify-between gap-3"><dt className="text-muted-foreground">Prioridad</dt><dd><PrioridadBadge prioridad={prioridad} /></dd></div>
            </dl>
            <div className="space-y-2 border-t border-border pt-3 text-sm" aria-label="Requisitos para registrar">
              <p className={personaId ? 'text-success-strong' : 'text-muted-foreground'}><Check size={15} className="mr-2 inline" aria-hidden="true" />{personaId ? 'Persona seleccionada' : 'Selecciona una persona'}</p>
              <p className={asunto.trim().length >= 4 ? 'text-success-strong' : 'text-muted-foreground'}><Check size={15} className="mr-2 inline" aria-hidden="true" />{asunto.trim().length >= 4 ? 'Incidencia lista para registrar' : 'Escribe un asunto de al menos 4 caracteres'}</p>
            </div>

          {error ? (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-[var(--radius-panel)] border border-destructive/40 bg-destructive-soft p-3 text-sm font-semibold text-destructive-strong"
            >
              <CircleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              {error}
            </p>
          ) : null}

          <Button
            variante="destacado"
            anchoCompleto
            cargando={enviando}
            disabled={!puedeEnviar}
            icono={<TicketPlus size={17} aria-hidden="true" />}
            onClick={() => void enviar()}
          >
            Registrar ticket
          </Button>
          <p className="border-t border-border pt-3 text-2xs leading-relaxed text-muted-foreground">El seguimiento de este registro se realiza con estados y notas internas. No se abre un chat con la persona.</p>
          </div>
          </Panel>
        </div>
      </div>
    </PantallaFormulario>
  )
}

function TituloPaso({ numero, titulo }: { numero: string; titulo: string }) {
  return <span className="flex items-center gap-3"><span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-sm font-bold text-primary-strong">{numero}</span>{titulo}</span>
}

function DatoResumen({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return <div className="flex min-w-0 items-start justify-between gap-3"><dt className="shrink-0 text-muted-foreground">{etiqueta}</dt><dd className="min-w-0 truncate text-right font-medium" title={valor}>{valor}</dd></div>
}

/** Prioridades que el backend acepta al crear un ticket manual. */
const PRIORIDADES_DISPONIBLES = [
  { valor: 'baja', etiqueta: 'Baja' },
  { valor: 'media', etiqueta: 'Media' },
  { valor: 'alta', etiqueta: 'Alta' },
  { valor: 'critica', etiqueta: 'Crítica' },
]
