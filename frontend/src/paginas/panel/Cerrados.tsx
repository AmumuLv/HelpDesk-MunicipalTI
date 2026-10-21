/**
 * Historial y casos críticos: una sola pantalla para los dos.
 *
 * Antes eran dos entradas de menú («Incidentes críticos» y «Tickets cerrados»)
 * quebaoaban a la misma lista con distinto filtro. Ahora es una pantalla con
 * dos pestañas, porque son dos consultas del mismo conjunto de tickets.
 *
 * «Críticos» son los casos de prioridad crítica o con el tiempo acordado ya
 * vencido: se miran primero por la mañana. «Historial» son los ya resueltos o
 * cerrados, con sus exportaciones.
 */

import { Download, FileSpreadsheet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { descargarDeLaApi, nombreDeArchivo } from '../../api/descarga'
import { useExportaciones } from '../../api/hooks'
import { Button } from '../../componentes/base/Button'
import {
  ContenidoTab,
  EmptyState,
  ErrorState,
  ListaTabs,
  Nota,
  Panel,
  SkeletonPanel,
  Tab,
  TabsPanel,
} from '../../componentes/base/Estructura'
import { fechaHora } from '../../dominio/formato'
import { useAvisos } from '../../estado/Avisos'
import { useSesion } from '../../estado/Sesion'
import { Bandeja } from './Bandeja'

/**
 * Las dos vistas que esta pantalla ofrece, y ninguna más.
 *
 * La fila de vistas rápidas es un atajo a la bandeja. Aquí ya hay pestañas
 * propias para exactamente estas dos consultas, así que repetir la fila entera
 * metía dentro del historial tres botones —«Abiertos», «Sin asignar» y «SLA en
 * riesgo»— que saltan a la cola abierta: navegación que te saca de la página
 * en la que estás.
 */
const VISTAS_DE_AQUI = ['criticos', 'cerrados'] as const

export function Cerrados() {
  const sesion = useSesion()
  const avisos = useAvisos()
  const [parametros, setParametros] = useSearchParams()
  const exportaciones = useExportaciones()
  const pestana = parametros.get('tab') === 'criticos' ? 'criticos' : 'cerrados'
  const setPestana = (valor: string) => { const nuevos = new URLSearchParams(); nuevos.set('tab', valor); setParametros(nuevos) }
  const [mostrarExportaciones, setMostrarExportaciones] = useState(false)
  const [descargando, setDescargando] = useState<string | null>(null)
  const [bajandoTodas, setBajandoTodas] = useState(false)
  const [bajadas, setBajadas] = useState(0)

  const listos = (exportaciones.data?.items ?? []).filter((item) => item.estado === 'listo')

  /**
   * Baja todos los archivos uno detrás de otro.
   *
   * Van de uno en uno y no en paralelo a propósito: los navegadores preguntan
   * antes de permitir varias descargas seguidas y, si se lanzan a la vez, las
   * bloquean todas. Con una pausa entre archivos, la primera no dispara el aviso
   * y las demás pasan.
   */
  const bajarTodas = async () => {
    if (bajandoTodas || !listos.length) return
    setBajandoTodas(true)
    setBajadas(0)
    const fallidos: string[] = []
    try {
      for (const [indice, item] of listos.entries()) {
        try {
          await descargarDeLaApi(`/exportaciones/${item.id}/descargar`, nombreDeArchivo(item.nombre_archivo, 'exportacion'))
        } catch {
          fallidos.push(item.nombre_archivo)
        }
        setBajadas(indice + 1)
        if (indice < listos.length - 1) await new Promise((resolver) => window.setTimeout(resolver, 350))
      }
      if (fallidos.length) avisos.error('No se pudieron descargar algunos archivos', fallidos.join(', '))
    } finally {
      setBajandoTodas(false)
    }
  }

  /*
    La descarga va por el cliente de la API, no con un enlace.

    Con `<a href>` el navegador pedía la ruta sin la cabecera de sesión y recibía
    un 401: el botón se pulsaba y no bajaba nada. Es el fallo que hace pensar que
    «Exportaciones no sirve» cuando lo que no funcionaba era el botón de bajar.
  */
  const bajar = async (item: { id: string; nombre_archivo: string }) => {
    setDescargando(item.id)
    try {
      await descargarDeLaApi(`/exportaciones/${item.id}/descargar`, nombreDeArchivo(item.nombre_archivo, 'exportacion'))
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setDescargando(null)
    }
  }

  useEffect(() => {
    document.title = 'Historial y casos críticos · Mesa de Ayuda TI'
  }, [])

  return (
    <>
      <TabsPanel valor={pestana} alCambiar={setPestana}>
        <ListaTabs>
          <Tab valor="criticos">Casos críticos</Tab>
          <Tab valor="cerrados">Historial cerrado</Tab>
        </ListaTabs>

        <ContenidoTab valor="criticos">
          {/* Solo las dos vistas que esta pantalla muestra. Las otras tres son
              atajos de la cola abierta y aquí no llevan a ninguna parte. */}
          <Bandeja vistaInicial="criticos" vistaFija titulo="Casos críticos" vistas={VISTAS_DE_AQUI} />
        </ContenidoTab>

        <ContenidoTab valor="cerrados">
          <Bandeja
            vistaInicial="cerrados"
            vistaFija
            titulo="Historial cerrado"
            vistas={VISTAS_DE_AQUI}
            accionesExtra={
              sesion.puede('exportar') ? (
                <Button
                  variante="secundario"
                  icono={<FileSpreadsheet size={16} aria-hidden="true" />}
                  onClick={() => setMostrarExportaciones((valor) => !valor)}
                  aria-expanded={mostrarExportaciones}
                  title="Abre los archivos que ya generaste, para bajarlos"
                >
                  Descargas ({exportaciones.data?.items.length ?? 0})
                </Button>
              ) : null
            }
          />

          {mostrarExportaciones ? (
            <Panel
              titulo="Archivos que puedes volver a bajar"
              descripcion="No genera nada nuevo: son archivos que ya creaste en Reportes."
            >
              {/*
                Este botón decía «Exportaciones» y solo abría una lista, así que
                pulsarlo no descargaba nada y parecía roto. Se llama «Descargas»,
                que es lo que hace y lo que todo el mundo entiende, y el panel
                aclara las dos cosas que faltaban: que aquí no se crea nada nuevo y
                que se baja todo de una vez.
              */}
              <Nota tono="info">
                <p>
                  Para crear un archivo nuevo, ve a <strong>Reportes</strong> y elige qué
                  sacar, de qué fechas y en qué formato. Lo que guardes ahí aparecerá
                  en esta lista para bajarlo otra vez cuando quieras.
                </p>
              </Nota>
              {exportaciones.isLoading ? (
                <SkeletonPanel filas={3} />
              ) : exportaciones.isError ? (
                <ErrorState
                  compacto
                  mensaje="No pudimos cargar las exportaciones."
                  alReintentar={() => void exportaciones.refetch()}
                />
              ) : (exportaciones.data?.items.length ?? 0) === 0 ? (
                <EmptyState
                  compacto
                  icono={<FileSpreadsheet size={20} aria-hidden="true" />}
                  titulo="Todavía no has generado ningún archivo"
                  descripcion="Se crean desde Reportes, eligiendo el rango y el formato."
                />
              ) : (
                <>
                  <ul className="divide-y divide-border">
                    {exportaciones.data?.items.map((item) => (
                      <li key={item.id} className="flex flex-wrap items-center gap-3 py-2.5">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{item.nombre_archivo}</p>
                          <p className="text-sm text-muted-foreground">
                            {item.tipo} · {item.formato.toUpperCase()} · {fechaHora(item.creado_en)}
                            {item.usuario_nombre ? ` · ${item.usuario_nombre}` : ''}
                          </p>
                          {item.error ? (
                            <p className="text-sm font-semibold text-destructive-strong">{item.error}</p>
                          ) : null}
                        </div>
                        {item.estado === 'listo' ? (
                          <Button variante="secundario" tamano="sm" icono={<Download size={14} aria-hidden="true" />}
                            disabled={descargando === item.id} onClick={() => void bajar(item)}>
                            {descargando === item.id ? 'Descargando…' : 'Descargar'}
                          </Button>
                        ) : (
                          <span className="text-sm font-semibold text-muted-foreground">{item.estado}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                  {listos.length > 1 ? (
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                      <p className="text-sm text-muted-foreground">
                        {listos.length} archivos listos para bajar.
                      </p>
                      <Button
                        variante="primario"
                        tamano="sm"
                        icono={<Download size={14} aria-hidden="true" />}
                        disabled={bajandoTodas}
                        onClick={() => void bajarTodas()}
                      >
                        {bajandoTodas ? `Descargando ${bajadas} de ${listos.length}…` : 'Descargar todos'}
                      </Button>
                    </div>
                  ) : null}
                </>
              )}
            </Panel>
          ) : null}
        </ContenidoTab>
      </TabsPanel>
    </>
  )
}
