/**
 * Mis equipos: el inventario de la persona, agrupado como lo vive.
 *
 * Primero los conjuntos (la computadora de la sala es una, la del escritorio es
 * otra), después el uso común de la oficina. Si no hay equipos registrados, se
 * dice con claridad a quién preguntar en vez de mostrar una tabla vacía.
 */

import { Monitor, Users } from 'lucide-react'
import { useEffect } from 'react'
import { useSesion } from '../../estado/Sesion'
import { Link } from 'react-router-dom'

import { useEquiposDePersona } from '../../api/hooks'
import { DisponibilidadBadge } from '../../componentes/dominio/Badge'
import { IconoTipoEquipo } from '../../componentes/dominio/IconoTipoEquipo'
import { Button } from '../../componentes/base/Button'
import {
  EmptyState,
  ErrorState,
  Nota,
  PageHeader,
  Panel,
  SkeletonPanel,
} from '../../componentes/base/Estructura'

export function MisEquipos() {
  const sesion = useSesion()
  const equipos = useEquiposDePersona()

  useEffect(() => {
    document.title = 'Mis equipos · Mesa de Ayuda'
  }, [])

  if (equipos.isLoading) return <SkeletonPanel filas={4} />

  if (equipos.isError) {
    return (
      <ErrorState
        mensaje="No pudimos cargar tus equipos."
        detalle={equipos.error instanceof Error ? equipos.error.message : undefined}
        alReintentar={() => void equipos.refetch()}
      />
    )
  }

  const datos = equipos.data
  const porConjunto = datos?.por_conjunto ?? []
  const usoComun = datos?.uso_comun_oficina ?? []
  const total = porConjunto.reduce((suma, grupo) => suma + grupo.equipos.length, 0) + usoComun.length

  if (total === 0) {
    return (
      <>
        <PageHeader titulo="Mis equipos" descripcion="Los equipos que tienes asignados en esta institución." />
        <EmptyState
          icono={<Monitor size={20} aria-hidden="true" />}
          titulo="No tienes equipos registrados"
          descripcion="Puedes pedir ayuda aunque tu equipo todavía no aparezca aquí."
          accion={
            <Button asChild variante="primario"><Link to={sesion.esTecnico ? "/panel/tickets/nuevo" : "/reportar"}>Pedir ayuda</Link></Button>
          }
        />
      </>
    )
  }

  return (
    <>
      <PageHeader titulo="Mis equipos" descripcion={`${total} equipo(s) a tu nombre en esta institución.`} />

      {porConjunto.map((grupo) => (
        <Panel key={grupo.conjunto ?? 'sin-conjunto'} titulo={grupo.conjunto ?? 'Equipos sin conjunto'}>
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {grupo.equipos.map((equipo) => (
              <li key={equipo.id}>
                <TarjetaEquipo equipo={equipo} />
              </li>
            ))}
          </ul>
        </Panel>
      ))}

      {usoComun.length ? (
        <Panel
          titulo="Uso común de la oficina"
          descripcion="Equipos compartidos: los puede usar cualquier persona de la oficina."
        >
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {usoComun.map((equipo) => (
              <li key={equipo.id}>
                <TarjetaEquipo equipo={equipo} />
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <Nota tono="info" titulo="Si algo no coincide" icono={<Users size={16} aria-hidden="true" />}>
        <p>
          Si un equipo no aparece o está mal descrito, <Link to={sesion.esTecnico ? "/panel/tickets/nuevo" : "/reportar"} className="font-semibold underline">pide ayuda a soporte</Link>. No necesitas elegir un equipo para enviar tu reporte.
        </p>
      </Nota>
    </>
  )
}

function TarjetaEquipo({
  equipo,
}: {
  equipo: {
    id: string
    tipo: string
    nombre_equipo?: string | null
    marca?: string | null
    modelo?: string | null
    estado: string
    codigo_patrimonial?: unknown
    responsable_nombre?: string | null
  }
}) {
  const nombre = equipo.nombre_equipo || `${equipo.marca ?? ''} ${equipo.modelo ?? ''}`.trim() || equipo.tipo
  const codigo = typeof equipo.codigo_patrimonial === 'string' ? equipo.codigo_patrimonial : null
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold">{nombre}</p>
          <p className="text-sm text-muted-foreground">
            {equipo.tipo}
            {codigo ? ` · ${codigo}` : ''}
          </p>
        </div>
        <span aria-hidden="true" className="shrink-0 text-muted-foreground">
          <IconoTipoEquipo tipo={equipo.tipo} tamano={26} />
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <DisponibilidadBadge estado={equipo.estado} />
      </div>
      {equipo.responsable_nombre ? (
        <p className="mt-1.5 text-2xs text-muted-foreground">Responsable: {equipo.responsable_nombre}</p>
      ) : null}
    </div>
  )
}
