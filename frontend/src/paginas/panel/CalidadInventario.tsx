/**
 * Calidad del inventario: cuánto está completo y qué falta.
 *
 * El número global es el que se muestra arriba; debajo, el desglose por campo,
 * por zona y por tipo, que es donde está la acción. Los campos marcados como
 * «No aplica» ya no cuentan, por eso el total de faltantes puede bajar sin que
 * se escriba nada nuevo.
 */

import { CircleCheck, Info, TriangleAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { useCalidadInventario, useCatalogoEquipos, useOficinas, useZonas } from '../../api/hooks'
import type { FiltrosCalidad } from '../../api/tipos'
import { KpiCard, KpiPorcentaje } from '../../componentes/dominio/KpiCard'
import { BarrasCampos } from '../../componentes/graficos/Graficos'
import { Select } from '../../componentes/base/Campo'
import { Button } from '../../componentes/base/Button'
import { EmptyState, ErrorState, Nota, PageHeader, Panel, SkeletonPanel } from '../../componentes/base/Estructura'
import { numero, porcentaje } from '../../dominio/formato'

/** Cuántas oficinas se muestran antes de que haya que pedir «ver todas». */
const LIMITE_OFICINAS = 12

export function CalidadInventario() {
  const navegar = useNavigate()
  /*
    Los filtros van también en la URL. Se guardaban solo en el estado del
    componente, así que la barra de direcciones no cambiaba nunca: el botón
    «Atrás» no deshacía el filtro y la vista filtrada no se podía compartir ni
    guardar. Es lo mismo que pasaba con el filtro por tipo del inventario.
  */
  const [parametros, cambiarParametros] = useSearchParams()
  const filtros: FiltrosCalidad = useMemo(
    () => ({
      ...(parametros.get('zona_id') ? { zona_id: parametros.get('zona_id') as string } : {}),
      ...(parametros.get('oficina_id') ? { oficina_id: parametros.get('oficina_id') as string } : {}),
    }),
    [parametros],
  )
  const fijarFiltros = (cambio: { zona_id?: string; oficina_id?: string }) => {
    const nuevos = new URLSearchParams(parametros)
    for (const clave of ['zona_id', 'oficina_id'] as const) {
      const valor = cambio[clave]
      if (valor === undefined) continue
      if (valor) nuevos.set(clave, valor)
      else nuevos.delete(clave)
    }
    cambiarParametros(nuevos)
  }

  const zonas = useZonas()
  const oficinas = useOficinas(filtros.zona_id ? { zona_id: filtros.zona_id } : {})
  const calidad = useCalidadInventario(filtros)
  const catalogos = useCatalogoEquipos()
  const datos = calidad.data

  /*
    Los tipos que existen de verdad, para poder marcar los que no.

    El Excel traía más columnas que el tipo de equipo y acabaron dentro de ese
    campo: «INOPERATIVO», «PERONAL», «SIN CONEXCION», «FALTAN», «FALTASTES»,
    «LAPTO» y hasta un código de patrimonio. Son **33 equipos** repartidos en 8 de
    las 16 filas del ranking: la mitad del panel eran tipos que no son tipos.

    Marcar los que no están en el catálogo convierte ese ruido en una lista de
    trabajo. Corregir el dato es cosa de alguien con criterio sobre qué es cada
    máquina, así que aquí solo se señala.
  */
  const tiposValidos = new Set((catalogos.data?.tipos_dispositivo ?? []).map((item) => item.valor.toLowerCase()))

  const hayFiltro = Boolean(filtros.zona_id || filtros.oficina_id)
  const hayFiltroZona = Boolean(filtros.zona_id)

  /*
    Las oficinas, de peor a mejor y recortadas.

    La API las trae ordenadas por cantidad de equipos, no por calidad: con eso la
    lista empezaba por las oficinas más grandes —que no son las peores— y no había
    forma de saber cuál de las 59 era la que había que ir a arreglar primero.
  */
  const [mostrarTodasLasOficinas, setMostrarTodasLasOficinas] = useState(false)
  const oficinasOrdenadas = useMemo(
    () => [...(datos?.por_oficina ?? [])].sort((a, b) => b.faltantes - a.faltantes),
    [datos?.por_oficina],
  )
  const oficinasVisibles = useMemo(() => {
    const lista = mostrarTodasLasOficinas ? oficinasOrdenadas : oficinasOrdenadas.slice(0, LIMITE_OFICINAS)
    const mitad = Math.ceil(lista.length / 2)
    return [
      { nombreLista: 'oficina', filas: lista.slice(0, mitad) },
      { nombreLista: 'oficina-b', filas: lista.slice(mitad) },
    ].filter((bloque) => bloque.filas.length)
  }, [oficinasOrdenadas, mostrarTodasLasOficinas])

  useEffect(() => {
    document.title = 'Calidad del inventario · Mesa de Ayuda TI'
  }, [])

  if (calidad.isError) {
    return (
      <ErrorState
        mensaje="No pudimos calcular la calidad del inventario."
        detalle={calidad.error instanceof Error ? calidad.error.message : undefined}
        alReintentar={() => void calidad.refetch()}
      />
    )
  }

  return (
    <>
      <PageHeader
        titulo="Calidad del inventario"
        descripcion="Cuántos datos esperados están escritos y cuáles faltan."
      />

      {/*
        El porcentaje va de 0 a 100 y sus dos extremos significan una sola cosa:

        - **0 %** = de estos equipos no hay **ningún** dato escrito.
        - **100 %** = de estos equipos está **todo** escrito.

        No es «equipos completos»: un equipo al que le falta un solo campo ya no
        cuenta, y por eso esa medida daba 0 % en grupos donde sí había casi todo
        escrito, que es justo lo que no cuadra al leerlo. Con esta, un 0 % solo
        puede significar que no hay nada, y un 100 % solo que no falta nada.

        Por eso cada fila lleva **escritos de esperados** en vez de un «completo»:
        «0 de 15 datos escritos» explica el 0 % sin pedirle nada a la cabeza,
        mientras que un «0 completos» al lado de un 36 % parece una contradicción
        aunque no lo sea.
      */}
      <Nota tono="info" titulo="Cómo se lee el porcentaje" icono={<Info size={16} aria-hidden="true" />}>
        <p>
          Las barras de datos escritos van de <strong>0 % a 100 %</strong>:{' '}
          <strong>0 % es que no hay ningún dato escrito</strong> y{' '}
          <strong>100 % es que no falta ninguno</strong>. Debajo de cada barra está
          el detalle —«36 equipos · 54 de 150 datos escritos»— para poder
          comprobarlo. Los campos marcados como «No aplica» o «No disponible» no
          cuentan como faltantes. En «Datos que faltan», 0 % significa que no queda ningún dato pendiente.
        </p>
      </Nota>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiPorcentaje
          etiqueta="Datos escritos"
          porcentaje={datos?.porcentaje_datos}
          tono={
            datos && datos.porcentaje_datos >= 90 ? 'exito' : datos && datos.porcentaje_datos >= 60 ? 'aviso' : 'peligro'
          }
          cargando={calidad.isLoading}
          detalle={
            datos
              ? `${numero(datos.esperados_totales - datos.faltantes_totales)} de ${numero(datos.esperados_totales)} casillas`
              : undefined
          }
        />
        <KpiCard
          etiqueta="Equipos registrados"
          detalle="Total en el alcance seleccionado"
          valor={datos?.total_activos}
          cargando={calidad.isLoading}
        />
        <KpiCard
          etiqueta="Datos que faltan"
          valor={datos ? porcentaje(datos.esperados_totales ? 100 * datos.faltantes_totales / datos.esperados_totales : 0, 1) : undefined}
          tono="aviso"
          cargando={calidad.isLoading}
          icono={<TriangleAlert size={16} aria-hidden="true" />}
          detalle={datos ? `${numero(datos.faltantes_totales)} de ${numero(datos.esperados_totales)} casillas esperadas` : undefined}
        />
        <KpiCard
          etiqueta="Equipos con todo escrito"
          valor={datos?.con_datos_completos}
          tono="exito"
          cargando={calidad.isLoading}
          icono={<CircleCheck size={16} aria-hidden="true" />}
          detalle={
            datos
              ? `Sin que les falte un solo campo · de ${numero(datos.total_activos)} equipos`
              : undefined
          }
        />
      </div>

      {/*
        Los filtros y, a su lado, **cuántos equipos quedan**. Sin eso, al elegir una
        zona los gráficos cambian de tamaño y no hay forma de saber si la zona
        elegida tiene 4 equipos o 511: el mismo 19 % significa cosas muy distintas.
        El botón de quitar aparece solo cuando hay algo puesto, que es cuando hace
        falta.
      */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2 xl:max-w-2xl">
          <Select
            etiqueta="Zona"
            value={filtros.zona_id ?? ''}
            onChange={(evento) =>
              fijarFiltros({
                zona_id: evento.target.value || undefined,
                // Al cambiar de zona la oficina de antes pertenece a otra, así que
                // se suelta: si no, se quedarían juntas dos filtros que no encajan.
                oficina_id: undefined,
              })
            }
            placeholder="Todas"
            opciones={(zonas.data?.items ?? []).map((zona) => ({ valor: zona.id, etiqueta: zona.nombre }))}
          />
          <Select
            etiqueta="Oficina"
            value={filtros.oficina_id ?? ''}
            onChange={(evento) => fijarFiltros({ oficina_id: evento.target.value || undefined })}
            placeholder="Todas"
            opciones={(oficinas.data?.items ?? []).map((oficina) => ({ valor: oficina.id, etiqueta: oficina.nombre }))}
          />
        </div>
        {hayFiltro ? (
          <div className="flex flex-col items-start gap-1.5 pb-0.5">
            <span className="text-sm text-muted-foreground">
              {numero(datos?.total_activos ?? 0)} equipos en este filtro
            </span>
            <Button variante="secundario" tamano="sm" onClick={() => cambiarParametros(new URLSearchParams())}>
              Quitar filtros
            </Button>
          </div>
        ) : null}
      </div>

      {calidad.isLoading ? (
        <SkeletonPanel filas={5} />
      ) : (datos?.total_activos ?? 0) === 0 ? (
        <EmptyState
          titulo="No hay equipos registrados"
          descripcion="Registra equipos o importa el inventario para poder medir la calidad de los datos."
        />
      ) : (
        <div className="flex flex-col gap-6">
          {/*
            Una rejilla de dos columnas obligaba a poner juntas dos paneles que no
            miden lo mismo: «Por zona» tiene 6 entradas y «Por oficina» 59. La
            columna izquierda se acababa a los 770 px y el hueco vacío de debajo llegaba
            a 1.300 px al pie de la página.

            Ahora los dos cortos van juntos arriba, y los dos largos —tipo y
            oficina— van debajo a todo el ancho, que es lo que aprovechan las
            barras. Oficina se reparte en dos columnas cuando hay sitio, que es lo
            único que hacía falta para que 59 entradas no fueran una escalera.
          */}
          {/*
            «Por zona» solo aparece si **no** hay filtro de zona. Con una zona
            elegida, el gráfico queda con una única fila —la zona que acabas de
            elegir—, que es lo mismo que ya dice el filtro de arriba. No es un
            resumen: es un indicador que ya está encendido al lado.

            No se pondría nada en su lugar: el gráfico de los datos que faltan ya
            está al lado y, con el filtro puesto, dice exactamente lo mismo que
            diría el de la zona.
          */}
          <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-2">
            <Panel titulo="Datos pendientes de completar" descripcion={`Equipos a los que les falta cada dato, de los ${numero(datos?.total_activos ?? 0)} equipos seleccionados.`}>
              <div className="flex flex-col gap-4">
                {(datos?.por_campo ?? []).map(fila => {
                  const nombres: Record<string, string> = { codigo_patrimonial: 'Código patrimonial', procesador: 'Procesador', memoria_ram: 'Memoria RAM', almacenamiento: 'Almacenamiento', direccion_ip: 'Dirección IP', direccion_mac: 'Dirección MAC', estado: 'Estado', tamano_pantalla: 'Tamaño de pantalla', marca: 'Marca', modelo: 'Modelo', nombre_equipo: 'Nombre del equipo', propiedad: 'Propiedad' }
                  const nombre = nombres[fila.campo] || String(fila.campo).replace(/_/g, ' ')
                  const valor = datos?.total_activos ? 100 * fila.faltantes / datos.total_activos : 0
                  return <div key={fila.campo}>
                    <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
                      <span className="font-medium">{nombre}</span>
                      <span className="flex flex-wrap gap-x-2"><span className="text-muted-foreground">{numero(fila.faltantes)} equipos</span><span className="font-semibold tabular-nums">{porcentaje(valor, 1)}</span></span>
                    </div>
                    <div role="meter" aria-label={`Equipos sin ${nombre}`} aria-valuenow={Number(valor.toFixed(1))} aria-valuemin={0} aria-valuemax={100} aria-valuetext={`${numero(fila.faltantes)} de ${numero(datos?.total_activos ?? 0)} equipos: ${porcentaje(valor, 1)}`} className="h-2.5 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, valor)}%`, backgroundColor: 'var(--color-chart-real)' }} />
                    </div>
                  </div>
                })}
                {!datos?.por_campo?.length ? <p className="text-sm text-success-strong">No hay datos pendientes de completar.</p> : null}
                <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">Barra completa = falta ese dato en el 100% de los equipos. Un mismo equipo puede tener varios datos pendientes; los porcentajes no se suman. Los campos que no aplican no se cuentan como faltantes.</p>
              </div>
            </Panel>

            {/*
            Dos porcentajes por fila, porque no dicen lo mismo y usar solo uno
            hacía que casi todo saliera a 0 %.

            La barra es **el porcentaje de datos escritos**: «de 3.000 casillas hay
            2.500», que es lo que se lee de un vistazo. El porcentaje de la derecha
            es **el de equipos con todo completo**, que es más severo: en cuanto un
            solo equipo del grupo tenga un hueco, ese grupo baja a 0. PISCINA
            MUNICIPAL tiene 96 datos que faltan y estaba a 0 %, lo que parece decir
            que no tiene nada escrito, y no es así.

            Con los dos, ninguna cifra puede sorprender: si está a 0 % de
            equipos completos pero la barra va llena, se entiende que lo que falta es
            poco y está repartido.
          */}
            {!hayFiltroZona ? (
              <Panel
                titulo="Por zona"
                descripcion="Datos escritos en cada zona. Al pulsar una se abre su inventario con lo que le falta."
              >
            <BarrasCampos
              nombreLista="zona"
              datos={(datos?.por_zona ?? []).map((fila) => ({
                etiqueta: fila.nombre,
                valor: fila.porcentaje_datos,
                detalle: `${numero(fila.total)} equipos · ${numero(fila.esperados - fila.faltantes)} de ${numero(fila.esperados)} datos escritos`,
                id: fila.id ?? undefined,
              }))}
              sufijo="%"
              maximo={100}
              anchoEtiqueta="w-40"
              alSeleccionar={(fila) => {
                  if (fila.id) navegar(`/panel/equipos?zona_id=${encodeURIComponent(fila.id)}&solo_faltantes=1`)
                }}
                />
              </Panel>
            ) : null}
          </div>

          <Panel
            titulo="Por tipo de equipo"
            descripcion="Datos escritos en cada tipo. Al pulsar uno se abre su inventario con lo que le falta. Los que no están en el catálogo necesitan corregirse."
          >
            {/*
              `fila.nombre`, no `fila.tipo`: `_agrupar` devuelve siempre la
              etiqueta en `nombre`, y el nombre del tipo **nunca** venía en `tipo`.
              Se leía una propiedad que no existía, salía la cadena vacía y el
              panel enseñaba barras sueltas con un porcentaje y **sin decir de qué
              equipo eran**: inútil de principio a fin.
            */}
            <BarrasCampos
              nombreLista="tipo"
              datos={(datos?.por_tipo ?? []).map((fila) => ({
                etiqueta: fila.nombre,
                valor: fila.porcentaje_datos,
                detalle: [
                  `${numero(fila.total)} equipos · ${numero(fila.esperados - fila.faltantes)} de ${numero(fila.esperados)} datos escritos`,
                  // Los que no están en el catálogo llevan la marca, para que la
                  // fila sea un aviso y no un dato más.
                  tiposValidos.size && !tiposValidos.has(fila.nombre.toLowerCase())
                    ? 'no está en el catálogo de tipos'
                    : null,
                ]
                  .filter(Boolean)
                  .join(' · '),
                // El id de este ranking es el propio tipo: se agrupa por `tipo` y
                // no hay ObjectId. Con eso la fila se puede pulsar y llevar al
                // inventario ya filtrado, como hacen zona y oficina.
                id: fila.nombre,
              }))}
              sufijo="%"
              maximo={100}
              anchoEtiqueta="w-40"
              alSeleccionar={(fila) => {
                if (fila.id) navegar(`/panel/equipos?tipo=${encodeURIComponent(fila.id)}&solo_faltantes=1`)
              }}
            />
          </Panel>

          <Panel
            titulo="Por oficina"
            descripcion={
              mostrarTodasLasOficinas
                ? 'Datos escritos en cada oficina, con los que más faltan. Pulsa una para abrir su inventario solo con lo que le falta.'
                : `Datos escritos en cada oficina, de peor a mejor. Se muestran las ${LIMITE_OFICINAS} con más pendientes de ${numero(datos?.por_oficina?.length ?? 0)}.`
            }
            acciones={
              (datos?.por_oficina?.length ?? 0) > LIMITE_OFICINAS ? (
                <Button variante="secundario" tamano="sm" onClick={() => setMostrarTodasLasOficinas((v) => !v)}>
                  {mostrarTodasLasOficinas ? 'Ver solo las peores' : `Ver las ${datos?.por_oficina?.length} oficinas`}
                </Button>
              ) : null
            }
          >
            {/*
              59 oficinas son 59 filas y la página se convertía en una escalera de
              dos pantallas: había que bajar para ver el final y no había forma de
              saber cuántas quedaban. Se muestran las peores —las que más datos
              tienen sin escribir—, que es lo que se va a ir a arreglar, y el resto
              está a un botón.

              Van en dos columnas porque en una sola ocupaban el doble de alto.
            */}
            <div className="grid grid-cols-1 items-start gap-6 2xl:grid-cols-2">
              {oficinasVisibles.map((bloque) => (
                <BarrasCampos
                  key={bloque.nombreLista}
                  nombreLista={bloque.nombreLista}
                  anchoEtiqueta="w-52"
                  datos={bloque.filas.map((fila) => ({
                    etiqueta: fila.nombre,
                    valor: fila.porcentaje_datos,
                    detalle: `${numero(fila.total)} equipos · ${numero(fila.esperados - fila.faltantes)} de ${numero(fila.esperados)} datos escritos${
                      (fila.campos_faltantes ?? []).length
                        ? ' · ' + fila.campos_faltantes.slice(0, 2).map((campo) => `${campo.campo.replace(/_/g, ' ')} (${numero(campo.faltantes)})`).join(' · ')
                        : ''
                    }`,
                    id: fila.id ?? undefined,
                  }))}
                  sufijo="%"
                  maximo={100}
                  alSeleccionar={(fila) => {
                    if (fila.id) navegar(`/panel/equipos?oficina_id=${encodeURIComponent(fila.id)}&solo_faltantes=1`)
                  }}
                />
              ))}
            </div>
          </Panel>
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        Totalidad global actual: {porcentaje(datos?.porcentaje_global)}. Los campos marcados como «No aplica» o «No
        disponible» no se cuentan como faltantes.
      </p>
    </>
  )
}
