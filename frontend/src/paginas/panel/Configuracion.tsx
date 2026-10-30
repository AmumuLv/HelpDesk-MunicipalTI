/**
 * Configuración: los ajustes de la institución.
 *
 * Pestañas por área porque cada una la toca alguien distinto. Los interruptores
 * de IA explican su estado real sin tecnicismos ni promesas que no puedan
 * cumplirse.
 *
 * Los permisos por rol se editan aparte, y siempre con confirmación antes de
 * tocar algo que afecta a todo el equipo TI.
 */

import { Save } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { api } from '../../api/cliente'
import { useConfiguracion, useEstadoIa, useMatrizPermisos, usePermisosTecnicos } from '../../api/hooks'
import { EtiquetaIA } from '../../componentes/dominio/Badge'
import { Button } from '../../componentes/base/Button'
import { Checkbox, Input, SearchInput, Select, Switch, Textarea } from '../../componentes/base/Campo'
import {
  ContenidoTab,
  ErrorState,
  ListaTabs,
  Nota,
  PageHeader,
  Panel,
  PantallaFormulario,
  SkeletonPanel,
  Tab,
  TabsPanel,
} from '../../componentes/base/Estructura'
import { useAvisos } from '../../estado/useAvisos'
import { TEXTOS_IA } from '../../dominio/textos-ia'
import { useSesion } from '../../estado/useSesion'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { ConfiguracionSla } from '../../componentes/dominio/ConfiguracionSla'

export function Configuracion() {
  const sesion = useSesion()
  const avisos = useAvisos()
  const config = useConfiguracion()
  const estadoIa = useEstadoIa()

  const [pestana, setPestana] = useState('negocio')
  const [institucion, setInstitucion] = useState('')
  const [iaGlobal, setIaGlobal] = useState(false)
  const [iaAprendizaje, setIaAprendizaje] = useState(false)
  const [iaRecomendaciones, setIaRecomendaciones] = useState(false)
  const [confianzaMinima, setConfianzaMinima] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [avisarAfectado, setAvisarAfectado] = useState(true)
  const [avisarReportante, setAvisarReportante] = useState(true)
  const ultimoFormulario = useRef<string | null>(null)
  const formularioActual = useRef('')
  formularioActual.current = JSON.stringify([institucion, iaGlobal, iaAprendizaje, iaRecomendaciones, confianzaMinima, avisarAfectado, avisarReportante])

  useEffect(() => {
    document.title = 'Configuración · Mesa de Ayuda TI'
  }, [])

  useEffect(() => {
    if (!config.data) return
    const actual = formularioActual.current
    const nuevo = JSON.stringify([config.data.institucion?.nombre ?? '', config.data.ia?.global_activa ?? false, config.data.ia?.aprendizaje_activo ?? false, config.data.ia?.recomendaciones_activas ?? false, String(config.data.ia?.confianza_minima ?? ''), config.data.notificaciones?.avisar_al_afectado ?? true, config.data.notificaciones?.avisar_al_reportante ?? true])
    const editando = ultimoFormulario.current !== null && actual !== ultimoFormulario.current
    ultimoFormulario.current = nuevo
    if (editando) return // Un aviso remoto nunca descarta lo que se está escribiendo.
    setInstitucion(config.data.institucion?.nombre ?? '')
    setIaGlobal(config.data.ia?.global_activa ?? false)
    setIaAprendizaje(config.data.ia?.aprendizaje_activo ?? false)
    setIaRecomendaciones(config.data.ia?.recomendaciones_activas ?? false)
    setConfianzaMinima(String(config.data.ia?.confianza_minima ?? ''))
    setAvisarAfectado(config.data.notificaciones?.avisar_al_afectado ?? true)
    setAvisarReportante(config.data.notificaciones?.avisar_al_reportante ?? true)
  }, [config.data])

  const puedeEditar = sesion.puede('configuracion.editar')

  const guardar = async () => {
    if (!institucion.trim() || !confianzaMinima.trim() || !Number.isFinite(Number(confianzaMinima)) || Number(confianzaMinima) < 0 || Number(confianzaMinima) > 1) {
      avisos.aviso('Revisa el nombre y la confianza mínima: debe ser un número entre 0 y 1.')
      return
    }
    setGuardando(true)
    try {
      await api.editar('/configuracion', {
        negocio: { institucion_nombre: institucion.trim() },
        notificaciones: { avisar_al_afectado: avisarAfectado, avisar_al_reportante: avisarReportante },
        ia: {
          global_activa: iaGlobal,
          aprendizaje_activo: iaAprendizaje,
          recomendaciones_activas: iaRecomendaciones,
          ...(confianzaMinima ? { confianza_minima: Number(confianzaMinima) } : {}),
        },
      })
      avisos.exito('Configuración guardada')
      await Promise.all([config.refetch(), estadoIa.refetch()])
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  if (config.isError) {
    return (
      <ErrorState
        mensaje="No pudimos cargar la configuración."
        detalle={config.error instanceof Error ? config.error.message : undefined}
        alReintentar={() => void config.refetch()}
      />
    )
  }

  return (
    <PantallaFormulario>
      <PageHeader
        titulo="Configuración"
        descripcion="Ajustes generales, ayudas automáticas y accesos del equipo."
        acciones={
          puedeEditar && !['sla', 'permisos', 'sistema'].includes(pestana) ? (
            <Button variante="primario" disabled={!config.data} cargando={guardando} onClick={() => void guardar()} icono={<Save size={16} aria-hidden="true" />}>
              Guardar cambios
            </Button>
          ) : null
        }
      />

      {config.isLoading ? (
        <SkeletonPanel filas={5} />
      ) : (
        <TabsPanel valor={pestana} alCambiar={setPestana}>
          <ListaTabs>
            <Tab valor="negocio">Institución</Tab>
            <Tab valor="ia">Ayudas automáticas</Tab>
            <Tab valor="sla">SLA y horarios</Tab>
            <Tab valor="notificaciones">Notificaciones</Tab>
            <Tab valor="permisos">Permisos por rol</Tab>
            <Tab valor="sistema">Sistema</Tab>
          </ListaTabs>

          <ContenidoTab valor="negocio">
            <Panel titulo="Datos de la institución" descripcion="Aparecen en la pantalla de acceso y en los encabezados">
              <div className="flex max-w-xl flex-col gap-4">
                <Input
                  etiqueta="Nombre de la institución"
                  value={institucion}
                  disabled={!puedeEditar}
                  onChange={(evento) => setInstitucion(evento.target.value)}
                />
                <dl className="grid grid-cols-2 gap-3">
                  <Campo etiqueta="Zona horaria" valor={config.data?.negocio?.zona_horaria ?? 'America/Lima'} />
                  <Campo etiqueta="Horario de la institución" valor={(config.data?.sla?.calendario?.tramos ?? []).map((tramo) => `${tramo.entrada}–${tramo.salida}`).join(' y ') || 'Sin horario configurado'} />
                </dl>
                <p className="text-sm text-muted-foreground">Días de atención: {(config.data?.sla?.calendario?.dias_laborables ?? []).map(dia => ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][dia]).join(', ')}. Las ausencias y horarios particulares se gestionan en Equipo TI.</p>
              </div>
            </Panel>
          </ContenidoTab>

          <ContenidoTab valor="ia">
            <div className="flex flex-col gap-4">
              <Panel
                titulo={
                  <span className="flex items-center gap-2">
                    Ayudas automáticas <EtiquetaIA />
                  </span>
                }
                descripcion="Clasificación, asignación, riesgo de SLA y resúmenes. Nunca es un requisito para trabajar."
              >
                {estadoIa.data ? (
                  <Nota tono={estadoIa.data.disponible ? 'exito' : 'aviso'}>
                    <p>{estadoIa.data.disponible ? TEXTOS_IA.disponible : TEXTOS_IA.basica}</p>
                  </Nota>
                ) : null}

                <div className="mt-4 flex flex-col gap-4">
                  <Switch
                    etiqueta="Activar las ayudas automáticas"
                    descripcion="Si se desactiva, nada cambia para el trabajo: solo deja de haber sugerencias."
                    valor={iaGlobal}
                    disabled={!puedeEditar}
                    alCambiar={setIaGlobal}
                  />
                  <Switch
                    etiqueta="Permitir recomendaciones al reportar"
                    descripcion="El portal sugiere una categoría y artículos de ayuda al crear un ticket."
                    valor={iaRecomendaciones}
                    disabled={!puedeEditar || !iaGlobal}
                    alCambiar={setIaRecomendaciones}
                  />
                  <Switch
                    etiqueta="Aprender de las decisiones"
                    descripcion="Permite utilizar las decisiones del equipo para mejorar futuras sugerencias."
                    valor={iaAprendizaje}
                    disabled={!puedeEditar || !iaGlobal}
                    alCambiar={setIaAprendizaje}
                  />
                  <label className="flex max-w-xs flex-col gap-1.5">
                    <span className="text-sm font-semibold">Confianza mínima para sugerir</span>
                    <input
                      value={confianzaMinima}
                      disabled={!puedeEditar}
                      onChange={(evento) => setConfianzaMinima(evento.target.value)}
                      inputMode="decimal" type="number" min="0" max="1" step="0.05"
                      className="h-[var(--spacing-control)] rounded-[var(--radius-control)] border border-input bg-surface px-3"
                    />
                    <span className="text-sm text-muted-foreground">
                      Entre 0 y 1. Por debajo de este valor no se muestra ninguna sugerencia.
                    </span>
                  </label>
                </div>
              </Panel>

            </div>
          </ContenidoTab>

          <ContenidoTab valor="sla">
            <ConfiguracionSla />
          </ContenidoTab>

          <ContenidoTab valor="notificaciones">
            <Panel titulo="Avisos dentro de la página" descripcion="Las personas reciben avisos en la campana de notificaciones y pueden abrir su ticket para ver los cambios.">
              <Nota tono="info">Estas opciones controlan las notificaciones dentro del sistema. El usuario también puede consultar siempre el estado y el historial en Mis tickets.</Nota>
              <Checkbox
                etiqueta="Avisar al afectado cuando cambia el estado de su ticket"
                valor={avisarAfectado}
                disabled={!puedeEditar}
                alCambiar={setAvisarAfectado}
              />
              <Checkbox
                etiqueta="Avisar a quien reportó, aunque no sea el afectado"
                valor={avisarReportante}
                disabled={!puedeEditar}
                alCambiar={setAvisarReportante}
              />
            </Panel>
          </ContenidoTab>

          <ContenidoTab valor="permisos">
            <PermisosPorRol />
          </ContenidoTab>

          <ContenidoTab valor="sistema">
            <Panel titulo="Información del sistema" descripcion="Solo lectura">
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <Campo etiqueta="Versión" valor={config.data?.sistema?.version ?? '—'} />
                <Campo etiqueta="Primer arranque completo" valor={config.data?.sistema?.primer_arranque_completo ? 'Sí' : 'No'} />
                <Campo etiqueta="Datos demo" valor={config.data?.sistema?.datos_demo ? 'Cargados' : 'No'} />
              </dl>
              <Nota tono="aviso">
                <p>
                  Los datos de demostración se borran con <code>python -m app.scripts.demo eliminar</code>.
                </p>
              </Nota>
            </Panel>
          </ContenidoTab>
        </TabsPanel>
      )}
    </PantallaFormulario>
  )
}

function Campo({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="break-words font-medium">{valor}</dd>
    </div>
  )
}

/**
 * Permisos delegables del equipo TI.
 *
 * La matriz viene del backend con todo apagado por defecto: nadie empieza con
 * permisos que no se le dieron. Cambiar algo afecta a todo el equipo, así que
 * hay confirmación antes de guardar.
 */
function PermisosPorRol() {
  const [busqueda, setBusqueda] = useState('')
  const [pagina, setPagina] = useState(1)
  const normal = (v: string) => v.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  const coincide = (...valores: string[]) => normal(valores.join(' ')).includes(normal(busqueda.trim()))
  const matriz = useMatrizPermisos()
  const tecnicos = usePermisosTecnicos()
  const avisos = useAvisos()
  const sesion = useSesion()

  const [pendientes, setPendientes] = useState<Record<string, Record<string, boolean>>>({})
  const [guardando, setGuardando] = useState(false)

  const alternar = (tecnicoId: string, permiso: string) => {
    setPendientes((actual) => {
      const lista = actual[tecnicoId] ?? tecnicos.data?.items.find((ficha) => ficha.usuario_id === tecnicoId)?.permisos ?? {}
      return {
        ...actual,
        [tecnicoId]: { ...lista, [permiso]: !lista[permiso] },
      }
    })
  }

  const guardar = async (tecnicoId: string) => {
    const cambios = { cambios: pendientes[tecnicoId] ?? {} }
    setGuardando(true)
    try {
      await api.reemplazar(`/permisos/tecnicos/${tecnicoId}`, cambios)
      avisos.exito('Permisos actualizados')
      setPendientes((actual) => {
        const copia = { ...actual }
        delete copia[tecnicoId]
        return copia
      })
      await tecnicos.refetch()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  if (matriz.isLoading || tecnicos.isLoading) return <SkeletonPanel filas={4} />
  if (matriz.isError || tecnicos.isError) return <ErrorState mensaje="No pudimos cargar los permisos." alReintentar={() => { void matriz.refetch(); void tecnicos.refetch() }} />

  const grupos = Array.isArray(matriz.data) ? matriz.data : []
  const fichas = tecnicos.data?.items ?? []
  const fichasVisibles = fichas.filter(ficha => coincide(ficha.nombre, ficha.rol) || grupos.some(g => coincide(g.etiqueta) || g.permisos.some(p => coincide(p.etiqueta, p.clave, p.descripcion || ''))))

  const totalPaginas = Math.max(1, Math.ceil(fichasVisibles.length / 2))
  const paginaActual = Math.min(pagina, totalPaginas)

  if (!sesion.puede('permisos.ver')) {
    return (
      <Panel titulo="Permisos por rol">
        <p className="text-sm text-muted-foreground">Necesitas el permiso de administrador para ver esta sección.</p>
      </Panel>
    )
  }

  return (
    <Panel
      titulo="Permisos por rol"
      descripcion={sesion.esSuperadmin ? "Permisos adicionales de cada técnico. Guarda los cambios de cada persona por separado." : "Solo el superadministrador puede cambiar los permisos."}
    >
      <div className="mb-4"><SearchInput etiqueta="Buscar permisos, roles o personas" valor={busqueda} alCambiar={valor => { setBusqueda(valor); setPagina(1) }} /></div>
      {fichas.length === 0 ? (
        <p className="text-sm text-muted-foreground">No hay técnicos registrados.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {!fichasVisibles.length ? <li className="py-4 text-sm text-muted-foreground">No hay permisos, roles o personas que coincidan con la búsqueda.</li> : null}
          {fichasVisibles.slice((paginaActual - 1) * 2, paginaActual * 2).map((ficha) => {
            const yaAsignados = pendientes[ficha.usuario_id] ?? ficha.permisos ?? {}
            return (
              <li key={ficha.usuario_id} className="rounded-[var(--radius-panel)] border border-border p-3">
                <p className="font-semibold">{ficha.nombre}</p>
                {grupos.filter(g => coincide(ficha.nombre, ficha.rol, g.etiqueta) || g.permisos.some(p => coincide(p.etiqueta, p.clave, p.descripcion || ''))).map((grupo) => (
                  <div key={grupo.grupo} className="mt-2">
                    <p className="text-2xs font-semibold text-muted-foreground uppercase">{grupo.etiqueta}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1">
                      {grupo.permisos.filter(p => coincide(ficha.nombre, ficha.rol, grupo.etiqueta, p.etiqueta, p.clave, p.descripcion || '')).map((permiso) => (
                        <label key={permiso.clave} className="flex items-center gap-1.5 text-sm">
                          <input
                            type="checkbox"
                            checked={Boolean(yaAsignados[permiso.clave])}
                            disabled={guardando || ficha.rol === 'administrador' || !sesion.esSuperadmin}
                            onChange={() => alternar(ficha.usuario_id, permiso.clave)}
                            className="size-4 accent-primary"
                          />
                          <span title={permiso.descripcion}>{permiso.etiqueta}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
                {pendientes[ficha.usuario_id] ? (
                  <div className="mt-2 flex justify-end">
                    <Button tamano="sm" variante="primario" cargando={guardando} onClick={() => void guardar(ficha.usuario_id)}>
                      Guardar cambios de {ficha.nombre.split(' ')[0]}
                    </Button>
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
      <Paginacion pagina={paginaActual} totalPaginas={totalPaginas} total={fichasVisibles.length} porPagina={2} alCambiar={setPagina} />
    </Panel>
  )
}

export { Select, Textarea }
