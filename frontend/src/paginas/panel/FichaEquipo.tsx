    /** Ficha editable del inventario OTIC, con disponibilidad de cada dato. */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Check, CircleAlert, Copy, Pencil, Save, Trash2, Layers, UserRound } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useActivo, useCatalogoEquipos, useConjuntos, useEsquemaEquipo, useOficinas, useUsuarios, useZonas } from '../../api/hooks'
import { HistorialConjunto } from '../../componentes/dominio/HistorialConjunto'
import { DisponibilidadConjuntos } from '../../componentes/dominio/DisponibilidadConjuntos'
import type { ActivoDetalle, CuerpoActivoActualizar } from '../../api/tipos'
import { CompletitudBadge, DisponibilidadBadge } from '../../componentes/dominio/Badge'
import { AdvancedSection } from '../../componentes/dominio/AdvancedSection'
import { Button } from '../../componentes/base/Button'
import { Input, Select, Textarea } from '../../componentes/base/Campo'
import { ConfirmDialog } from '../../componentes/base/Sobreposiciones'
import { ErrorState, Nota, PageHeader, Panel, PantallaFormulario, SkeletonPanel } from '../../componentes/base/Estructura'
import { fechaCorta } from '../../dominio/formato'
import { useAvisos } from '../../estado/Avisos'
import { useSesion } from '../../estado/Sesion'
import { ZonaBadge } from '../../componentes/dominio/ZonaBadge'
import { IconoTipoEquipo } from '../../componentes/dominio/IconoTipoEquipo'
import { BarraProgreso } from '../../componentes/dominio/BarraProgreso'
import { TarjetaPerfil } from '../../componentes/dominio/TarjetaPerfil'
import { ICONOS_DATOS, IndicadorDato, PresentacionEquipo, ResumenDisponibilidad, estadoDatoEquipo } from '../../componentes/dominio/PresentacionEquipo'

const CAMPOS_OTIC = [
  { campo: 'nombre_equipo', etiqueta: 'Nombre del equipo', maximo: 160 },
  { campo: 'codigo_patrimonial', etiqueta: 'Código patrimonial', maximo: 60 },
  { campo: 'marca', etiqueta: 'Marca', maximo: 120 },
  { campo: 'modelo', etiqueta: 'Modelo', maximo: 120 },
  { campo: 'tamano_pantalla', etiqueta: 'Tamaño de pantalla', maximo: 60 },
  { campo: 'procesador', etiqueta: 'Procesador', maximo: 200 },
  { campo: 'memoria_ram', etiqueta: 'Memoria RAM', maximo: 200 },
  { campo: 'almacenamiento', etiqueta: 'Disco duro / almacenamiento', maximo: 200 },
  { campo: 'direccion_ip', etiqueta: 'Dirección IP', maximo: 45 },
  { campo: 'direccion_mac', etiqueta: 'Dirección MAC', maximo: 40 },
  { campo: 'propiedad', etiqueta: 'Propiedad', maximo: 60 },
  { campo: 'estado', etiqueta: 'Estado del equipo', maximo: 60 },
  { campo: 'observaciones', etiqueta: 'Observaciones', maximo: 4000 },
] as const

type CampoOtic = (typeof CAMPOS_OTIC)[number]['campo']
type FormularioEquipo = Record<CampoOtic | 'tipo' | 'oficina_id' | 'conjunto_id' | 'responsable_id', string>
type EquipoDuplicado = {
  id: string
  nombre: string
  oficina_nombre: string | null
  zona_nombre: string | null
  coincide_en: string[]
}

/**
 * Campos que no deberían aparecer en dos equipos.
 *
 * Avisar de ellos **no vuelve obligatorio rellenarlos**: el inventario viene de
 * un Excel de años y muchos equipos no tienen código ni IP, y hay Claim de
 * repuestos que comparten propósito. La advertencia dice «esto ya está en otro
 * equipo», que es información para decidir, no un bloqueo.
 */
const CAMPOS_UNICOS: CampoOtic[] = ['codigo_patrimonial', 'direccion_ip', 'direccion_mac']

const FORMULARIO_VACIO: FormularioEquipo = {
  tipo: '', oficina_id: '', conjunto_id: '', responsable_id: '', nombre_equipo: '', codigo_patrimonial: '',
  marca: '', modelo: '', tamano_pantalla: '', procesador: '', memoria_ram: '', almacenamiento: '',
  direccion_ip: '', direccion_mac: '', propiedad: '', estado: '', observaciones: '',
}

/**
 * La alarma de dato repetido.
 *
 * Es **una sola línea** y dice cuál se repite, con enlace a su ficha. Antes eran
 * tres cosas en dos sitios: el número («Repetido en 1»), una línea aparte debajo
 * («También en DESKTOP-LCFMHER. No es obligatorio.») y un recuadro grande arriba
 * con la lista entera. Una misma alarma, en tres formatos y en dos sitios.
 *
 * El ancho está acotado a propósito y el nombre se recorta con puntos: no se sale
 * de su columna por muy largo que sea el equipo, y el resto —todos los que
 * repiten, con su oficina, y que no bloquea nada— está en la explicación al pasar
 * el ratón.
 */
function AlertaRepetido({ repetido }: { repetido: EquipoDuplicado[] }) {
  const primero = repetido[0]
  const explicacion = [
    `Este valor ya está en ${repetido.length === 1 ? 'otro equipo' : `${repetido.length} equipos más`}:`,
    ...repetido.map((otro) => `· ${otro.nombre}${otro.oficina_nombre ? ` (${otro.oficina_nombre})` : ''}`),
    'No es obligatorio ni bloquea el registro.',
  ].join('\n')
  return (
    <span
      className="flex min-w-0 max-w-full items-center gap-1 self-start rounded-full border border-warning-borde bg-warning-soft py-0.5 pr-2 pl-1.5 text-2xs font-semibold text-warning-strong"
      title={explicacion}
    >
      <Copy size={11} aria-hidden="true" className="shrink-0" />
      <span className="shrink-0">Repetido en</span>
      <Link
        to={`/panel/equipos/${primero.id}`}
        className="min-w-0 truncate underline underline-offset-2 hover:no-underline"
        title={explicacion}
      >
        {primero.nombre}
      </Link>
      {repetido.length > 1 ? (
        <span className="shrink-0" title={explicacion}>+{repetido.length - 1}</span>
      ) : null}
    </span>
  )
}

function formularioDe(datos: ActivoDetalle): FormularioEquipo {
  const formulario = {
    ...FORMULARIO_VACIO,
    tipo: datos.tipo,
    oficina_id: datos.oficina_id ?? '',
    conjunto_id: datos.conjunto_id ?? '',
    responsable_id: datos.responsable_id ?? '',
  }
  for (const { campo } of CAMPOS_OTIC) formulario[campo] = datos[campo] ?? ''
  if (datos.tipo.toLocaleLowerCase('es') === 'impresora' && datos.campos?.direccion_ip?.motivo === 'Cable USB') formulario.direccion_ip = 'Cable USB'
  return formulario
}

/** Conserva valores importados que todavía no figuran en el catálogo. */
function opcionesConActual(valores: { valor: string; etiqueta: string; activo: boolean }[], actual: string) {
  const opciones = valores.filter((item) => item.activo).map(({ valor, etiqueta }) => ({ valor, etiqueta: etiqueta || valor }))
  if (actual && !opciones.some((item) => item.valor === actual)) opciones.unshift({ valor: actual, etiqueta: actual })
  return opciones
}

export function FichaEquipo() {
  const { id } = useParams<{ id: string }>()
  const navegar = useNavigate()
  const sesion = useSesion()
  const avisos = useAvisos()
  const consultas = useQueryClient()
  const equipo = useActivo(id)
  const oficinas = useOficinas()
  const zonas = useZonas({ solo_activas: false })
  const catalogos = useCatalogoEquipos()
  const [formulario, setFormulario] = useState<FormularioEquipo>(FORMULARIO_VACIO)
  const usuarios = useUsuarios({ ...(formulario.oficina_id ? { oficina_id: formulario.oficina_id } : {}), solo_activos: true, por_pagina: 200 })
  /*
    Los conjuntos de la oficina del equipo, para poder elegirlo desde aquí. Antes
    no había forma: si un equipo se registraba suelto y luego se caía en la
    cuenta de que era parte de una computadora, no había dónde colgarlo.

    Solo se piden cuando hay oficina, por lo mismo que en el alta: sin ella
    saldrían los 261 conjuntos del municipio, y el backend hace una consulta al
    inventario por conjunto.
  */
  const conjuntos = useConjuntos({ oficina_id: formulario.oficina_id }, Boolean(formulario.oficina_id))
  const [guardando, setGuardando] = useState(false)
  const [editando, setEditando] = useState(false)
  const [confirmarDescartar, setConfirmarDescartar] = useState(false)
  const [marcandoCampo, setMarcandoCampo] = useState<CampoOtic | null>(null)
  const [duplicados, setDuplicados] = useState<EquipoDuplicado[]>([])
  const [duplicadosConfirmados, setDuplicadosConfirmados] = useState('')
  const [quitarAvanzado, setQuitarAvanzado] = useState(false)
  const [confirmarEliminar, setConfirmarEliminar] = useState(false)
  const [eliminando, setEliminando] = useState(false)
  const editado = useRef(false)
  const fichaId = useRef<string | undefined>(undefined)
  const datos = equipo.data
  const esquema = useEsquemaEquipo(formulario.tipo || null)
  /*
    Solo se muestran los campos que el esquema del tipo declara. Si la consulta
    del esquema falla se muestran los trece campos: es preferible un formulario
    de más a uno que esconda un dato ya escrito, y arriba avisa del problema.
  */
  const camposVisibles = esquema.data
    ? CAMPOS_OTIC.filter(({ campo }) =>
        [...esquema.data.esperados, ...esquema.data.opcionales].includes(campo),
      )
    : CAMPOS_OTIC
  const puedeEditar = sesion.puede('equipos.editar')
  const puedeMarcarCampos = puedeEditar && sesion.puede('equipos.marcar_no_aplica')
  const puedeEditarAvanzados = puedeEditar && sesion.puede('equipos.opciones_avanzadas')

  useEffect(() => {
    if (datos) document.title = `${datos.nombre_equipo || datos.tipo} · Equipos`
  }, [datos])

  useEffect(() => {
    if (!datos) return
    // Marcar disponibilidad recarga la ficha sin borrar cambios aún sin guardar.
    if (fichaId.current === datos.id && editado.current) return
    fichaId.current = datos.id
    editado.current = false
    setFormulario(formularioDe(datos))
  }, [datos])

  /*
    Datos repetidos: se buscan sobre lo que hay en el formulario, con retardo.
    Antes el aviso solo salía al guardar, y para entonces ya se había escrito la
    ficha entera. Mirarlo mientras se escribe es lo que evita tener que volver
    atrás a corregirlo.

    Se consulta **el formulario**, no `datos`, para que avise tanto de lo ya
    guardado como de lo que se está tecleando ahora mismo.
  */
  const [repetidosFingerprint, setRepetidosFingerprint] = useState('')
  useEffect(() => {
    const actual = JSON.stringify([
      formulario.codigo_patrimonial.trim(),
      formulario.direccion_ip.trim(),
      formulario.direccion_mac.trim(),
    ])
    const temporizador = window.setTimeout(() => setRepetidosFingerprint(actual), 600)
    return () => window.clearTimeout(temporizador)
  }, [formulario.codigo_patrimonial, formulario.direccion_ip, formulario.direccion_mac])

  const repetidos = useQuery({
    queryKey: ['activos-repetidos', id, repetidosFingerprint],
    queryFn: async () => {
      const [codigo, ip, mac] = JSON.parse(repetidosFingerprint) as string[]
      const parametros = new URLSearchParams({ excluir_id: id ?? '' })
      if (codigo) parametros.set('codigo_patrimonial', codigo)
      if (ip) parametros.set('direccion_ip', ip)
      if (mac) parametros.set('direccion_mac', mac)
      const respuesta = await api.obtener<{ items: EquipoDuplicado[] }>(`/activos/duplicados?${parametros.toString()}`)
      return respuesta.items
    },
    enabled: Boolean(id) && repetidosFingerprint !== '["","",""]',
    staleTime: 5 * 60_000,
    retry: false,
  })

  const repetidosPorCampo = useMemo(() => {
    const mapa = new Map<CampoOtic, EquipoDuplicado[]>()
    for (const campo of CAMPOS_UNICOS) mapa.set(campo, [])
    for (const equipoRepetido of repetidos.data ?? []) {
      for (const campo of equipoRepetido.coincide_en) {
        if (mapa.has(campo as CampoOtic)) mapa.get(campo as CampoOtic)?.push(equipoRepetido)
      }
    }
    return mapa
  }, [repetidos.data])

  const cambiar = (campo: keyof FormularioEquipo, valor: string) => {
    editado.current = true
    if (campo === 'codigo_patrimonial' || campo === 'direccion_ip' || campo === 'direccion_mac') {
      setDuplicados([])
      setDuplicadosConfirmados('')
    }
    setFormulario((actual) => ({
      ...actual,
      [campo]: valor,
      // Al cambiar de oficina se sueltan el responsable y el conjunto, que son de
      // la oficina anterior. Si no, se guardaría un equipo de MERCADO con un
      // conjunto de PALACIO, y el backend lo rechaza con «el conjunto pertenece a
      // otra oficina».
      ...(campo === 'oficina_id' && valor !== actual.oficina_id ? { responsable_id: '', conjunto_id: '' } : {}),
    }))
  }

  const actualizarConsultas = async () => {
    await Promise.all([
      equipo.refetch(),
      ...[['activos'], ['calidad-inventario'], ['conjuntos'], ['equipos'], ['mi-perfil'], ['usuario'], ['usuarios'], ['oficina'], ['oficinas'], ['zona'], ['zonas'], ['campana'], ['analitica'], ['instalacion']].map((queryKey) => consultas.invalidateQueries({ queryKey })),
    ])
  }

  const guardar = async () => {
    if (!id || !puedeEditar || guardando) return
    if (formulario.tipo.trim().length < 2 || !formulario.oficina_id) {
      avisos.error('Indica el tipo de equipo y su oficina antes de guardar.')
      return
    }
    setGuardando(true)
    try {
      const parametros = new URLSearchParams()
      if (formulario.codigo_patrimonial.trim()) parametros.set('codigo_patrimonial', formulario.codigo_patrimonial.trim())
      if (formulario.direccion_ip.trim()) parametros.set('direccion_ip', formulario.direccion_ip.trim())
      if (formulario.direccion_mac.trim()) parametros.set('direccion_mac', formulario.direccion_mac.trim())
      parametros.set('excluir_id', id)
      const claveActual = JSON.stringify([
        formulario.codigo_patrimonial.trim(),
        formulario.direccion_ip.trim(),
        formulario.direccion_mac.trim(),
      ])
      const revisarDuplicados = Boolean(
        formulario.codigo_patrimonial.trim() || formulario.direccion_ip.trim() || formulario.direccion_mac.trim(),
      )
      if (revisarDuplicados && duplicadosConfirmados !== claveActual) {
        const respuesta = await api.obtener<{ items: EquipoDuplicado[] }>(`/activos/duplicados?${parametros.toString()}`)
        if (respuesta.items.length) {
          setDuplicados(respuesta.items)
          setDuplicadosConfirmados(claveActual)
          avisos.aviso('Posibles equipos duplicados', 'Revisa las fichas encontradas; si corresponde, guarda de todos modos.')
          return
        }
        setDuplicados([])
        setDuplicadosConfirmados(claveActual)
      }
      const cuerpo: CuerpoActivoActualizar = {
        tipo: formulario.tipo.trim(), oficina_id: formulario.oficina_id,
        // El conjunto se manda siempre, también cuando está vacío: mandarlo en
        // blanco es lo que **saca** al equipo del conjunto que tuviera, mientras
        // que omitirlo lo dejaría como estuviera.
        conjunto_id: /^(cpu|monitor|teclado|mouse|computadora|pc)$/i.test(formulario.tipo) ? formulario.conjunto_id || null : null,
        ...(formulario.responsable_id !== (datos?.responsable_id ?? '')
          ? { responsable_id: formulario.responsable_id || null } : {}),
      }
      // Enviar null permite borrar un dato; omitirlo conservaría el valor anterior.
      for (const { campo } of camposVisibles) cuerpo[campo] = formulario[campo].trim() || null
      await api.editar(`/activos/${id}`, cuerpo)
      editado.current = false
      await actualizarConsultas()
      avisos.exito('Equipo actualizado')
      setEditando(false)
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  const marcarCampo = async (campo: CampoOtic, estado: string) => {
    if (!id || !puedeMarcarCampos || marcandoCampo || guardando) return
    setMarcandoCampo(campo)
    try {
      await api.crear(`/activos/${id}/campos`, { campos: [campo], estado, motivo: 'Actualizado desde la ficha del equipo' })
      await actualizarConsultas()
      avisos.exito('Disponibilidad del dato actualizada')
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setMarcandoCampo(null)
    }
  }

  /*
    Tickets de este equipo.

    El enlace sí filtraba —el backend acepta `activo_id`—, pero tenía dos fallos.
    El primero es que no decía cuántos son. El segundo es peor: contaba **todos**
    los tickets y enlazaba a la bandeja de **abiertos**, así que un equipo con un
    ticket ya cerrado prometía «1 ticket» y al seguirlo se veía una lista vacía.
    Eso es exactamente lo que hace que un enlace así parezca un enlace roto.

    Ahora se cuentan las dos cosas por separado y cada número lleva a la lista
    donde ese número es cierto: los abiertos a la bandeja, los cerrados al
    historial cerrado. El enlace de cerrados lleva `?vista=cerrados` porque esa
    página abre en «Casos críticos» y, sin ese parámetro, un ticket ya cerrado
    que no es crítico no sale: el enlace llevaría a otra lista vacía.
  */
  const ticketsEquipo = useQuery({
    queryKey: ['activos-tickets', id],
    queryFn: async () => {
      const [todos, abiertos] = await Promise.all([
        api.obtener<{ total: number }>(`/tickets?activo_id=${id ?? ''}&por_pagina=1`),
        api.obtener<{ total: number }>(`/tickets?activo_id=${id ?? ''}&por_pagina=1&solo_abiertos=1`),
      ])
      return { total: todos.total, abiertos: abiertos.total, cerrados: Math.max(0, todos.total - abiertos.total) }
    },
    enabled: Boolean(id),
    staleTime: 60_000,
    retry: false,
  })

  const conteo = ticketsEquipo.data

  /*
    Los dos números, con distinta jerarquía.

    Antes eran dos líneas del mismo peso: «Ver los 1 tickets abiertos de este
    equipo» y «1 ticket en el historial cerrado». La primera—sobre la que hay que
    actuar— pesaba lo mismo que el historial. Y el plural salía mal: «los 1
    tickets».

    Ahora un ticket abierto es una fila marcada, porque es lo pendiente; el
    historial cerrado es una línea discreta, porque ya pasó. Con cero abiertos se
    dice con palabras y se da por bien, en vez de dejar una línea vacía al lado de
    un enlace.
  */
  const bloqueTickets = ticketsEquipo.isLoading ? (
    <p className="text-sm text-muted-foreground">Buscando los tickets de este equipo…</p>
  ) : !conteo?.total ? (
    <p className="text-sm text-muted-foreground">
      Este equipo no tiene ningún ticket, que es lo normal: la mayor parte del inventario nunca ha generado uno.
    </p>
  ) : (
    <div className="flex flex-col gap-2">
      {conteo.abiertos ? (
        <Link
          to={`/panel/tickets?activo_id=${id}`}
          className="flex items-center gap-2.5 rounded-[var(--radius-control)] border border-warning-borde bg-warning-soft px-3 py-2 transition-colors hover:bg-warning-soft/70"
        >
          <CircleAlert size={15} className="shrink-0 text-warning-strong" aria-hidden="true" />
          <span className="min-w-0 flex-1 text-sm font-medium text-warning-strong">
            {conteo.abiertos === 1 ? '1 ticket abierto' : `${conteo.abiertos} tickets abiertos`}
          </span>
          <span className="shrink-0 text-2xs font-semibold text-warning-strong">Ver</span>
        </Link>
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Check size={14} className="shrink-0 text-success-strong" aria-hidden="true" />
          Sin tickets abiertos
        </p>
      )}
      {conteo.cerrados && !datos?.responsable_id ? <HistorialConjunto estado="cerrado" equipoId={datos?.id} nombre={datos?.nombre_equipo || datos?.tipo} etiqueta={`${conteo.cerrados} ${conteo.cerrados === 1 ? 'caso cerrado' : 'casos cerrados'} en el historial`} /> : conteo.cerrados ? (
        <Link
          to={`/panel/usuarios/${datos?.responsable_id}?tab=tickets&activo_id=${id}&estado=cerrado`}
          className="text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          {conteo.cerrados === 1 ? '1 caso cerrado' : `${conteo.cerrados} casos cerrados`}{' '}
          <span className="text-2xs">en el historial</span>
        </Link>
      ) : null}
    </div>
  )

  /*
    Las oficinas se agrupan por zona dentro del desplegable.

    Antes todas iban en una lista plana con el texto «OFICINA · ZONA». Con dos
    palabras en mayúsculas y un punto de separación, no se veía dónde acababa una
    y empezaba la otra: parecía un solo nombre largo. Ahora la zona es un
    encabezado con su color —el mismo que lleva la pastilla en el resto de la
    aplicación— y debajo van solo los nombres de oficina, que es lo que se busca
    al elegir.

    La oficina actual se cuela en su grupo si el filtro de zonas la dejó fuera: si
    no, su valor no estaría en la lista y el selector mostraría el hueco en blanco.

    Esto va **antes** de los `return` de carga y de error porque son `useMemo`:
    un hook que solo se ejecuta a veces rompe el orden de los hooks y deja la
    página en blanco.
  */
  const zonasPorId = useMemo(
    () => new Map((zonas.data?.items ?? []).map((zona) => [zona.id, zona])),
    [zonas.data],
  )

  const oficinasAgrupadas = useMemo(() => {
    const grupos = new Map<string, { etiqueta: string; color?: string; opciones: { valor: string; etiqueta: string }[] }>()
    grupos.set('', { etiqueta: 'Sin zona', opciones: [] })
    for (const oficina of oficinas.data?.items ?? []) {
      const zona = zonasPorId.get(oficina.zona_id)
      const clave = zona?.id ?? ''
      if (!grupos.has(clave)) {
        grupos.set(clave, {
          etiqueta: zona?.nombre || 'Sin zona',
          color: zona?.color_indice ? `var(--zona-${zona.color_indice})` : undefined,
          opciones: [],
        })
      }
      grupos.get(clave)!.opciones.push({ valor: oficina.id, etiqueta: oficina.nombre })
    }
    for (const grupo of grupos.values()) {
      grupo.opciones.sort((a, b) => a.etiqueta.localeCompare(b.etiqueta, 'es'))
    }
    return [...grupos.values()].filter((grupo) => grupo.opciones.length)
  }, [oficinas.data, zonasPorId])

  const opcionesOficinas = useMemo(() => {
    if (!formulario.oficina_id || oficinasAgrupadas.some((g) => g.opciones.some((o) => o.valor === formulario.oficina_id))) {
      return oficinasAgrupadas
    }
    const zona = zonasPorId.get(datos?.zona_id ?? '')
    return [
      ...oficinasAgrupadas,
      {
        etiqueta: zona?.nombre || 'Oficina actual',
        color: zona?.color_indice ? `var(--zona-${zona.color_indice})` : undefined,
        opciones: [{ valor: formulario.oficina_id, etiqueta: datos?.oficina_nombre || 'Oficina actual' }],
      },
    ]
  }, [oficinasAgrupadas, zonasPorId, formulario.oficina_id, datos])

  /*
    La pastilla de zona sigue a la **oficina elegida**, no a la que está
    guardada. Con la zona fija, cambiar de oficina a otra de otra zona dejaba la
    pastilla diciendo la zona antigua mientras el selector decía otra cosa: dos
    verdades distintas en la misma fila.
  */
  const zonaElegida = useMemo(() => {
    const oficina = (oficinas.data?.items ?? []).find((item) => item.id === formulario.oficina_id)
    if (oficina) return zonasPorId.get(oficina.zona_id)
    // Si el filtro no trajo la oficina actual, se usa la zona del registro.
    return zonasPorId.get(datos?.zona_id ?? '')
  }, [oficinas.data, zonasPorId, formulario.oficina_id, datos])

  if (equipo.isLoading) return <SkeletonPanel filas={6} />
  if (equipo.isError || !datos) {
    return <ErrorState mensaje="No pudimos cargar la ficha del equipo."
      detalle={equipo.error instanceof Error ? equipo.error.message : undefined} alReintentar={() => void equipo.refetch()} />
  }

  const responsables = (usuarios.data?.items ?? [])
    .filter((usuario) => usuario.activo && usuario.oficina_id === formulario.oficina_id)
    .map((usuario) => ({ valor: usuario.id, etiqueta: usuario.nombre }))
  if (formulario.responsable_id && !responsables.some((item) => item.valor === formulario.responsable_id)) {
    responsables.unshift({ valor: formulario.responsable_id, etiqueta: datos.responsable_nombre || 'Responsable actual' })
  }
  const marcaModelo = (['marca', 'modelo'] as const).filter(campo => estadoDatoEquipo(datos, campo) === 'completo').map(campo => datos[campo]).filter(Boolean).join(' ')

  return (
    <PantallaFormulario>
      <PageHeader titulo="Ficha del equipo"
        descripcion={<>{datos.oficina_id && sesion.puede('org.ver') ? <Link to={`/panel/oficinas/${datos.oficina_id}`} className="text-info-strong hover:underline">{datos.oficina_nombre || 'Ver oficina'}</Link> : 'Sin oficina'} · {datos.zona_nombre || 'Sin zona'}</>}
        migas={[{ texto: 'Panel', enlace: '/panel' }, { texto: 'Equipos', enlace: '/panel/equipos' }, { texto: 'Ficha' }]}
        acciones={
          <>
            {puedeEditar ? <Button variante={editando ? 'secundario' : 'primario'} icono={<Pencil size={16} aria-hidden="true" />} disabled={guardando} onClick={() => {
              if (editando && editado.current) { setConfirmarDescartar(true); return }
              editado.current = false
              setFormulario(formularioDe(datos))
              setEditando(!editando)
            }}>{editando ? 'Volver a presentación' : 'Editar equipo'}</Button> : null}
            {sesion.puede('equipos.eliminar') ? <Button variante="fantasma" tamano="sm" soloIcono aria-label="Eliminar equipo" title="Eliminar equipo" className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive-strong" icono={<Trash2 size={16} aria-hidden="true" />} disabled={guardando || eliminando} onClick={() => setConfirmarEliminar(true)} /> : null}
            <Button asChild variante="secundario"><Link to="/panel/equipos" className="flex items-center gap-2">
              <ArrowLeft size={16} aria-hidden="true" />Volver
            </Link></Button>
          </>
        } />

      <TarjetaPerfil
        titulo={datos.nombre_equipo || datos.tipo}
        subtitulo={
          /* El tipo va primero y en su propia pieza. Con nombres como «PRINTGDS» o
             «DESKTPO-AOAAH4T» el nombre no dice qué es, y el icono —que sí lo dice—
             no se lee de lejos. Antes el subtítulo era marca, modelo y oficina, y el
             tipo no aparecía en ningún sitio de la pantalla. */
          <>
            <span className="font-semibold text-foreground">{datos.tipo}</span>
            {marcaModelo ? ` · ${marcaModelo}` : ''}
            {' · '}{datos.oficina_id && sesion.puede('org.ver') ? <Link to={`/panel/oficinas/${datos.oficina_id}`} className="text-info-strong hover:underline">{datos.oficina_nombre || 'Ver oficina'}</Link> : datos.oficina_nombre || 'Sin oficina'}
          </>
        }
        icono={<IconoTipoEquipo tipo={datos.tipo} tamano={30} />}
        colorIndice={zonas.data?.items.find((zona) => zona.id === datos.zona_id)?.color_indice}
        metricas={[
          { etiqueta: 'Tipo', valor: datos.tipo },
          { etiqueta: 'Estado', valor: <DisponibilidadBadge estado={datos.estado} /> },
          { etiqueta: 'Completitud', valor: <CompletitudBadge porcentaje={datos.completitud} faltantes={datos.faltantes} /> },
          { etiqueta: 'Responsable', valor: datos.responsable_id && sesion.puede('usuarios.ver') ? <Link to={`/panel/usuarios/${datos.responsable_id}`} className="text-info-strong hover:underline">{datos.responsable_nombre || 'Ver responsable'}</Link> : datos.responsable_nombre || 'Uso común' },
        ]}
      />
      <BarraProgreso etiqueta="Completitud del inventario" valor={datos.completitud} />
      <DisponibilidadConjuntos equipoActualId={datos.id} oficinaId={formulario.oficina_id || datos.oficina_id} conjuntoId={formulario.conjunto_id || undefined} />

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel titulo={editando ? 'Editar datos del equipo' : 'Información del equipo'} descripcion="Ubicación, responsable y características registradas en el inventario.">
          {puedeEditar && editando ? (
            <form onSubmit={(evento) => { evento.preventDefault(); void guardar() }} className="flex flex-col gap-4">
              {esquema.isError ? (
                <Nota tono="aviso" titulo="No se pudo cargar el esquema de campos">
                  <p>{esquema.error instanceof Error ? esquema.error.message : 'Se muestran todos los campos disponibles.'}</p>
                </Nota>
              ) : null}
              {/*
                Aviso de duplicados **antes de guardar**. Antes era un recuadro
                grande con la lista completa; ahora es una línea con la misma
                alarma del panel de disponibilidad, porque es el mismo dato dicho
                dos veces en dos formatos distintos.

                No se quita sin más: este avisa de lo que se acaba de escribir, que
                todavía no está guardado, y sin él se guardaría a ciegas.
              */}
              {duplicados.length ? (
                <p className="flex min-w-0 items-center gap-1.5 text-sm text-warning-strong">
                  <AlertTriangle size={14} aria-hidden="true" className="shrink-0" />
                  <span className="min-w-0">
                    {`Repetido en ${duplicados.length === 1 ? '' : `${duplicados.length} equipos`} `}
                    {duplicados.map((equipo, indice) => (
                      <span key={equipo.id}>
                        {indice > 0 ? ', ' : ''}
                        <Link
                          className="font-semibold underline underline-offset-2 hover:no-underline"
                          to={`/panel/equipos/${equipo.id}`}
                          title={`${equipo.nombre}${equipo.oficina_nombre ? ` · ${equipo.oficina_nombre}` : ''}`}
                        >
                          {equipo.nombre}
                        </Link>
                      </span>
                    ))}
                    . Puedes guardar igual.
                  </span>
                </p>
              ) : null}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Select etiqueta="Tipo de equipo" requerido value={formulario.tipo} disabled={guardando}
                  onChange={(evento) => cambiar('tipo', evento.target.value)}
                  opciones={opcionesConActual(catalogos.data?.tipos_dispositivo ?? [], formulario.tipo)} />
                {/*
                  La zona va debajo de su propio selector, no suelta en una celda
                  de la retícula. Antes ocupaba la casilla de al lado del tipo de
                  equipo y dejaba un hueco debajo del selector: la fila quedaba
                  desalineada y la zona, que es parte de la ubicación, parecía un
                  dato suelto sin dueño. Aquí acompaña a la oficina, que es de
                  donde se deduce.
                */}
                <Select etiqueta="Oficina y zona" requerido value={formulario.oficina_id} disabled={guardando}
                  onChange={(evento) => cambiar('oficina_id', evento.target.value)} grupos={opcionesOficinas}
                  ayuda={<span className="flex flex-wrap items-center gap-1.5">Zona:<ZonaBadge id={zonaElegida?.id} nombre={zonaElegida?.nombre} /></span>} />
                <Select etiqueta="Responsable" value={formulario.responsable_id} disabled={guardando || usuarios.isLoading}
                  onChange={(evento) => cambiar('responsable_id', evento.target.value)} placeholder="Sin responsable"
                  ayuda={usuarios.isError ? 'No se pudo cargar el directorio de responsables.' : 'Personas activas de la oficina seleccionada.'}
                  opciones={responsables} />
                {/*
                  El conjunto, que antes no se podía cambiar desde aquí. Va junto a
                  la oficina porque es de donde sale: solo se ofrecen los conjuntos
                  de esa oficina, cada uno con su número de equipos, que es lo que
                  hace falta para saber cuál es el de esta computadora.
                */}
                <Select
                  etiqueta="Conjunto"
                  value={formulario.conjunto_id}
                  disabled={guardando || !formulario.oficina_id || !/^(cpu|monitor|teclado|mouse|computadora|pc)$/i.test(formulario.tipo)}
                  onChange={(evento) => cambiar('conjunto_id', evento.target.value)}
                  placeholder="Sin conjunto"
                  opciones={(conjuntos.data?.items ?? []).map((conjunto) => ({
                    valor: conjunto.id,
                    etiqueta: `${conjunto.nombre} · ${conjunto.total_activos} ${conjunto.total_activos === 1 ? 'equipo' : 'equipos'}`,
                  }))}
                  ayuda={
                    !formulario.oficina_id
                      ? 'Elige antes la oficina: los conjuntos son de una oficina.'
                      : conjuntos.isError
                        ? 'No se pudieron cargar los conjuntos de esta oficina.'
                        : conjuntos.data?.items.length
                          ? `${conjuntos.data.items.length} conjuntos en esta oficina.`
                          : 'Esta oficina todavía no tiene conjuntos.'
                  }
                />
                {camposVisibles.filter(({ campo }) => campo !== 'observaciones').map(({ campo, etiqueta, maximo }) => (
                  campo === 'estado' || campo === 'propiedad' ? (
                    <Select key={campo} etiqueta={etiqueta} value={formulario[campo]} disabled={guardando}
                      onChange={(evento) => cambiar(campo, evento.target.value)} placeholder="Sin definir"
                      opciones={opcionesConActual(campo === 'estado' ? catalogos.data?.estados_activo ?? [] : catalogos.data?.propiedades ?? [], formulario[campo])} />
                  ) : (
                    <Input key={campo} etiqueta={etiqueta} value={formulario[campo]} maxLength={maximo} disabled={guardando}
                      acciones={campo === 'direccion_ip' && formulario.tipo.toLocaleLowerCase('es') === 'impresora' ? <Button tamano="sm" disabled={guardando} onClick={() => cambiar('direccion_ip', 'Cable USB')}>Cable USB</Button> : undefined}
                      onChange={(evento) => cambiar(campo, evento.target.value)} />
                  )
                ))}
              </div>
              {camposVisibles.some(({ campo }) => campo === 'observaciones') ? (
                <Textarea etiqueta="Observaciones" value={formulario.observaciones} filas={5} maxLength={4000} disabled={guardando}
                  onChange={(evento) => cambiar('observaciones', evento.target.value)} ayuda="Incluye las anotaciones importadas desde el Excel." />
              ) : null}
              <div className="flex justify-end">
                <Button type="submit" variante="primario" cargando={guardando} disabled={marcandoCampo !== null} icono={<Save size={16} aria-hidden="true" />}>
                  {duplicados.length ? 'Guardar de todos modos' : 'Guardar cambios'}
                </Button>
              </div>
            </form>
          ) : (
            <PresentacionEquipo datos={datos} campos={camposVisibles} />
          )}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel titulo="Disponibilidad de los datos" descripcion={editando ? 'No aplica y No disponible se excluyen de la completitud.' : undefined} className="shadow-sm">
            <ResumenDisponibilidad datos={datos} campos={camposVisibles} />
            {/*
              Aviso de datos repetidos.

              Aquí había **dos** avisos y sobraba uno: un recuadro grande arriba del
              todo, «Hay datos que ya están en otro equipo», con la lista de cada
              coincidencia, y luego en cada campo una línea «También en X. No es
              obligatorio.» El primero ocupaba media pantalla y repetía lo que el
              segundo ya decía junto al campo, que es donde se mira.

              Ahora solo queda la alarma del campo. Dice **cuál** se repite —con
              enlace a su ficha— y lleva el resto en la explicación, así que no
              ocupa sitio. Sigue siendo un aviso y no un error: el código, la IP y
              la MAC no se obligan a rellenar nunca, porque el inventario viene de
              un Excel de años donde muchos equipos no los tienen.
            */}
            <ul className="flex flex-col gap-3">
              {camposVisibles.map(({ campo, etiqueta }) => {
                const info = datos.campos?.[campo]
                const estadoReal = estadoDatoEquipo(datos, campo)
                const estado = estadoReal === 'completo' ? 'pendiente' : estadoReal
                const registrado = estadoReal === 'completo'
                const IconoCampo = ICONOS_DATOS[campo]
                const repetido = repetidosPorCampo.get(campo) ?? []
                return (
                  <li key={campo} className="flex flex-col gap-1.5 border-b border-border pb-3 last:border-0 last:pb-0">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="flex min-w-0 items-center gap-2 text-sm font-medium">{IconoCampo ? <IconoCampo size={15} className="shrink-0 text-info-strong" aria-hidden="true" /> : null}{etiqueta}</span>
                      <div className="flex items-center gap-1.5">
                        {editando && puedeMarcarCampos ? (
                          <select aria-label={`Disponibilidad: ${etiqueta}`} value={estado} disabled={marcandoCampo !== null || guardando}
                            onChange={(evento) => void marcarCampo(campo, evento.target.value)}
                            className="max-w-full rounded-[var(--radius-control)] border border-input bg-surface px-2 py-1 text-sm disabled:opacity-60">
                            <option value="pendiente">{registrado ? 'Dato registrado' : 'Pendiente'}</option>
                            <option value="no_aplica">No aplica</option>
                            <option value="no_disponible">No disponible</option>
                          </select>
                        ) : <IndicadorDato estado={estadoReal} />}
                      </div>
                    </div>
                    {/* La alarma va en su propia línea, no junto al desplegable. Esa
                        columna mide 327 px y el desplegable se come 130: al lado,
                        el nombre del otro equipo se cortaba en «Computador…», que es
                        justo lo que había que evitar. Debajo tiene todo el ancho y
                        además se puede acotar con `max-w` para que un nombre enorme
                        no empuje nada. */}
                    {repetido.length ? <AlertaRepetido repetido={repetido} /> : null}
                    {info?.motivo ? <p className="text-2xs text-muted-foreground">{info.motivo}</p> : null}
                    {info?.nota ? <p className="whitespace-pre-wrap text-2xs text-muted-foreground">{info.nota}</p> : null}
                  </li>
                )
              })}
            </ul>
          </Panel>

          <Panel titulo="Asignación y registro">
            <div className="mb-4 flex min-w-0 items-center gap-3 border-b border-border pb-4"><span className="rounded-xl bg-info-soft p-2.5 text-info-strong"><Layers size={23} /></span><div className="min-w-0"><p className="text-xs text-muted-foreground">Forma parte de</p><p className="truncate font-semibold" title={datos.conjunto_nombre || undefined}>{datos.conjunto_nombre || 'Equipo independiente'}</p></div></div>
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <Dato etiqueta="Número de equipo en el conjunto" valor={datos.numero_equipo ? `N°${datos.numero_equipo}` : 'Sin conjunto'} />
              <div className="min-w-0"><span className="flex items-center gap-1 text-xs text-muted-foreground"><UserRound size={13} /> A cargo de</span>{datos.responsable_id ? <Link to={`/panel/usuarios/${datos.responsable_id}`} className="font-semibold text-primary-strong hover:underline">{datos.responsable_nombre}</Link> : <span className="font-medium">{datos.oficina_nombre ? 'La oficina · uso compartido' : 'Sin responsable asignado'}</span>}</div>
              <Dato etiqueta="Uso común" valor={datos.uso_comun ? 'Sí' : 'No'} />
              <Dato etiqueta="Registrado" valor={fechaCorta(datos.creado_en)} />
            </dl>
            <div className="mt-3">{bloqueTickets}</div>
            <div className="mt-3 flex flex-wrap gap-1 border-t border-border pt-3"><HistorialConjunto equipoId={datos.id} nombre={datos.nombre_equipo || datos.tipo} /><HistorialConjunto id={datos.conjunto_id} nombre={datos.conjunto_nombre} /></div>
          </Panel>

          {datos.opciones_avanzadas ? (
            <AdvancedSection key={datos.id} detalleActual={datos.detalle_avanzado} titulo="Opciones avanzadas" descripcion="Detalle técnico del equipo."
              equipoId={datos.id} tipo={datos.tipo} puedeEditar={editando && puedeEditarAvanzados}
              alQuitar={() => setQuitarAvanzado(true)} alActualizar={() => void actualizarConsultas()} />
          ) : null}
        </div>
      </div>

      <ConfirmDialog abierto={confirmarDescartar} alCerrar={() => setConfirmarDescartar(false)} titulo="Descartar cambios" mensaje="Volverás a la presentación sin guardar los cambios." textoConfirmar="Descartar cambios" peligro alConfirmar={() => { editado.current = false; setFormulario(formularioDe(datos)); setEditando(false); setConfirmarDescartar(false) }} />
      <ConfirmDialog abierto={confirmarEliminar} alCerrar={() => { if (!eliminando) setConfirmarEliminar(false) }}
        titulo="Eliminar equipo"
        mensaje={`Se quitará «${datos.nombre_equipo || datos.tipo}» del inventario activo. Su historial se conservará. Si tiene tickets abiertos, primero deberás resolverlos. Los cambios sin guardar se descartarán.`}
        textoConfirmar="Eliminar equipo" peligro cargando={eliminando}
        alConfirmar={async () => {
          if (eliminando || !sesion.puede('equipos.eliminar')) return
          setEliminando(true)
          try {
            await api.borrar(`/activos/${datos.id}`)
            setConfirmarEliminar(false)
            navegar('/panel/equipos', { replace: true })
            consultas.removeQueries({ queryKey: ['activo', datos.id] })
            await consultas.invalidateQueries()
            avisos.exito('Equipo eliminado del inventario')
          } catch (fallo) { avisos.desdeError(fallo) }
          finally { setEliminando(false) }
        }} />
      <ConfirmDialog abierto={quitarAvanzado} alCerrar={() => setQuitarAvanzado(false)}
        alConfirmar={async () => {
          if (!puedeEditarAvanzados) return
          setQuitarAvanzado(false)
          try {
            await api.borrar(`/activos/${datos.id}/detalle-avanzado`)
            await actualizarConsultas()
            avisos.exito('Datos avanzados eliminados')
          } catch (fallo) { avisos.desdeError(fallo) }
        }}
        titulo="Eliminar los datos avanzados" mensaje="Se eliminará el detalle técnico avanzado de este equipo."
        textoConfirmar="Eliminar" peligro />

      {!puedeEditar ? <Nota tono="info"><p>Tu permiso es de lectura: puedes ver la ficha pero no modificarla.</p></Nota> : null}
    </PantallaFormulario>
  )
}

function Dato({ etiqueta, valor, enlace }: { etiqueta: string; valor: string | null | undefined; enlace?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="whitespace-pre-wrap break-words font-medium">{enlace ? <Link className="text-primary-strong hover:underline" to={enlace}>{valor || '—'}</Link> : valor || '—'}</dd>
    </div>
  )
}
