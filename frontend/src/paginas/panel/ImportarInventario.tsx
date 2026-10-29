import { LimpiarRegistros } from '../../componentes/dominio/LimpiarRegistros'
/** Importación de inventario: cada hoja representa una zona. */

import { ArrowLeft, CircleAlert, FileSpreadsheet, RotateCcw, TriangleAlert, Upload } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../api/cliente'
import { useEstadoImportacion } from '../../api/hooks'
import { Input, Select } from '../../componentes/base/Campo'
import { Paginacion } from '../../componentes/dominio/DataTable'
import { PiePasos, Stepper } from '../../componentes/base/Stepper'
import { Button } from '../../componentes/base/Button'
import { Panel, Nota, EmptyState, PantallaFormulario } from '../../componentes/base/Estructura'
import { cn } from '../../lib/cn'
import { fechaCorta, numero } from '../../dominio/formato'
import { useAvisos } from '../../estado/useAvisos'
import { useSesion } from '../../estado/useSesion'

const PASOS = [
  { clave: 'archivo', titulo: 'Archivo' },
  { clave: 'previsualizar', titulo: 'Previsualizar' },
  { clave: 'confirmar', titulo: 'Resultado' },
]

/**
 * Filas por página en la previsualización.
 *
 * Antes no había paginación: se pintaban 100 y se informaba con «Muestra de 100
 * de 875», sin forma de llegar a las otras 775. Verificar una importación es el
 * motivo de esta pantalla, así que la lista tiene que poder recorrerse entera.
 */
const POR_PAGINA = 100

/** El backend escribe `crear`/`actualizar`/`omitir`; aquí se pone en palabras. */
const ACCION: Record<string, string> = {
  crear: 'Se creará',
  actualizar: 'Se actualizará',
  omitir: 'Se omitirá',
}

const TONO_ACCION: Record<string, string> = {
  crear: 'bg-primary-soft text-primary-strong',
  actualizar: 'bg-muted text-foreground',
  omitir: 'bg-muted text-muted-foreground',
}

type Hoja = { nombre_hoja: string; zona_nombre: string; filas: number; oficinas: string[] }
type Lote = {
  lote_id: string
  nombre_archivo: string
  estado: string
  analisis: { hojas: Hoja[]; columnas_por_hoja: Record<string, string[]> }
  reversible: boolean
}
type Fila = {
  hoja: string
  numero: number
  zona_nombre: string
  oficina_nombre: string
  tipo: string
  grupo_crudo: string
  codigo_patrimonial: string | null
  advertencias: string[]
  errores: string[]
  accion: string
  [campo: string]: unknown
}
type Previsualizacion = {
  lote_id: string
  filas: Fila[]
  total_filas: number
  validas: number
  con_error: number
  con_advertencia: number
  crearia: number
  actualizaria: number
  omitiria: number
}
type Resultado = {
  creados: number
  actualizados: number
  omitidos: number
  errores: number
  detalle: string[]
  reversible: boolean
  /** Estructura que la importación creó por el camino. El backend la devuelve y
      no se mostraba en ninguna parte: si el archivo trae una zona que no
      existía, se creaba sin que nadie se enterara. */
  zonas_creadas?: number
  oficinas_creadas?: number
  conjuntos_creados?: number
}
type DetalleResponsable = {
  clave: string
  usuario_id?: string
  nombre_excel: string
  nombre_asignado: string | null
  accion: 'creado' | 'vinculado'
  oficina_nombre: string | null
  zona_nombre: string | null
  coincidencia: 'exacta' | 'parecida' | null
  similitud: number | null
  equipos: number
  nombre_parece_oficina: boolean
}
type ResultadoResponsables = {
  personas_creadas: number
  equipos_vinculados: number
  detalle: DetalleResponsable[]
}
type GrupoResponsableExcel = {
  clave: string
  oficina_id: string
  oficina_nombre: string
  nombre_original: string
  nombres_originales: string[]
  equipos: number
  candidatos: { id: string; nombre: string; coincidencia: 'exacta' | 'parecida'; similitud: number }[]
}

export function ImportarInventario() {
  const avisos = useAvisos()
  const historial = useEstadoImportacion()
  const sesion = useSesion()
  const archivoRef = useRef<HTMLInputElement>(null)
  const [paso, setPaso] = useState('archivo')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [lote, setLote] = useState<Lote | null>(null)
  const [vista, setVista] = useState<Previsualizacion | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [hojaVista, setHojaVista] = useState('')
  const [subiendo, setSubiendo] = useState(false)
  const [aplicando, setAplicando] = useState(false)
  const [deshaciendo, setDeshaciendo] = useState(false)
  const [descargando, setDescargando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gruposResponsables, setGruposResponsables] = useState<GrupoResponsableExcel[]>([])
  const [seleccionesResponsables, setSeleccionesResponsables] = useState<Record<string, string>>({})
  const [confirmandoResponsables, setConfirmandoResponsables] = useState(false)
  const [resultadoResponsables, setResultadoResponsables] = useState<ResultadoResponsables | null>(null)
  const [busquedaPersona, setBusquedaPersona] = useState('')
  const [paginaPersona, setPaginaPersona] = useState(1)
  const [responsablesRevisados, setResponsablesRevisados] = useState(false)
  const [paginaPedida, setPaginaPedida] = useState(1)
  /* Cuando se decide no vincular a nadie del Excel, el bloque desaparece pero
     los equipos se quedan como estaban. Hay que decirlo, o parece que el paso
     se resolvió solo. */
  const [responsablesOmitidos, setResponsablesOmitidos] = useState(false)
  /* Qué regla global eligió la persona: ninguna, crear lo que falta, o no
     vincular a nadie. Las dos reglas son contradictorias, así que una sola. */
  const [decision, setDecision] = useState<'ninguno' | 'crear' | 'nadie'>('ninguno')

  /*
    El titular y la frase del resultado, en palabras.

    «Inventario importado» con «Se crearon 0 equipos y se actualizaron 875»
    debajo se leía como un fallo: un 0 en «creados» parece que no se hizo nada,
    cuando lo que pasó es lo normal en una reimportación. El titular ahora lleva
    los dos números y la frase dice qué pasó con cada grupo de filas.
  */
  const tituloResultado = !resultado
    ? ''
    : resultado.errores
      ? 'La importación terminó con errores'
      : resultado.creados === 0 && resultado.actualizados > 0
        ? `Se actualizaron ${numero(resultado.actualizados)} equipos que ya estaban`
        : resultado.actualizados === 0 && resultado.creados > 0
          ? `Se crearon ${numero(resultado.creados)} equipos nuevos`
          : `${numero(resultado.creados + resultado.actualizados)} equipos importados`

  /*
    La línea de debajo del titular.

    Cuando solo pasa una cosa, el titular ya la dice y repetirla es ruido: se
    veía «Se actualizaron 875 equipos que ya están» seguido de «875
    actualizados». Con dos o más grupos de filas sí aporta, porque entonces el
    titular lleva la suma y la línea el desglose.
  */
  const detalleResultado = !resultado
    ? ''
    : (() => {
        const partes: string[] = []
        if (resultado.creados > 0) partes.push(`${numero(resultado.creados)} nuevos`)
        if (resultado.actualizados > 0) partes.push(`${numero(resultado.actualizados)} actualizados`)
        if (resultado.omitidos > 0) partes.push(`${numero(resultado.omitidos)} omitidos`)
        if (resultado.errores > 0) partes.push(`${numero(resultado.errores)} con error`)
        return partes.length > 1 ? partes.join(' · ') : ''
      })()

  /* Los errores del backend llegan como lista plana de hasta 200 textos. Con
     muchos fallos son 200 renglones casi idénticos, que empujan los botones
     fuera de la pantalla: se agrupan por texto, igual que los avisos. */
  const detalleResultadoAgrupado = useMemo(() => {
    const cuenta = new Map<string, number>()
    for (const mensaje of resultado?.detalle ?? []) cuenta.set(mensaje, (cuenta.get(mensaje) ?? 0) + 1)
    return [...cuenta.entries()]
      .map(([mensaje, n]) => ({ clave: mensaje, mensaje, n }))
      .sort((a, b) => b.n - a.n)
  }, [resultado?.detalle])

  const zonasCreadas = resultado?.zonas_creadas ?? 0
  const oficinasCreadas = resultado?.oficinas_creadas ?? 0

  /*
    Los casos que **podrían** estar mal, para resaltarlos en la pantalla final.

    Dos cosas, y ninguna es un error comprobado: se señalan para que una mirada
    rápida decida si hay que corregir algo.

    - **el nombre del Excel es el de la oficina**: en estos libros la columna de
      responsable a veces trae el nombre del área y no el de una persona;
    - **coincidencia parecida**: se parece a alguien pero no es el mismo nombre;
      es lo más fácil de equivocar sin enterarse;
    Los perfiles sin credenciales se explican aparte: crearlos no es un error.
  */
  const sospechosos = (resultadoResponsables?.detalle ?? []).filter(
    (fila) => fila.nombre_parece_oficina || fila.coincidencia === 'parecida',
  )
  const normalizarBusqueda = (texto: string) => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
  const personasFiltradas = (resultadoResponsables?.detalle ?? []).filter((fila) =>
    normalizarBusqueda([fila.nombre_excel, fila.nombre_asignado, fila.oficina_nombre, fila.zona_nombre].filter(Boolean).join(' '))
      .includes(normalizarBusqueda(busquedaPersona.trim())),
  )
  const paginasPersonas = Math.max(1, Math.ceil(personasFiltradas.length / 20))
  const paginaPersonasActual = Math.min(paginaPersona, paginasPersonas)
  const personasDeLaPagina = personasFiltradas.slice((paginaPersonasActual - 1) * 20, paginaPersonasActual * 20)
  const conjuntosCreados = resultado?.conjuntos_creados ?? 0

  /* «1 zona nueva, 4 oficinas nuevas y 12 conjuntos nuevos»: una sola «y», antes
     del último. Con dos condicionales seguidos salía «…y 4 oficinas nuevas y 12
     conjuntos nuevos». */
  const fraseCreado = (() => {
    const partes: string[] = []
    if (zonasCreadas) partes.push(plural(zonasCreadas, 'zona nueva', 'zonas nuevas'))
    if (oficinasCreadas) partes.push(plural(oficinasCreadas, 'oficina nueva', 'oficinas nuevas'))
    if (conjuntosCreados) partes.push(plural(conjuntosCreados, 'conjunto nuevo', 'conjuntos nuevos'))
    if (!partes.length) return ''
    return partes.length === 1 ? partes[0] : `${partes.slice(0, -1).join(', ')} y ${partes[partes.length - 1]}`
  })()

  useEffect(() => {
    document.title = 'Importar inventario · Mesa de Ayuda TI'
  }, [])

  const ocupado = subiendo || aplicando || deshaciendo
  const indicePaso = PASOS.findIndex((item) => item.clave === paso)
  /*
    Las filas de la hoja elegida, memorizadas.

    Sin esto, `filasVisibles` es un array nuevo en cada render, el `useMemo` de
    los avisos agrupados no se guarda nunca y con el Excel del municipio —877
    filas, cada una con sus avisos— se agrupan 877 elementos en cada tecla. Con
    el archivo de muestra no se nota; con el real sí.
  */
  const filasVisibles = useMemo(
    () => vista?.filas.filter((fila) => !hojaVista || fila.hoja === hojaVista) ?? [],
    [vista?.filas, hojaVista],
  )
  const filasConIncidencias = filasVisibles.filter((fila) => fila.errores.length || fila.advertencias.length)

  /*
    Paginación de la tabla.

    Se enseñaban solo las primeras 100 y se acababa ahí: con el Excel municipal
    salía «Muestra de 100 de 875» y **no había forma de llegar a las otras 775**.
    No es un detalle menor —esta pantalla existe para revisar antes de importar—:
    una revisión que solo llega al 12 % no es una revisión.

    Páginas de 100 porque es lo que cabe sin que la tabla pierda lectura, con
    salto directo a la primera y a la última. Al cambiar de hoja se vuelve a la
    primera, porque si no se aterriza en una página que puede no existir.
  */
  const totalPaginas = Math.max(1, Math.ceil(filasVisibles.length / POR_PAGINA))
  const pagina = Math.min(paginaPedida, totalPaginas)
  const desde = (pagina - 1) * POR_PAGINA
  const hasta = Math.min(desde + POR_PAGINA, filasVisibles.length)
  const filasDeLaPagina = filasVisibles.slice(desde, hasta)

  useEffect(() => {
    setPaginaPedida(1)
  }, [hojaVista])
  const zonasDetectadas = new Set(vista?.filas.map((fila) => fila.zona_nombre).filter(Boolean) ?? []).size
  const oficinasDetectadas = new Set(
    vista?.filas
      .filter((fila) => fila.oficina_nombre)
      .map((fila) => `${fila.zona_nombre}\u0000${fila.oficina_nombre}`) ?? [],
  ).size

  /*
    Los avisos, agrupados por texto.

    Se contaban una tarjeta por fila, y en el Excel de muestra salían **58
    tarjetas para decir dos frases**: 39 veces «sin propiedad indicada» y 36
    veces «sin código patrimonial». Un aviso repetido 39 veces no informa: lo que
    sirve es saber cuántas filas lo tienen y dónde están, para ir a buscarlas al
    archivo. Se agrupa por mensaje y se anota la fila de cada una.

    Un error manda sobre un aviso aunque coincidan: si una fila tiene de los
    dos, sale como error, porque es lo que impide importar esa fila.

    Se cuentan sobre las filas que se están viendo —las de la hoja elegida—, que
    es como estaban antes; si no, al elegir una hoja el bloque de avisos seguiría
    hablando de zonas que no has abierto.
  */
  const avisosAgrupados = useMemo(() => {
    const mapa = new Map<string, { clave: string; mensaje: string; errores: boolean; numeros: number[] }>()
    for (const fila of filasVisibles) {
      for (const mensaje of fila.errores) {
        const clave = `error::${mensaje}`
        const grupo = mapa.get(clave) ?? { clave, mensaje, errores: true, numeros: [] }
        grupo.numeros.push(fila.numero)
        mapa.set(clave, grupo)
      }
      for (const mensaje of fila.advertencias) {
        const clave = `aviso::${mensaje}`
        const grupo = mapa.get(clave) ?? { clave, mensaje, errores: false, numeros: [] }
        grupo.numeros.push(fila.numero)
        mapa.set(clave, grupo)
      }
    }
    return [...mapa.values()]
      .map((grupo) => ({ ...grupo, n: grupo.numeros.length }))
      .sort((a, b) => (b.errores === a.errores ? b.n - a.n : b.errores ? 1 : -1))
  }, [filasVisibles])

  /*
    Cuántos nombres hay, y cuántos se pueden emparejar con alguien que ya tiene
    cuenta.

    Es lo que faltaba para entender el bloque: salía una lista de 263
    desplegables sin decir nada del conjunto. Con estos dos números se sabe de
    golpe si vale la pena revisarla o si lo que toca es crearlos todos.
  */
  const resumenResponsables = useMemo(() => {
    const conCoincidencia = gruposResponsables.filter((grupo) => grupo.candidatos.length > 0)
    return {
      total: gruposResponsables.length,
      conCoincidencia: conCoincidencia.length,
      sinCoincidencia: gruposResponsables.length - conCoincidencia.length,
      equipos: gruposResponsables.reduce((suma, grupo) => suma + grupo.equipos, 0),
    }
  }, [gruposResponsables])

  /* Cuántos quedan por decidir y de qué tipo. Lo usan los dos botones. */
  const pendientesDeDecision = useMemo(
    () => gruposResponsables.filter((grupo) => !seleccionesResponsables[grupo.clave]),
    [gruposResponsables, seleccionesResponsables],
  )
  const elegidasComoCoincidencia = gruposResponsables.filter(
    (grupo) => { const v = seleccionesResponsables[grupo.clave]; return v && v !== 'crear' },
  ).length
  const porCrear =
    pendientesDeDecision.length + gruposResponsables.filter((g) => seleccionesResponsables[g.clave] === 'crear').length

  const reiniciar = () => {
    setPaso('archivo')
    setArchivo(null)
    setLote(null)
    setVista(null)
    setResultado(null)
    setHojaVista('')
    setGruposResponsables([])
    setSeleccionesResponsables({})
    setResultadoResponsables(null)
    setResponsablesRevisados(false)
    setResponsablesOmitidos(false)
    setDecision('ninguno')
    setPaginaPedida(1)
    setError(null)
  }

  /*
    Volver a mirar el archivo después de importar.

    No deshace nada —los datos ya están en el inventario— y por eso el botón
    lo dice. Lo que sirve es volver a la previsualización para comprobar una
    fila concreta que quedó rara, con la lista y los avisos a mano, sin tener
    que subir el archivo otra vez.
  */
  const volverAlArchivo = () => {
    setPaso('previsualizar')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  /*
    Los dos botones del final.

    Eran tres y dos de ellos hacían lo mismo: «Confirmar 263 personas» con todo
    ya marcado en «crear» y «Vincular todas como nuevas» terminaban en el mismo
    sitio. Ahora son dos, y cada uno significa algo distinto:

    - **Confirmar** — respeta lo que hayas elegido a mano y crea el perfil de
      quien faltaba. Es el botón de «sí, hazlo».
    - **Continuar sin vincular** — no crea a nadie. Los equipos se quedan con el
      nombre del Excel guardado pero sin persona detrás.

    El detalle que faltaba y era un fallo de verdad: «Vincular todas como
    nuevas» **pisaba las coincidencias que habías elegido a mano**. Elegías
    «es esta persona» en cuatro nombres, pulsabas el botón para resolver los
    259 que quedaban en blanco, y los cuatro volvían a «crear». Ahora solo
    rellena los que siguen **vacíos**.
  */
  const resolverPendientesComoNuevas = () => {
    setSeleccionesResponsables((actual) => {
      const siguiente = { ...actual }
      for (const grupo of gruposResponsables) {
        if (!siguiente[grupo.clave]) siguiente[grupo.clave] = 'crear'
      }
      return siguiente
    })
  }

  const confirmarTodo = () => {
    resolverPendientesComoNuevas()
    /* `confirmarConSelecciones` lee las selecciones que se le pasen, no las del
       estado: en el mismo clic el `set` todavía no se ha aplicado. */
    const completa = Object.fromEntries(
      gruposResponsables.map((grupo) => [grupo.clave, seleccionesResponsables[grupo.clave] || 'crear']),
    )
    setSeleccionesResponsables(completa)
    void confirmarConSelecciones(completa)
  }

  /*
    Las dos casillas y el botón «Continuar».

    Eran dos botones grandes —«Continuar sin vincular» y «Confirmar y crear N
    perfiles»— y se parecían demasiado: los dos actuaban de inmediato, y
    confundirlos era fácil justo en el momento de decidir si se crean 263 cuentas.

    Ahora son **dos casillas excluyentes** y **un solo botón**:

    - marcar «No vincular a nadie» → se aplica esa regla y se anula la otra;
    - marcar «Crear los que faltan» → se crean, respetando lo elegido a mano;
    - **no marcar ninguna** → se avanza solo con lo que se haya elegido en la
      lista, sin crear nada por sorpresa.

    Las casillas son la decisión —se pueden leer de un vistazo y se pueden
    deshacer— y el botón es solo el paso de salida. Excluyentes porque las dos
    reglas son contradictorias: una crea cuentas y la otra dice que no.
  */
  const aplicarDecision = () => {
    if (decision === 'ninguno') {
      omitirResponsables()
      return
    }
    if (decision === 'crear') {
      confirmarTodo()
      return
    }
    // Sin casilla: solo se confirma lo que ya esté elegido a mano. Si no hay
    // nada elegido, no se inventa ninguna cuenta.
    if (elegidasComoCoincidencia === 0) {
      omitirResponsables()
      return
    }
    const completas = Object.fromEntries(
      gruposResponsables
        .filter((grupo) => seleccionesResponsables[grupo.clave])
        .map((grupo) => [grupo.clave, seleccionesResponsables[grupo.clave]]),
    )
    setSeleccionesResponsables(completas)
    void confirmarConSelecciones(completas)
  }

  const omitirResponsables = () => {
    setGruposResponsables([])
    setResponsablesOmitidos(true)
  }

  const subir = async (archivoElegido: File) => {
    if (ocupado) return
    if (!/\.(xlsx|xlsm|csv)$/i.test(archivoElegido.name)) {
      setError('Selecciona un archivo .xlsx, .xlsm o .csv.')
      return
    }
    setSubiendo(true)
    setError(null)
    setArchivo(archivoElegido)
    setLote(null)
    setVista(null)
    setResultado(null)
    setHojaVista('')
    try {
      const datos = new FormData()
      datos.append('archivo', archivoElegido)
      const respuesta = await api.subir<{ lote_id: string; hojas: Hoja[] }>('/importacion/subir', datos)
      const documento = await api.obtener<Lote>(`/importacion/${respuesta.lote_id}`)
      setLote(documento)
      const previa = await api.crear<Previsualizacion>(`/importacion/${respuesta.lote_id}/previsualizar`, {})
      setVista(previa)
      setPaso('previsualizar')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No pudimos leer el archivo.')
    } finally {
      setSubiendo(false)
    }
  }

  const aplicar = async () => {
    /*
      El guardia no comprueba `filas.length === total_filas`, que es lo que
      tenía antes. Ese aviso era **imposible que saltara**: el backend arma
      `total_filas` con `len(filas)`, así que los dos números son la misma
      variable y la comparación siempre sale cierta. No era una red de
      seguridad, era decorado.

      Y tenía un riesgo: si algún día el backend pasara a devolver una muestra
      en vez de todas las filas —que es lo que habría que hacer con los 877
      equipos—, este guardia no avisaría de nada, dejaría el botón apagado sin
      explicación y nadie sabría por qué no se podía importar.
    */
    if (!lote || !vista?.validas || ocupado || resultado) return
    setAplicando(true)
    setError(null)
    try {
      const respuesta = await api.crear<Resultado>(`/importacion/${lote.lote_id}/confirmar`, {})
      setResultado(respuesta)
      setPaso('confirmar')
      /*
    El aviso verde decía «0 creados y 875 actualizados». Con el cero delante
    parece que no se hizo nada, y el que sale abajo en la pantalla ya dice
    «Se actualizaron 875 equipos que ya estaban». Que los dos digan lo mismo:
    el aviso es lo primero que se lee y lo último que se entiende.

    Y si hubo errores va en amarillo, no en verde: un visto bueno con tilde
    verde al lado de un bloque rojo de fallos se contradice.
  */
  const resumenAviso = respuesta.creados > 0 && respuesta.actualizados > 0
    ? `${numero(respuesta.creados)} nuevos y ${numero(respuesta.actualizados)} actualizados`
    : respuesta.creados > 0
      ? `${numero(respuesta.creados)} equipos nuevos`
      : `${numero(respuesta.actualizados)} equipos actualizados, que ya estaban`
  const textoAviso = respuesta.errores ? 'Importación terminada con errores' : 'Importación terminada'
  if (respuesta.errores) avisos.aviso(textoAviso, resumenAviso)
  else avisos.exito(textoAviso, resumenAviso)
      if (sesion.puede('usuarios.editar')) {
        try {
          const pendientes = await api.obtener<{ items: GrupoResponsableExcel[] }>('/importacion/responsables-excel')
          setGruposResponsables(pendientes.items)
          setResponsablesRevisados(true)
          /*
            Las coincidencias **exactas** se marcan solas; el resto se queda en
            «sin decidir».

            Antes, todo nombre que no estuviera en ninguna cuenta venía marcado
            como «crear perfil»: con el Excel municipal eso eran 263 personas
            decididas de antemano, y el botón de confirmar solo formalizaba una
            decisión que ya estaba tomada. Crear una cuenta no es un detalle
            menor —alguien va a poder reportar tickets con ese nombre—, así que
            no se preselecciona.

            Vincular una coincidencia exacta no crea nada: solo apunta a una
            cuenta que ya existe, y por eso sí se deja elegida.
          */
          setSeleccionesResponsables(Object.fromEntries(pendientes.items.map((grupo) => {
            const exactos = grupo.candidatos.filter((persona) => persona.coincidencia === 'exacta')
            return [grupo.clave, exactos.length === 1 ? exactos[0].id : '']
          })))
        } catch (fallo) {
          avisos.desdeError(fallo)
        }
      }
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No pudimos confirmar la importación.')
    } finally {
      setAplicando(false)
    }
  }

  /* Se separa del botón para que el botón de «confirmar» pueda pasar una
     selección ya completada —con los vacíos rellenados como «crear»— sin
     depender de que el estado se haya aplicado ya en el mismo clic. */
  const confirmarConSelecciones = async (selecciones: Record<string, string>) => {
    if (!gruposResponsables.length) return
    setConfirmandoResponsables(true)
    try {
      const respuesta = await api.crear<ResultadoResponsables>(
        '/importacion/responsables-excel/confirmar',
        { selecciones: gruposResponsables.map((grupo) => ({ clave: grupo.clave, usuario_id: selecciones[grupo.clave] })) },
      )
      setResultadoResponsables(respuesta)
      setBusquedaPersona('')
      setPaginaPersona(1)
      setGruposResponsables([])
      avisos.exito(
        'Personas del Excel vinculadas',
        `${plural(respuesta.personas_creadas, 'perfil creado', 'perfiles creados')} · ${plural(respuesta.equipos_vinculados, 'equipo con responsable', 'equipos con responsable')}`,
      )
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setConfirmandoResponsables(false)
    }
  }

  const deshacer = async () => {
    if (!lote || !resultado?.reversible || ocupado) return
    setDeshaciendo(true)
    setError(null)
    try {
      const respuesta = await api.crear<{ eliminados: number; restaurados: number }>(`/importacion/${lote.lote_id}/deshacer`, {})
      avisos.exito('Importación deshecha', `${respuesta.eliminados} equipos importados eliminados`)
      reiniciar()
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No pudimos deshacer la importación.')
    } finally {
      setDeshaciendo(false)
    }
  }

  const descargarPlantilla = async () => {
    setDescargando(true)
    try {
      const contenido = await api.archivo('/importacion/plantilla')
      const url = URL.createObjectURL(contenido)
      const enlace = document.createElement('a')
      enlace.href = url
      enlace.download = 'plantilla-inventario.xlsx'
      document.body.appendChild(enlace)
      enlace.click()
      enlace.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (fallo) {
      avisos.desdeError(fallo)
    } finally {
      setDescargando(false)
    }
  }

  return (
    <PantallaFormulario>
      <header>
        <h1 className="titulo-pagina">Importar inventario desde Excel</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cada hoja representa una zona y la columna Área corresponde a una oficina. Revisa los datos antes de importar los equipos.
        </p>
      </header>
      <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-3 sm:p-4">
        {/*
          Los pasos hechos se pueden volver a abrir, **también con la importación
          ya aplicada**. Antes el Stepper se apagaba en cuanto había resultado y
          el paso 2 quedaba cerrado para siempre: si alguien veía el resultado,
          le iba una fila rara y no podía volver a mirar el archivo sin subirlo
          otra vez desde cero.

          Ir hacia atrás no deshace nada —el inventario ya tiene los datos— y el
          botón del final lo dice.
        */}
        <Stepper pasos={PASOS} actual={paso} alIr={!ocupado ? setPaso : undefined} alcanzado={resultado ? 'confirmar' : undefined} />
      </div>
      {error ? <Nota tono="peligro" titulo="No se pudo completar la operación"><p role="alert">{error}</p></Nota> : null}

      {paso === 'archivo' ? (
        <Panel titulo="1. Elige el archivo">
          <div
            onDragOver={(evento) => evento.preventDefault()}
            onDrop={(evento) => {
              evento.preventDefault()
              const soltado = evento.dataTransfer.files?.[0]
              if (soltado) void subir(soltado)
            }}
            className="flex flex-col items-center gap-3 rounded-[var(--radius-panel)] border-2 border-dashed border-border bg-muted/30 p-8 text-center"
          >
            <FileSpreadsheet size={28} className="text-muted-foreground" aria-hidden="true" />
            <p className="font-semibold">Arrastra aquí tu archivo o selecciónalo desde tu computadora</p>
            <p className="text-sm text-muted-foreground">Excel (.xlsx, .xlsm) o CSV</p>
            <input
              ref={archivoRef}
              type="file"
              accept=".xlsx,.xlsm,.csv"
              aria-label="Archivo de Excel con el inventario"
              className="solo-lectores"
              disabled={ocupado}
              onChange={(evento) => {
                const elegido = evento.target.files?.[0]
                evento.target.value = ''
                if (elegido) void subir(elegido)
              }}
            />
            <Button variante="primario" cargando={subiendo} onClick={() => archivoRef.current?.click()} icono={<Upload size={16} aria-hidden="true" />}>
              Elegir archivo
            </Button>
            <Button variante="fantasma" cargando={descargando} onClick={() => void descargarPlantilla()}>
              Descargar la plantilla oficial
            </Button>
          </div>
          {/*
            Aviso antes de subir, no después.

            Importar **actualiza** los equipos que ya existen: no solo da de alta los
            que faltan. El riesgo no es inventado —importar el mismo Excel otra vez
            refresca los 877 equipos—, pero se decide sin decirlo, y en una pantalla
            donde se está trabajando con esos equipos eso importa.
          */}
          <p className="mt-3 text-sm text-muted-foreground">
            Si el archivo trae equipos que <strong>ya están</strong> en el inventario, se les
            cambian los datos por los del archivo. Verás cuántos son antes de aplicar.
          </p>
        </Panel>
      ) : null}

      {/*
        Historial de importaciones.

        Existía desde el principio —`GET /importacion` y `useEstadoImportacion`— y
        **nadie lo llamaba**: en el municipio había 29 importaciones guardadas y la
        pantalla no enseñaba ninguna. Sin esto no hay forma de responder a las dos
        preguntas que aparecen siempre después de importar: «¿qué se me actualizó la
        última vez?» y «¿cuándo se subió esto?».
      */}
      <Panel
        titulo="Importaciones anteriores"
        acciones={sesion.esAdmin ? <LimpiarRegistros ruta={`/importacion${lote ? `?conservar_lote=${encodeURIComponent(lote.lote_id)}` : ''}`} titulo="Limpiar historial" descripcion="Se eliminarán las importaciones anteriores, incluidas sus previsualizaciones. El trabajo abierto y los equipos importados se conservan. Ya no podrás deshacer las importaciones eliminadas." alLimpiar={() => historial.refetch()} /> : null}
        descripcion="Cada archivo que se ha subido, con lo que creó y lo que actualizó."
      >
        {historial.isLoading ? (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        ) : (historial.data?.items.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">Todavía no se ha importado ningún archivo.</p>
        ) : (
          <ul className="divide-y divide-border">
            {historial.data?.items.slice(0, 8).map((lote) => {
              const nuevos = lote.creados?.length ?? 0
              const tocados = lote.actualizados?.length ?? 0
              const confirmado = lote.estado === 'confirmado'
              return (
                <li key={lote.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                  <FileSpreadsheet
                    size={15}
                    className={confirmado ? 'shrink-0 text-success-strong' : 'shrink-0 text-muted-foreground'}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1 truncate font-medium">{lote.nombre_archivo}</span>
                  <span className={confirmado ? 'text-success-strong' : 'text-muted-foreground'}>
                    {confirmado ? 'aplicada' : 'solo vista previa'}
                  </span>
                  {confirmado ? (
                    <span className="text-muted-foreground">
                      {nuevos > 0 ? `${numero(nuevos)} nuevos` : null}
                      {nuevos > 0 && tocados > 0 ? ' · ' : null}
                      {tocados > 0 ? `${numero(tocados)} actualizados` : null}
                      {nuevos === 0 && tocados === 0 ? 'sin cambios' : null}
                    </span>
                  ) : null}
                  <span className="text-2xs text-muted-foreground">{fechaCorta(lote.creado_en)}</span>
                </li>
              )
            })}
          </ul>
        )}
        {(historial.data?.items.length ?? 0) > 8 ? (
          <p className="mt-2 text-2xs text-muted-foreground">
            Se muestran las 8 últimas de {numero(historial.data?.items.length ?? 0)}.
          </p>
        ) : null}
      </Panel>

      {paso === 'previsualizar' && vista ? (
        <Panel titulo={`Previsualización de ${lote?.nombre_archivo ?? archivo?.name ?? 'el archivo'}`}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            <Cifra etiqueta="Zonas detectadas" valor={zonasDetectadas} />
            <Cifra etiqueta="Oficinas detectadas" valor={oficinasDetectadas} />
            <Cifra etiqueta="Filas en el archivo" valor={vista.total_filas} />
            <Cifra etiqueta="Listas para importar" valor={vista.validas} tono="exito" />
            <Cifra etiqueta="Con error" valor={vista.con_error} tono={vista.con_error ? 'peligro' : 'neutro'} />
            <Cifra etiqueta="Equipos nuevos" valor={vista.crearia} />
            <Cifra etiqueta="Equipos a actualizar" valor={vista.actualizaria} />
            <Cifra etiqueta="Se omitirán" valor={vista.omitiria} />
          </div>
          {/*
            Avisar de que «actualizar» es **sobrescribir**.

            El número estaba ahí desde siempre, pero con la etiqueta «Actualizaciones»,
            que se lee como «habrá novedades». No lo es:Importar **reescribe los datos
            de los equipos que ya están en el inventario**. En una pantalla que se usa
            mientras se trabaja con esos mismos equipos, eso no es un detalle: es la
            diferencia entre leer el archivo y perder el trabajo que se había puesto a
            mano en ellos.

            Por eso el aviso va **antes** de aplicar, que es cuando se decide, y no solo
            en el resultado, que llega cuando ya no hay nada que hacer.
          */}
          {vista.actualizaria > 0 ? (
            <Nota
              tono={vista.actualizaria > 50 ? 'aviso' : 'info'}
              titulo={`Se van a sobrescribir ${numero(vista.actualizaria)} equipos que ya están en el inventario`}
              icono={<CircleAlert size={16} aria-hidden="true" />}
            >
              <p>
                Esos equipos no se duplican: se les cambian los datos por los del archivo.
                Si alguien ha escrito a mano la marca, el modelo o el responsable de uno de
                ellos, ese dato <strong>se pierde</strong>. Si el archivo es una copia del
                inventario de la fecha de hoy, no habrá ningún cambio real.
              </p>
              {vista.actualizaria === vista.validas ? (
                <p className="mt-1.5">
                  Aquí <strong>todas</strong> las filas válidos actualizan un equipo
                  existente: esto es una reimportación, no un alta.
                </p>
              ) : null}
            </Nota>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {lote?.analisis.hojas.map((hoja) => (
              <span key={hoja.nombre_hoja} className="rounded bg-muted px-2 py-1 text-sm">
                {/* El nombre de la hoja llega con espacios sobrantes del Excel: se
                    recortan para que no se lea «ZONA MERCADO » con un hueco al
                    final que parece un error de la pantalla. */}
                {hoja.zona_nombre}: {vista.filas.filter((fila) => fila.hoja === hoja.nombre_hoja).length} filas · {plural(new Set(hoja.oficinas).size, 'oficina', 'oficinas')}
              </span>
            ))}
          </div>
          {vista.con_error ? <p className="mt-3 text-sm text-destructive-strong">Las filas con error se omiten y no se importan. Arregla el archivo y vuelve a subirlo.</p> : null}
        </Panel>
      ) : null}

      {paso === 'previsualizar' && vista ? (
        <Panel titulo="2. Datos y advertencias" className="min-w-0 max-w-full" cuerpoClassName="min-w-0">
          <Select etiqueta="Hoja del Excel" value={hojaVista} onChange={(evento) => setHojaVista(evento.target.value)} placeholder="Todas las hojas" opciones={(lote?.analisis.hojas ?? []).map((hoja) => ({ valor: hoja.nombre_hoja, etiqueta: hoja.nombre_hoja.trim() }))} />
          {/*
            Por qué la lista empieza en la fila 3, aquí y no solo en el pie de la
            tabla. Se preguntó dos veces y la explicación estaba escondida al
            final de una tabla de veinte columnas: es lo primero que se ve al
            mirar y lo primero que se pregunta.
          */}
          <p className="mt-1.5 text-2xs text-muted-foreground">
            La fila 1 de cada hoja es el título del archivo y la 2 el encabezado; por eso
            los datos empiezan en la 3. No faltan filas: el número es la posición real en
            el Excel, para poder abrir el archivo y caer en esa fila.
          </p>
          {filasVisibles.length ? (
            <div
              role="region"
              aria-label="Vista previa del inventario"
              tabIndex={0}
              className="sin-barra relative isolate mt-3 w-full min-w-0 max-w-full overflow-auto overscroll-contain rounded-[var(--radius-panel)] border border-border"
              style={{ maxHeight: 'min(60vh, 620px)' }}
            >
              {/*
                La tabla se queda en una altura acotada y se desplaza **dentro**.

                Antes el contenedor solo tenía desplazamiento horizontal: la barra
                para ir de izquierda a derecha quedaba al final de las 100 filas,
                así que había que bajar hasta el final de la lista para poder
                usarla. Con la altura acotada, las dos barras están siempre a la
                vista, sin importar cuántas filas haya, y el encabezado —que ya
                es `sticky top-0`— acompaña al desplazamiento vertical para no
                perder los nombres de las columnas.
              */}
              <table className="w-full text-sm">
                <caption className="mb-2 text-left text-muted-foreground">
                  {/*
                    El número de fila es **la fila real del Excel**, no la posición
                    en la lista. Por eso en el archivo municipal empieza en la 3
                    y no en la 1: la 1 es el título de la hoja («EQUIPOS
                    INFORMATICOS») y la 2 el encabezado. Es a propósito —con ese
                    número se abre el Excel y se cae en la fila exacta—, pero sin
                    decirlo parece que faltan las dos primeras, y no es así.
                  */}
                  Mostrando {desde + 1}–{hasta} de {filasVisibles.length} filas. El
                  número es la fila del archivo Excel: en las hojas municipales la
                  1 es el título y la 2 el encabezado, por eso los datos empiezan en la 3.
                </caption>
                {/*
                  «Acción» va **de primera y pegada al canto izquierdo**, y el
                  encabezado también, porque es la pregunta de esta pantalla:
                  ¿qué va a pasar con cada fila? Estaba en la columna 20 de 20, y
                  con 1.744 px de tabla en 1.066 de hueco nunca se veía sin
                  arrastrar hasta el final. Ahora se lee sin mover nada, y al
                  desplazar sigue en su sitio.

                  La etiqueta de la fila se reduce a hoja + número porque
                  «ZONA COMPLEJO» estaba repetido en tres columnas y era el mismo
                  texto tres veces.
                */}
                <thead className="sticky top-0 z-20 bg-muted">
                  <tr>
                    {/* La primera columna es fija en los dos ejes: por la izquierda
                        para no perderse al desplazar, y su `z` va por encima del
                        de las celdas. Con el mismo, la celda «Se creará» de la
                        primera fila se pintaba encima del encabezado y lo
                        tapaba: parecía que la columna se llamaba «Se creará». */}
                    <th scope="col" className="sticky left-0 z-30 whitespace-nowrap bg-muted px-2 py-1 text-left font-semibold">Acción</th>
                    {['Hoja · fila', 'Área / oficina', 'Tipo de equipo', 'Dispositivo', 'Código', 'Marca', 'Modelo', 'Pantalla', 'Nombre', 'Procesador', 'RAM', 'Almacenamiento', 'IP', 'MAC', 'Propiedad', 'Estado', 'Responsable'].map((titulo) => <th key={titulo} scope="col" className="whitespace-nowrap px-2 py-1 text-left font-semibold">{titulo}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {filasDeLaPagina.map((fila) => (
                    <tr key={`${fila.hoja}-${fila.numero}`} className="border-t border-border">
                      <td className="sticky left-0 z-10 whitespace-nowrap bg-surface px-2 py-1">
                        <span className={cn('rounded px-1.5 py-0.5 text-2xs font-semibold', TONO_ACCION[fila.accion] ?? 'bg-muted text-muted-foreground')}>
                          {ACCION[fila.accion] ?? fila.accion}
                        </span>
                      </td>
                      {[`${fila.hoja.trim()} · ${fila.numero}`, fila.oficina_nombre, fila.grupo_crudo, fila.tipo, fila.codigo_patrimonial,
                        ...['marca', 'modelo', 'tamano_pantalla', 'nombre_equipo', 'procesador', 'memoria_ram', 'almacenamiento', 'direccion_ip', 'direccion_mac', 'propiedad', 'estado', 'responsable_nombre'].map((campo) => fila[campo])].map((valor, indice) => (
                        <td key={indice} className="whitespace-nowrap px-2 py-1">{valor == null || valor === '' ? '—' : String(valor)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState compacto titulo="No hay filas para mostrar" />}
          {/* El paginador va **fuera** del `overflow-x-auto`: dentro, la barra
              horizontal del contenedor se llevaría los botones hacia la derecha
              y a los lados saldrían de la pantalla al desplazar. */}
          {totalPaginas > 1 ? (
            <nav aria-label="Páginas de la previsualización" className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-muted-foreground">
                Página {pagina} de {totalPaginas} · {filasVisibles.length} filas
                {hojaVista ? ` en ${hojaVista.trim()}` : ''}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button variante="secundario" tamano="sm" disabled={pagina === 1} onClick={() => setPaginaPedida(1)}>Primera</Button>
                <Button variante="secundario" tamano="sm" disabled={pagina === 1} onClick={() => setPaginaPedida(pagina - 1)}>Anterior</Button>
                <span className="px-1 text-sm font-semibold">{pagina} / {totalPaginas}</span>
                <Button variante="secundario" tamano="sm" disabled={pagina === totalPaginas} onClick={() => setPaginaPedida(pagina + 1)}>Siguiente</Button>
                <Button variante="secundario" tamano="sm" disabled={pagina === totalPaginas} onClick={() => setPaginaPedida(totalPaginas)}>Última</Button>
              </div>
            </nav>
          ) : null}
          {filasConIncidencias.length ? (
            <div className="mt-4">
              {/*
                Los avisos se **agrupan por mensaje**, no fila por fila.

                En el Excel de muestra eran 58 tarjetas para decir dos cosas: 39
                veces «sin propiedad indicada» y 36 veces «sin código
                patrimonial». Lo importante no era que lo dijera 39 veces, sino
                cuántas filas lo dicen y cuáles son, para poder ir a buscarlas al
                Excel. Repetir el mismo texto 39 veces esconde el segundo aviso
                debajo del primero.

                Cada línea lleva el mensaje, cuántas filas lo tienen y su número
                de página en el archivo; las hojas del desplegable de arriba
                sirven para bajar a verlas una a una.
              */}
              <p className="font-semibold">
                Advertencias y errores ({filasConIncidencias.length}{' '}
                {filasConIncidencias.length === 1 ? 'fila' : 'filas'})
              </p>
              <ul className="mt-2 flex flex-col gap-1.5">
                {avisosAgrupados.map((grupo) => (
                  <li key={grupo.clave} className={cn('rounded border p-2 text-sm', grupo.errores ? 'border-destructive/40 bg-destructive-soft' : 'border-border')}>
                    <p className={grupo.errores ? 'font-semibold text-destructive-strong' : 'text-muted-foreground'}>
                      {grupo.errores ? 'Error' : 'Aviso'} · {grupo.mensaje}
                    </p>
                    <p className="mt-0.5 text-2xs text-muted-foreground">
                      En {grupo.n} {grupo.n === 1 ? 'fila' : 'filas'}
                      {grupo.n > 1 ? ` · filas ${grupo.numeros.slice(0, 12).join(', ')}${grupo.numeros.length > 12 ? ` y ${grupo.numeros.length - 12} más` : ''}` : ''}
                    </p>
                  </li>
                ))}
              </ul>
              {filasConIncidencias.some((fila) => fila.errores.length) ? (
                <p className="mt-2 text-sm text-destructive-strong">
                  Las filas con error se omiten y no se importan. Arregla el archivo y vuelve a subirlo.
                </p>
              ) : null}
            </div>
          ) : <p className="mt-3 text-sm text-success-strong">No se encontraron advertencias ni errores.</p>}
        </Panel>
      ) : null}

      {paso === 'confirmar' && resultado ? (
        <Panel titulo="3. Resultado de la importación">
          {/*
            El titular dice **qué pasó**, no solo que terminó.

            Decía «Inventario importado» con «Se crearon 0 y se actualizaron 875»
            debajo, y eso parece un fallo: 0 creados parece que no se hizo nada.
            Lo que pasó es lo normal en una reimportación —los 875 equipos ya
            existían y se refrescaron sus datos—, pero la pantalla no lo decía y
            el número se leía como un error.

            Por eso el titular se arma con los dos números y les pone el nombre de
            lo que son, y la frase de «actualizar» solo aparece cuando de verdad
            hubo actualizaciones, para que quede claro que no se duplicó nada.
          */}
          <Nota
            tono={resultado.errores ? 'aviso' : 'exito'}
            titulo={tituloResultado}
          >
            <p>{detalleResultado}</p>
            {resultado.actualizados > 0 ? (
              /* Con `<strong>`, no con `**`. En JSX los asteriscos salen
                 tal cual: se veían en pantalla tal cual están escritos. */
              <p className="mt-1.5 text-sm">
                Actualizar significa que el equipo <strong>ya estaba en el
                inventario</strong> y se refrescaron sus datos con los del archivo.
                No se creó una copia.
              </p>
            ) : null}
          </Nota>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Cifra etiqueta="Equipos nuevos" valor={resultado.creados} tono={resultado.creados > 0 ? 'exito' : 'neutro'} />
            <Cifra etiqueta="Equipos actualizados" valor={resultado.actualizados} />
            <Cifra etiqueta="Filas omitidas" valor={resultado.omitidos} />
            <Cifra etiqueta="Errores" valor={resultado.errores} tono={resultado.errores ? 'peligro' : 'neutro'} />
          </div>
          {/* Lo que la importación creó por el camino. El backend lo devolvía y
              no se mostraba: si el archivo traía una zona que no existía, se
              creaba en silencio y nadie se enteraba hasta verla en otra
              pantalla. */}
          {fraseCreado ? <p className="mt-3 text-sm text-muted-foreground">Además se creó {fraseCreado}.</p> : null}
          {/* Los errores del backend vienen como una lista plana de hasta 200
              textos. Con muchos fallos son 200 líneas iguales de forma, que
              empujan los botones fuera de la pantalla: se agrupan por texto igual
              que los avisos de la previsualización. */}
          {resultado.detalle.length ? (
            <div className="mt-4">
              <p className="font-semibold text-destructive-strong">
                Qué falló{resultado.detalle.length >= 200 ? ' (primeras 200)' : ''}
              </p>
              <ul className="sin-barra mt-2 flex max-h-72 flex-col gap-1.5 overflow-y-auto">
                {detalleResultadoAgrupado.map((grupo) => (
                  <li key={grupo.clave} className="rounded border border-destructive/40 bg-destructive-soft p-2 text-sm">
                    <p className="text-destructive-strong">{grupo.mensaje}</p>
                    {grupo.n > 1 ? <p className="mt-0.5 text-2xs text-muted-foreground">Ocurrió {grupo.n} veces</p> : null}
                  </li>
                ))}
              </ul>
              {/* Sin esto el bloque dice qué falló pero no qué hacer, y lo que
                  salió bien se mezcla con lo que no. */}
              <p className="mt-2 text-sm text-muted-foreground">
                El resto del archivo sí se importó. Arregla esas filas en el Excel y
                vuelve a subir el archivo: las que ya entraron se actualizan, no se
                duplican.
              </p>
            </div>
          ) : null}
          {/*
    El detalle de lo que se hizo con cada persona.

    Antes solo quedaban dos números —«se crearon 6 perfiles, se vincularon 7
    equipos»— y el bloque se iba a «No quedan responsables del Excel sin
    vincular». Eso no confirma nada: no dice **quién** se creó ni en qué zona, y
    no permite revisar si lo que se hizo era lo que se quería.

    Con la lista, lo hecho queda a la vista y se puede corregir desde la ficha.
    Y se marcan las tres cosas que **podrían** estar mal:

    - **coincidencia parecida**: el nombre del Excel se parece a alguien pero no es
      el mismo; es la más fácil de equivocar y la más difícil de notar.
    - **el nombre es el de la oficina**: en estos libros la columna de responsable
      a veces trae el nombre del área y no el de una persona.
    - **perfil creado sin cuenta**: no está mal, pero conviene saberlo.
  */}
          {resultadoResponsables ? (
            <section className="mt-5 rounded-[var(--radius-panel)] border border-border p-4">
              <h3 className="font-semibold">Qué se hizo con cada persona</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {resultadoResponsables.personas_creadas > 0
                  ? `Se crearon ${plural(resultadoResponsables.personas_creadas, 'perfil nuevo', 'perfiles nuevos')} sin correo ni contraseña. `
                  : 'No se creó ninguna cuenta nueva. '}
                {plural(resultadoResponsables.equipos_vinculados, 'equipo quedó', 'equipos quedaron')} con
                responsable asignado.
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                Todos los perfiles están en la lista de abajo. Busca por nombre, oficina o zona y usa las páginas para ver los demás.
                Los perfiles sin credenciales no pueden iniciar sesión.
              </p>

              {sospechosos.length > 0 ? (
                <div className="mt-3 rounded-[var(--radius-panel)] border border-warning/40 bg-warning-soft p-3">
                  <p className="flex items-center gap-1.5 text-sm font-semibold text-warning-strong">
                    <TriangleAlert size={15} aria-hidden="true" />
                    Revisa {plural(sospechosos.length, 'caso', 'casos')} que podrían estar mal
                  </p>
                  <ul className="mt-1.5 flex flex-col gap-1.5">
                    {sospechosos.map((fila) => (
                      <li key={fila.clave} className="text-sm">
                        <p className="font-medium">
                          {fila.nombre_excel}
                          {fila.zona_nombre ? <span className="font-normal text-muted-foreground"> · {fila.zona_nombre}</span> : null}
                        </p>
                        <p className="text-2xs text-muted-foreground">
                          {fila.nombre_parece_oficina
                            ? 'El nombre del Excel es el de la oficina, no el de una persona. Comprueba si aquí iba el nombre de alguien.'
                            : fila.coincidencia === 'parecida'
                              ? `Se vinculó a «${fila.nombre_asignado}» porque se le parece (${Math.round((fila.similitud ?? 0) * 100)} %). Puede que no sea la misma persona.`
                              : 'Se creó el perfil sin cuenta, así que no puede entrar al sistema.'}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="mt-3">
                <Input etiqueta="Buscar perfiles del resultado" value={busquedaPersona} onChange={(evento) => { setBusquedaPersona(evento.target.value); setPaginaPersona(1) }} placeholder="Nombre, oficina o zona" />
              </div>
              <ul aria-label="Perfiles creados y vinculados" className="mt-3 flex flex-col gap-1.5">
                {personasDeLaPagina.map((fila) => (
                  <li key={fila.clave} className="rounded border border-border p-2 text-sm">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold">{fila.nombre_excel}</span>
                      {fila.accion === 'creado' ? (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-2xs">Perfil nuevo</span>
                      ) : (
                        <span className="rounded bg-primary-soft px-1.5 py-0.5 text-2xs text-primary-strong">
                          Vinculada a {fila.nombre_asignado}
                        </span>
                      )}
                    </div>
                    <p className="text-2xs text-muted-foreground">
                      {[fila.zona_nombre, fila.oficina_nombre, plural(fila.equipos, 'equipo', 'equipos')]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                    {fila.usuario_id && sesion.puede('usuarios.ver') ? (
                      <Link className="mt-2 inline-block font-semibold text-primary-strong hover:underline" to={`/panel/usuarios/${fila.usuario_id}`}>
                        Ver perfil de {fila.nombre_asignado || fila.nombre_excel}
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
              {!personasFiltradas.length ? <p className="mt-3 text-sm text-muted-foreground">No hay perfiles que coincidan con la búsqueda.</p> : null}
              <div className="mt-3">
                <Paginacion pagina={paginaPersonasActual} totalPaginas={paginasPersonas} total={personasFiltradas.length} porPagina={20} alCambiar={setPaginaPersona} />
              </div>
              <p className="mt-2 text-2xs text-muted-foreground">
                Para corregir uno, abre su ficha desde Equipos → Inventario, o cambia el
                responsable del equipo.
              </p>
            </section>
          ) : null}
          {sesion.puede('usuarios.editar') && responsablesRevisados ? (
            <section className="mt-5 rounded-[var(--radius-panel)] border border-border p-4">
              {/*
                Este bloque salía como una pila de desplegables idénticos, uno
                por nombre, sin decir cuántos había. En el Excel municipal son
                decenas y la lista empujaba los botones de deshacer y de importar
                otro archivo fuera de la pantalla.

                Ahora dice cuántos son de entrada, se queda en una altura fija
                con su propio desplazamiento, y cada línea se lee
                «oficina — persona (N equipos)». Cuando el nombre de la persona
                es el mismo que el de la oficina —«ADMINISTRACION ·
                ADMINISTRACION»— no se repite dos veces, porque no son dos datos.
              */}
              <h3 className="font-semibold">Crear personas desde el Excel</h3>
              {/* Al omitirlo, el bloque se va pero queda constancia de que los equipos
                  siguen sin responsable y de dónde se resuelve. Sin esto,
                  desaparecer el bloque parece que el paso se hizo solo. */}
              {responsablesOmitidos ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  No se vinculó a nadie. Los equipos quedan como estaban, con el nombre del
                  Excel guardado pero sin persona detrás. Puedes ocuparte más tarde desde{' '}
                  <strong>Equipos → Inventario</strong>, con el filtro{' '}
                  <strong>«El responsable no tiene cuenta»</strong>.
                </p>
              ) : !gruposResponsables.length ? <p className="mt-2 text-sm text-muted-foreground">No quedan responsables del Excel sin vincular.</p> : <>
                {/*
                  El resumen va **antes** que la lista, y la lista se esconde.

                  Antes era una pila de 263 desplegables sin decir nada del
                  conjunto: imposible saber de un vistazo si lo que tocaba era
                  revisarla o crearla entera. Con los dos números —cuántos se
                  pueden emparejar y cuántos no— la decisión se toma en una
                  línea, y quien quiera revisarlos abre el desplegable.
                */}
                <p className="mt-2 text-sm">
                  El archivo nombra a{' '}
                  <strong>{plural(resumenResponsables.total, 'persona', 'personas')}</strong> en{' '}
                  {plural(resumenResponsables.equipos, 'equipo', 'equipos')}.{' '}
                  {resumenResponsables.conCoincidencia > 0 ? (
                    <>
                      <strong>{numero(resumenResponsables.conCoincidencia)}</strong> se parecen a
                      alguien que ya tiene cuenta.{' '}
                    </>
                  ) : null}
                  {resumenResponsables.sinCoincidencia > 0 ? (
                    <>
                      <strong>{numero(resumenResponsables.sinCoincidencia)}</strong> no aparecen en
                      ninguna cuenta.
                    </>
                  ) : null}
                </p>

                {/* Qué significa «crear un perfil». La pregunta es lógica —para
                    qué sirve algo que no tiene contraseña— y la respuesta es
                    que exista alguien a quien adjudicarle los tickets. */}
                <div className="mt-3 rounded-[var(--radius-panel)] border border-border bg-muted/40 p-3 text-sm">
                  <p className="font-semibold">Qué es «crear un perfil sin credenciales»</p>
                  <p className="mt-1 text-muted-foreground">
                    Añade a esa persona a <strong>Usuarios</strong> con su nombre y su oficina,
                    para que sus equipos dejen de estar sin dueño.{' '}
                    <strong>No puede entrar al sistema</strong>: se crea sin correo y sin
                    contraseña, y hasta que alguien le asigne una cuenta solo sirve como
                    responsable. Si no quieres crear ninguno, el botón de abajo lo deja
                    todo como está.
                  </p>
                </div>

                {gruposResponsables.length > 12 ? (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-semibold text-primary-strong">
                      Revisar uno por uno ({resumenResponsables.total})
                    </summary>
                    <ul className="sin-barra mt-3 flex max-h-96 flex-col gap-3 overflow-y-auto pr-1">
                      {gruposResponsables.map((grupo) => (
                        <li key={grupo.clave}>
                          <Select
                            etiqueta={
                              grupo.oficina_nombre.trim().toLowerCase() === grupo.nombre_original.trim().toLowerCase()
                                ? `${grupo.oficina_nombre} · ${plural(grupo.equipos, 'equipo', 'equipos')}`
                                : `${grupo.oficina_nombre} · ${grupo.nombre_original} · ${plural(grupo.equipos, 'equipo', 'equipos')}`
                            }
                            value={seleccionesResponsables[grupo.clave] ?? ''}
                            onChange={(evento) => setSeleccionesResponsables((actual) => ({ ...actual, [grupo.clave]: evento.target.value }))}
                            placeholder="Sin decidir"
                            opciones={[
                              { valor: 'crear', etiqueta: 'Crear perfil sin credenciales' },
                              ...grupo.candidatos.map((persona) => ({
                                valor: persona.id,
                                etiqueta: `${persona.nombre} (${persona.coincidencia === 'exacta' ? 'coincide' : 'parecido'})`,
                              })),
                            ]}
                          />
                        </li>
                      ))}
                    </ul>
                    {elegidasComoCoincidencia > 0 ? (
                      <p className="mt-2 text-2xs text-muted-foreground">
                        Has vinculado {plural(elegidasComoCoincidencia, 'persona a una cuenta existente', 'personas a cuentas existentes')}.
                        El botón de abajo las respeta: solo crea las que quedan sin decidir.
                      </p>
                    ) : null}
                  </details>
                ) : (
                  <ul className="mt-3 flex flex-col gap-3">
                    {gruposResponsables.map((grupo) => (
                      <li key={grupo.clave}>
                        <Select
                          etiqueta={
                            grupo.oficina_nombre.trim().toLowerCase() === grupo.nombre_original.trim().toLowerCase()
                              ? `${grupo.oficina_nombre} · ${plural(grupo.equipos, 'equipo', 'equipos')}`
                              : `${grupo.oficina_nombre} · ${grupo.nombre_original} · ${plural(grupo.equipos, 'equipo', 'equipos')}`
                          }
                          value={seleccionesResponsables[grupo.clave] ?? ''}
                          onChange={(evento) => setSeleccionesResponsables((actual) => ({ ...actual, [grupo.clave]: evento.target.value }))}
                          placeholder="Sin decidir"
                          opciones={[
                            { valor: 'crear', etiqueta: 'Crear perfil sin credenciales' },
                            ...grupo.candidatos.map((persona) => ({
                              valor: persona.id,
                              etiqueta: `${persona.nombre} (${persona.coincidencia === 'exacta' ? 'coincide' : 'parecido'})`,
                            })),
                          ]}
                        />
                      </li>
                    ))}
                  </ul>
                )}

                {/*
                  La decisión son **dos casillas excluyentes** y el botón es solo
                  el paso de salida. Antes eran dos botones grandes que actuaban
                  los dos al instante, y confundirlos era fácil justo cuando la
                  decisión es «¿creo 263 cuentas o no?».

                  Las casillas se pueden leer y deshacer; el botón no decide nada,
                  solo aplica lo que esté marcado. Si no hay ninguna marcada, se
                  avanza con lo elegido a mano y **no se crea nada por sorpresa**.
                */}
                <fieldset className="mt-4 rounded-[var(--radius-panel)] border border-border p-3">
                  <legend className="px-1 text-sm font-semibold">¿Qué hago con las {numero(resumenResponsables.total - elegidasComoCoincidencia)} personas sin decidir?</legend>
                  <div className="flex flex-col gap-2">
                    <label className={cn('flex cursor-pointer items-start gap-2.5 rounded-[var(--radius-control)] p-2 transition-colors', decision === 'crear' ? 'bg-primary-soft' : 'hover:bg-muted', decision === 'nadie' && 'opacity-50')}>
                      <input
                        type="checkbox"
                        className="mt-0.5 size-4 shrink-0 accent-primary"
                        checked={decision === 'crear'}
                        disabled={decision === 'nadie'}
                        onChange={(evento) => setDecision(evento.target.checked ? 'crear' : 'ninguno')}
                      />
                      <span className="min-w-0">
                        <span className="block text-sm font-medium">Crear un perfil para las que faltan</span>
                        <span className="block text-2xs text-muted-foreground">
                          {plural(porCrear, 'perfil nuevo', 'perfiles nuevos')} sin correo ni contraseña. No podrán
                          entrar al sistema hasta que alguien les asigne una cuenta.
                        </span>
                      </span>
                    </label>
                    <label className={cn('flex cursor-pointer items-start gap-2.5 rounded-[var(--radius-control)] p-2 transition-colors', decision === 'nadie' ? 'bg-primary-soft' : 'hover:bg-muted', decision === 'crear' && 'opacity-50')}>
                      <input
                        type="checkbox"
                        className="mt-0.5 size-4 shrink-0 accent-primary"
                        checked={decision === 'nadie'}
                        disabled={decision === 'crear'}
                        onChange={(evento) => setDecision(evento.target.checked ? 'nadie' : 'ninguno')}
                      />
                      <span className="min-w-0">
                        <span className="block text-sm font-medium">No vincular a nadie de momento</span>
                        <span className="block text-2xs text-muted-foreground">
                          Los equipos conservan el nombre del Excel pero se quedan sin persona detrás.
                        </span>
                        {/* Al quedar inhabilitada, si no se dice nada parece un
                            fallo de la pantalla y no se entiende por qué no
                            responde. */}
                        {decision === 'crear' ? (
                          <span className="mt-0.5 block text-2xs italic">
                            Desmarca la de arriba para poder elegir esta.
                          </span>
                        ) : null}
                      </span>
                    </label>
                  </div>
                  <p className="mt-2 text-2xs text-muted-foreground">
                    {decision === 'ninguno'
                      ? elegidasComoCoincidencia > 0
                        ? `Sin marcar ninguna: se vincularán solo las ${plural(elegidasComoCoincidencia, 'persona que hayas elegido', 'personas que hayas elegido')} y no se creará ninguna cuenta nueva.`
                        : 'Sin marcar ninguna: no se creará ninguna cuenta ni se vinculará a nadie.'
                      : ''}
                  </p>
                </fieldset>

                <div className="mt-3 flex justify-end">
                  <Button variante="primario" cargando={confirmandoResponsables} onClick={aplicarDecision}>
                    Continuar
                  </Button>
                </div>
              </>}
            </section>
          ) : null}
          {/*
            Las tres salidas del final. «Deshacer» **solo aparece cuando la
            importación se puede deshacer** —es decir, cuando no hubo
            actualizaciones— porque ofrecer un botón que no puede funcionar es
            peor que no ofrecerlo.

            «Volver a revisar el archivo» es lo que faltaba: los pasos ya hechos
            son pulsables en el Stepper de arriba, así que volver atrás también
            se puede desde allí. El botón se queda porque desde el final es donde
            se busca.
          */}
          <div className="mt-4 flex flex-wrap gap-2">
            {resultado.reversible ? <Button variante="secundario" cargando={deshaciendo} onClick={() => void deshacer()} icono={<RotateCcw size={16} aria-hidden="true" />}>Deshacer la importación</Button> : null}
            <Button variante="secundario" disabled={ocupado} onClick={volverAlArchivo} icono={<ArrowLeft size={16} aria-hidden="true" />}>
              Volver a revisar el archivo
            </Button>
            <Button variante="primario" disabled={ocupado} onClick={reiniciar}>Importar otro archivo</Button>
          </div>
          {!resultado.reversible ? (
            <p className="mt-2 text-2xs text-muted-foreground">
              No se puede deshacer: la importación actualizó equipos que ya existían, y
              «deshacer» solo existe cuando lo único que se hizo fue crear. Para corregir
              algo, abre la ficha del equipo.
            </p>
          ) : null}
        </Panel>
      ) : null}

      {!resultado ? (
        <div className="sticky bottom-0 z-10 rounded-[var(--radius-panel)] border border-border bg-surface">
          <PiePasos
            paso={indicePaso + 1}
            total={PASOS.length}
            alAtras={indicePaso > 0 && !ocupado ? () => setPaso(PASOS[indicePaso - 1].clave) : undefined}
            alAdelante={indicePaso === 0 && vista ? () => setPaso('previsualizar') : undefined}
            puedeAdelantar={!ocupado}
            alEnviar={paso === 'previsualizar' ? () => void aplicar() : undefined}
            textoEnviar="Aplicar la importación"
            enviando={aplicando}
            puedeEnviar={Boolean(lote && vista?.validas && !ocupado)}
          />
        </div>
      ) : null}
    </PantallaFormulario>
  )
}

function Cifra({ etiqueta, valor, tono = 'neutro' }: { etiqueta: string; valor: number | string; tono?: 'neutro' | 'exito' | 'peligro' }) {
  const color = { neutro: 'text-foreground', exito: 'text-success-strong', peligro: 'text-destructive-strong' }[tono]
  return (
    <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-2">
      <p className="text-2xs text-muted-foreground">{etiqueta}</p>
      <p className={`text-lg font-bold ${color}`}>{valor}</p>
    </div>
  )
}

/** «1 oficina» y «2 oficinas», no «1 oficinas». */
function plural(cantidad: number, singular: string, plural_: string): string {
  return `${cantidad} ${cantidad === 1 ? singular : plural_}`
}
