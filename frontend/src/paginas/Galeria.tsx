/**
 * Galería de componentes.
 *
 * Solo en desarrollo: sirve para ver la librería completa en un mismo sitio y
 * detectar de un vistazo si algo se rompió. No es una pantalla del producto, por
 * eso la ruta no existe en una compilación de producción.
 */

import { useState } from 'react'

import { Button } from '../componentes/base/Button'
import { Checkbox, Input, SearchInput, Select, Switch, Textarea } from '../componentes/base/Campo'
import { Combobox } from '../componentes/base/Combobox'
import { RadioCard } from '../componentes/base/RadioCard'
import { Stepper } from '../componentes/base/Stepper'
import {
  ContenidoTab,
  EmptyState,
  ErrorState,
  ListaTabs,
  Nota,
  NoPermission,
  Panel,
  Skeleton,
  SkeletonKpis,
  Tab,
  TabsPanel,
  Avatar,
} from '../componentes/base/Estructura'
import { ConfirmDialog, DialogModal, InfoTooltip, PopoverSimple, Sheet } from '../componentes/base/Sobreposiciones'
import { useAvisos } from '../estado/useAvisos'
import {
  CompletitudBadge,
  ConfianzaIABadge,
  DisponibilidadBadge,
  EstadoBadge,
  EstadoCampoBadge,
  EtiquetaIA,
  PrioridadBadge,
  SlaBadge,
} from '../componentes/dominio/Badge'
import { KpiCard, KpiPorcentaje } from '../componentes/dominio/KpiCard'
import { DataTable, Paginacion } from '../componentes/dominio/DataTable'
import { BarrasCampos, GraficoLinea } from '../componentes/graficos/Graficos'
import { ESTADOS, PRIORIDADES, SLA } from '../dominio/estados'

/** Avisos de prueba: se eosin para ver los cuatro tonos a la vez. */
function GaleriaAvisos() {
  const avisos = useAvisos()
  return (
    <div className="flex flex-wrap gap-2">
      <Button onClick={() => avisos.exito('Guardado correctamente', 'El cambio ya está en el sistema.')}>Éxito</Button>
      <Button onClick={() => avisos.aviso('Faltan datos', 'Revisa el campo código patrimonial.')}>Aviso</Button>
      <Button onClick={() => avisos.error('No se pudo guardar', 'El servidor respondió con un error.')}>Error</Button>
      <Button onClick={() => avisos.info('Sugerencia', 'Clasificación automática disponible.')}>Información</Button>
    </div>
  )
}

export function Galeria() {
  const [dialogo, setDialogo] = useState(false)
  const [confirmacion, setConfirmacion] = useState(false)
  const [panel, setPanel] = useState(false)
  const [interruptor, setInterruptor] = useState(true)
  const [busquedaGaleria, setBusquedaGaleria] = useState('')
  const [marca, setMarca] = useState<string | null>(null)
  const [tipo, setTipo] = useState<string | null>('hardware')

  const filas = [
    { id: '1', codigo: 'TI-2026-001', asunto: 'No enciende la computadora', estado: 'nuevo', prioridad: 'alta' },
    { id: '2', codigo: 'TI-2026-002', asunto: 'Sin internet en la sala 3', estado: 'en_progreso', prioridad: 'media' },
    { id: '3', codigo: 'TI-2026-003', asunto: 'Solicitud de equipo nuevo', estado: 'cerrado', prioridad: 'baja' },
  ]

  return (
    <div className="flex flex-col gap-4 p-4">
      <header>
        <h1 className="titulo-pagina">Galería de componentes</h1>
        <p className="text-sm text-muted-foreground">
          Solo existe en desarrollo. Sirve para revisar la librería completa de una vez.
        </p>
      </header>

      <Panel titulo="Botones" descripcion="Cinco variantes, cuatro tamaños, con y sin icono">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button variante="primario">Primario</Button>
            <Button variante="secundario">Secundario</Button>
            <Button variante="fantasma">Fantasma</Button>
            <Button variante="destructivo">Destructivo</Button>
            <Button variante="exito">Éxito</Button>
            <Button variante="primario" cargando>
              Cargando
            </Button>
            <Button variante="primario" disabled>
              Desactivado
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variante="primario" tamano="sm">
              Chico
            </Button>
            <Button variante="primario" tamano="md">
              Mediano
            </Button>
            <Button variante="primario" tamano="lg">
              Grande
            </Button>
            <Button variante="primario" tamano="tactil">
              Táctil 48px
            </Button>
          </div>
          <GaleriaAvisos />
        </div>
      </Panel>

      <Panel titulo="Insignias de estado" descripcion="Siempre color + texto + icono">
        {/* Cada familia va en su propia lista: si se mezclan, se repiten claves */}
        <div className="flex flex-wrap gap-2">
          {Object.values(ESTADOS).map((estado) => (
            <EstadoBadge key={`estado-${estado.clave}`} estado={estado.clave} />
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.values(PRIORIDADES).map((prioridad) => (
            <PrioridadBadge key={`prioridad-${prioridad.clave}`} prioridad={prioridad.clave} />
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.keys(SLA).map((clave) => (
            <SlaBadge key={`sla-${clave}`} estado={clave} minutos={90} />
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <DisponibilidadBadge estado="disponible" />
          <DisponibilidadBadge estado="ausente" />
          <EstadoCampoBadge estado="pendiente" />
          <EstadoCampoBadge estado="no_aplica" />
          <CompletitudBadge porcentaje={45} faltantes={3} />
          <CompletitudBadge porcentaje={100} />
          <ConfianzaIABadge confianza={0.82} />
          <ConfianzaIABadge confianza={0.3} />
          <EtiquetaIA />
        </div>
      </Panel>

      <Panel titulo="Campos" descripcion="Etiqueta, ayuda y error pegado al campo">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input etiqueta="Texto" ayuda="Así se ayuda sin abrir nada" placeholder="Escribe aquí" />
          <Input etiqueta="Con error" error="Este campo es obligatorio" />
          <Textarea etiqueta="Área de texto" filas={3} placeholder="Cuéntanos qué pasa" />
          <Select
            etiqueta="Lista"
            opciones={[
              { valor: 'a', etiqueta: 'Opción A' },
              { valor: 'b', etiqueta: 'Opción B' },
            ]}
            placeholder="Elige una"
          />
          {/* Con estado propio y no con `valor=""`: el buscador ya no filtra al
              teclear, así que con un valor fijo el botón de «Buscar» de la galería
              sería un callejón sin salida. */}
          <SearchInput etiqueta="Buscador" valor={busquedaGaleria} alCambiar={setBusquedaGaleria} />
          <div className="flex flex-col gap-3">
            <Checkbox etiqueta="Casilla marcada" valor alCambiar={() => undefined} descripcion="Con descripción" />
            <Switch etiqueta="Interruptor" valor={interruptor} alCambiar={setInterruptor} />
          </div>
        </div>
      </Panel>

      <Panel titulo="Elección grande" descripcion="RadioCard: comparar opciones de un vistazo">
        <RadioCard
          etiqueta="Tipo de problema"
          columnas={3}
          valor={tipo}
          alCambiar={setTipo}
          opciones={[
            { valor: 'hardware', titulo: 'Hardware', descripcion: 'La computadora o un periférico' },
            { valor: 'software', titulo: 'Software', descripcion: 'Un programa o el sistema' },
            { valor: 'red', titulo: 'Red', descripcion: 'Internet o la red de la oficina' },
          ]}
        />
      </Panel>

      <Panel titulo="Sugerencias y escritura libre" descripcion="Combobox con frecuencia real">
        <div className="max-w-md">
          <Combobox
            etiqueta="Marca"
            valor={marca}
            alCambiar={setMarca}
            sugerencias={[
              { valor: 'HP', detalle: '34 equipos', frecuencia: 34 },
              { valor: 'Dell', detalle: '21 equipos', frecuencia: 21 },
              { valor: 'Lenovo', detalle: '12 equipos', frecuencia: 12 },
            ]}
          />
        </div>
      </Panel>

      <Panel titulo="Indicadores">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KpiCard etiqueta="Abiertos" valor={18} detalle="Sin asignar" />
          <KpiCard etiqueta="Con variación" valor={24} variacion={-12.5} menosEsMejor />
          <KpiPorcentaje etiqueta="Cumplimiento de SLA" porcentaje={86.4} />
          <KpiCard etiqueta="Cargando" cargando valor={0} />
        </div>
        <div className="mt-3">
          <SkeletonKpis cantidad={3} />
        </div>
      </Panel>

      <Panel titulo="Tabla" descripcion="Con tarjetas automáticas en móvil">
        <DataTable
          columnas={[
            { accessorKey: 'codigo', header: 'Código' },
            { accessorKey: 'asunto', header: 'Asunto' },
            {
              accessorKey: 'estado',
              header: 'Estado',
              cell: ({ row }) => <EstadoBadge estado={row.original.estado} tamano="sm" />,
            },
            {
              accessorKey: 'prioridad',
              header: 'Prioridad',
              cell: ({ row }) => <PrioridadBadge prioridad={row.original.prioridad} tamano="sm" />,
            },
          ]}
          datos={filas}
          claveFila={(fila) => fila.id}
          columnasConfigurables
        />
        <div className="mt-3">
          <Paginacion pagina={2} totalPaginas={7} total={168} porPagina={25} alCambiar={() => undefined} />
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel titulo="Gráfico de barras">
          <BarrasCampos
            datos={[
              { etiqueta: 'codigo_patrimonial', valor: 12 },
              { etiqueta: 'direccion_ip', valor: 8 },
              { etiqueta: 'numero_serie', valor: 3 },
            ]}
            unidad="equipos"
          />
        </Panel>
        <Panel titulo="Gráfico con tabla alternativa">
          <GraficoLinea
            titulo="Tickets por día"
            unidad="tickets"
            datos={[
              { etiqueta: 'lun', valor: 4 },
              { etiqueta: 'mar', valor: 7 },
              { etiqueta: 'mié', valor: 5 },
              { etiqueta: 'jue', valor: 9 },
            ]}
          />
        </Panel>
      </div>

      <Panel titulo="Pasos">
        <Stepper
          pasos={[
            { clave: 'a', titulo: 'Equipo' },
            { clave: 'b', titulo: 'Ubicación' },
            { clave: 'c', titulo: 'Confirmar' },
          ]}
          actual="b"
          alIr={() => undefined}
        />
      </Panel>

      <Panel titulo="Estados de pantalla">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <EmptyState
            compacto
            titulo="No hay nada aquí"
            descripcion="Con su acción para no dejar un hueco muerto."
            accion={<Button variante="primario">Hacer algo</Button>}
          />
          <ErrorState mensaje="No pudimos cargar." alReintentar={() => undefined} />
          <NoPermission queIntentas="esta sección" permiso="auditoria.ver" />
          <Nota tono="ia" titulo="Sugerencia de la IA">
            <p>Con su explicación al lado.</p>
          </Nota>
          <Nota tono="peligro" titulo="Algo va fuera de tiempo">
            <p>Con su explicación.</p>
          </Nota>
          <Skeleton className="h-12 w-full" />
        </div>
      </Panel>

      <Panel titulo="Personas">
        <div className="flex flex-wrap items-center gap-3">
          <Avatar nombre="Ana Pérez Ruiz" />
          <Avatar nombre="Luis Ramírez" tamano="lg" />
          <InfoTooltip contenido="Más detalle en un tooltip">
            <Button variante="secundario" tamano="sm">
              Pasa el cursor
            </Button>
          </InfoTooltip>
          <PopoverSimple
            disparador={<Button variante="secundario">Popover</Button>}
            contenido={<p className="text-sm">Contenido del popover.</p>}
          />
        </div>
      </Panel>

      <Panel titulo="Capas superpuestas">
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setDialogo(true)}>Diálogo</Button>
          <Button onClick={() => setConfirmacion(true)}>Confirmación</Button>
          <Button onClick={() => setPanel(true)}>Panel lateral</Button>
          {/* Botón largo a propósito: sirve para ver que la línea no se desborda */}
          <Button variante="fantasma">Un botón con un texto muy largo que no cabe</Button>
          <div className="hidden md:block">
            <TabsPanel valor="uno" alCambiar={() => undefined}>
              <ListaTabs>
                <Tab valor="uno">Pestaña 1</Tab>
                <Tab valor="dos">Pestaña 2</Tab>
              </ListaTabs>
              <ContenidoTab valor="uno">
                <p className="py-2 text-sm">Contenido de la primera pestaña.</p>
              </ContenidoTab>
              <ContenidoTab valor="dos">
                <p className="py-2 text-sm">Contenido de la segunda.</p>
              </ContenidoTab>
            </TabsPanel>
          </div>
        </div>
      </Panel>

      <DialogModal abierto={dialogo} alCerrar={() => setDialogo(false)} titulo="Diálogo de ejemplo" descripcion="Con su descripción">
        <p className="text-sm">El contenido del diálogo. Radix mantiene el foco atrapado y Escape cierra.</p>
      </DialogModal>

      <ConfirmDialog
        abierto={confirmacion}
        alCerrar={() => setConfirmacion(false)}
        alConfirmar={() => setConfirmacion(false)}
        titulo="Confirmar acción"
        mensaje="Esta acción tiene consecuencia. El texto explica exactamente cuál."
        textoConfirmar="Hacerlo"
        peligro
      />

      <Sheet abierto={panel} alCerrar={() => setPanel(false)} titulo="Panel lateral" descripcion="Para formularios de dos pasos">
        <div className="flex flex-col gap-3">
          <Input etiqueta="Campo 1" />
          <Textarea etiqueta="Campo 2" filas={4} />
          <div className="flex justify-end gap-2">
            <Button onClick={() => setPanel(false)}>Cancelar</Button>
            <Button variante="primario" onClick={() => setPanel(false)}>
              Guardar
            </Button>
          </div>
        </div>
      </Sheet>
    </div>
  )
}