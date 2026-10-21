import { etiquetaPropiedad } from '../../dominio/propiedad'
import { Button } from '../base/Button'
import { CampoTecnicoSugerido } from './CampoTecnicoSugerido'
import { DisponibilidadConjuntos } from './DisponibilidadConjuntos'
/**
 * Asistente de registro de equipo.
 *
 * Tres pasos porque registrar bien cuesta: qué equipo es, dónde está y quién
 * responde. En el segundo paso se elige **zona y luego oficina**, porque la zona
 * filtra las oficinas y es lo que dice dónde queda el equipo: el backend copia la
 * zona desde la oficina. El conjunto se elige de los que ya hay en esa oficina, con
 * su número de equipos a la vista, y solo se escribe un nombre nuevo si de verdad
 * no existe. Los campos usan las sugerencias reales del inventario, ordenadas por
 * frecuencia, con la opción de escribir un valor nuevo.
 *
 * El backend solo exige `tipo` y `oficina_id`; la zona no se manda porque se deduce
 * de la oficina. Aquí se pide igual, y antes que la oficina, para poder filtrar y
 * para no registrar en una zona sin querer. El resto de campos del inventario
 * pueden quedar «Pendiente», «No aplica» o «No disponible», y eso no bloquea el
 * registro.
 */

import { Monitor, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../api/cliente'
import {
  useCatalogoEquipos,
  useConjuntos,
  useOficinas,
  useSiguienteNombreConjunto,
  useEsquemaEquipo,
  useSugerenciasCampo,
  useUsuarios,
  useZonas,
} from '../../api/hooks'
import type { CuerpoActivoCrear } from '../../api/tipos'
import { Combobox } from '../base/Combobox'
import { Checkbox, Input, Select } from '../base/Campo'
import { PiePasos, Stepper } from '../base/Stepper'
import { Nota, Panel } from '../base/Estructura'
import { useAvisos } from '../../estado/Avisos'
import { IconoTipoEquipo } from './IconoTipoEquipo'

const PASOS = [
  { clave: 'equipo', titulo: 'Equipo' },
  { clave: 'ubicacion', titulo: 'Ubicación' },
  { clave: 'confirmar', titulo: 'Confirmar' },
]

const ETIQUETAS_CAMPOS: Record<string, string> = {
  tamano_pantalla: 'Tamaño de pantalla',
  procesador: 'Procesador',
  memoria_ram: 'Memoria RAM',
  almacenamiento: 'Disco duro / almacenamiento',
  direccion_ip: 'Dirección IP',
  direccion_mac: 'Dirección MAC',
  estado: 'Estado del equipo',
}
const CAMPOS_REGISTRO_FIJOS = new Set([
  'codigo_patrimonial',
  'marca',
  'modelo',
  'nombre_equipo',
  'propiedad',
])

/**
 * Tipos que suelen formar parte del conjunto de una computadora.
 *
 * El resto se registra suelto: un router, una tablet o un sistema de audio no
 * son «el monitor y el teclado de la PC». Antes se offered todo como conjunto y
 * se acababa metiendo un amplificador dentro de «Computadora N°01».
 */
const TIPOS_EN_CONJUNTO = new Set(['CPU', 'Monitor', 'Teclado', 'Mouse'])
type EquipoDuplicado = {
  id: string
  nombre: string
  tipo: string
  oficina_nombre: string | null
  zona_nombre: string | null
  coincide_en: string[]
}

export function RegistroEquipo({ alGuardar }: { alCerrar: () => void; alGuardar: () => void }) {
  const avisos = useAvisos()

  /*
   * La zona va antes que la oficina porque es lo que **filtra** la oficina, y
   * además es la única forma de saber dónde va a quedar el equipo: el backend
   * copia la zona desde la oficina, así que ver las 59 oficinas de golpe —27 de
   * PALACIO, 12 de COMPLEJO, 11 de MERCADO…— no dizia nada de dónde se acababa
   * registrando. La zona se declara aquí y no junto a los demás estados porque
   * las oficinas ya la necesitan para consultarse.
   */
  const [zonaId, setZonaId] = useState('')

  const catalogos = useCatalogoEquipos()
  const zonas = useZonas()
  const oficinas = useOficinas({ zona_id: zonaId || undefined })

  const [paso, setPaso] = useState('equipo')
  const [tipo, setTipo] = useState('')
  const [marca, setMarca] = useState<string | null>(null)
  const [modelo, setModelo] = useState<string | null>(null)
  const [nombreEquipo, setNombreEquipo] = useState('')
  const [codigo, setCodigo] = useState('')
  const [oficinaId, setOficinaId] = useState('')
  /*
    Los responsables, **de la oficina elegida**.

    Antes pedía el directorio entero (`useUsuarios({})`), así que el desplegable
    ofrecía las primeras 25 cuentas de la municipalidad sin relación con la oficina:
    en una pantalla que dice «Personas activas de la oficina elegida» y en la que la
    oficina es obligatoria. Con 267 cuentas, quien se iba a hacer cargo del equipo
    tenía que buscarse entre nombres de otras oficinas.

    Solo se consulta cuando hay oficina: sin ella no hay nadie que ofrecer.
  */
  const usuarios = useUsuarios(
    { oficina_id: oficinaId, solo_activos: true, por_pagina: 200 },
    Boolean(oficinaId),
  )
  const [conjuntoId, setConjuntoId] = useState('')
  const [nombreConjunto, setNombreConjunto] = useState('')
  const [responsableId, setResponsableId] = useState('')
  const [comoConjunto, setComoConjunto] = useState(false)
  const [propiedad, setPropiedad] = useState('')
  const esPersonal = propiedad.trim().toLocaleLowerCase('es') === 'personal'
  const [campos, setCampos] = useState<Record<string, string>>({})
  const [duplicados, setDuplicados] = useState<EquipoDuplicado[]>([])
  const [duplicadosConfirmados, setDuplicadosConfirmados] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    document.title = 'Registrar equipo · Mesa de Ayuda TI'
  }, [])

  // El nombre siguiente del conjunto lo propone el backend según la oficina
  const sugerenciaNombre = useSiguienteNombreConjunto(oficinaId || undefined, Boolean(oficinaId) && comoConjunto)
  useEffect(() => {
    if (sugerenciaNombre.data?.nombre && !nombreConjunto) setNombreConjunto(sugerenciaNombre.data.nombre)
  }, [sugerenciaNombre.data, nombreConjunto])

  // Las marcas se piden al backend; los modelos dependen de la marca elegida
  const marcas = useSugerenciasCampo('marca', null, Boolean(tipo))
  const modelos = useSugerenciasCampo('modelo', marca, Boolean(tipo && marca))
  const esquema = useEsquemaEquipo(tipo || null)
  const camposDinamicos = [...(esquema.data?.esperados ?? []), ...(esquema.data?.opcionales ?? [])]
    .filter((campo, indice, todos) => todos.indexOf(campo) === indice && !CAMPOS_REGISTRO_FIJOS.has(campo) && ETIQUETAS_CAMPOS[campo])

  const crearConjunto = async (): Promise<string | undefined> => {
    if (!comoConjunto || !oficinaId || !nombreConjunto.trim()) return undefined
    const creado = await api.crear<{ id: string }>('/conjuntos', {
      nombre: nombreConjunto.trim(),
      oficina_id: oficinaId,
      uso_comun: false,
      activo: true,
    })
    return creado.id
  }

  const guardar = async () => {
    if (enviando) return
    setEnviando(true)
    try {
      const parametros = new URLSearchParams()
      if (!esPersonal && codigo.trim()) parametros.set('codigo_patrimonial', codigo.trim())
      if (campos.direccion_ip?.trim()) parametros.set('direccion_ip', campos.direccion_ip.trim())
      if (campos.direccion_mac?.trim()) parametros.set('direccion_mac', campos.direccion_mac.trim())
      const claveActual = JSON.stringify([codigo.trim(), campos.direccion_ip?.trim(), campos.direccion_mac?.trim()])
      const consultaDuplicados = parametros.toString()
      if (consultaDuplicados && duplicadosConfirmados !== claveActual) {
        const respuesta = await api.obtener<{ items: EquipoDuplicado[] }>(`/activos/duplicados?${consultaDuplicados}`)
        if (respuesta.items.length) {
          setDuplicados(respuesta.items)
          setDuplicadosConfirmados(claveActual)
          avisos.aviso('Posibles equipos duplicados', 'Revisa las fichas encontradas; si corresponde, guarda de todos modos.')
          return
        }
        setDuplicados([])
        setDuplicadosConfirmados(claveActual)
      }
      const conjuntoCreado = TIPOS_EN_CONJUNTO.has(tipo) ? conjuntoId || (await crearConjunto()) : undefined
      if (conjuntoCreado && !conjuntoId) setConjuntoId(conjuntoCreado)
      const cuerpo: CuerpoActivoCrear = {
        tipo,
        oficina_id: oficinaId,
        ...(marca ? { marca } : {}),
        ...(modelo ? { modelo } : {}),
        ...(nombreEquipo.trim() ? { nombre_equipo: nombreEquipo.trim() } : {}),
        ...(!esPersonal && codigo.trim() ? { codigo_patrimonial: codigo.trim() } : {}),
        ...(esPersonal ? { campos_estado: { codigo_patrimonial: { estado: 'no_aplica', motivo: 'Equipo de propiedad personal' } } } : {}),
        ...(conjuntoCreado ? { conjunto_id: conjuntoCreado } : {}),
        ...(responsableId ? { responsable_id: responsableId } : {}),
        ...(propiedad ? { propiedad } : {}),
        opciones_avanzadas: false,
      }
      for (const campo of camposDinamicos) {
        const valor = campos[campo]?.trim()
        if (valor) Object.assign(cuerpo, { [campo]: valor })
      }
      await api.crear('/activos', cuerpo)
      avisos.exito('Equipo registrado', `${tipo}${nombreEquipo ? ` · ${nombreEquipo}` : ''}`)
      alGuardar()
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  const listaTipos = (catalogos.data?.tipos_dispositivo ?? [])
    .filter((item) => item.activo)
    .map((item) => ({ valor: item.valor, etiqueta: item.etiqueta || item.valor }))
  if (!listaTipos.some((item) => item.valor.toLocaleLowerCase('es') === 'otro')) {
    listaTipos.push({ valor: 'Otro', etiqueta: 'Otro' })
  }

  // En el primer paso solo hace falta el tipo: la oficina se elige en el
  // segundo. Antes se exigian las dos aqui, asi que «Continuar» nunca se activaba
  // y no se podia registrar ningun equipo.
  const indicePaso = PASOS.findIndex((item) => item.clave === paso)

  const nombreZona = zonas.data?.items.find((zona) => zona.id === zonaId)?.nombre

  /*
   * Los conjuntos que ya existen en esa oficina.
   *
   * Antes solo se ofrecía un nombre en blanco con la sugerencia del sistema al
   * lado, y no había forma de saber qué conjuntos había. Eso producía conjuntos
   * repetidos: «Computadora N°3» se creaba otra vez porque no se veía que ya
   * existía, y acababan varias copias del mismo equipo repartidas por la
   * oficina. El backend ya traía `total_activos` en la lista y no se usaba.
   *
   * La consulta espera a que haya oficina a propósito: sin ella salían los **261**
   * conjuntos del municipio, y el backend hace una consulta al inventario por cada
   * uno para contar sus equipos. Es un gasto para no mostrar nada, porque la lista
   * solo se ofrece cuando ya se eligió dónde va el equipo.
   */
  const conjuntos = useConjuntos({ oficina_id: oficinaId }, Boolean(oficinaId))
  // El endpoint ya devuelve solo los conjuntos activos; no hace falta filtrar más.
  const conjuntosExistentes = useMemo(() => conjuntos.data?.items ?? [], [conjuntos.data])
  const nombreConjuntoElegido = conjuntosExistentes.find((conjunto) => conjunto.id === conjuntoId)?.nombre

  return (
    <div className="flex flex-col gap-4">
      <Stepper pasos={PASOS} actual={paso} alIr={setPaso} />

      {paso === 'equipo' ? (
        <div className="flex flex-col gap-4">
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Tipo de equipo <span className="text-destructive-strong">*</span></legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {listaTipos.map((opcion) => (
                <button
                  key={opcion.valor}
                  type="button"
                  aria-pressed={tipo === opcion.valor}
                  onClick={() => {
                    setTipo(opcion.valor)
                    // Cada tipo tiene su punto de partida para el conjunto
                    setComoConjunto(TIPOS_EN_CONJUNTO.has(opcion.valor))
                    setConjuntoId('')
                    setCampos({})
                  }}
                  className={`flex min-h-24 flex-col items-center justify-center gap-2 rounded-[var(--radius-control)] border p-3 text-center transition-colors ${
                    tipo === opcion.valor ? 'border-primary bg-primary-soft' : 'border-border bg-surface hover:bg-muted'
                  }`}
                >
                  <IconoTipoEquipo tipo={opcion.valor} tamano={34} />
                  <span className="text-sm font-semibold">{opcion.etiqueta}</span>
                </button>
              ))}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">Solo el tipo y la oficina son obligatorios.</p>
          </fieldset>

          {tipo ? (
            <>
              <Combobox
                etiqueta="Marca"
                valor={marca}
                alCambiar={(valor) => {
                  setMarca(valor)
                  setModelo(null)
                }}
                sugerencias={(marcas.data?.valores ?? []).map((item) => ({
                  valor: item.valor,
                  detalle: `${item.frecuencia} equipos con esta marca`,
                  frecuencia: item.frecuencia,
                }))}
                ayuda="Ordenado por lo que ya existe en el inventario. Puedes escribir una marca nueva."
              />
              <Combobox
                etiqueta="Modelo"
                valor={modelo}
                alCambiar={setModelo}
                sugerencias={(modelos.data?.valores ?? []).map((item) => ({
                  valor: item.valor,
                  detalle: item.marca ? `De la marca ${item.marca}` : undefined,
                  frecuencia: item.frecuencia,
                }))}
                sinSeleccion="Sin modelo"
              />
              {esquema.isError ? (
                <Nota tono="aviso" titulo="No se pudieron cargar los campos sugeridos">
                  <p>{esquema.error instanceof Error ? esquema.error.message : 'Revisa el esquema del tipo de equipo.'}</p>
                </Nota>
              ) : null}
              {camposDinamicos.map((campo) => (
                campo === 'estado' ? (
                  <Select
                    key={campo}
                    etiqueta={ETIQUETAS_CAMPOS[campo]}
                    value={campos[campo] ?? ''}
                    onChange={(evento) => setCampos((actual) => ({ ...actual, [campo]: evento.target.value }))}
                    placeholder="Sin definir"
                    opciones={(catalogos.data?.estados_activo ?? []).map((item) => ({
                      valor: item.valor,
                      etiqueta: item.etiqueta || item.valor,
                    }))}
                  />
                ) : ['procesador', 'memoria_ram', 'almacenamiento', 'tamano_pantalla'].includes(campo) ? (<CampoTecnicoSugerido key={campo} campo={campo} etiqueta={ETIQUETAS_CAMPOS[campo]} valor={campos[campo] || ''} alCambiar={valor => setCampos(actual => ({ ...actual, [campo]: valor }))} />) : (
                  <Input
                    key={campo}
                    etiqueta={ETIQUETAS_CAMPOS[campo]}
                    value={campos[campo] ?? ''}
                    onChange={(evento) => {
                      setCampos((actual) => ({ ...actual, [campo]: evento.target.value }))
                      if (campo === 'direccion_ip' || campo === 'direccion_mac') {
                        setDuplicados([])
                        setDuplicadosConfirmados('')
                      }
                    }}
                    acciones={campo === 'direccion_ip' && tipo.toLocaleLowerCase('es') === 'impresora' ? <Button tamano="sm" onClick={() => setCampos(actual => ({ ...actual, direccion_ip: 'Cable USB' }))}>Cable USB</Button> : undefined}
                  />
                )
              ))}
            </>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <label htmlFor="nombre-equipo" className="text-sm font-semibold">
              Nombre del equipo
            </label>
            <input
              id="nombre-equipo"
              value={nombreEquipo}
              onChange={(evento) => setNombreEquipo(evento.target.value)}
              placeholder="Opcional: «Monitor recepción»"
              className="h-[var(--spacing-control)] w-full rounded-[var(--radius-control)] border border-input bg-surface px-3"
            />
            <p className="text-sm text-muted-foreground">
              Si el equipo tiene un nombre propio, escríbelo. Si no, se usan marca y tipo.
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="codigo-patrimonial" className="text-sm font-semibold">
              Código patrimonial
            </label>
            <input
              id="codigo-patrimonial"
              autoComplete="off"
              value={esPersonal ? 'No aplica' : codigo}
              disabled={esPersonal}
              onChange={(evento) => {
                setCodigo(evento.target.value)
                setDuplicados([])
                setDuplicadosConfirmados('')
              }}
              placeholder="Opcional"
              className="h-[var(--spacing-control)] w-full rounded-[var(--radius-control)] border border-input bg-surface px-3"
            />
          </div>
        </div>
      ) : null}

      {paso === 'ubicacion' ? (
        <div className="flex flex-col gap-4">
          <Select
            etiqueta="Zona"
            requerido
            value={zonaId}
            onChange={(evento) => {
              setZonaId(evento.target.value)
              // Cambiar de zona deja sin sentido la oficina y el conjunto que
              // estaban elegidos, así que se sueltan: si no, se guardaría un
              // equipo en PALACIO con un conjunto de MERCADO y el backend lo
              // rechazaría con «el conjunto pertenece a otra oficina».
              setOficinaId('')
              setConjuntoId('')
              setNombreConjunto('')
            }}
            placeholder="Elige la zona"
            opciones={(zonas.data?.items ?? [])
              .filter((zona) => zona.activa)
              .map((zona) => ({ valor: zona.id, etiqueta: `${zona.nombre} · ${zona.total_oficinas} oficinas` }))}
            ayuda="El equipo queda en la zona de la oficina que elijas. La zona sale de la oficina, no al revés."
          />

          <Select
            etiqueta="Oficina"
            requerido
            disabled={!zonaId}
            value={oficinaId}
            onChange={(evento) => {
              setOficinaId(evento.target.value)
              setConjuntoId('')
              setNombreConjunto('')
            }}
            placeholder={zonaId ? 'Elige la oficina' : 'Antes, elige la zona'}
            opciones={(oficinas.data?.items ?? []).map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
            ayuda={
              zonaId
                ? `Solo las oficinas de ${nombreZona ?? 'la zona elegida'}.`
                : 'Se elige después de la zona, para no bajar entre 59 oficinas.'
            }
          />

          <Checkbox
            etiqueta="Es parte de una PC de escritorio"
            disabled={!TIPOS_EN_CONJUNTO.has(tipo)}
            descripcion={
              TIPOS_EN_CONJUNTO.has(tipo)
                ? 'Un conjunto de escritorio incluye CPU, monitor, teclado y mouse.'
                : `Un ${tipo} se registra como equipo independiente.`
            }
            valor={comoConjunto}
            alCambiar={(marcado) => {
              setComoConjunto(marcado)
              /*
               * Desmarcar tiene que soltar las dos cosas del conjunto, no solo el
               * interruptor.
               *
               * `conjuntoId` no se limpiaba, y es justo lo que se manda primero:
               * `guardar` hace `conjuntoId || crearConjunto()`. Con un conjunto
               * elegido y la casilla desmarcada, se guardaba **enlazado a ese
               * conjunto**, que es justo lo que se dijo que no.
               *
               * `nombreConjunto` tampoco, y hacía que la pantalla de confirmación
               * sigiera enseñando «Computadora N°2» con la casilla desmarcada: la
               * sugerencia del sistema lo rellena solo y nadie lo vacía.
               */
              if (!marcado) {
                setConjuntoId('')
                setNombreConjunto('')
              }
            }}
          />

          {comoConjunto ? (
            <div className="flex flex-col gap-2.5">
              <Select
                etiqueta="Conjunto"
                value={conjuntoId}
                onChange={(evento) => {
                  setConjuntoId(evento.target.value)
                  // Al elegir uno existente el nombre nuevo no hace falta, y al
                  // volver a «crear uno nuevo» el campo aparece vacío para que la
                  // sugerencia del sistema vuelva a proponer el número siguiente.
                  if (evento.target.value) setNombreConjunto('')
                }}
                disabled={!oficinaId}
                placeholder={oficinaId ? 'Crear uno nuevo' : 'Antes, elige la oficina'}
                opciones={conjuntosExistentes.map((conjunto) => ({
                  valor: conjunto.id,
                  etiqueta: `${conjunto.nombre} · ${conjunto.total_activos} ${conjunto.total_activos === 1 ? 'equipo' : 'equipos'}`,
                }))}
                ayuda={
                  conjuntos.isLoading
                    ? 'Buscando conjuntos de esta oficina…'
                    : conjuntosExistentes.length
                      ? `${conjuntosExistentes.length} conjuntos en esta oficina. Elige el de esta computadora para no crear otro igual.`
                      : 'Esta oficina todavía no tiene conjuntos.'
                }
              />

              <DisponibilidadConjuntos registrando oficinaId={oficinaId} conjuntoId={conjuntoId} />
              {!conjuntoId ? (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="nombre-conjunto" className="text-sm font-semibold">
                    Nombre del conjunto nuevo
                  </label>
                  <input
                    id="nombre-conjunto"
                    value={nombreConjunto}
                    onChange={(evento) => setNombreConjunto(evento.target.value)}
                    placeholder="Computadora N°3"
                    className="h-[var(--spacing-control)] w-full rounded-[var(--radius-control)] border border-input bg-surface px-3"
                  />
                  {sugerenciaNombre.data?.nombre ? (
                    <p className="flex items-center gap-1.5 text-sm text-ai-strong">
                      <Sparkles size={14} aria-hidden="true" />
                      Sugerido por el sistema: {sugerenciaNombre.data.nombre}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          <Select
            etiqueta="Responsable"
            value={responsableId}
            onChange={(evento) => setResponsableId(evento.target.value)}
            placeholder="Sin responsable"
            opciones={(usuarios.data?.items ?? [])
              .filter((usuario) => usuario.activo)
              .map((usuario) => ({ valor: usuario.id, etiqueta: usuario.nombre }))}
            /* El directorio pide `usuarios.ver`. Si la cuenta no lo tiene, el
               desplegable salía vacío sin decir por qué, que es indistinguible de
               «esta oficina no tiene gente». La ficha de equipo ya lo decía; aquí
               faltaba. */
            ayuda={
              usuarios.isError
                ? 'No se pudieron cargar las personas de la oficina. Revisa los permisos de esta cuenta.'
                : oficinaId
                  ? 'Personas activas de la oficina elegida.'
                  : 'Elige la oficina para ver quién puede quedar a cargo.'
            }
          />

          <Select
            etiqueta="Propiedad"
            value={propiedad}
            onChange={(evento) => { setPropiedad(evento.target.value); setDuplicados([]); setDuplicadosConfirmados('') }}
            placeholder="Sin definir"
            opciones={[
              { valor: 'Propiedad de la municipalidad', etiqueta: 'MUNICIPALIDAD' },
              { valor: 'Personal', etiqueta: 'Personal' },
              { valor: 'Alquilado', etiqueta: 'Alquilado' },
              { valor: 'En comodato', etiqueta: 'En comodato' },
              { valor: 'Prestamo de proveedor', etiqueta: 'Préstamo de proveedor' },
            ]}
          />
        </div>
      ) : null}

      {paso === 'confirmar' ? (
        <Panel titulo="Revisa antes de guardar">
          {duplicados.length ? (
            <Nota tono="aviso" titulo="Hay equipos con el mismo código o dirección">
              <ul className="list-inside list-disc">
                {duplicados.map((equipo) => (
                  <li key={equipo.id}>
                    <Link className="font-semibold text-primary-strong hover:underline" to={`/panel/equipos/${equipo.id}`}>
                      {equipo.nombre} · {equipo.oficina_nombre || equipo.zona_nombre || 'Sin ubicación'}
                    </Link>
                    <span className="ml-1 text-muted-foreground">
                      Coincide en {equipo.coincide_en.map((campo) => ({
                        codigo_patrimonial: 'código',
                        direccion_ip: 'IP',
                        direccion_mac: 'MAC',
                      }[campo] ?? campo)).join(', ')}.
                    </span>
                  </li>
                ))}
              </ul>
              <p>Si es un equipo distinto, puedes continuar: el registro no se bloqueará.</p>
            </Nota>
          ) : null}
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <Dato etiqueta="Tipo" valor={tipo || '—'} />
            <Dato etiqueta="Marca" valor={marca ?? '—'} />
            <Dato etiqueta="Modelo" valor={modelo ?? '—'} />
            <Dato etiqueta="Nombre" valor={nombreEquipo || '—'} />
            <Dato etiqueta="Zona" valor={nombreZona ?? '—'} />
            <Dato etiqueta="Oficina" valor={oficinas.data?.items.find((o) => o.id === oficinaId)?.nombre ?? '—'} />
            {/*
              * Cuando la casilla está desmarcada sale «No aplica» sin mirar nada
              * más. Antes se miraba el nombre guardado, así que con la casilla
              * desmarcada pero el nombre puesto —que es lo que pasa al desmarcar,
              * porque la sugerencia lo rellena solo— la confirmación anunciaba un
              * conjunto que no se iba a guardar. Ahora la revisión no puede
              * contradecir lo que está marcado arriba.
              */}
            <Dato
              etiqueta="Conjunto"
              valor={
                !comoConjunto
                  ? 'No aplica'
                  : (nombreConjuntoElegido
                      ?? (conjuntoId ? 'Elegido' : (nombreConjunto.trim() || 'Sin elegir')))
              }
            />
            <Dato etiqueta="Responsable" valor={usuarios.data?.items.find((u) => u.id === responsableId)?.nombre ?? 'Sin asignar'} />
            <Dato etiqueta="Propiedad" valor={etiquetaPropiedad(propiedad) || 'Sin definir'} />
            <Dato etiqueta="Código" valor={esPersonal ? 'No aplica' : codigo || 'Sin código'} />
            {camposDinamicos.map((campo) => (
              <Dato key={campo} etiqueta={ETIQUETAS_CAMPOS[campo]} valor={campos[campo] || 'Sin definir'} />
            ))}
          </dl>

          <Nota tono="info" titulo="Los datos que faltan no bloquean" icono={<Monitor size={16} aria-hidden="true" />}>
            <p>
              El equipo se registra con lo que escribiste. Los campos vacíos quedan como «Pendiente» y se pueden
              completar después desde la ficha del equipo.
            </p>
          </Nota>
        </Panel>
      ) : null}

      <PiePasos
        paso={indicePaso + 1}
        total={PASOS.length}
        alAtras={indicePaso > 0 ? () => setPaso(PASOS[indicePaso - 1].clave) : undefined}
        alAdelante={indicePaso < PASOS.length - 1 ? () => setPaso(PASOS[indicePaso + 1].clave) : undefined}
        alEnviar={indicePaso === PASOS.length - 1 ? () => void guardar() : undefined}
        textoEnviar={duplicados.length ? 'Registrar de todos modos' : 'Guardar equipo'}
        enviando={enviando}
        puedeAdelantar={indicePaso === 0 ? Boolean(tipo) : true}
        puedeEnviar={
          // Marcar «es parte de un conjunto» sin elegir uno ni escribir su nombre
          // no puede pasar: se guardaría un equipo suelto con la casilla marcada,
          // que es la misma contradicción al revés.
          Boolean(tipo && zonaId && oficinaId && (!comoConjunto || conjuntoId || nombreConjunto.trim()))
        }
      />
    </div>
  )
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="truncate font-medium">{valor}</dd>
    </div>
  )
}
